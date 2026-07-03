from __future__ import annotations

import json
import time
import uuid
from typing import Any

from .client import TencentVodClient, TencentVodError
from .mapping import (
    build_image2video_payload,
    build_motion_control_payload,
    build_multi_images_payload,
    build_multimodal_payload,
    build_text2video_payload,
)
from ..base import (
    AdvancedElementCreateRequest,
    CustomVoiceCreateRequest,
    ElementResult,
    Image2VideoRequest,
    MotionControlRequest,
    MultiImagesToVideoRequest,
    MultiModalVideoEditRequest,
    TencentVodVideoConfig,
    Text2VideoRequest,
    VideoGenerationResult,
    VoiceResult,
)

CREATE_VIDEO_ACTION = "CreateAigcVideoTask"
DESCRIBE_TASK_ACTION = "DescribeTaskDetail"
CREATE_ELEMENT_ACTION = "CreateAigcAdvancedCustomElement"
DESCRIBE_ELEMENTS_ACTION = "DescribeAigcAdvancedCustomElements"
DELETE_ELEMENT_ACTION = "DeleteAigcAdvancedCustomElement"
CREATE_VOICE_ACTION = "CreateAigcCustomVoice"

_MODEL_VERSION_MAP = {
    "kling-v1-6": "1.6",
    "kling-v2": "2.0",
    "kling-v2-1": "2.1",
    "kling-v2-5-turbo": "2.5",
    "kling-v2-6": "2.6",
    "kling-v3": "3.0",
    "kling-v3-omni": "3.0-Omni",
    "kling-video-o1": "O1",
}

_MODE_TO_GENERATION = {
    "std": "Standard",
    "pro": "Professional",
    "4k": "Professional",
}

_TASK_KEYS = (
    "AigcVideoTask",
    "CreateAigcAdvancedCustomElementTask",
    "CreateAigcCustomVoiceTask",
)


class TencentVodVideoProvider:
    def __init__(self, config: TencentVodVideoConfig):
        self._config = config
        self._client = TencentVodClient(config)

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def _request(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._client.request(action, payload)

    def _create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(CREATE_VIDEO_ACTION, payload)

    def _describe_task(self, task_id: str) -> dict[str, Any]:
        return self._request(
            DESCRIBE_TASK_ACTION,
            {"TaskId": task_id, "SubAppId": int(self._config.sub_app_id)},
        )

    @staticmethod
    def _extract_task(detail: dict[str, Any], preferred_keys: tuple[str, ...] = _TASK_KEYS) -> dict[str, Any] | None:
        for key in preferred_keys:
            value = detail.get(key)
            if isinstance(value, dict):
                return value
        for value in detail.values():
            if isinstance(value, dict) and ("TaskId" in value or "Status" in value):
                return value
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and ("TaskId" in item or "Status" in item):
                        return item
        if "TaskId" in detail or "Status" in detail:
            return detail
        return None

    @staticmethod
    def _normalize_status(task: dict[str, Any] | None) -> str:
        if not task:
            return "UNKNOWN"
        return str(task.get("Status") or "").strip().upper() or "UNKNOWN"

    @staticmethod
    def _task_error(task: dict[str, Any]) -> str | None:
        err_code = task.get("ErrCode")
        err_code_ext = str(task.get("ErrCodeExt") or "").strip()
        if err_code not in (None, 0, "0") or err_code_ext:
            return (
                f"ErrCode={err_code}, ErrCodeExt={err_code_ext or '-'}, "
                f"Message={task.get('Message') or '-'}"
            )
        return None

    def _wait_for_task(
        self,
        task_id: str,
        preferred_keys: tuple[str, ...],
    ) -> dict[str, Any]:
        started = time.monotonic()
        last_status = None
        while True:
            detail = self._describe_task(task_id)
            task = self._extract_task(detail, preferred_keys)
            status = self._normalize_status(task)
            if status != last_status:
                print(f"[Tencent VOD] task {task_id}: {status}")
                last_status = status
            if status in {"FINISH", "SUCCESS", "FAIL", "FAILED", "ABORTED"}:
                if task is None:
                    raise TencentVodError(f"Tencent VOD task {task_id} returned no task details: {detail}")
                error = self._task_error(task)
                if status in {"FAIL", "FAILED", "ABORTED"} or error:
                    raise TencentVodError(
                        f"Tencent VOD task {task_id} failed with status={status}: "
                        f"{error or task.get('Message') or task}"
                    )
                return task
            if time.monotonic() - started > self._config.max_wait_seconds:
                raise TimeoutError(
                    f"Tencent VOD task {task_id} did not finish within "
                    f"{self._config.max_wait_seconds} seconds."
                )
            time.sleep(self._config.poll_interval)

    @staticmethod
    def _extract_urls(task: dict[str, Any] | None) -> list[str]:
        output = (task or {}).get("Output") or {}
        return [
            item.get("FileUrl") or item.get("Url")
            for item in output.get("FileInfos") or []
            if isinstance(item, dict) and (item.get("FileUrl") or item.get("Url"))
        ]

    def _wait_for_video(self, task_id: str) -> VideoGenerationResult:
        task = self._wait_for_task(task_id, ("AigcVideoTask",))
        output = task.get("Output") or {}
        file_infos = output.get("FileInfos") or []
        if not file_infos or not self._extract_urls(task):
            raise TencentVodError(
                f"Tencent VOD task {task_id} completed but returned no file URL: {task}"
            )
        first = file_infos[0]
        return VideoGenerationResult(
            url=first.get("FileUrl") or first.get("Url"),
            video_id=first.get("FileId") or first.get("VideoId") or task_id,
            task_id=task_id,
            raw=task,
        )

    @staticmethod
    def _resolve_model_version(model_name: str) -> str:
        try:
            return _MODEL_VERSION_MAP[model_name]
        except KeyError as exc:
            raise ValueError(f"Unsupported Tencent VOD Kling model: {model_name}") from exc

    def _resolve_generation_mode(self, requested_mode: str | None) -> str:
        if requested_mode is None:
            return self._config.generation_mode
        try:
            return _MODE_TO_GENERATION[requested_mode]
        except KeyError as exc:
            raise ValueError(f"Unsupported Tencent VOD generation mode: {requested_mode}") from exc

    @staticmethod
    def _session_id(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:24]}"

    def _submit_video(self, payload: dict[str, Any], task_name: str) -> VideoGenerationResult:
        response = self._create_task(payload)
        task_id = str(response.get("TaskId") or "").strip()
        if not task_id:
            raise TencentVodError(f"Tencent VOD {task_name} returned no TaskId: {response}")
        result = self._wait_for_video(task_id)
        if getattr(result, "raw", None) is not None:
            result.raw = {"submit": response, "task": result.raw}
        return result

    def generate_image2video(self, request: Image2VideoRequest) -> VideoGenerationResult:
        payload = build_image2video_payload(
            self._config,
            request,
            self._resolve_model_version(request.model_name),
            self._resolve_generation_mode(request.mode),
            self._session_id("comfy-i2v"),
        )
        return self._submit_video(payload, "image2video")

    def generate_text2video(self, request: Text2VideoRequest) -> VideoGenerationResult:
        payload = build_text2video_payload(
            self._config,
            request,
            self._resolve_model_version(request.model_name),
            self._resolve_generation_mode(request.mode),
            self._session_id("comfy-t2v"),
        )
        return self._submit_video(payload, "text2video")

    def generate_multi_images(self, request: MultiImagesToVideoRequest) -> VideoGenerationResult:
        payload = build_multi_images_payload(
            self._config,
            request,
            self._resolve_model_version(request.model_name),
            self._resolve_generation_mode(request.mode),
            self._session_id("comfy-multi-image"),
        )
        return self._submit_video(payload, "multi-image video")

    def generate_motion_control(self, request: MotionControlRequest) -> VideoGenerationResult:
        payload = build_motion_control_payload(
            self._config,
            request,
            self._resolve_model_version(request.model_name),
            self._resolve_generation_mode(request.mode),
            self._session_id("comfy-motion"),
        )
        return self._submit_video(payload, "motion control")

    def generate_multimodal_edit(self, request: MultiModalVideoEditRequest) -> VideoGenerationResult:
        payload = build_multimodal_payload(
            self._config,
            request,
            self._resolve_model_version(request.model_name),
            self._resolve_generation_mode(request.mode),
            self._session_id("comfy-multimodal"),
        )
        return self._submit_video(payload, "multimodal edit")

    @staticmethod
    def _decode_json_object(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, str) and raw.strip():
            try:
                decoded = json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
            return decoded if isinstance(decoded, dict) else {"value": decoded}
        return {}

    @classmethod
    def _element_result_from_task(
        cls,
        task: dict[str, Any],
        task_id: str,
        request_id: str = "",
    ) -> ElementResult:
        info_list = ((task.get("Output") or {}).get("InfoList") or [])
        if not info_list:
            raise TencentVodError(
                f"Tencent VOD subject task {task_id} completed but returned no InfoList."
            )
        info = info_list[0]
        payload = cls._decode_json_object(info.get("ElementInfo"))
        element_id = str(
            info.get("ElementId")
            or payload.get("element_id")
            or payload.get("id")
            or ""
        )
        payload.setdefault("element_id", element_id)
        return ElementResult(payload, element_id, task_id, request_id, task)

    def create_element(self, request: AdvancedElementCreateRequest) -> ElementResult:
        extra_payload = dict(request.extra_payload or {})
        tag_list = (
            request.tag_list
            or extra_payload.pop("TagList", None)
            or extra_payload.pop("tag_list", None)
        )
        for protected_key in (
            "SubAppId",
            "ElementName",
            "ElementDescription",
            "ReferenceType",
            "ElementVoiceId",
            "ElementImageList",
            "ElementVideoList",
            "SessionId",
        ):
            extra_payload.pop(protected_key, None)
        payload: dict[str, Any] = extra_payload
        payload.update({
            "SubAppId": int(self._config.sub_app_id),
            "ElementName": request.element_name,
            "ElementDescription": request.element_description,
            "ReferenceType": request.reference_type,
            "SessionId": self._session_id("comfy-element"),
        })
        if request.element_voice_id:
            payload["ElementVoiceId"] = request.element_voice_id
        if request.element_image_list:
            payload["ElementImageList"] = TencentVodClient.canonical_json(request.element_image_list)
        if request.element_video_list:
            payload["ElementVideoList"] = TencentVodClient.canonical_json(request.element_video_list)
        if tag_list:
            payload["TagList"] = TencentVodClient.canonical_json(tag_list)
        response = self._request(CREATE_ELEMENT_ACTION, payload)
        task_id = str(response.get("TaskId") or "")
        if not task_id:
            raise TencentVodError(f"Tencent VOD subject creation returned no TaskId: {response}")
        task = self._wait_for_task(task_id, ("CreateAigcAdvancedCustomElementTask",))
        return self._element_result_from_task(task, task_id, str(response.get("RequestId") or ""))

    def query_element(self, query_mode: str, identifier: str) -> ElementResult:
        if query_mode == "task_id":
            task = self._wait_for_task(identifier, ("CreateAigcAdvancedCustomElementTask",))
            return self._element_result_from_task(task, identifier)
        offset = 0
        limit = 100
        while True:
            response = self._request(
                DESCRIBE_ELEMENTS_ACTION,
                {
                    "SubAppId": int(self._config.sub_app_id),
                    "Offset": offset,
                    "Limit": limit,
                },
            )
            for item in response.get("ElementSet") or []:
                element_id = str(item.get("Id") or item.get("ElementId") or "")
                if element_id == identifier:
                    payload = {
                        "element_id": element_id,
                        "element_name": item.get("Name") or "",
                        "element_description": item.get("Description") or "",
                        "create_time": item.get("CreateTime") or "",
                    }
                    return ElementResult(
                        payload,
                        element_id,
                        request_id=str(response.get("RequestId") or ""),
                        raw=response,
                    )
            offset += limit
            if offset >= int(response.get("TotalCount") or 0):
                break
        raise TencentVodError(f"Tencent VOD subject not found: {identifier}")

    def delete_element(self, element_id: str) -> str:
        last_error = None
        for attempt in range(4):
            try:
                response = self._request(
                    DELETE_ELEMENT_ACTION,
                    {"SubAppId": int(self._config.sub_app_id), "ElementId": element_id},
                )
                return str(response.get("RequestId") or "")
            except TencentVodError as exc:
                last_error = exc
                if "Code=FailedOperation" not in str(exc) or attempt == 3:
                    raise
                time.sleep(5)
        raise last_error

    @classmethod
    def _voice_result_from_task(
        cls,
        task: dict[str, Any],
        task_id: str,
        request_id: str = "",
    ) -> VoiceResult:
        info_list = ((task.get("Output") or {}).get("InfoList") or [])
        if not info_list:
            raise TencentVodError(
                f"Tencent VOD custom voice task {task_id} completed but returned no InfoList."
            )
        info = info_list[0]
        payload = cls._decode_json_object(info.get("VoiceInfo"))
        voice_id = str(info.get("VoiceId") or payload.get("voice_id") or "")
        payload.setdefault("voice_id", voice_id)
        return VoiceResult(payload, task_id, request_id, task)

    def create_custom_voice(self, request: CustomVoiceCreateRequest) -> VoiceResult:
        payload = {
            "SubAppId": int(self._config.sub_app_id),
            "VoiceName": request.voice_name,
            "SessionId": self._session_id("comfy-voice"),
        }
        if request.voice_url:
            payload["VoiceUrl"] = request.voice_url
        if request.video_id:
            payload["VideoId"] = request.video_id
        response = self._request(CREATE_VOICE_ACTION, payload)
        task_id = str(response.get("TaskId") or "")
        if not task_id:
            raise TencentVodError(f"Tencent VOD custom voice creation returned no TaskId: {response}")
        task = self._wait_for_task(task_id, ("CreateAigcCustomVoiceTask",))
        return self._voice_result_from_task(task, task_id, str(response.get("RequestId") or ""))

    def query_custom_voice(self, task_id: str) -> VoiceResult:
        task = self._wait_for_task(task_id, ("CreateAigcCustomVoiceTask",))
        return self._voice_result_from_task(task, task_id)


__all__ = ["TencentVodError", "TencentVodVideoProvider"]
