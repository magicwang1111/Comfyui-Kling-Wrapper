#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import oss2

REPO_ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = REPO_ROOT.parents[1]
if str(COMFYUI_ROOT) not in sys.path:
    sys.path.insert(0, str(COMFYUI_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from py.api.providers import (  # noqa: E402
    AdvancedElementCreateRequest,
    CustomVoiceCreateRequest,
    Image2VideoRequest,
    MotionControlRequest,
    MultiImagesToVideoRequest,
    MultiModalVideoEditRequest,
    TencentVodVideoConfig,
    TencentVodVideoProvider,
    Text2VideoRequest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run minimum-cost Tencent VOD provider smoke tests.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--image-1", type=Path, required=True)
    parser.add_argument("--image-2", type=Path, required=True)
    parser.add_argument("--image-3", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--voice", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated step names; empty runs all steps.",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_bucket(config: dict[str, Any]) -> oss2.Bucket:
    endpoint = str(config["oss_endpoint"])
    if "://" not in endpoint:
        endpoint = f"https://{endpoint}"
    auth = oss2.Auth(config["oss_access_key_id"], config["oss_access_key_secret"])
    return oss2.Bucket(auth, endpoint, config["oss_bucket"])


def upload_assets(
    bucket: oss2.Bucket,
    config: dict[str, Any],
    assets: dict[str, Path],
) -> tuple[dict[str, str], list[str]]:
    prefix = str(config.get("oss_prefix") or "").strip("/")
    run_id = f"live-smoke-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    expires = int(config.get("oss_signed_url_expires") or 86400)
    urls: dict[str, str] = {}
    keys: list[str] = []
    for label, path in assets.items():
        key = "/".join(part for part in (prefix, run_id, f"{label}{path.suffix.lower()}") if part)
        print(f"[upload] {label}: {path.name}", flush=True)
        bucket.put_object_from_file(key, str(path))
        keys.append(key)
        urls[label] = bucket.sign_url("GET", key, expires, slash_safe=True)
    return urls, keys


def request_id_from_video(result: Any) -> str:
    raw = getattr(result, "raw", None)
    if isinstance(raw, dict):
        submit = raw.get("submit")
        if isinstance(submit, dict):
            return str(submit.get("RequestId") or "")
    return ""


def video_summary(result: Any) -> dict[str, Any]:
    return {
        "task_id": result.task_id,
        "request_id": request_id_from_video(result),
        "video_id": result.video_id,
        "url": result.url,
    }


def run_step(report: dict[str, Any], name: str, callback: Callable[[], dict[str, Any]]) -> None:
    selected = report.get("selected_steps") or []
    if selected and name not in selected:
        print(f"[skip] {name}", flush=True)
        return
    print(f"[start] {name}", flush=True)
    started = time.monotonic()
    try:
        output = callback()
        report["results"][name] = {
            "ok": True,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            **output,
        }
        print(f"[pass] {name}: {json.dumps(output, ensure_ascii=False)}", flush=True)
    except Exception as exc:
        if isinstance(exc, TimeoutError):
            report["retain_oss_inputs"] = True
        report["results"][name] = {
            "ok": False,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(f"[fail] {name}: {type(exc).__name__}: {exc}", flush=True)


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    for path in (args.image_1, args.image_2, args.image_3, args.video, args.voice):
        if not path.is_file():
            raise SystemExit(f"Missing test asset: {path}")

    bucket = build_bucket(config)
    urls, keys = upload_assets(
        bucket,
        config,
        {
            "image1": args.image_1,
            "image2": args.image_2,
            "image3": args.image_3,
            "video": args.video,
            "voice": args.voice,
        },
    )
    provider = TencentVodVideoProvider(
        TencentVodVideoConfig(
            secret_id=config["secret_id"],
            secret_key=config["secret_key"],
            sub_app_id=int(config["sub_app_id"]),
            region=str(config.get("region") or "ap-guangzhou"),
            request_timeout=120,
            poll_interval=5.0,
            max_wait_seconds=3600,
        )
    )
    report: dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "selected_steps": [
            item.strip()
            for item in str(args.only or "").split(",")
            if item.strip()
        ],
        "results": {},
    }
    created_element_id = ""
    try:
        run_step(
            report,
            "text2video",
            lambda: video_summary(provider.generate_text2video(Text2VideoRequest(
                model_name="kling-v3",
                prompt="A red fox runs through fresh snow, cinematic natural motion.",
                mode="std",
                duration="3",
                aspect_ratio="16:9",
                sound="off",
            ))),
        )
        run_step(
            report,
            "image2video",
            lambda: video_summary(provider.generate_image2video(Image2VideoRequest(
                model_name="kling-v3",
                prompt="The subject turns toward the camera while the clothing moves naturally.",
                mode="std",
                duration="3",
                sound="off",
                image_urls=[urls["image3"]],
            ))),
        )
        run_step(
            report,
            "multi_images_to_video",
            lambda: video_summary(provider.generate_multi_images(MultiImagesToVideoRequest(
                model_name="kling-v3",
                prompt="Keep the same clothing and person identity while the camera moves naturally.",
                mode="std",
                duration="5",
                aspect_ratio="9:16",
                image_urls=[urls["image1"], urls["image2"], urls["image3"]],
            ))),
        )
        run_step(
            report,
            "motion_control",
            lambda: video_summary(provider.generate_motion_control(MotionControlRequest(
                model_name="kling-v3",
                image_url=urls["image3"],
                video_url=urls["video"],
                prompt="Transfer the body motion while preserving the subject and clothing.",
                mode="std",
                duration="3",
                keep_original_sound=False,
                character_orientation="video",
            ))),
        )
        run_step(
            report,
            "multimodal_video_edit",
            lambda: video_summary(provider.generate_multimodal_edit(MultiModalVideoEditRequest(
                model_name="kling-v3-omni",
                video_url=urls["video"],
                prompt="Preserve the motion and camera movement while matching the clothing in the reference image.",
                edit_mode="base",
                keep_original_sound=False,
                mode="std",
                duration="3",
                aspect_ratio="9:16",
                image_urls=[urls["image3"]],
            ))),
        )

        def create_subject() -> dict[str, Any]:
            nonlocal created_element_id
            result = provider.create_element(AdvancedElementCreateRequest(
                element_name=f"codex-test-{int(time.time())}"[:20],
                element_description="Temporary live smoke test subject.",
                reference_type="image_refer",
                element_image_list={
                    "frontal_image": urls["image1"],
                    "refer_images": [
                        {"image_url": urls["image2"]},
                        {"image_url": urls["image3"]},
                    ],
                },
            ))
            created_element_id = result.element_id
            queried = provider.query_element("element_id", result.element_id)
            return {
                "task_id": result.task_id,
                "request_id": result.request_id,
                "element_id": result.element_id,
                "query_element_id": queried.element_id,
            }

        run_step(report, "advanced_element_create_query", create_subject)

        run_step(
            report,
            "custom_voice_create_query",
            lambda: (
                lambda created: {
                    "task_id": created.task_id,
                    "request_id": created.request_id,
                    "voice_id": created.voice.get("voice_id", ""),
                    "voice_name": created.voice.get("voice_name", ""),
                    "trial_url": created.voice.get("trial_url", ""),
                    "query_voice_id": provider.query_custom_voice(created.task_id).voice.get("voice_id", ""),
                    "cleanup": "No Tencent VOD custom voice delete API; retained intentionally.",
                }
            )(provider.create_custom_voice(CustomVoiceCreateRequest(
                voice_name=f"codex-test-{int(time.time())}"[:20],
                voice_url=urls["voice"],
            ))),
        )
    finally:
        if created_element_id:
            try:
                request_id = provider.delete_element(created_element_id)
                report["subject_cleanup"] = {
                    "ok": True,
                    "element_id": created_element_id,
                    "request_id": request_id,
                }
                print(f"[cleanup] deleted subject {created_element_id}", flush=True)
            except Exception as exc:
                report["subject_cleanup"] = {
                    "ok": False,
                    "element_id": created_element_id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                print(f"[cleanup-fail] subject {created_element_id}: {exc}", flush=True)
        provider.close()
        if report.get("retain_oss_inputs"):
            report["oss_cleanup"] = "Retained because a cloud task was still processing at local timeout."
        else:
            for key in keys:
                try:
                    bucket.delete_object(key)
                except Exception as exc:
                    print(f"[cleanup-fail] OSS {key}: {exc}", flush=True)
        report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    ok = all(item.get("ok") for item in report["results"].values())
    subject_was_selected = (
        not report["selected_steps"]
        or "advanced_element_create_query" in report["selected_steps"]
    )
    cleanup_ok = (
        not subject_was_selected
        or report.get("subject_cleanup", {}).get("ok")
    )
    return 0 if ok and cleanup_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
