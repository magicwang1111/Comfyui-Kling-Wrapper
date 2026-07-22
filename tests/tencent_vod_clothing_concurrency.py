#!/usr/bin/env python3
"""Run ten concurrent Tencent VOD videos with one image and one clothing element."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import oss2


REPO_ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = REPO_ROOT.parents[1]
for path in (COMFYUI_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from py.api.providers import (  # noqa: E402
    Image2VideoRequest,
    TencentVodVideoConfig,
    TencentVodVideoProvider,
)


DEFAULT_MAIN_IMAGE = Path(r"D:\Comfyui-workflow\20260717可灵腾讯云文档\1 (25).png")
DEFAULT_ELEMENT_REPORT = Path(__file__).with_name("tencent_vod_clothing_asset_report.json")
DEFAULT_REPORT = Path(__file__).with_name("tencent_vod_clothing_concurrency_report.json")
DEFAULT_PROMPT = """仅使用输入图片作为唯一主画面参考，生成一段15秒、9:16竖屏的高级电商大秀走秀视频。

全片为多机位硬切分镜，不要一镜到底，不要单一长镜头，必须有明显的镜头切换节奏，至少出现7个不同机位镜头，切换干净利落，具有真实时装秀拍摄感。

全程保持同一人物、同一张脸、同一套服装、同一个空间场景、同一背景、同一光线。人物在原场景中自然向前走秀，步态稳定优雅，动作连贯自然，表情自然，眼神稳定。服装面料真实，衣摆、裤脚和配饰随着走路自然摆动，符合真实布料动态。

所有镜头属于同一次连续走秀，严格按照以下分镜执行：
镜头1，0至2秒：正面全身后退跟拍，人物居中，稳定向前走秀。
镜头2，2至4秒：高位俯拍，展示人物整体造型与走秀动线。
镜头3，4至6秒：右前45度中景，摇臂轻微下降，突出人物上半身与服装动态。
镜头4，6至8秒：低机位脚步镜头，突出鞋子落地、步伐节奏、服装下摆摆动。
镜头5，8至10秒：侧面全身跟拍，展示身体线条和服装轮廓。
镜头6，10至12秒：左前45度半身跟拍，突出面部状态和服装材质细节。
镜头7，12至15秒：正面中景收尾，人物继续向前，镜头稳定收住，形成干净利落的结尾画面。

真实摄影机质感，高级电商大秀氛围，画面干净，构图高级，镜头语言专业。"""
DEFAULT_NEGATIVE_PROMPT = (
    "文字，logo，水印，换脸，滑步，跳帧，闪烁，背景漂移，身体畸形，服装变化，"
    "服装颜色变化，服装版型变化，鞋子变化，配饰变化，场景变化，背景变化，光线突变"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tencent VOD clothing-element concurrency test.")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config.local.json")
    parser.add_argument("--main-image", type=Path, default=DEFAULT_MAIN_IMAGE)
    parser.add_argument("--element-id", default="")
    parser.add_argument("--element-report", type=Path, default=DEFAULT_ELEMENT_REPORT)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--requests-per-model", type=int, default=10)
    parser.add_argument("--models", default="kling-v3,kling-v3-omni")
    parser.add_argument("--mode", choices=("std", "pro", "4k"), default="pro")
    parser.add_argument("--duration", default="15")
    parser.add_argument("--cfg-scale", type=float, default=0.8)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--negative-prompt", default=DEFAULT_NEGATIVE_PROMPT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--keep-oss-input", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def config_value(config: dict[str, Any], primary: str, fallback: str | None = None) -> Any:
    value = config.get(primary)
    if value in (None, "") and fallback:
        value = config.get(fallback)
    if value in (None, ""):
        raise KeyError(f"Missing config value: {primary}")
    return value


def resolve_element_id(args: argparse.Namespace) -> str:
    if args.element_id.strip():
        return args.element_id.strip()
    if not args.element_report.is_file():
        raise FileNotFoundError(
            f"Missing element report: {args.element_report}. Register the clothing asset first or pass --element-id."
        )
    report = json.loads(args.element_report.read_text(encoding="utf-8-sig"))
    element_id = str(report.get("element_id") or "").strip()
    if not report.get("ok") or not element_id:
        raise ValueError(f"Element report does not contain a successful element_id: {args.element_report}")
    return element_id


def build_bucket(config: dict[str, Any]) -> oss2.Bucket:
    endpoint = str(config_value(config, "oss_endpoint"))
    if "://" not in endpoint:
        endpoint = f"https://{endpoint}"
    auth = oss2.Auth(
        config_value(config, "oss_access_key_id"),
        config_value(config, "oss_access_key_secret"),
    )
    return oss2.Bucket(auth, endpoint, config_value(config, "oss_bucket"))


def upload_main_image(bucket: oss2.Bucket, config: dict[str, Any], path: Path) -> tuple[str, str]:
    prefix = str(config.get("oss_prefix") or "").strip("/")
    key = "/".join(part for part in (
        prefix,
        f"tencent-concurrency-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}",
        path.name,
    ) if part)
    bucket.put_object_from_file(key, str(path))
    expires = int(config.get("oss_signed_url_expires") or 86400)
    return bucket.sign_url("GET", key, expires, slash_safe=True), key


def make_provider(config: dict[str, Any]) -> TencentVodVideoProvider:
    return TencentVodVideoProvider(TencentVodVideoConfig(
        secret_id=str(config_value(config, "tencent_secret_id", "secret_id")),
        secret_key=str(config_value(config, "tencent_secret_key", "secret_key")),
        sub_app_id=int(config_value(config, "tencent_sub_app_id", "sub_app_id")),
        region=str(config.get("tencent_region") or config.get("region") or "ap-guangzhou"),
        request_timeout=int(config.get("tencent_request_timeout") or 120),
        poll_interval=float(config.get("tencent_poll_interval") or 5.0),
        max_wait_seconds=int(config.get("tencent_max_wait_seconds") or 3600),
    ))


def request_id_from_result(result: Any) -> str:
    raw = getattr(result, "raw", None)
    submit = raw.get("submit") if isinstance(raw, dict) else None
    return str(submit.get("RequestId") or "") if isinstance(submit, dict) else ""


def run_once(
    index: int,
    model: str,
    image_url: str,
    element_id: str,
    config: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    started = time.perf_counter()
    provider = make_provider(config)
    try:
        result = provider.generate_image2video(Image2VideoRequest(
            model_name=model,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            cfg_scale=args.cfg_scale,
            mode=args.mode,
            duration=str(args.duration),
            sound="off",
            image_urls=[image_url],
            element_list=[{"element_id": element_id}],
        ))
        return {
            "index": index,
            "model": model,
            "ok": True,
            "task_id": result.task_id,
            "request_id": request_id_from_result(result),
            "video_id": result.video_id,
            "video_url": result.url,
            "generation_elapsed_s": round(time.perf_counter() - started, 4),
            "error": None,
        }
    except Exception as exc:
        return {
            "index": index,
            "model": model,
            "ok": False,
            "task_id": None,
            "request_id": None,
            "video_id": None,
            "video_url": None,
            "generation_elapsed_s": round(time.perf_counter() - started, 4),
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        provider.close()


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct / 100
    lower, upper = math.floor(rank), math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - rank) + ordered[upper] * (rank - lower)


def summarize_model(model: str, results: list[dict[str, Any]], elapsed: float) -> dict[str, Any]:
    successful_times = [item["generation_elapsed_s"] for item in results if item["ok"]]
    return {
        "model": model,
        "requests": len(results),
        "success": len(successful_times),
        "failure": len(results) - len(successful_times),
        "success_rate": round(len(successful_times) / len(results), 4) if results else 0,
        "stage_elapsed_s": round(elapsed, 4),
        "mean_generation_s": round(sum(successful_times) / len(successful_times), 4) if successful_times else None,
        "p50_generation_s": round(percentile(successful_times, 50) or 0, 4) if successful_times else None,
        "p95_generation_s": round(percentile(successful_times, 95) or 0, 4) if successful_times else None,
    }


def main() -> int:
    args = parse_args()
    if args.concurrency <= 0 or args.requests_per_model <= 0:
        raise SystemExit("--concurrency and --requests-per-model must be positive integers.")
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    if not models:
        raise SystemExit("--models must contain at least one model name.")
    unsupported = [model for model in models if model not in {"kling-v3", "kling-v3-omni"}]
    if unsupported:
        raise SystemExit(f"This test supports kling-v3 and kling-v3-omni only: {unsupported}")
    if not args.main_image.is_file():
        raise SystemExit(f"Missing main image: {args.main_image}")
    if args.main_image.stat().st_size > 10 * 1024 * 1024:
        raise SystemExit("Tencent VOD input images must not exceed 10 MB.")
    if len(args.prompt) > 1000 or len(args.negative_prompt) > 1000:
        raise SystemExit("Tencent VOD prompt and negative prompt must each be at most 1000 characters.")
    config = load_config(args.config)
    element_id = resolve_element_id(args)

    print("Tencent VOD clothing concurrency test")
    print("Maximum concurrency:", args.concurrency)
    print("Models:", models)
    print("Task attempts per model:", args.requests_per_model)
    print("Total task attempts:", args.requests_per_model * len(models))
    print("Main image:", args.main_image)
    print("Clothing element_id:", element_id)
    print("Mode/duration:", args.mode, args.duration)
    print("Successful submissions create real billable video tasks.")
    if args.dry_run:
        print("Dry run only. No upload or Tencent VOD request was made.")
        return 0

    bucket = build_bucket(config)
    image_url, object_key = upload_main_image(bucket, config, args.main_image)
    results: list[dict[str, Any]] = []
    model_summaries: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        for model in models:
            stage_results: list[dict[str, Any]] = []
            stage_started = time.perf_counter()
            print(f"[stage {model}] starting {args.requests_per_model} tasks", flush=True)
            with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
                futures = [
                    executor.submit(run_once, index, model, image_url, element_id, config, args)
                    for index in range(1, args.requests_per_model + 1)
                ]
                for future in as_completed(futures):
                    item = future.result()
                    stage_results.append(item)
                    results.append(item)
                    print(
                        f"[{model} task {item['index']}] ok={item['ok']} task_id={item['task_id'] or '-'} "
                        f"generation={item['generation_elapsed_s']}s",
                        flush=True,
                    )
                    if item["error"]:
                        print(f"[{model} task {item['index']} error] {item['error']}", flush=True)
            stage_results.sort(key=lambda item: item["index"])
            summary = summarize_model(model, stage_results, time.perf_counter() - stage_started)
            model_summaries.append(summary)
            print(
                f"[stage {model}] success={summary['success']} failure={summary['failure']} "
                f"p95_generation={summary['p95_generation_s']}s",
                flush=True,
            )
    finally:
        retain_oss_input = args.keep_oss_input or any(
            str(item.get("error") or "").startswith("TimeoutError:")
            for item in results
        )
        if retain_oss_input:
            print("[cleanup] Main-image OSS input retained because a task may still be processing.", flush=True)
        else:
            try:
                bucket.delete_object(object_key)
            except Exception as exc:
                print(f"[cleanup-fail] OSS {object_key}: {exc}", flush=True)

    results.sort(key=lambda item: (models.index(item["model"]), item["index"]))
    overall_elapsed = time.perf_counter() - started
    successful_times = [item["generation_elapsed_s"] for item in results if item["ok"]]
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "main_image": str(args.main_image),
        "element_id": element_id,
        "models": models,
        "mode": args.mode,
        "duration": str(args.duration),
        "concurrency": args.concurrency,
        "requests_per_model": args.requests_per_model,
        "total_requests": args.requests_per_model * len(models),
        "success": len(successful_times),
        "failure": len(results) - len(successful_times),
        "success_rate": round(len(successful_times) / len(results), 4) if results else 0,
        "overall_elapsed_s": round(overall_elapsed, 4),
        "mean_generation_s": round(sum(successful_times) / len(successful_times), 4) if successful_times else None,
        "p50_generation_s": round(percentile(successful_times, 50) or 0, 4) if successful_times else None,
        "p95_generation_s": round(percentile(successful_times, 95) or 0, 4) if successful_times else None,
        "oss_input_retained": retain_oss_input,
        "prompt": args.prompt,
        "negative_prompt": args.negative_prompt,
        "model_summaries": model_summaries,
        "results": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Completed: success={report['success']} failure={report['failure']} "
        f"p95_generation={report['p95_generation_s']}s"
    )
    print("Report:", args.report)
    return 0 if report["failure"] == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
