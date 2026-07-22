#!/usr/bin/env python3
"""Submit-only concurrency test for Vapeur Kling image-to-video.

The reference image is uploaded to the wrapper's configured OSS once, then every
concurrent request submits the same signed URL. Successful submissions create
real billable generation tasks; use --dry-run before executing a load stage.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = REPO_ROOT.parent.parent
for path in (COMFYUI_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from py.nodes import _upload_file_to_oss  # noqa: E402


SUBMIT_PATH = "/v1/kling/image-to-video/submit"
DESCRIBE_PATH = "/v1/kling/image-to-video/describe"
SUCCESS_STATUSES = {"DONE", "SUCCESS", "SUCCEED", "SUCCEEDED", "COMPLETED", "FINISH"}
FAILED_STATUSES = {"FAIL", "FAILED", "ERROR", "ABORTED", "CANCELLED", "CANCELED"}
DEFAULT_START_IMAGE = Path(r"E:\批量测试输出\20260623羽绒服测试\伯希和4.png")
DEFAULT_OUTPUT = Path(__file__).with_name("vapeur_submit_concurrency_report.json")
DEFAULT_PROMPT = "人物自然轻微转身，衣服随风轻摆，镜头稳定，保持人物和服装一致。"
_thread_local = threading.local()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit-only Vapeur Kling image-to-video concurrency test.")
    parser.add_argument("--config-json", type=Path, default=REPO_ROOT / "config.local.json")
    parser.add_argument("--api-key")
    parser.add_argument("--base-url")
    parser.add_argument("--start-image", type=Path, default=DEFAULT_START_IMAGE)
    parser.add_argument("--image-url", help="Reuse an existing OSS/public URL instead of uploading --start-image.")
    parser.add_argument("--model", default="kling-v3-cn")
    parser.add_argument("--mode", default="pro")
    parser.add_argument("--duration", default="15")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--negative-prompt", default="")
    parser.add_argument("--cfg-scale", type=float, default=0.8)
    parser.add_argument("--levels", default="1,2,5", help="Comma-separated submit concurrency levels.")
    parser.add_argument("--requests-per-level", type=int, default=0)
    parser.add_argument("--stage-pause", type=float, default=5.0)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--max-wait-seconds", type=int, default=3600)
    parser.add_argument("--success-threshold", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_config(args: argparse.Namespace) -> dict[str, Any]:
    data = json.loads(args.config_json.read_text(encoding="utf-8-sig")) if args.config_json.exists() else {}
    args.api_key = args.api_key or data.get("vapeur_api_key") or os.getenv("VAPEUR_API_KEY")
    args.base_url = (args.base_url or data.get("vapeur_base_url") or "https://api.vapeur.ai").rstrip("/")
    args.timeout = int(data.get("vapeur_request_timeout") or args.timeout)
    args.poll_interval = float(data.get("vapeur_poll_interval") or args.poll_interval)
    args.max_wait_seconds = int(data.get("vapeur_max_wait_seconds") or args.max_wait_seconds)
    return data


def parse_levels(raw: str) -> list[int]:
    levels = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not levels or any(level <= 0 for level in levels):
        raise ValueError("Concurrency levels must be positive integers.")
    return levels


def session() -> requests.Session:
    value = getattr(_thread_local, "session", None)
    if value is None:
        value = requests.Session()
        _thread_local.session = value
    return value


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct / 100
    lower, upper = math.floor(rank), math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - rank) + ordered[upper] * (rank - lower)


def submit_once(index: int, args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    result = {
        "index": index,
        "ok": False,
        "job_id": None,
        "status_code": None,
        "error": None,
        "generation_ok": None,
        "generation_status": None,
        "generation_error": None,
        "generation_elapsed_s": None,
        "_request_started": started,
    }
    try:
        response = session().post(
            f"{args.base_url}{SUBMIT_PATH}",
            headers={"Authorization": f"Bearer {args.api_key}"},
            json=payload,
            timeout=args.timeout,
        )
        result["status_code"] = response.status_code
        try:
            body = response.json()
        except ValueError:
            body = None
        response_body = body.get("Response", body) if isinstance(body, dict) else None
        job_id = response_body.get("JobId") if isinstance(response_body, dict) else None
        if response.ok and job_id:
            result.update(ok=True, job_id=str(job_id))
        else:
            result["error"] = body if body is not None else response.text[:500]
    except requests.RequestException as exc:
        result["error"] = f"{exc.__class__.__name__}: {exc}"
    result["elapsed_s"] = round(time.perf_counter() - started, 4)
    return result


def wait_for_generation(result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    poll_started = time.perf_counter()
    while True:
        try:
            response = session().post(
                f"{args.base_url}{DESCRIBE_PATH}",
                headers={"Authorization": f"Bearer {args.api_key}"},
                json={"JobId": result["job_id"]},
                timeout=args.timeout,
            )
            response.raise_for_status()
            body = response.json()
            detail = body.get("Response", body) if isinstance(body, dict) else None
            if not isinstance(detail, dict):
                raise ValueError(f"Invalid describe response: {body!r}")

            status = str(detail.get("Status") or detail.get("TaskStatus") or "").strip().upper()
            error_code = str(detail.get("ErrorCode") or "").strip()
            error_message = str(detail.get("ErrorMessage") or detail.get("TaskStatusMsg") or "").strip()
            result["generation_status"] = status or None
            if status in FAILED_STATUSES or error_code:
                result["generation_ok"] = False
                result["generation_error"] = (
                    f"status={status or 'UNKNOWN'}, ErrorCode={error_code or '-'}, "
                    f"ErrorMessage={error_message or '-'}"
                )
                break
            if status in SUCCESS_STATUSES:
                result["generation_ok"] = True
                break
        except (requests.RequestException, ValueError) as exc:
            result["generation_ok"] = False
            result["generation_error"] = f"{exc.__class__.__name__}: {exc}"
            break

        if time.perf_counter() - poll_started > args.max_wait_seconds:
            result["generation_ok"] = False
            result["generation_error"] = f"Timed out after {args.max_wait_seconds} seconds"
            break
        time.sleep(args.poll_interval)

    result["generation_elapsed_s"] = round(time.perf_counter() - result.pop("_request_started"), 4)
    return result


def summarize(level: int, results: list[dict[str, Any]], elapsed: float) -> dict[str, Any]:
    latencies = [item["elapsed_s"] for item in results]
    generation_times = [
        item["generation_elapsed_s"] for item in results
        if item["generation_ok"] and item["generation_elapsed_s"] is not None
    ]
    failures = Counter(
        "http_429" if item["status_code"] == 429
        else "http_5xx" if item["status_code"] and item["status_code"] >= 500
        else f"http_{item['status_code']}" if item["status_code"]
        else "request_error"
        for item in results if not item["ok"]
    )
    success = sum(bool(item["ok"]) for item in results)
    return {
        "concurrency": level,
        "requests": len(results),
        "success": success,
        "failure": len(results) - success,
        "success_rate": round(success / len(results), 4) if results else 0,
        "stage_elapsed_s": round(elapsed, 4),
        "throughput_rps": round(len(results) / elapsed, 4) if elapsed else None,
        "mean_latency_s": round(sum(latencies) / len(latencies), 4) if latencies else None,
        "p50_latency_s": round(percentile(latencies, 50) or 0, 4) if latencies else None,
        "p95_latency_s": round(percentile(latencies, 95) or 0, 4) if latencies else None,
        "generation_success": len(generation_times),
        "generation_failure": sum(item["generation_ok"] is False for item in results),
        "mean_generation_s": round(sum(generation_times) / len(generation_times), 4) if generation_times else None,
        "p50_generation_s": round(percentile(generation_times, 50) or 0, 4) if generation_times else None,
        "p95_generation_s": round(percentile(generation_times, 95) or 0, 4) if generation_times else None,
        "failure_kinds": dict(failures),
        "job_ids": [item["job_id"] for item in results if item["ok"]],
        "sample_failures": [item for item in results if not item["ok"]][:5],
    }


def main() -> int:
    args = parse_args()
    config = load_config(args)
    levels = parse_levels(args.levels)
    if not args.api_key:
        raise SystemExit("Missing vapeur_api_key / VAPEUR_API_KEY.")
    if not args.image_url and not args.start_image.exists():
        raise FileNotFoundError(args.start_image)

    print("Vapeur base URL:", args.base_url)
    print("Reference image:", args.image_url or args.start_image)
    print("Concurrency levels:", levels)
    print("Submit-only test: yes; successful submissions are billable")
    if args.dry_run:
        print("Dry run only. No upload or API requests were made.")
        return 0

    image_url = args.image_url or _upload_file_to_oss(args.start_image)
    payload = {
        "Model": args.model,
        "Image": {"Url": image_url},
        "Prompt": args.prompt,
        "CfgScale": args.cfg_scale,
        "Mode": args.mode,
        "Duration": str(args.duration),
        "Sound": "off",
    }
    if args.negative_prompt.strip():
        payload["NegativePrompt"] = args.negative_prompt.strip()

    summaries, details = [], []
    overall_started = time.perf_counter()
    for stage, level in enumerate(levels):
        count = args.requests_per_level or level
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=level) as executor:
            futures = [executor.submit(submit_once, index, args, payload) for index in range(1, count + 1)]
            results = [future.result() for future in as_completed(futures)]
        submit_elapsed = time.perf_counter() - started
        submitted = [item for item in results if item["ok"]]
        if submitted:
            with ThreadPoolExecutor(max_workers=len(submitted)) as executor:
                futures = [executor.submit(wait_for_generation, item, args) for item in submitted]
                for future in as_completed(futures):
                    item = future.result()
                    print(
                        f"[level {level} task {item['index']}] job_id={item['job_id']} "
                        f"status={item['generation_status'] or 'UNKNOWN'} "
                        f"generation={item['generation_elapsed_s']}s"
                    )
        for item in results:
            item.pop("_request_started", None)
        results.sort(key=lambda item: item["index"])
        summary = summarize(level, results, submit_elapsed)
        summaries.append(summary)
        details.append({"level": level, "results": results})
        print(
            f"[level {level}] requests={count} success={summary['success']} failure={summary['failure']} "
            f"rate={summary['success_rate'] * 100:.1f}% submit_p95={summary['p95_latency_s']}s "
            f"generation_p95={summary['p95_generation_s']}s"
        )
        if stage < len(levels) - 1 and args.stage_pause:
            time.sleep(args.stage_pause)

    stable = [
        item["concurrency"] for item in summaries
        if item["success_rate"] >= args.success_threshold
        and not any(kind in item["failure_kinds"] for kind in ("http_429", "http_5xx", "request_error"))
    ]
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base_url": args.base_url,
        "image_path": str(args.start_image),
        "image_url": image_url.split("?", 1)[0],
        "model": args.model,
        "mode": args.mode,
        "duration": str(args.duration),
        "levels": levels,
        "overall_elapsed_s": round(time.perf_counter() - overall_started, 4),
        "recommended_stable_limit": max(stable) if stable else None,
        "level_summaries": summaries,
        "details": details,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Recommended stable submit concurrency:", report["recommended_stable_limit"])
    print("Report:", args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
