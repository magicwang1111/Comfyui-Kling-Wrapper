from __future__ import annotations

import json
from typing import Any

from ..base import (
    Image2VideoRequest,
    MotionControlRequest,
    MultiImagesToVideoRequest,
    MultiModalVideoEditRequest,
    TencentVodVideoConfig,
    Text2VideoRequest,
)


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _merge_extra(base: dict[str, Any], extra: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(extra or {})
    merged.update(_without_none(base))
    return merged


def _normalize_camera_control(camera_control: Any) -> Any:
    if camera_control is None:
        return None
    if hasattr(camera_control, "to_dict"):
        return camera_control.to_dict()
    return camera_control


def _resolve_audio_generation(default_value: str, sound: str | None) -> str:
    if sound == "on":
        return "Enabled"
    if sound == "off":
        return "Disabled"
    return default_value


def _resolve_resolution(config: TencentVodVideoConfig, mode: str | None) -> str:
    return {
        "std": "720P",
        "pro": "1080P",
        "4k": "4K",
    }.get(mode or "", config.resolution)


def build_output_config(
    config: TencentVodVideoConfig,
    *,
    mode: str | None = None,
    duration: str | float | None = None,
    aspect_ratio: str | None = None,
    sound: str | None = None,
) -> dict[str, Any]:
    payload = {
        "StorageMode": config.storage_mode,
        "Duration": float(duration or config.duration),
        "Resolution": _resolve_resolution(config, mode),
        "AudioGeneration": _resolve_audio_generation(config.audio_generation, sound),
        "PersonGeneration": config.person_generation,
        "InputComplianceCheck": config.input_compliance_check,
        "OutputComplianceCheck": config.output_compliance_check,
    }
    if aspect_ratio:
        payload["AspectRatio"] = aspect_ratio
    return payload


def url_file_info(
    url: str,
    *,
    usage: str | None = None,
    category: str = "Image",
    reference_type: str | None = None,
    keep_original_sound: bool | None = None,
) -> dict[str, Any]:
    result = {
        "Type": "Url",
        "Category": category,
        "Url": url,
    }
    if usage:
        result["Usage"] = usage
    if reference_type:
        result["ReferenceType"] = reference_type
    if keep_original_sound is not None:
        result["KeepOriginalSound"] = "Enabled" if keep_original_sound else "Disabled"
    return result


def build_subject_infos(element_list: list | None) -> list[dict[str, str]] | None:
    subjects = []
    for item in element_list or []:
        if isinstance(item, str):
            identifier = item.strip()
            name = ""
        elif isinstance(item, dict):
            identifier = str(item.get("element_id") or item.get("id") or item.get("Id") or "").strip()
            name = str(item.get("name") or item.get("Name") or "").strip()
        else:
            continue
        if identifier:
            subject = {"Id": identifier}
            if name:
                subject["Name"] = name
            subjects.append(subject)
    return subjects or None


def _build_ext_info(explicit: dict[str, Any], extra: dict[str, Any] | None) -> str | None:
    merged = _merge_extra(explicit, extra)
    if not merged:
        return None
    return json.dumps(merged, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _base_video_payload(
    config: TencentVodVideoConfig,
    *,
    model_version: str,
    generation_mode: str,
    prompt: str,
    negative_prompt: str | None,
    output_config: dict[str, Any],
    session_id: str,
) -> dict[str, Any]:
    payload = {
        "SubAppId": int(config.sub_app_id),
        "ModelName": "Kling",
        "ModelVersion": model_version,
        "Prompt": prompt,
        "GenerationMode": generation_mode,
        "InputRegion": "Mainland",
        "OutputConfig": output_config,
        "SessionId": session_id,
    }
    if negative_prompt:
        payload["NegativePrompt"] = negative_prompt
    return payload


def build_image2video_payload(
    config: TencentVodVideoConfig,
    request: Image2VideoRequest,
    model_version: str,
    generation_mode: str,
    session_id: str,
) -> dict[str, Any]:
    if not request.image_urls:
        raise ValueError("Tencent VOD image2video requires at least one uploaded image URL.")
    payload = _base_video_payload(
        config,
        model_version=model_version,
        generation_mode=generation_mode,
        prompt=request.prompt or "",
        negative_prompt=request.negative_prompt,
        output_config=build_output_config(
            config,
            mode=request.mode,
            duration=request.duration,
            sound=request.sound,
        ),
        session_id=session_id,
    )
    payload["FileInfos"] = [
        url_file_info(request.image_urls[0], usage="FirstFrame"),
        *[
            url_file_info(url, usage="Reference")
            for url in request.image_urls[1:]
            if url
        ],
    ]
    if request.reference_video:
        payload["FileInfos"].append(
            url_file_info(
                request.reference_video,
                usage="Reference",
                category="Video",
                reference_type="feature",
                keep_original_sound=False,
            )
        )
    if request.image_tail_url:
        payload["LastFrameUrl"] = request.image_tail_url
    subjects = build_subject_infos(request.element_list)
    if subjects:
        payload["SubjectInfos"] = subjects
    ext_info = _build_ext_info({
        "CfgScale": request.cfg_scale,
        "VoiceList": request.voice_list,
        "ShotType": request.shot_type if request.shot_type != "single" else None,
        "CameraControl": _normalize_camera_control(request.camera_control),
    }, request.extra_payload)
    if ext_info:
        payload["ExtInfo"] = ext_info
    return payload


def build_text2video_payload(
    config: TencentVodVideoConfig,
    request: Text2VideoRequest,
    model_version: str,
    generation_mode: str,
    session_id: str,
) -> dict[str, Any]:
    payload = _base_video_payload(
        config,
        model_version=model_version,
        generation_mode=generation_mode,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        output_config=build_output_config(
            config,
            mode=request.mode,
            duration=request.duration,
            aspect_ratio=request.aspect_ratio,
            sound=request.sound,
        ),
        session_id=session_id,
    )
    subjects = build_subject_infos(request.element_list)
    if subjects:
        payload["SubjectInfos"] = subjects
    ext_info = _build_ext_info({
        "CfgScale": request.cfg_scale,
        "VoiceList": request.voice_list,
        "ShotType": request.shot_type if request.shot_type != "single" else None,
        "CameraControl": _normalize_camera_control(request.camera_control),
    }, request.extra_payload)
    if ext_info:
        payload["ExtInfo"] = ext_info
    return payload


def build_multi_images_payload(
    config: TencentVodVideoConfig,
    request: MultiImagesToVideoRequest,
    model_version: str,
    generation_mode: str,
    session_id: str,
) -> dict[str, Any]:
    if len(request.image_urls) < 2:
        raise ValueError("Tencent VOD multi-image video requires at least two uploaded image URLs.")
    if str(request.duration or "") not in {"5", "10"}:
        raise ValueError("Tencent VOD Kling multi-image video supports duration 5 or 10 seconds.")
    payload = _base_video_payload(
        config,
        model_version=model_version,
        generation_mode=generation_mode,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        output_config=build_output_config(
            config,
            mode=request.mode,
            duration=request.duration,
            aspect_ratio=request.aspect_ratio,
            sound="off",
        ),
        session_id=session_id,
    )
    payload["FileInfos"] = [
        url_file_info(url, usage="Reference")
        for url in request.image_urls
        if url
    ]
    if request.image_tail_url:
        payload["LastFrameUrl"] = request.image_tail_url
    ext_info = _build_ext_info({}, request.extra_payload)
    if ext_info:
        payload["ExtInfo"] = ext_info
    return payload


def build_motion_control_payload(
    config: TencentVodVideoConfig,
    request: MotionControlRequest,
    model_version: str,
    generation_mode: str,
    session_id: str,
) -> dict[str, Any]:
    payload = _base_video_payload(
        config,
        model_version=model_version,
        generation_mode=generation_mode,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        output_config=build_output_config(
            config,
            mode=request.mode,
            duration=request.duration,
            sound="on" if request.keep_original_sound else "off",
        ),
        session_id=session_id,
    )
    payload["SceneType"] = "motion_control"
    payload["FileInfos"] = [
        url_file_info(request.image_url, usage="FirstFrame"),
        url_file_info(
            request.video_url,
            usage="Reference",
            category="Video",
            reference_type="feature",
            keep_original_sound=request.keep_original_sound,
        ),
    ]
    subjects = build_subject_infos(request.element_list)
    if subjects:
        payload["SubjectInfos"] = subjects
    ext_info = _build_ext_info({
        "CharacterOrientation": request.character_orientation,
    }, request.extra_payload)
    if ext_info:
        payload["ExtInfo"] = ext_info
    return payload


def build_multimodal_payload(
    config: TencentVodVideoConfig,
    request: MultiModalVideoEditRequest,
    model_version: str,
    generation_mode: str,
    session_id: str,
) -> dict[str, Any]:
    payload = _base_video_payload(
        config,
        model_version=model_version,
        generation_mode=generation_mode,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        output_config=build_output_config(
            config,
            mode=request.mode,
            duration=request.duration,
            aspect_ratio=request.aspect_ratio,
            sound="on" if request.keep_original_sound else "off",
        ),
        session_id=session_id,
    )
    payload["FileInfos"] = [
        url_file_info(
            request.video_url,
            usage="Reference",
            category="Video",
            reference_type=request.edit_mode,
            keep_original_sound=request.keep_original_sound,
        ),
        *[
            url_file_info(url, usage="Reference")
            for url in request.image_urls
            if url
        ],
    ]
    ext_info = _build_ext_info({}, request.extra_payload)
    if ext_info:
        payload["ExtInfo"] = ext_info
    return payload
