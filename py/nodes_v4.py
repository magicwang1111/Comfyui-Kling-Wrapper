from urllib.parse import urlsplit

import comfy.model_management

from .api.capabilities import CUSTOM_VOICE_LIST_TYPE, ELEMENT_LIST_TYPE, NODE_CATEGORY
from .api.video_v4 import build_payload, submit_and_wait
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
        "first_frame": ("IMAGE", {"tooltip": "单张首帧，引用 @first_frame"}),
        "middle_frames": ("IMAGE", {"tooltip": "中间帧批次，引用 @middle_frame_1、@middle_frame_2…"}),
        "last_frame": ("IMAGE", {"tooltip": "单张尾帧，引用 @last_frame"}),
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
        return _run("image", prompt, resolution, duration,
                    contents=_frames(first_frame, middle_frames, last_frame),
                    watermark=watermark, callback_url=callback_url, external_task_id=external_task_id)


class Kling4OmniVideo(Kling4Text2Video):
    @classmethod
    def INPUT_TYPES(cls):
        inputs = _common_inputs()
        inputs["required"]["aspect_ratio"] = (["adaptive", "21:9", "16:9", "9:16", "1:1"], {"default": "adaptive"})
        inputs["optional"].update(_frame_inputs())
        inputs["optional"].update({
            "reference_images": ("IMAGE", {"tooltip": "参考图片批次：@image_1、@image_2…；关键帧不占用这些编号。"}),
            "base_video": ("VIDEO", {"tooltip": "待编辑视频；有此输入时为 @video_1。与 base_video_url 二选一。"}),
            "base_video_url": ("STRING", {"default": ""}),
            "feature_video": ("VIDEO", {"tooltip": "特征参考视频；接在 base_video 后编号，无 base_video 时为 @video_1。"}),
            "feature_video_urls": ("STRING", {"multiline": True, "default": "", "tooltip": "每行一个特征视频 URL，接在 VIDEO 输入之后继续编号。"}),
            "element_list": (ELEMENT_LIST_TYPE, {"tooltip": "现有主体列表：@element_1、@element_2…"}),
            "custom_voice_list": (CUSTOM_VOICE_LIST_TYPE, {"tooltip": "现有音色列表：@voice_1、@voice_2…"}),
        })
        return inputs

    def generate(self, prompt, resolution="1080p", duration="10", aspect_ratio="adaptive",
                 first_frame=None, middle_frames=None, last_frame=None, reference_images=None,
                 base_video=None, base_video_url="", feature_video=None, feature_video_urls="",
                 element_list=None, custom_voice_list=None, watermark=False, callback_url="", external_task_id=""):
        if base_video is not None and base_video_url.strip():
            raise ValueError("Provide base_video or base_video_url, not both.")
        urls = [_video_url(line) for line in feature_video_urls.splitlines() if line.strip()]
        base_url = _video_url(base_video_url) if base_video_url.strip() else None
        contents = _frames(first_frame, middle_frames, last_frame)
        if reference_images is not None:
            for index, value in enumerate(_image_batch_to_base64_list(reference_images), 1):
                contents.append({"type": "refer_image", "url": value, "id": f"image_{index}"})
        videos = []
        if base_video is not None:
            base_url = _upload_video_reference(base_video)
        if base_url:
            videos.append(("base_video", base_url))
        if feature_video is not None:
            videos.append(("feature_video", _upload_video_reference(feature_video)))
        videos.extend(("feature_video", url) for url in urls)
        for index, (kind, url) in enumerate(videos, 1):
            contents.append({"type": kind, "url": url, "id": f"video_{index}"})
        for index, element in enumerate(_normalize_element_list(element_list) or [], 1):
            contents.append({"type": "element", "element_id": element["element_id"], "id": f"element_{index}"})
        for index, voice in enumerate(_normalize_voice_list(custom_voice_list) or [], 1):
            contents.append({"type": "voice", "voice_id": voice["voice_id"], "id": f"voice_{index}"})
        return _run("omni", prompt, resolution, duration, aspect_ratio, contents,
                    watermark=watermark, callback_url=callback_url, external_task_id=external_task_id)
