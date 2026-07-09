from __future__ import annotations

import time
from typing import Any

from ..base import Image2VideoRequest, Text2VideoRequest, VideoGenerationResult


TURBO_MODEL_NAME = "kling-v3-turbo"
TURBO_TEXT_PATH = "/text-to-video/kling-3.0-turbo"
TURBO_IMAGE_PATH = "/image-to-video/kling-3.0-turbo"
TURBO_MODE_TO_RESOLUTION = {
    "std": "720p",
    "pro": "1080p",
    "4k": "1080p",
}

_ACTIVE_STATUSES = {"submitted", "processing", "pending", "queued", "running"}
_SUCCESS_STATUSES = {"succeeded", "succeed", "success", "completed", "finish", "finished"}
_FAILURE_STATUSES = {"failed", "fail", "failure", "error", "canceled", "cancelled"}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _reject_unsupported_common(request: Image2VideoRequest | Text2VideoRequest) -> None:
    if _clean_text(getattr(request, "negative_prompt", None)):
        raise ValueError("kling-v3-turbo does not support a separate negative_prompt field; include constraints in prompt.")
    if getattr(request, "cfg_scale", None) is not None:
        raise ValueError("kling-v3-turbo does not support cfg_scale.")
    if getattr(request, "camera_control", None) is not None:
        raise ValueError("kling-v3-turbo does not support camera control.")
    if getattr(request, "sound", "off") == "on":
        raise ValueError("kling-v3-turbo does not support the sound option in this API.")
    if getattr(request, "voice_list", None):
        raise ValueError("kling-v3-turbo does not support voice_list in this API.")
    if getattr(request, "shot_type", "single") not in (None, "", "single"):
        raise ValueError("kling-v3-turbo multi-shot control must be written into the prompt text.")
    if getattr(request, "element_list", None):
        raise ValueError("kling-v3-turbo does not support element_list in this API.")
    if getattr(request, "reference_video", None):
        raise ValueError("kling-v3-turbo does not support reference_video in this API.")


def _settings(request: Image2VideoRequest | Text2VideoRequest, include_aspect_ratio: bool) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    mode = _clean_text(getattr(request, "mode", None)) or "std"
    settings["resolution"] = TURBO_MODE_TO_RESOLUTION.get(mode, "720p")
    duration = _clean_text(getattr(request, "duration", None))
    if duration:
        settings["duration"] = int(duration)
    if include_aspect_ratio:
        aspect_ratio = _clean_text(getattr(request, "aspect_ratio", None))
        if aspect_ratio:
            settings["aspect_ratio"] = aspect_ratio
    return settings


def _options(request: Image2VideoRequest | Text2VideoRequest) -> dict[str, Any]:
    extra = dict(getattr(request, "extra_output_config", None) or {})
    watermark_info = extra.pop("watermark_info", None)
    if not isinstance(watermark_info, dict):
        watermark_info = {"enabled": False}
    else:
        watermark_info.setdefault("enabled", False)
    options = {"watermark_info": watermark_info}
    for key in ("callback_url", "external_task_id"):
        value = _clean_text(extra.pop(key, ""))
        if value:
            options[key] = value
    options.update(extra)
    return options


def build_text2video_payload(request: Text2VideoRequest) -> dict[str, Any]:
    _reject_unsupported_common(request)
    prompt = _clean_text(request.prompt)
    if not prompt:
        raise ValueError("kling-v3-turbo text2video requires prompt.")
    return {
        "prompt": prompt,
        "settings": _settings(request, include_aspect_ratio=True),
        "options": _options(request),
    }


def build_image2video_payload(request: Image2VideoRequest) -> dict[str, Any]:
    _reject_unsupported_common(request)
    if getattr(request, "image_tail_base64", None) or getattr(request, "image_tail_url", None):
        raise ValueError("kling-v3-turbo supports first frame only, not image_tail.")
    if getattr(request, "image_list", None) or getattr(request, "image_urls", None):
        raise ValueError("kling-v3-turbo supports one first frame, not image_list.")

    prompt = _clean_text(request.prompt)
    image_value = _clean_text(getattr(request, "image_base64", None))
    if not image_value:
        raise ValueError("kling-v3-turbo image2video requires a primary image.")

    contents = []
    if prompt:
        contents.append({"type": "prompt", "text": prompt})
    contents.append({"type": "first_frame", "url": image_value})
    return {
        "contents": contents,
        "settings": _settings(request, include_aspect_ratio=False),
        "options": _options(request),
    }


def _ensure_ok(response: dict[str, Any], action: str) -> None:
    code = response.get("code", 0)
    if code not in (0, "0", None):
        message = response.get("message") or response
        raise RuntimeError(f"Kling v3 Turbo {action} failed with code={code}: {message}")


def _extract_task_id(response: dict[str, Any]) -> str:
    data = response.get("data") or {}
    task_id = _clean_text(data.get("id") or data.get("task_id"))
    if not task_id:
        raise RuntimeError(f"Kling v3 Turbo task creation returned no task id: {response}")
    return task_id


def _poll_task(client, task_id: str) -> dict[str, Any]:
    response = client.request("GET", "/tasks", params={"task_ids": task_id})
    _ensure_ok(response, "task query")
    data = response.get("data")
    if isinstance(data, list):
        if not data:
            raise RuntimeError(f"Kling v3 Turbo task query returned no task records for {task_id}.")
        return data[0]
    if isinstance(data, dict) and isinstance(data.get("result"), list):
        if not data["result"]:
            raise RuntimeError(f"Kling v3 Turbo task query returned no task records for {task_id}.")
        return data["result"][0]
    if isinstance(data, dict):
        return data
    raise RuntimeError(f"Kling v3 Turbo task query returned unexpected data: {response}")


def _extract_video_result(task: dict[str, Any], task_id: str) -> VideoGenerationResult:
    outputs = task.get("outputs") or []
    video = next((item for item in outputs if isinstance(item, dict) and item.get("type") == "video"), None)
    if not video:
        raise RuntimeError(f"Kling v3 Turbo task {task_id} succeeded but returned no video output: {task}")
    url = _clean_text(video.get("url") or video.get("watermark_url"))
    if not url:
        raise RuntimeError(f"Kling v3 Turbo task {task_id} returned an empty video URL: {task}")
    billing = task.get("billing") or []
    final_unit_deduction = None
    if billing and isinstance(billing[0], dict):
        try:
            final_unit_deduction = float(billing[0].get("amount"))
        except (TypeError, ValueError):
            final_unit_deduction = None
    return VideoGenerationResult(
        url=url,
        video_id=_clean_text(video.get("id")) or task_id,
        task_id=task_id,
        final_unit_deduction=final_unit_deduction,
        raw=task,
    )


def submit_and_wait(client, path: str, payload: dict[str, Any]) -> VideoGenerationResult:
    response = client.request("POST", path, json=payload)
    _ensure_ok(response, "task creation")
    task_id = _extract_task_id(response)
    last_status = None
    while True:
        time.sleep(client.poll_interval)
        task = _poll_task(client, task_id)
        status = _clean_text(task.get("status")).lower()
        if status != last_status:
            print(f"[Kling v3 Turbo] task {task_id}: {status or 'unknown'}")
            last_status = status
        if status in _SUCCESS_STATUSES:
            return _extract_video_result(task, task_id)
        if status in _FAILURE_STATUSES:
            details = _clean_text(task.get("message")) or "Kling returned no additional failure details."
            raise RuntimeError(f"Kling v3 Turbo task {task_id} failed: {details}")
        if status and status not in _ACTIVE_STATUSES:
            raise RuntimeError(f"Kling v3 Turbo task {task_id} returned unknown status {status!r}: {task}")


def generate_turbo_text2video(client, request: Text2VideoRequest) -> VideoGenerationResult:
    return submit_and_wait(client, TURBO_TEXT_PATH, build_text2video_payload(request))


def generate_turbo_image2video(client, request: Image2VideoRequest) -> VideoGenerationResult:
    return submit_and_wait(client, TURBO_IMAGE_PATH, build_image2video_payload(request))
