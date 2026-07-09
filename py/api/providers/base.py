from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

OFFICIAL_PROVIDER = "official"
TENCENT_VOD_PROVIDER = "tencent_vod"
VIDEO_PROVIDER_OPTIONS = [OFFICIAL_PROVIDER, TENCENT_VOD_PROVIDER]


@dataclass
class OfficialVideoConfig:
    access_key: str
    secret_key: str
    api_key: str | None = None
    in_china: bool = True
    timeout: int = 30
    poll_interval: float = 1.0


@dataclass
class TencentVodVideoConfig:
    secret_id: str
    secret_key: str
    sub_app_id: int
    region: str = "ap-guangzhou"
    request_timeout: int = 30
    poll_interval: float = 5.0
    max_wait_seconds: int = 3600
    duration: float = 3.0
    resolution: str = "720P"
    generation_mode: str = "Standard"
    storage_mode: str = "Temporary"
    audio_generation: str = "Disabled"
    person_generation: str = "AllowAdult"
    input_compliance_check: str = "Enabled"
    output_compliance_check: str = "Enabled"


@dataclass
class Image2VideoRequest:
    model_name: str
    prompt: str | None = None
    negative_prompt: str | None = None
    cfg_scale: float | None = None
    mode: str | None = None
    duration: str | None = None
    sound: str = "off"
    voice_list: list | None = None
    shot_type: str = "single"
    image_base64: str | None = None
    image_tail_base64: str | None = None
    image_tail_url: str | None = None
    image_list: list[str] | None = None
    image_urls: list[str] = field(default_factory=list)
    element_list: list | None = None
    reference_video: str | None = None
    camera_control: Any = None
    extra_payload: dict[str, Any] | None = None
    extra_output_config: dict[str, Any] | None = None


@dataclass
class Text2VideoRequest:
    model_name: str
    prompt: str
    negative_prompt: str | None = None
    cfg_scale: float | None = None
    mode: str | None = None
    aspect_ratio: str | None = None
    duration: str | None = None
    sound: str = "off"
    voice_list: list | None = None
    shot_type: str = "single"
    image_list: list | None = None
    image_urls: list[str] = field(default_factory=list)
    element_list: list | None = None
    reference_video: str | None = None
    camera_control: Any = None
    extra_payload: dict[str, Any] | None = None
    extra_output_config: dict[str, Any] | None = None


@dataclass
class VideoGenerationResult:
    url: str
    video_id: str
    task_id: str | None = None
    final_unit_deduction: float | None = None
    raw: Any = None


@dataclass
class MultiImagesToVideoRequest:
    model_name: str
    prompt: str = ""
    negative_prompt: str | None = None
    mode: str | None = None
    duration: str | None = None
    aspect_ratio: str | None = None
    image_base64_list: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    image_tail_base64: str | None = None
    image_tail_url: str | None = None
    extra_payload: dict[str, Any] | None = None


@dataclass
class MotionControlRequest:
    model_name: str
    image_url: str
    video_url: str
    prompt: str = ""
    negative_prompt: str | None = None
    mode: str | None = None
    duration: str | None = None
    character_orientation: str = "video"
    keep_original_sound: bool = True
    element_list: list | None = None
    extra_payload: dict[str, Any] | None = None


@dataclass
class MultiModalVideoEditRequest:
    model_name: str
    video_url: str
    prompt: str
    negative_prompt: str | None = None
    edit_mode: str = "base"
    keep_original_sound: bool = False
    mode: str | None = None
    duration: str | None = None
    aspect_ratio: str | None = None
    image_urls: list[str] = field(default_factory=list)
    image_base64_list: list[str] = field(default_factory=list)
    extra_payload: dict[str, Any] | None = None


@dataclass
class AdvancedElementCreateRequest:
    element_name: str
    element_description: str
    reference_type: str
    element_image_list: dict[str, Any] | None = None
    element_video_list: dict[str, Any] | None = None
    element_voice_id: str | None = None
    tag_list: list[dict[str, Any]] | None = None
    extra_payload: dict[str, Any] | None = None


@dataclass
class ElementResult:
    element: dict[str, Any]
    element_id: str = ""
    task_id: str = ""
    request_id: str = ""
    raw: Any = None


@dataclass
class CustomVoiceCreateRequest:
    voice_name: str
    voice_url: str | None = None
    video_id: str | None = None
    external_task_id: str | None = None
    callback_url: str | None = None


@dataclass
class VoiceResult:
    voice: dict[str, Any]
    task_id: str = ""
    request_id: str = ""
    raw: Any = None
