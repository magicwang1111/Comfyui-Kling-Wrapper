from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


CLOTHING_DUPE_PATH = "/solutions/e-commerce/clothing_dupe"
CLOTHING_DUPE_QUERY_PATH = "/solutions"
CLOTHING_DUPE_VOICE_IDS = (
    "energetic_sales_girl",
    "gentle_sales_woman",
    "crisp_sales_girl",
    "mature_sales_woman",
    "calm_sales_woman",
    "soft_sales_woman",
    "energetic_sales_boy",
    "enthusiastic_sales_man",
    "steady_sales_man",
    "calm_sales_man",
)

_ACTIVE_STATUSES = {"submitted", "processing"}
_SUCCESS_STATUSES = {"succeed", "succeeded"}
_FAILURE_STATUSES = {"failed"}

_VIDEO_OUTPUT_PRIORITY = (
    "product_video",
    "video_tts_bgm",
    "video_tts_only",
    "video_bgm_only",
    "video_silent",
)


@dataclass
class ClothingDupeResult:
    video_url: str
    watermark_video_url: str
    task_id: str
    raw: dict[str, Any]


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _ensure_ok(response: dict[str, Any], action: str) -> None:
    code = response.get("code", 0)
    if code not in (0, "0", None):
        message = response.get("message") or response
        raise RuntimeError(f"Kling Clothing Dupe {action} failed with code={code}: {message}")


def _extract_task_id(response: dict[str, Any]) -> str:
    data = response.get("data") or {}
    task_id = _clean_text(data.get("task_id") or data.get("id"))
    if not task_id:
        raise RuntimeError(f"Kling Clothing Dupe task creation returned no task id: {response}")
    return task_id


def _query_task(client, task_id: str) -> dict[str, Any]:
    response = client.request("GET", CLOTHING_DUPE_QUERY_PATH, params={"task_ids": task_id})
    _ensure_ok(response, "task query")
    data = response.get("data")
    if isinstance(data, list):
        if not data:
            raise RuntimeError(f"Kling Clothing Dupe task query returned no task records for {task_id}.")
        return data[0]
    if isinstance(data, dict):
        return data
    raise RuntimeError(f"Kling Clothing Dupe task query returned unexpected data: {response}")


def _extract_result(task: dict[str, Any], task_id: str) -> ClothingDupeResult:
    outputs = task.get("outputs") or []
    video = None
    for output_type in _VIDEO_OUTPUT_PRIORITY:
        video = next(
            (
                item
                for item in outputs
                if isinstance(item, dict) and _clean_text(item.get("type")) == output_type
            ),
            None,
        )
        if video:
            break
    if not video:
        raise RuntimeError(
            f"Kling Clothing Dupe task {task_id} succeeded but returned no supported video output: {task}"
        )
    video_url = _clean_text(video.get("url"))
    if not video_url:
        raise RuntimeError(f"Kling Clothing Dupe task {task_id} returned an empty video URL: {task}")
    return ClothingDupeResult(
        video_url=video_url,
        watermark_video_url=_clean_text(video.get("watermark_url")),
        task_id=task_id,
        raw=task,
    )


def submit_and_wait(client, payload: dict[str, Any]) -> ClothingDupeResult:
    response = client.request("POST", CLOTHING_DUPE_PATH, json=payload)
    _ensure_ok(response, "task creation")
    task_id = _extract_task_id(response)
    last_status = None

    while True:
        time.sleep(client.poll_interval)
        task = _query_task(client, task_id)
        status = _clean_text(task.get("status")).lower()
        if status != last_status:
            print(f"[Kling Clothing Dupe] task {task_id}: {status or 'unknown'}")
            last_status = status
        if status in _SUCCESS_STATUSES:
            return _extract_result(task, task_id)
        if status in _FAILURE_STATUSES:
            message = _clean_text(task.get("message")) or "Kling returned no additional failure details."
            raise RuntimeError(f"Kling Clothing Dupe task {task_id} failed: {message}")
        if status not in _ACTIVE_STATUSES:
            raise RuntimeError(
                f"Kling Clothing Dupe task {task_id} returned unknown status {status!r}: {task}"
            )
