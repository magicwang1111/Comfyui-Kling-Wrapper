from urllib.parse import urlsplit
import re

import comfy.model_management

from .api.capabilities import CUSTOM_VOICE_LIST_TYPE, ELEMENT_LIST_TYPE, NODE_CATEGORY
from .api.video_v4 import build_payload, submit_and_wait, validate_material_counts
from .nodes import (_image_batch_to_base64_list, _normalize_element_list, _normalize_voice_list,
                    _runtime_client, _upload_video_reference)


def _common_inputs():
    return {
        "required": {
            "prompt": ("STRING", {"multiline": True, "default": "", "tooltip": "用 @image_1、@video_1、@element_1、@voice_1 引用对应素材。"}),
            "resolution": (["720p", "1080p"], {"default": "1080p"}),
            "duration": (["auto"] + [str(n) for n in range(3, 31)], {"default": "10"}),
        },
        "optional": {
            "watermark": ("BOOLEAN", {"default": False}),
            "callback_url": ("STRING", {"default": ""}),
            "external_task_id": ("STRING", {"default": ""}),
        },
    }


def _frame_inputs():
    return {
        "first_frame": ("IMAGE", {"tooltip": "单张首帧，所有图片按首帧→中间帧→尾帧→参考图统一编号。"}),
        "middle_frames": ("IMAGE", {"tooltip": "中间帧批次，每张占用一个 image_N 编号；接在首帧之后。"}),
        "last_frame": ("IMAGE", {"tooltip": "单张尾帧，接在所有中间帧之后编号。"}),
    }


def _frames(first_frame, middle_frames, last_frame):
    contents = []
    for kind, images in (("first_frame", first_frame), ("middle_frame", middle_frames), ("last_frame", last_frame)):
        if images is None:
            continue
        encoded = _image_batch_to_base64_list(images)
        if kind != "middle_frame" and len(encoded) != 1:
            raise ValueError(f"{kind} requires a single image; use middle_frames for a batch.")
        for index, value in enumerate(encoded, 1):
            identifier = f"middle_frame_{index}" if kind == "middle_frame" else kind
            contents.append({"type": kind, "url": value, "id": identifier})
    return contents


def _video_url(value):
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Video references must be HTTP(S) URLs, or connect a VIDEO input.")
    return value


def _unify_image_ids(prompt, contents):
    aliases = {}
    result = []
    for item in contents:
        if item["type"] in {"first_frame", "middle_frame", "last_frame", "refer_image"}:
            new_id = f"image_{len(aliases) + 1}"
            aliases[item["id"]] = new_id
            item = {**item, "id": new_id}
        result.append(item)
    # A named keyframe marker identifies the legacy namespace. Replace once,
    # including its old reference-image IDs, so substitutions cannot cascade.
    pattern = r"@(first_frame|middle_frame_[1-9]\d*|last_frame|image_[1-9]\d*)(?![A-Za-z0-9_])"
    tokens = re.findall(pattern, prompt or "")
    if any(name in aliases and not name.startswith("image_") for name in tokens):
        prompt = re.sub(pattern, lambda m: "@" + aliases.get(m[1], m[1]), prompt)
    return prompt, result


def _run(kind, prompt, resolution, duration, aspect_ratio=None, contents=None, **options):
    payload = build_payload(kind, prompt, resolution, duration, aspect_ratio, contents, **options)
    with _runtime_client() as client:
        result = submit_and_wait(client, kind, payload,
                                 interrupt_check=comfy.model_management.throw_exception_if_processing_interrupted)
    return result.url, result.video_id


class Kling4Text2Video:
    CATEGORY = NODE_CATEGORY + "/Kling 4.0"
    FUNCTION = "generate"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("url", "video_id")

    @classmethod
    def INPUT_TYPES(cls):
        inputs = _common_inputs()
        inputs["required"]["aspect_ratio"] = (["21:9", "16:9", "9:16", "1:1"], {"default": "16:9"})
        inputs["required"]["prompt"][1]["tooltip"] = "描述画面、镜头、动作、声音和负向要求。"
        return inputs

    def generate(self, prompt, resolution="1080p", duration="10", aspect_ratio="16:9",
                 watermark=False, callback_url="", external_task_id=""):
        return _run("text", prompt, resolution, duration, aspect_ratio,
                    watermark=watermark, callback_url=callback_url, external_task_id=external_task_id)


class Kling4Image2Video(Kling4Text2Video):
    @classmethod
    def INPUT_TYPES(cls):
        inputs = _common_inputs()
        inputs["optional"].update(_frame_inputs())
        return inputs

    def generate(self, prompt, resolution="1080p", duration="10", first_frame=None,
                 middle_frames=None, last_frame=None, watermark=False, callback_url="", external_task_id=""):
        prompt, contents = _unify_image_ids(prompt, _frames(first_frame, middle_frames, last_frame))
        return _run("image", prompt, resolution, duration,
                    contents=contents,
                    watermark=watermark, callback_url=callback_url, external_task_id=external_task_id)


class Kling4OmniVideo(Kling4Text2Video):
    @classmethod
    def INPUT_TYPES(cls):
        inputs = _common_inputs()
        inputs["required"]["aspect_ratio"] = (["adaptive", "21:9", "16:9", "9:16", "1:1"], {"default": "adaptive"})
        inputs["optional"].update(_frame_inputs())
        inputs["optional"].update({
            "reference_images": ("IMAGE", {"tooltip": "旧参考图片批次，接在关键帧之后统一分配 image_N。"}),
            "base_video": ("VIDEO", {"tooltip": "待编辑视频；有此输入时为 @video_1。与 base_video_url 二选一。"}),
            "base_video_url": ("STRING", {"default": ""}),
            "feature_video": ("VIDEO", {"tooltip": "特征参考视频；接在 base_video 后编号，无 base_video 时为 @video_1。"}),
            "feature_video_urls": ("STRING", {"multiline": True, "default": "", "tooltip": "每行一个特征视频 URL，接在 VIDEO 输入之后继续编号。"}),
            "element_list": (ELEMENT_LIST_TYPE, {"tooltip": "现有主体列表：@element_1、@element_2…"}),
            "custom_voice_list": (CUSTOM_VOICE_LIST_TYPE, {"tooltip": "现有音色列表：@voice_1、@voice_2…"}),
        })
        for index in range(1, 11):
            inputs["optional"][f"image_{index}"] = ("IMAGE", {"tooltip": "单张参考图；引用编号在所有关键帧之后，查看接口旁标签。"})
        for index in range(1, 6):
            inputs["optional"][f"feature_video_{index}"] = ("VIDEO", {"tooltip": "参考视频，实际 @video 编号显示在连接口旁。"})
        return inputs

    def generate(self, prompt, resolution="1080p", duration="10", aspect_ratio="adaptive",
                 first_frame=None, middle_frames=None, last_frame=None, reference_images=None,
                 base_video=None, base_video_url="", feature_video=None, feature_video_urls="",
                 element_list=None, custom_voice_list=None, watermark=False, callback_url="", external_task_id="", **dynamic_inputs):
        if base_video is not None and base_video_url.strip():
            raise ValueError("Provide base_video or base_video_url, not both.")
        urls = [_video_url(line) for line in feature_video_urls.splitlines() if line.strip()]
        base_url = _video_url(base_video_url) if base_video_url.strip() else None
        contents = _frames(first_frame, middle_frames, last_frame)
        dynamic_images = []
        dynamic_videos = []
        for name, value in dynamic_inputs.items():
            if value is None:
                continue
            match = re.fullmatch(r"(image|feature_video)_([1-9]\d*)", name)
            if not match:
                raise ValueError(f"Unknown Kling 4.0 input: {name}")
            kind, index = match[1], int(match[2])
            if index > (10 if kind == "image" else 5):
                raise ValueError(f"Kling 4.0 input index out of range: {name}")
            (dynamic_images if kind == "image" else dynamic_videos).append((index, value))
        if dynamic_images and reference_images is not None:
            raise ValueError("Use image_N inputs or legacy reference_images, not both.")
        for index, image in sorted(dynamic_images):
            encoded = _image_batch_to_base64_list(image)
            if len(encoded) != 1:
                raise ValueError(f"image_{index} requires a single image; connect each reference separately.")
            contents.append({"type": "refer_image", "url": encoded[0], "id": f"image_{index}"})
        if reference_images is not None:
            for index, value in enumerate(_image_batch_to_base64_list(reference_images), 1):
                contents.append({"type": "refer_image", "url": value, "id": f"image_{index}"})
        videos = []
        if base_video is not None or base_url:
            videos.append(("base_video", base_video if base_video is not None else base_url, 1))
        offset = len(videos)
        if feature_video is not None:
            videos.append(("feature_video", feature_video, offset + 1))
            offset += 1
        for index, video in sorted(dynamic_videos):
            videos.append(("feature_video", video, offset + index))
        next_index = max((v[2] for v in videos), default=0) + 1
        videos.extend(("feature_video", url, next_index + i) for i, url in enumerate(urls))
        for kind, value, index in videos:
            contents.append({"type": kind, "url": value, "id": f"video_{index}"})
        for index, element in enumerate(_normalize_element_list(element_list) or [], 1):
            contents.append({"type": "element", "element_id": element["element_id"], "id": f"element_{index}"})
        for index, voice in enumerate(_normalize_voice_list(custom_voice_list) or [], 1):
            contents.append({"type": "voice", "voice_id": voice["voice_id"], "id": f"voice_{index}"})
        validate_material_counts(contents)
        prompt, contents = _unify_image_ids(prompt, contents)
        for item in contents:
            if item["type"] in {"base_video", "feature_video"} and not isinstance(item["url"], str):
                item["url"] = _upload_video_reference(item["url"])
        return _run("omni", prompt, resolution, duration, aspect_ratio, contents,
                    watermark=watermark, callback_url=callback_url, external_task_id=external_task_id)
