from __future__ import annotations

import time
from typing import Any

import httpx

from ..base import (
    AdvancedElementCreateRequest,
    CustomVoiceCreateRequest,
    ElementResult,
    Image2VideoRequest,
    MotionControlRequest,
    MultiImagesToVideoRequest,
    MultiModalVideoEditRequest,
    Text2VideoRequest,
    VapeurVideoConfig,
    VideoGenerationResult,
    VoiceResult,
)


class VapeurError(RuntimeError):
    pass


_MODEL_MAP = {
    "kling-v2-6": "kling-v2-6-cn",
    "kling-v3": "kling-v3-cn",
}


def _model(value: str) -> str:
    try:
        return _MODEL_MAP[value]
    except KeyError as exc:
        raise ValueError(f"Unsupported Vapeur Kling model: {value}") from exc


def _without_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _camera_control(value: Any) -> Any:
    if value is not None and hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def _element_list(values: list | None) -> list[dict[str, str]] | None:
    result = []
    for item in values or []:
        if isinstance(item, str):
            identifier = item.strip()
        elif isinstance(item, dict):
            identifier = str(item.get("element_id") or item.get("ElementId") or item.get("id") or "").strip()
        else:
            identifier = ""
        if identifier:
            result.append({"ElementId": identifier})
    return result or None


def _media(value: str | None) -> dict[str, str] | None:
    value = str(value or "").strip()
    if not value:
        return None
    return {"Url": value} if value.startswith(("http://", "https://")) else {"Base64": value}


class VapeurVideoProvider:
    _SUCCESS = {"DONE", "SUCCESS", "SUCCEED", "SUCCEEDED", "COMPLETED", "FINISH"}
    _FAILED = {"FAIL", "FAILED", "ERROR", "ABORTED", "CANCELLED", "CANCELED"}

    def __init__(self, config: VapeurVideoConfig):
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {config.api_key}"},
            timeout=config.request_timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            details = exc.response.text[:1000]
            raise VapeurError(f"Vapeur request failed for {path}: HTTP {exc.response.status_code}: {details}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise VapeurError(f"Vapeur request failed for {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise VapeurError(f"Vapeur {path} returned a non-object response: {data!r}")
        body = data.get("Response", data)
        if not isinstance(body, dict):
            raise VapeurError(f"Vapeur {path} returned an invalid Response object: {data!r}")
        error = body.get("Error")
        if error:
            raise VapeurError(f"Vapeur {path} failed: {error}")
        return body

    def _submit(self, kind: str, payload: dict[str, Any]) -> VideoGenerationResult:
        submitted = self._post(f"/v1/kling/{kind}/submit", payload)
        task_id = str(submitted.get("JobId") or "").strip()
        if not task_id:
            raise VapeurError(f"Vapeur {kind} submission returned no JobId: {submitted}")
        started = time.monotonic()
        while True:
            detail = self._post(f"/v1/kling/{kind}/describe", {"JobId": task_id})
            status = str(detail.get("Status") or detail.get("TaskStatus") or "").strip().upper()
            error_code = str(detail.get("ErrorCode") or "").strip()
            error_message = str(detail.get("ErrorMessage") or detail.get("TaskStatusMsg") or "").strip()
            if status in self._FAILED or error_code:
                raise VapeurError(
                    f"Vapeur {kind} task {task_id} failed with status={status or 'UNKNOWN'}, "
                    f"ErrorCode={error_code or '-'}, ErrorMessage={error_message or '-'}"
                )
            if status in self._SUCCESS:
                url = str(detail.get("ResultVideoUrl") or "").strip()
                if not url:
                    raise VapeurError(f"Vapeur {kind} task {task_id} completed but returned no ResultVideoUrl: {detail}")
                deduction = detail.get("FinalUnitDeduction")
                try:
                    deduction = float(deduction) if deduction not in (None, "") else None
                except (TypeError, ValueError):
                    deduction = None
                return VideoGenerationResult(
                    url=url,
                    video_id=str(detail.get("VideoId") or task_id),
                    task_id=task_id,
                    final_unit_deduction=deduction,
                    raw={"submit": submitted, "task": detail},
                )
            if time.monotonic() - started > self._config.max_wait_seconds:
                raise TimeoutError(f"Vapeur {kind} task {task_id} did not finish within {self._config.max_wait_seconds} seconds.")
            time.sleep(self._config.poll_interval)

    @staticmethod
    def _video_base(request: Any) -> dict[str, Any]:
        payload = dict(request.extra_payload or {})
        payload.update(_without_none({
            "Model": _model(request.model_name),
            "Prompt": request.prompt,
            "NegativePrompt": request.negative_prompt,
            "Mode": request.mode,
            "Duration": request.duration,
        }))
        return payload

    def generate_text2video(self, request: Text2VideoRequest) -> VideoGenerationResult:
        payload = self._video_base(request)
        payload.update(_without_none({
            "AspectRatio": request.aspect_ratio,
            "CfgScale": request.cfg_scale,
            "Sound": request.sound,
            "VoiceList": request.voice_list,
            "ShotType": request.shot_type if request.shot_type != "single" else None,
            "ImageList": request.image_list,
            "ElementList": _element_list(request.element_list),
            "ReferenceVideo": request.reference_video,
            "CameraControl": _camera_control(request.camera_control),
        }))
        return self._submit("text-to-video", payload)

    def generate_image2video(self, request: Image2VideoRequest) -> VideoGenerationResult:
        payload = self._video_base(request)
        payload.update(_without_none({
            "Image": _media(request.image_base64),
            "ImageTail": _media(request.image_tail_base64 or request.image_tail_url),
            "ImageList": request.image_list,
            "CfgScale": request.cfg_scale,
            "Sound": request.sound,
            "VoiceList": request.voice_list,
            "ShotType": request.shot_type if request.shot_type != "single" else None,
            "ElementList": _element_list(request.element_list),
            "ReferenceVideo": request.reference_video,
            "CameraControl": _camera_control(request.camera_control),
        }))
        return self._submit("image-to-video", payload)

    def generate_multi_images(self, request: MultiImagesToVideoRequest) -> VideoGenerationResult:
        payload = self._video_base(request)
        images = request.image_base64_list or request.image_urls
        payload.update(_without_none({
            "ImageList": [{"Image": _media(image)} for image in images],
            "ImageTail": _media(request.image_tail_base64 or request.image_tail_url),
            "AspectRatio": request.aspect_ratio,
        }))
        return self._submit("multi-image-to-video", payload)

    def generate_motion_control(self, request: MotionControlRequest) -> VideoGenerationResult:
        payload = self._video_base(request)
        payload.update({
            "Image": _media(request.image_url),
            "Video": _media(request.video_url),
            "CharacterOrientation": request.character_orientation,
            "KeepOriginalSound": "yes" if request.keep_original_sound else "no",
        })
        if request.element_list:
            payload["ElementList"] = _element_list(request.element_list)
        return self._submit("video-motion-control", payload)

    def generate_video_extend(self, video_id: str, prompt: str) -> VideoGenerationResult:
        return self._submit("video-extend", {"Model": _model("kling-v3"), "VideoId": video_id, "Prompt": prompt})

    def generate_multimodal_edit(self, request: MultiModalVideoEditRequest) -> VideoGenerationResult:
        payload = self._video_base(request)
        payload.update(_without_none({
            "Video": _media(request.video_url),
            "ReferType": request.edit_mode,
            "ImageList": [
                {"Image": _media(image)}
                for image in (request.image_base64_list or request.image_urls)
            ] or None,
            "Sound": "on" if request.keep_original_sound else "off",
            "AspectRatio": request.aspect_ratio,
        }))
        return self._submit("video-edit", payload)

    @staticmethod
    def _voice(body: dict[str, Any], task_id: str) -> VoiceResult:
        entries = body.get("VoicesList") or []
        task = entries[0] if entries and isinstance(entries[0], dict) else body
        voices = task.get("Voices") or []
        voice = voices[0] if voices and isinstance(voices[0], dict) else {}
        payload = {
            "voice_id": str(voice.get("VoiceId") or ""),
            "voice_name": str(voice.get("VoiceName") or ""),
            "trial_url": str(voice.get("TrialUrl") or ""),
        }
        return VoiceResult(payload, task_id, str(body.get("RequestId") or ""), body)

    def query_custom_voice(self, task_id: str) -> VoiceResult:
        started = time.monotonic()
        while True:
            body = self._post("/v1/kling/voices/describe", {"JobId": task_id, "Model": _model("kling-v2-6")})
            entries = body.get("VoicesList") or []
            task = entries[0] if entries and isinstance(entries[0], dict) else body
            status = str(task.get("TaskStatus") or task.get("Status") or "").strip().upper()
            if status in self._FAILED:
                raise VapeurError(
                    f"Vapeur voice task {task_id} failed with status={status}: "
                    f"{task.get('TaskStatusMsg') or task.get('ErrorMessage') or task}"
                )
            if status in self._SUCCESS:
                return self._voice(body, task_id)
            if time.monotonic() - started > self._config.max_wait_seconds:
                raise TimeoutError(f"Vapeur voice task {task_id} did not finish within {self._config.max_wait_seconds} seconds.")
            time.sleep(self._config.poll_interval)

    def create_custom_voice(self, request: CustomVoiceCreateRequest) -> VoiceResult:
        submitted = self._post("/v1/kling/voices", _without_none({
            "Model": _model("kling-v2-6"),
            "VoiceName": request.voice_name,
            "VoiceUrl": request.voice_url,
            "VideoId": request.video_id,
        }))
        task_id = str(submitted.get("JobId") or "")
        if not task_id:
            raise VapeurError(f"Vapeur voice creation returned no JobId: {submitted}")
        return self.query_custom_voice(task_id)

    @staticmethod
    def _element(body: dict[str, Any], task_id: str = "") -> ElementResult:
        payload = dict(body)
        element_id = str(body.get("ElementId") or "")
        payload.setdefault("element_id", element_id)
        return ElementResult(payload, element_id, task_id or str(body.get("JobId") or ""), str(body.get("RequestId") or ""), body)

    def create_element(self, request: AdvancedElementCreateRequest) -> ElementResult:
        extra = dict(request.extra_payload or {})
        payload = extra
        image_list = request.element_image_list or {}
        element_images = None
        if image_list:
            element_images = {
                "FrontalImage": image_list.get("frontal_image") or image_list.get("FrontalImage"),
                "ReferImages": [
                    {"ImageUrl": item.get("image_url") or item.get("ImageUrl")}
                    for item in (image_list.get("refer_images") or image_list.get("ReferImages") or [])
                ],
            }
        video_list = request.element_video_list or {}
        videos = [
            item.get("video_url") or item.get("VideoUrl")
            for item in (video_list.get("refer_videos") or video_list.get("ReferVideos") or [])
            if item.get("video_url") or item.get("VideoUrl")
        ]
        payload.update(_without_none({
            "Model": _model("kling-v3"),
            "Name": request.element_name,
            "Description": request.element_description,
            "ReferenceType": request.reference_type,
            "ElementImageList": element_images,
            "VideoList": videos or None,
            "ElementVoiceId": request.element_voice_id,
            "TagList": request.tag_list,
            "Provider": ["kling"],
        }))
        return self._element(self._post("/v1/kling/elements", payload))

    def query_element(self, query_mode: str, identifier: str) -> ElementResult:
        if query_mode == "task_id":
            body = self._post("/v1/kling/elements/describe", {"ElementId": identifier, "Model": _model("kling-v3")})
            return self._element(body, identifier)
        page = 1
        while page <= 1000:
            body = self._post("/v1/kling/elements/list", {"PageNum": page, "PageSize": 100})
            items = body.get("ElementList") or []
            for item in items:
                if str(item.get("ElementId") or "") == identifier:
                    detail = self._post("/v1/kling/elements/describe", {"ElementId": identifier, "Model": _model("kling-v3")})
                    return self._element(detail)
            if len(items) < 100:
                break
            page += 1
        raise VapeurError(f"Vapeur subject not found: {identifier}")


__all__ = ["VapeurError", "VapeurVideoProvider"]
