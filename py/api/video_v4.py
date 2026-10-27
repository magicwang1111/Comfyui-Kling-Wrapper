import math
import os
import time

import av

from .providers.base import VideoGenerationResult


PATHS = {
    "text": "/text-to-video/kling-4.0",
    "image": "/image-to-video/kling-4.0",
    "omni": "/omni-video/kling-4.0",
}
FRAME_TYPES = {"first_frame", "middle_frame", "last_frame"}
CONTENT_TYPES = FRAME_TYPES | {"refer_image", "feature_video", "base_video", "element", "voice"}


VIDEO_ELEMENT_TYPES = {"video_character", "video_refer"}
MAX_VIDEO_BYTES = 300 * 1024 * 1024


def validate_material_counts(contents, elements=()):
    counts = {
        "images": sum(c["type"] in FRAME_TYPES | {"refer_image"} for c in contents),
        "videos": sum(c["type"] in {"base_video", "feature_video"} for c in contents),
        "elements": sum(c["type"] == "element" for c in contents),
        "voices": sum(c["type"] == "voice" for c in contents),
    }
    if sum(counts.values()) > 15:
        raise ValueError(f"Kling 4.0 supports at most 15 materials total (including keyframes): {counts}")
    for name, limit in (("images", 10), ("videos", 5), ("elements", 7), ("voices", 3)):
        if counts[name] > limit:
            raise ValueError(f"Kling 4.0 supports at most {limit} {name}; got {counts[name]}.")
    if sum(c["type"] == "base_video" for c in contents) > 1:
        raise ValueError("Kling 4.0 supports at most 1 base_video.")
    video_elements = sum(e.get("type") in VIDEO_ELEMENT_TYPES for e in elements)
    if video_elements > 3:
        raise ValueError(f"Kling 4.0 supports at most 3 video character elements; got {video_elements}.")
    if video_elements + counts["videos"] > 5:
        raise ValueError("Kling 4.0 supports at most 5 reference videos and video character elements combined.")


def known_duration(value):
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return None
    return duration if math.isfinite(duration) and duration > 0 else None


def read_video_metadata(path):
    metadata = {"size": os.path.getsize(path)}
    if metadata["size"] > MAX_VIDEO_BYTES:
        return metadata
    # Probe only the already prepared upload file; never count/decode frames.
    try:
        with av.open(path, options={"probesize": "32768", "analyzeduration": "1"}) as container:
            metadata["format"] = container.format.name
            stream = next(iter(container.streams.video), None)
            if stream is not None:
                metadata.update(width=stream.width, height=stream.height)
                fps = known_duration(stream.average_rate)
                if fps is not None:
                    metadata["fps"] = fps
                duration = None
                if stream.duration is not None and stream.time_base is not None:
                    duration = known_duration(stream.duration * stream.time_base)
                if duration is None and container.duration is not None:
                    duration = known_duration(container.duration / av.time_base)
                if duration is None and stream.frames and fps is not None:
                    duration = known_duration(stream.frames / fps)
                metadata["duration"] = duration
    except av.error.FFmpegError:
        pass  # Unavailable metadata is left to the service to validate.
    return metadata


def validate_video_metadata(metadata, label):
    if metadata.get("size", 0) > MAX_VIDEO_BYTES:
        raise ValueError(f"{label}: video file must not exceed 300 MB.")
    container_format = metadata.get("format")
    if container_format and not {"mp4", "mov"}.intersection(container_format.split(",")):
        raise ValueError(f"{label}: video format must be MP4 or MOV; got {container_format}.")
    duration = known_duration(metadata.get("duration"))
    if duration is not None and not 3 <= duration <= 30:
        raise ValueError(f"{label}: input video duration must be 3–30 seconds; got {duration:g}.")
    width, height = metadata.get("width"), metadata.get("height")
    for name, value in (("width", width), ("height", height)):
        if value and not 700 <= value <= 4553:
            raise ValueError(f"{label}: video {name} must be 700–4553 px; got {value}.")
    if width and height:
        if width * height > 8294400:
            raise ValueError(f"{label}: video pixel area must not exceed 8294400; got {width}×{height}.")
        if not 2 / 5 <= width / height <= 5 / 2:
            raise ValueError(f"{label}: video aspect ratio must be between 2:5 and 5:2; got {width}×{height}.")
    fps = known_duration(metadata.get("fps"))
    if fps is not None and not 24 <= fps <= 60:
        raise ValueError(f"{label}: input video frame rate must be 24–60 fps; got {fps:g}.")


def validate_video_duration_total(durations):
    known = [d for d in durations if d is not None]
    total = sum(known)
    if total > 30 or (known and len(known) == len(durations) and total < 3):
        raise ValueError(f"Kling 4.0 total video duration must be 3–30 seconds, including video character elements; known total: {total:g}.")


def build_payload(kind, prompt, resolution, duration, aspect_ratio=None, contents=None,
                  watermark=False, callback_url="", external_task_id=""):
    if kind not in PATHS:
        raise ValueError(f"Unknown Kling 4.0 task type: {kind}")
    if resolution not in {"720p", "1080p"}:
        raise ValueError("Kling 4.0 resolution must be 720p or 1080p.")
    settings = {"resolution": resolution}
    if str(duration) != "auto":
        if str(duration) not in {str(n) for n in range(3, 31)}:
            raise ValueError("Kling 4.0 duration must be auto or 3–30 seconds.")
        settings["duration"] = int(duration)
    if kind != "image":
        allowed = {"21:9", "16:9", "9:16", "1:1"}
        if kind == "omni":
            allowed.add("adaptive")
        aspect_ratio = aspect_ratio or ("adaptive" if kind == "omni" else "16:9")
        if aspect_ratio not in allowed:
            raise ValueError(f"Unsupported Kling 4.0 aspect ratio: {aspect_ratio}")
        settings["aspect_ratio"] = aspect_ratio
    prompt = str(prompt or "").strip()
    if kind == "text" and not prompt:
        raise ValueError("Text2Video requires a prompt.")
    options = {"watermark_info": {"enabled": bool(watermark)}}
    for key, value in (("callback_url", callback_url), ("external_task_id", external_task_id)):
        if value.strip():
            options[key] = value.strip()
    payload = {"settings": settings, "options": options}
    if kind == "text":
        payload["prompt"] = prompt
        return payload
    contents = list(contents or [])
    validate_material_counts(contents)
    if kind == "image" and not contents:
        raise ValueError("Image2Video requires at least one keyframe image.")
    ids = set()
    for item in contents:
        content_type = item.get("type")
        if content_type not in (FRAME_TYPES if kind == "image" else CONTENT_TYPES):
            raise ValueError(f"Unsupported {kind} material type: {content_type}")
        identifier = item.get("id")
        if not identifier or identifier in ids:
            raise ValueError(f"Missing or duplicate material id: {identifier}")
        ids.add(identifier)
        field = {"element": "element_id", "voice": "voice_id"}.get(content_type, "url")
        if not item.get(field):
            raise ValueError(f"{identifier} requires {field}.")
    payload["contents"] = ([{"type": "prompt", "text": prompt}] if prompt else []) + contents
    return payload


def _data(response):
    if response.get("code", 0) not in (0, "0"):
        raise RuntimeError(f"Kling 4.0 API error: {response.get('message', 'Unknown error')}")
    return response.get("data")


def submit_and_wait(client, kind, payload, interrupt_check=None, max_wait_seconds=3600):
    if interrupt_check:
        interrupt_check()
    created = _data(client.request("POST", PATHS[kind], json=payload))
    task_id = created.get("id") if isinstance(created, dict) else None
    if not task_id:
        raise RuntimeError("Kling 4.0 submission returned no task ID.")
    print(f"[Kling 4.0] submitted task {task_id}")
    deadline = time.monotonic() + max_wait_seconds
    while time.monotonic() < deadline:
        if interrupt_check:
            interrupt_check()
        time.sleep(client.poll_interval)
        try:
            records = _data(client.request("GET", "/tasks", params={"task_ids": task_id}))
        except Exception as exc:
            raise RuntimeError(
                f"Kling 4.0 task {task_id} query failed; query this ID before resubmitting: {exc}"
            ) from exc
        task = next((item for item in records if item.get("id") == task_id), None) if isinstance(records, list) else None
        if task is None:
            raise RuntimeError(f"Kling 4.0 task {task_id} was missing from the query response.")
        status = task.get("status")
        if status == "succeeded":
            video = next((item for item in task.get("outputs", []) if item.get("type") == "video"), None)
            if not video or not video.get("url"):
                raise RuntimeError(f"Kling 4.0 task {task_id} returned no video URL.")
            return VideoGenerationResult(url=video["url"], video_id=str(video.get("id") or ""),
                                         task_id=task_id, raw=task)
        if status == "failed":
            raise RuntimeError(f"Kling 4.0 task {task_id} failed: {task.get('message') or 'Unknown error'}")
        if status not in {"submitted", "processing"}:
            raise RuntimeError(f"Kling 4.0 task {task_id} returned unknown status: {status}")
    raise TimeoutError(f"Kling 4.0 task {task_id} is still pending after {max_wait_seconds}s; query this ID before resubmitting.")
