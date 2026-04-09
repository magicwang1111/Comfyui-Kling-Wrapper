NODE_PREFIX = "Comfyui-Kling-Wrapper"
NODE_CATEGORY = NODE_PREFIX

CLIENT_TYPE = "COMFYUI_KLING_WRAPPER_API_CLIENT"
LIPSYNC_INPUT_TYPE = "COMFYUI_KLING_WRAPPER_LIPSYNC_INPUT"
ELEMENT_TYPE = "COMFYUI_KLING_WRAPPER_ELEMENT"
ELEMENT_LIST_TYPE = "COMFYUI_KLING_WRAPPER_ELEMENT_LIST"

DEFAULT_VIDEO_ASPECT_RATIOS = ["16:9", "9:16", "1:1"]
EXTENDED_IMAGE_ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3", "21:9", "auto"]
DEFAULT_IMAGE_RESOLUTIONS = ["1k", "2k"]
DEFAULT_VIDEO_DURATIONS = ["3", "5", "10", "15"]
DEFAULT_MODES = ["std", "pro"]
SHOT_TYPES = ["single", "intelligence"]
SOUND_OPTIONS = ["off", "on"]

IMAGE_MODEL_CAPABILITIES = {
    "kling-v1": {
        "resolutions": ["1k", "2k"],
        "aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3"],
        "supports_image_reference": True,
        "supports_image_fidelity": True,
        "supports_human_fidelity": True,
        "supports_watermark": True,
    },
    "kling-v1-5": {
        "resolutions": ["1k", "2k"],
        "aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3", "21:9"],
        "supports_image_reference": True,
        "supports_image_fidelity": True,
        "supports_human_fidelity": True,
        "supports_watermark": True,
    },
    "kling-v2": {
        "resolutions": ["1k", "2k"],
        "aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3"],
        "supports_image_reference": True,
        "supports_image_fidelity": True,
        "supports_human_fidelity": True,
        "supports_watermark": True,
    },
    "kling-v2-new": {
        "resolutions": ["1k", "2k"],
        "aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3"],
        "requires_input_image": True,
        "supports_image_reference": True,
        "supports_image_fidelity": True,
        "supports_human_fidelity": True,
        "supports_watermark": True,
    },
    "kling-v2-1": {
        "resolutions": ["1k", "2k"],
        "aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3"],
        "supports_image_reference": True,
        "supports_image_fidelity": False,
        "supports_human_fidelity": False,
        "supports_watermark": True,
    },
    "kling-image-o1": {
        "resolutions": ["1k", "2k"],
        "aspect_ratios": ["1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9"],
        "supports_auto_aspect_on_image_input": True,
        "supports_image_reference": False,
        "supports_image_fidelity": False,
        "supports_human_fidelity": False,
        "supports_negative_prompt": False,
        "supports_cfg_scale": False,
        "supports_watermark": True,
    },
    "kling-v3": {
        "resolutions": ["1k", "2k"],
        "aspect_ratios": ["1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9"],
        "supports_image_reference": False,
        "supports_image_fidelity": False,
        "supports_human_fidelity": False,
        "supports_negative_prompt": False,
        "supports_cfg_scale": False,
        "supports_watermark": True,
    },
    "kling-v3-omni": {
        "resolutions": ["1k", "2k"],
        "aspect_ratios": ["1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9"],
        "supports_image_reference": False,
        "supports_image_fidelity": False,
        "supports_human_fidelity": False,
        "supports_negative_prompt": False,
        "supports_cfg_scale": False,
        "supports_watermark": True,
    },
}

VIDEO_MODEL_CAPABILITIES = {
    "kling-v1": {
        "tasks": {"text2video", "image2video"},
        "modes": ["std", "pro"],
        "durations": ["5", "10"],
        "supports_camera_control": True,
        "supports_image_tail": False,
        "supports_image_list": False,
        "supports_element_list": False,
        "supports_reference_video": False,
        "supports_sound": False,
        "supports_voice_list": False,
        "shot_types": ["single"],
        "supports_watermark": True,
    },
    "kling-v1-5": {
        "tasks": {"image2video"},
        "modes": ["std", "pro"],
        "durations": ["5", "10"],
        "supports_camera_control": True,
        "supports_image_tail": True,
        "supports_image_list": False,
        "supports_element_list": False,
        "supports_reference_video": False,
        "supports_sound": False,
        "supports_voice_list": False,
        "shot_types": ["single"],
        "supports_watermark": True,
    },
    "kling-v1-6": {
        "tasks": {"text2video", "image2video"},
        "modes": ["std", "pro"],
        "durations": ["5", "10"],
        "supports_camera_control": True,
        "supports_image_tail": True,
        "supports_image_list": False,
        "supports_element_list": False,
        "supports_reference_video": False,
        "supports_sound": False,
        "supports_voice_list": False,
        "shot_types": ["single"],
        "supports_watermark": True,
    },
    "kling-v2-master": {
        "tasks": {"text2video", "image2video"},
        "modes": ["std", "pro"],
        "durations": ["5", "10"],
        "supports_camera_control": False,
        "supports_image_tail": False,
        "supports_image_list": False,
        "supports_element_list": False,
        "supports_reference_video": False,
        "supports_sound": False,
        "supports_voice_list": False,
        "shot_types": ["single"],
        "supports_watermark": True,
    },
    "kling-v2-1": {
        "tasks": {"text2video", "image2video", "multi_image2video"},
        "modes": ["std", "pro"],
        "durations": ["5", "10"],
        "supports_camera_control": False,
        "supports_image_tail": True,
        "supports_image_list": True,
        "supports_element_list": False,
        "supports_reference_video": False,
        "supports_sound": False,
        "supports_voice_list": False,
        "shot_types": ["single"],
        "supports_watermark": True,
    },
    "kling-v2-1-master": {
        "tasks": {"text2video", "image2video"},
        "modes": ["std", "pro"],
        "durations": ["5", "10"],
        "supports_camera_control": False,
        "supports_image_tail": True,
        "supports_image_list": False,
        "supports_element_list": False,
        "supports_reference_video": False,
        "supports_sound": False,
        "supports_voice_list": False,
        "shot_types": ["single"],
        "supports_watermark": True,
    },
    "kling-v2-5-turbo": {
        "tasks": {"text2video", "image2video", "multi_image2video"},
        "modes": ["std", "pro"],
        "durations": ["5", "10"],
        "supports_camera_control": False,
        "supports_image_tail": True,
        "image_tail_modes": ["pro"],
        "supports_image_list": True,
        "supports_element_list": False,
        "supports_reference_video": False,
        "supports_sound": False,
        "supports_voice_list": False,
        "shot_types": ["single"],
        "supports_watermark": True,
    },
    "kling-v2-6": {
        "tasks": {"text2video", "image2video"},
        "modes": ["pro"],
        "durations": ["5", "10"],
        "supports_camera_control": False,
        "supports_image_tail": False,
        "supports_image_list": False,
        "supports_element_list": False,
        "supports_reference_video": False,
        "supports_sound": True,
        "supports_voice_list": True,
        "supports_negative_prompt": False,
        "supports_cfg_scale": False,
        "shot_types": ["single"],
        "supports_watermark": True,
    },
    "kling-video-o1": {
        "tasks": {"text2video", "image2video", "multi_image2video"},
        "modes": ["std", "pro"],
        "durations": ["5", "10"],
        "supports_camera_control": False,
        "supports_image_tail": True,
        "supports_image_list": True,
        "supports_element_list": True,
        "supports_reference_video": True,
        "supports_sound": False,
        "supports_voice_list": False,
        "supports_negative_prompt": False,
        "supports_cfg_scale": False,
        "shot_types": ["single"],
        "supports_watermark": True,
    },
    "kling-v3": {
        "tasks": {"text2video", "image2video", "multi_image2video"},
        "modes": ["std", "pro"],
        "durations": ["3", "5", "10", "15"],
        "supports_camera_control": False,
        "supports_image_tail": True,
        "supports_image_list": True,
        "supports_element_list": True,
        "supports_reference_video": False,
        "supports_sound": False,
        "supports_voice_list": False,
        "supports_negative_prompt": False,
        "supports_cfg_scale": False,
        "shot_types": ["single", "intelligence"],
        "supports_watermark": True,
    },
    "kling-v3-omni": {
        "tasks": {"text2video", "image2video", "multi_image2video"},
        "modes": ["std", "pro"],
        "durations": ["3", "5", "10", "15"],
        "reference_video_durations": ["3", "5", "10"],
        "supports_camera_control": False,
        "supports_image_tail": True,
        "supports_image_list": True,
        "supports_element_list": True,
        "supports_reference_video": True,
        "supports_sound": False,
        "supports_voice_list": False,
        "supports_negative_prompt": False,
        "supports_cfg_scale": False,
        "shot_types": ["single", "intelligence"],
        "supports_watermark": True,
    },
}

# ComfyUI input options are static, so we keep the visible dropdowns aligned
# with models verified on the active endpoint. Newer documented models may
# still exist in VIDEO_MODEL_CAPABILITIES for future use, but remain hidden
# until live account support is confirmed.
IMAGE_GENERATION_MODELS = [
    "kling-v1",
    "kling-v1-5",
    "kling-v2",
    "kling-v2-new",
    "kling-v2-1",
    "kling-v3",
]

TEXT_TO_VIDEO_MODELS = [
    "kling-v1",
    "kling-v1-6",
    "kling-v2-master",
    "kling-v2-1-master",
    "kling-v2-5-turbo",
    "kling-v2-6",
    "kling-v3",
]

IMAGE_TO_VIDEO_MODELS = [
    "kling-v1",
    "kling-v1-5",
    "kling-v1-6",
    "kling-v2-master",
    "kling-v2-1",
    "kling-v2-1-master",
    "kling-v2-5-turbo",
    "kling-v2-6",
    "kling-v3",
]

# Multi-image generation is routed through image2video with a primary `image`
# plus supplemental `image_list`.
MULTI_IMAGE_TO_VIDEO_MODELS = [
    "kling-v2-1",
    "kling-v2-5-turbo",
    "kling-v3",
]


def get_image_capability(model_name):
    if model_name not in IMAGE_MODEL_CAPABILITIES:
        raise ValueError(f"Unsupported image generation model: {model_name}")
    return IMAGE_MODEL_CAPABILITIES[model_name]


def get_video_capability(model_name):
    if model_name not in VIDEO_MODEL_CAPABILITIES:
        raise ValueError(f"Unsupported video generation model: {model_name}")
    return VIDEO_MODEL_CAPABILITIES[model_name]


def validate_image_generation_request(
        model_name,
        has_input_image=False,
        aspect_ratio=None,
        resolution=None,
        image_reference_mode="None",
        image_fidelity=None,
        human_fidelity=None,
):
    capability = get_image_capability(model_name)

    if resolution and resolution not in capability["resolutions"]:
        raise ValueError(
            f"Model {model_name} only supports resolutions: {', '.join(capability['resolutions'])}."
        )

    if capability.get("requires_input_image") and not has_input_image:
        raise ValueError(f"Model {model_name} requires an input image for this node.")

    if aspect_ratio:
        supports_auto = capability.get("supports_auto_aspect_on_image_input", False)
        if aspect_ratio == "auto":
            if not has_input_image or not supports_auto:
                raise ValueError(f"Model {model_name} does not support aspect_ratio=auto for this request.")
        elif aspect_ratio not in capability["aspect_ratios"]:
            raise ValueError(
                f"Model {model_name} only supports aspect ratios: {', '.join(capability['aspect_ratios'])}."
            )

    if image_reference_mode != "None" and not capability.get("supports_image_reference", False):
        raise ValueError(f"Model {model_name} does not support image_reference.")

    uses_reference_controls = has_input_image or image_reference_mode != "None"
    if uses_reference_controls and image_fidelity is not None and not capability.get("supports_image_fidelity", False):
        raise ValueError(f"Model {model_name} does not support image_fidelity.")

    if uses_reference_controls and human_fidelity is not None and not capability.get("supports_human_fidelity", False):
        raise ValueError(f"Model {model_name} does not support human_fidelity.")

    return capability


def validate_video_generation_request(
        task_name,
        model_name,
        mode,
        duration,
        shot_type="single",
        has_image_tail=False,
        has_image_list=False,
        has_element_list=False,
        has_reference_video=False,
        has_sound=False,
        has_voice_list=False,
        has_camera_control=False,
        element_types=None,
):
    capability = get_video_capability(model_name)

    if task_name not in capability["tasks"]:
        raise ValueError(f"Model {model_name} does not support {task_name}.")

    if mode and mode not in capability["modes"]:
        raise ValueError(f"Model {model_name} only supports modes: {', '.join(capability['modes'])}.")

    if duration and duration not in capability["durations"]:
        raise ValueError(
            f"Model {model_name} only supports durations: {', '.join(capability['durations'])} seconds."
        )

    if shot_type not in capability["shot_types"]:
        raise ValueError(f"Model {model_name} does not support shot_type={shot_type}.")

    if has_camera_control and not capability.get("supports_camera_control", False):
        raise ValueError(f"Model {model_name} does not support camera control.")

    if model_name == "kling-v3-omni" and has_reference_video and (has_sound or has_voice_list):
        raise ValueError("kling-v3-omni cannot use reference_video together with native audio generation.")

    if has_sound and not capability.get("supports_sound", False):
        raise ValueError(f"Model {model_name} does not support sound control.")

    if has_voice_list and not capability.get("supports_voice_list", False):
        raise ValueError(f"Model {model_name} does not support voice_list.")

    if has_image_tail:
        if task_name == "text2video":
            raise ValueError("image_tail is only available for image-based video generation.")
        if not capability.get("supports_image_tail", False):
            raise ValueError(f"Model {model_name} does not support image_tail.")
        image_tail_modes = capability.get("image_tail_modes")
        if image_tail_modes and mode not in image_tail_modes:
            raise ValueError(
                f"Model {model_name} only supports image_tail in modes: {', '.join(image_tail_modes)}."
            )

    if has_image_list and not capability.get("supports_image_list", False):
        raise ValueError(f"Model {model_name} does not support image_list.")

    if has_element_list and not capability.get("supports_element_list", False):
        raise ValueError(f"Model {model_name} does not support element_list.")

    if has_reference_video:
        if task_name == "text2video":
            raise ValueError("reference_video is only available for image-based video generation.")
        if not capability.get("supports_reference_video", False):
            raise ValueError(f"Model {model_name} does not support reference_video.")
        reference_video_durations = capability.get("reference_video_durations")
        if reference_video_durations and duration not in reference_video_durations:
            raise ValueError(
                f"Model {model_name} only supports reference_video at durations: "
                f"{', '.join(reference_video_durations)} seconds."
            )

    if shot_type == "intelligence" and has_image_tail:
        raise ValueError("Multi-shot generation does not support start and end frames.")

    if model_name == "kling-video-o1":
        if duration not in {"5", "10"}:
            raise ValueError("kling-video-o1 currently only supports 5s or 10s generation in this node.")
        if has_image_tail and has_element_list:
            raise ValueError("kling-video-o1 does not support binding elements when using start and end frames.")
        if element_types and any(element_type == "video_character" for element_type in element_types):
            raise ValueError("kling-video-o1 only supports multi-image elements, not video-character elements.")

    return capability
