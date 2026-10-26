import time

from .providers.base import VideoGenerationResult


PATHS = {
    "text": "/text-to-video/kling-4.0",
    "image": "/image-to-video/kling-4.0",
    "omni": "/omni-video/kling-4.0",
}
FRAME_TYPES = {"first_frame", "middle_frame", "last_frame"}
CONTENT_TYPES = FRAME_TYPES | {"refer_image", "feature_video", "base_video", "element", "voice"}


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
