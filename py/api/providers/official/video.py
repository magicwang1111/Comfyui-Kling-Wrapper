from __future__ import annotations

from ... import Client, Image2Video, Text2Video
from ...exceptions import KLingAPIError
from ..base import Image2VideoRequest, OfficialVideoConfig, Text2VideoRequest, VideoGenerationResult
from .turbo import generate_turbo_image2video, generate_turbo_text2video


class OfficialVideoProvider:
    def __init__(self, config: OfficialVideoConfig):
        self._config = config

    def _make_client(self) -> Client:
        return Client(
            self._config.access_key,
            self._config.secret_key,
            in_china=self._config.in_china,
            timeout=self._config.timeout,
            poll_interval=self._config.poll_interval,
            api_key=self._config.api_key,
        )

    @staticmethod
    def _preferred_media_url(media_info):
        return (
            getattr(media_info, "url", None)
            or getattr(media_info, "video_url", None)
            or getattr(media_info, "resource_url", None)
            or getattr(media_info, "image_url", None)
            or getattr(media_info, "watermark_url", None)
        )

    @classmethod
    def _extract_result(cls, response, task_name: str) -> VideoGenerationResult:
        task_status = str(getattr(response, "task_status", "") or "").strip().lower()
        task_status_msg = str(getattr(response, "task_status_msg", "") or "").strip()
        task_id = str(getattr(response, "task_id", "") or "").strip() or "unknown"
        task_result = getattr(response, "task_result", None)
        videos = getattr(task_result, "videos", None) or []

        if task_status and task_status not in {"succeed", "success", "completed"}:
            details = task_status_msg or "Kling returned no additional failure details."
            raise ValueError(
                f"{task_name} task {task_id} ended with status {task_status or 'unknown'}: {details}"
            )

        if not videos:
            raise ValueError(f"{task_name} task {task_id} succeeded but returned no videos.")

        first = videos[0]
        url = cls._preferred_media_url(first)
        if not url:
            raise ValueError(f"{task_name} task {task_id} completed but returned an empty video URL.")
        return VideoGenerationResult(
            url=url,
            video_id=getattr(first, "id", "") or "",
            task_id=getattr(response, "task_id", None),
            final_unit_deduction=getattr(response, "final_unit_deduction", None),
            raw=response,
        )

    def generate_image2video(self, request: Image2VideoRequest) -> VideoGenerationResult:
        if request.model_name == "kling-v3-turbo":
            with self._make_client() as client:
                return generate_turbo_image2video(client, request)

        generator = Image2Video()
        generator.model_name = request.model_name
        if request.prompt is not None:
            generator.prompt = request.prompt
        if request.negative_prompt is not None:
            generator.negative_prompt = request.negative_prompt
        if request.cfg_scale is not None:
            generator.cfg_scale = request.cfg_scale
        if request.mode is not None:
            generator.mode = request.mode
        if request.duration is not None:
            generator.duration = request.duration
        if request.image_base64 is not None:
            generator.image = request.image_base64
        if request.image_tail_base64 is not None:
            generator.image_tail = request.image_tail_base64
        if request.image_list:
            generator.image_list = list(request.image_list)
        if request.sound is not None:
            generator.sound = request.sound
        if request.voice_list:
            generator.voice_list = request.voice_list
        if request.shot_type and request.shot_type != "single":
            generator.shot_type = request.shot_type
        if request.element_list:
            generator.element_list = request.element_list
        if request.reference_video:
            generator.reference_video = request.reference_video
        if request.camera_control is not None:
            generator.camera_control = request.camera_control

        try:
            with self._make_client() as client:
                response = generator.run(client)
        except KLingAPIError as exc:
            raise exc
        return self._extract_result(response, "Official image2video")

    def generate_text2video(self, request: Text2VideoRequest) -> VideoGenerationResult:
        if request.model_name == "kling-v3-turbo":
            with self._make_client() as client:
                return generate_turbo_text2video(client, request)

        generator = Text2Video()
        generator.model_name = request.model_name
        generator.prompt = request.prompt
        if request.negative_prompt is not None:
            generator.negative_prompt = request.negative_prompt
        if request.cfg_scale is not None:
            generator.cfg_scale = request.cfg_scale
        if request.mode is not None:
            generator.mode = request.mode
        if request.aspect_ratio is not None:
            generator.aspect_ratio = request.aspect_ratio
        if request.duration is not None:
            generator.duration = request.duration
        if request.sound is not None:
            generator.sound = request.sound
        if request.voice_list:
            generator.voice_list = request.voice_list
        if request.shot_type and request.shot_type != "single":
            generator.shot_type = request.shot_type
        if request.image_list:
            generator.image_list = request.image_list
        if request.element_list:
            generator.element_list = request.element_list
        if request.reference_video:
            generator.reference_video = request.reference_video
        if request.camera_control is not None:
            generator.camera_control = request.camera_control

        try:
            with self._make_client() as client:
                response = generator.run(client)
        except KLingAPIError as exc:
            raise exc
        return self._extract_result(response, "Official text2video")
