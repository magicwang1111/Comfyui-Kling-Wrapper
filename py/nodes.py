from .api import Client, ImageGenerator, ImageExpander, Image2Video, Video2Audio, Text2Audio, \
    Text2Video, CameraControl, CameraControlConfig, KolorsVurtualTryOn, VideoExtend, LipSync, LipSyncInput, EffectInput, \
    Effects, MultiImages2Video, MultiModelVideoEdit, AdvancedCustomElements, MotionControl
from .api.capabilities import DEFAULT_IMAGE_RESOLUTIONS, DEFAULT_MODES, DEFAULT_VIDEO_ASPECT_RATIOS, \
    DEFAULT_VIDEO_DURATIONS, ELEMENT_LIST_TYPE, ELEMENT_TYPE, EXTENDED_IMAGE_ASPECT_RATIOS, IMAGE_GENERATION_MODELS, \
    IMAGE_TO_VIDEO_MODELS, LIPSYNC_INPUT_TYPE, MULTI_IMAGE_TO_VIDEO_MODELS, NODE_CATEGORY, NODE_PREFIX, SHOT_TYPES, \
    SOUND_OPTIONS, TEXT_TO_VIDEO_MODELS, get_image_capability, get_video_capability, \
    validate_image_generation_request, validate_video_generation_request
from .api.exceptions import KLingAPIError
import base64
import configparser
from contextlib import contextmanager
import email.utils
import hashlib
import hmac
import io
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import numpy
import PIL
import requests
import torch
from collections.abc import Iterable
import folder_paths
from comfy_extras.nodes_audio import LoadAudio
import time
import urllib.parse
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_JSON_PATH = ROOT_DIR / "config.local.json"
LEGACY_CONFIG_PATH = ROOT_DIR / "config.ini"
LEGACY_CONFIG_SECTION = "API"

DEFAULT_FILENAME_PREFIX = NODE_PREFIX
DEFAULT_VIDEO_FILENAME_PREFIX = "video/timeline"
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_UPLOAD_TIMEOUT = 120
DEFAULT_AREA_OPTIONS = ["global", "china"]
CAMERA_CONTROL_TYPES = ["None", "simple", "down_back", "forward_up", "right_turn_forward", "left_turn_forward"]
CAMERA_CONTROL_CONFIGS = ["horizontal", "vertical", "pan", "tilt", "roll", "zoom"]
MOTION_CONTROL_MODELS = ["kling-v2-6", "kling-v3"]
MOTION_CONTROL_DURATIONS = ["auto", "3", "5", "10", "15", "30"]
TMPFILES_UPLOAD_API_URL = "https://tmpfiles.org/api/v1/upload"
CATBOX_UPLOAD_API_URL = "https://catbox.moe/user/api.php"
TMPFILES_MAX_SIZE_BYTES = 100 * 1024 * 1024
TMPFILES_UPLOAD_RETRY_COUNT = 3
TMPFILES_UPLOAD_RETRY_DELAY = 1.0
LOCAL_MEDIA_UPLOAD_SUBFOLDER = "kling_uploads"
DEFAULT_REFERENCE_VIDEO_FPS = 24.0
LIPSYNC_AUDIO_TYPES = {
    "阳光少年": "genshin_vindi2",
    "懂事小弟": "zhinen_xuesheng",
    "运动少年": "tiyuxi_xuedi",
    "青春少女": "ai_shatang",
    "温柔小妹": "genshin_klee2",
    "元气少女": "guanxiaofang-v2",
    "阳光男生": "ai_kaiya",
    "幽默小哥": "tiexin_nanyou",
    "文艺小哥": "ai_chenjiahao_712",
    "甜美邻家": "girlfriend_1_speech02",
    "温柔姐姐": "chat1_female_new-3",
    "职场女青": "girlfriend_2_speech02",
    "活泼男童": "cartoon-boy-07",
    "俏皮女童": "cartoon-girl-01",
    "稳重老爸": "ai_huangyaoshi_712",
    "温柔妈妈": "you_pingjing",
    "严肃上司": "ai_laoguowang_712",
    "优雅贵妇": "chengshu_jiejie",
    "慈祥爷爷": "zhuxi_speech02",
    "唠叨爷爷": "uk_oldman3",
    "唠叨奶奶": "laopopo_speech02",
    "和蔼奶奶": "heainainai_speech02",
    "东北老铁": "dongbeilaotie_speech02",
    "重庆小伙": "chongqingxiaohuo_speech02",
    "四川妹子": "chuanmeizi_speech02",
    "潮汕大叔": "chaoshandashu_speech02",
    "台湾男生": "ai_taiwan_man2_speech02",
    "西安掌柜": "xianzhanggui_speech02",
    "天津姐姐": "tianjinjiejie_speech02",
    "新闻播报男": "diyinnansang_DB_CN_M_04-v2",
    "译制片男": "yizhipiannan-v1",
    "撒娇女友": "tianmeixuemei-v1",
    "刀片烟嗓": "daopianyansang-v1",
    "乖巧正太": "mengwa-v1",
    "Sunny": "genshin_vindi2",
    "Sage": "zhinen_xuesheng",
    "Ace": "AOT",
    "Blossom": "ai_shatang",
    "Peppy": "genshin_klee2",
    "Dove": "genshin_kirara",
    "Shine": "ai_kaiya",
    "Anchor": "oversea_male1",
    "Lyric": "ai_chenjiahao_712",
    "Melody": "girlfriend_4_speech02",
    "Tender": "chat1_female_new-3",
    "Siren": "chat_0407_5-1",
    "Zippy": "cartoon-boy-07",
    "Bud": "uk_boy1",
    "Sprite": "cartoon-girl-01",
    "Candy": "PeppaPig_platform",
    "Beacon": "ai_huangzhong_712",
    "Rock": "ai_huangyaoshi_712",
    "Titan": "ai_laoguowang_712",
    "Grace": "chengshu_jiejie",
    "Helen": "you_pingjing",
    "Lore": "calm_story1",
    "Crag": "uk_man2",
    "Prattle": "laopopo_speech02",
    "Hearth": "heainainai_speech02",
    "The Reader": "reader_en_m-v1",
    "Commercial Lady": "commercial_lady_en_f-v1",
}


def _build_voice_preset_items():
    labels_by_id = {}
    for label, voice_id in LIPSYNC_AUDIO_TYPES.items():
        labels_by_id.setdefault(voice_id, []).append(label)

    items = [("None", "")]
    for voice_id, labels in labels_by_id.items():
        preferred_label = next((label for label in labels if label.isascii()), labels[0])
        items.append((f"{preferred_label} | {voice_id}", voice_id))
    return items


VOICE_PRESET_ITEMS = _build_voice_preset_items()
VOICE_PRESET_OPTIONS = [label for label, _ in VOICE_PRESET_ITEMS]
VOICE_PRESET_VALUE_BY_LABEL = {label: voice_id for label, voice_id in VOICE_PRESET_ITEMS}
DEFAULT_VOICE_PRESET = "None"


def _load_json_config():
    if not CONFIG_JSON_PATH.exists():
        return {}

    try:
        with CONFIG_JSON_PATH.open("r", encoding="utf-8") as handle:
            config_data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{CONFIG_JSON_PATH.name} is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Failed to read {CONFIG_JSON_PATH.name}: {exc}") from exc

    if not isinstance(config_data, dict):
        raise ValueError(f"{CONFIG_JSON_PATH.name} must contain a top-level JSON object.")

    return config_data


def _json_value_present(config_data, key):
    if key not in config_data:
        return False

    value = config_data[key]
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _load_env_value(*keys):
    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""


def _load_legacy_config_value(*keys):
    config = configparser.ConfigParser()
    config.read(LEGACY_CONFIG_PATH, encoding="utf-8")
    for key in keys:
        value = config.get(LEGACY_CONFIG_SECTION, key, fallback="").strip()
        if value:
            return value
    return ""


def _parse_request_timeout(value):
    if isinstance(value, bool):
        raise ValueError("request_timeout must be an integer.")

    if isinstance(value, int):
        timeout = value
    else:
        try:
            timeout = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError("request_timeout must be an integer.") from exc

    if timeout < 5:
        raise ValueError("request_timeout must be greater than or equal to 5.")

    return timeout


def _parse_poll_interval(value):
    if isinstance(value, bool):
        raise ValueError("poll_interval must be a number.")

    if isinstance(value, (int, float)):
        interval = float(value)
    else:
        try:
            interval = float(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError("poll_interval must be a number.") from exc

    if interval <= 0:
        raise ValueError("poll_interval must be greater than 0.")

    return interval


def _normalize_area(value):
    normalized = str(value).strip().lower()
    aliases = {
        "global": "global",
        "intl": "global",
        "international": "global",
        "china": "china",
        "cn": "china",
    }
    if normalized in aliases:
        return aliases[normalized]
    raise ValueError(f"area must be one of: {', '.join(DEFAULT_AREA_OPTIONS)}.")


def _resolve_access_key(config_data):
    if _json_value_present(config_data, "access_key"):
        return str(config_data["access_key"]).strip()

    env_value = _load_env_value("KLINGAI_API_ACCESS_KEY", "KLING_ACCESS_KEY")
    if env_value:
        return env_value

    legacy_value = _load_legacy_config_value("KLINGAI_API_ACCESS_KEY")
    if legacy_value:
        return legacy_value

    raise ValueError(
        "An access_key is required. Add access_key to config.local.json, set KLINGAI_API_ACCESS_KEY or "
        "KLING_ACCESS_KEY, or add KLINGAI_API_ACCESS_KEY to config.ini."
    )


def _resolve_secret_key(config_data):
    if _json_value_present(config_data, "secret_key"):
        return str(config_data["secret_key"]).strip()

    env_value = _load_env_value("KLINGAI_API_SECRET_KEY", "KLING_SECRET_KEY")
    if env_value:
        return env_value

    legacy_value = _load_legacy_config_value("KLINGAI_API_SECRET_KEY")
    if legacy_value:
        return legacy_value

    raise ValueError(
        "A secret_key is required. Add secret_key to config.local.json, set KLINGAI_API_SECRET_KEY or "
        "KLING_SECRET_KEY, or add KLINGAI_API_SECRET_KEY to config.ini."
    )


def _resolve_area(config_data):
    if _json_value_present(config_data, "area"):
        return _normalize_area(config_data["area"])

    env_value = _load_env_value("KLINGAI_AREA")
    if env_value:
        return _normalize_area(env_value)

    legacy_value = _load_legacy_config_value("KLINGAI_AREA")
    if legacy_value:
        return _normalize_area(legacy_value)

    return DEFAULT_AREA_OPTIONS[0]


def _resolve_poll_interval(config_data):
    if _json_value_present(config_data, "poll_interval"):
        return _parse_poll_interval(config_data["poll_interval"])

    env_value = _load_env_value("KLINGAI_POLL_INTERVAL")
    if env_value:
        return _parse_poll_interval(env_value)

    legacy_value = _load_legacy_config_value("KLINGAI_POLL_INTERVAL")
    if legacy_value:
        return _parse_poll_interval(legacy_value)

    return DEFAULT_POLL_INTERVAL


def _resolve_request_timeout(config_data):
    if _json_value_present(config_data, "request_timeout"):
        return _parse_request_timeout(config_data["request_timeout"])

    env_value = _load_env_value("KLINGAI_REQUEST_TIMEOUT")
    if env_value:
        return _parse_request_timeout(env_value)

    legacy_value = _load_legacy_config_value("KLINGAI_REQUEST_TIMEOUT")
    if legacy_value:
        return _parse_request_timeout(legacy_value)

    return DEFAULT_REQUEST_TIMEOUT


def _create_runtime_client():
    config_data = _load_json_config()
    client = Client(
        _resolve_access_key(config_data),
        _resolve_secret_key(config_data),
        in_china=_resolve_area(config_data) == "china",
        timeout=_resolve_request_timeout(config_data),
        poll_interval=_resolve_poll_interval(config_data),
    )
    return client


@contextmanager
def _runtime_client():
    client = _create_runtime_client()
    try:
        yield client
    finally:
        client.close()


def _fetch_image(url, stream=True):
    return requests.get(url, stream=stream).content


def _tensor2images(tensor):
    np_imgs = numpy.clip(tensor.cpu().numpy() * 255.0, 0.0, 255.0).astype(numpy.uint8)
    return [PIL.Image.fromarray(np_img) for np_img in np_imgs]


def _images2tensor(images):
    if isinstance(images, Iterable):
        return torch.stack([torch.from_numpy(numpy.array(image)).float() / 255.0 for image in images])
    return torch.from_numpy(numpy.array(images)).unsqueeze(0).float() / 255.0


def _decode_image(data_bytes, rtn_mask=False):
    with io.BytesIO(data_bytes) as bytes_io:
        img = PIL.Image.open(bytes_io)
        if not rtn_mask:
            img = img.convert('RGB')
        elif 'A' in img.getbands():
            img = img.getchannel('A')
        else:
            img = None
    return img


def _encode_image(img, mask=None):
    if mask is not None:
        img = img.copy()
        img.putalpha(mask)
    with io.BytesIO() as bytes_io:
        if mask is not None:
            img.save(bytes_io, format='PNG')
        else:
            img.save(bytes_io, format='JPEG')
        data_bytes = bytes_io.getvalue()
    return data_bytes


def _image_to_base64(image):
    if image is None:
        return None
    return base64.b64encode(_encode_image(_tensor2images(image)[0])).decode("utf-8")


def _image_batch_to_base64_list(image):
    if image is None:
        return []
    return [base64.b64encode(_encode_image(frame)).decode("utf-8") for frame in _tensor2images(image)]


def _parse_json_input(raw_value, field_name):
    if raw_value is None:
        return None
    if isinstance(raw_value, (dict, list)):
        return raw_value
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a JSON string.")

    stripped = raw_value.strip()
    if not stripped:
        return None

    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be valid JSON: {exc}") from exc


def _build_watermark_info(enabled):
    if not enabled:
        return None
    return {"enabled": True}


def _clean_optional_text(value):
    if not isinstance(value, str):
        return value
    value = value.strip()
    return value or None


def _set_if_present(target, field_name, value):
    if value is not None:
        setattr(target, field_name, value)


def _resolve_voice_id(voice_preset):
    if not isinstance(voice_preset, str):
        return None
    voice_preset = voice_preset.strip()
    if not voice_preset or voice_preset == "None":
        return None
    if voice_preset in VOICE_PRESET_VALUE_BY_LABEL:
        return VOICE_PRESET_VALUE_BY_LABEL[voice_preset]
    if voice_preset in LIPSYNC_AUDIO_TYPES.values():
        return voice_preset
    if "|" in voice_preset:
        candidate = voice_preset.rsplit("|", 1)[-1].strip()
        if candidate:
            return candidate
    return voice_preset


def _build_voice_list_from_preset(voice_preset):
    voice_id = _resolve_voice_id(voice_preset)
    if not voice_id:
        return None
    return [{"voice_id": voice_id}]


def _apply_prompt_controls(target, capability, prompt=None, negative_prompt=None, cfg_scale=None):
    cleaned_prompt = _clean_optional_text(prompt)
    cleaned_negative_prompt = _clean_optional_text(negative_prompt)

    _set_if_present(target, "prompt", cleaned_prompt)

    if cleaned_negative_prompt and capability.get("supports_negative_prompt", True):
        target.negative_prompt = cleaned_negative_prompt

    if cfg_scale is not None and capability.get("supports_cfg_scale", True):
        target.cfg_scale = cfg_scale


def _normalize_requested_mode(model_name, capability, mode):
    supported_modes = capability.get("modes") or []
    if not supported_modes:
        return mode
    if mode in supported_modes:
        return mode
    if len(supported_modes) == 1 and mode in (None, "", "std"):
        resolved_mode = supported_modes[0]
        print(f"[{NODE_PREFIX}] normalized mode for {model_name}: {mode!r} -> {resolved_mode!r}")
        return resolved_mode
    return mode


def _raise_with_model_guidance(exc, model_name):
    if (
        isinstance(exc, KLingAPIError)
        and exc.code == 1201
        and isinstance(exc.message, str)
        and "model is not supported" in exc.message.lower()
        and model_name in {"kling-v3-omni", "kling-video-o1"}
    ):
        raise ValueError(
            f"Kling API returned `1201 model is not supported` for `{model_name}`. "
            f"This node now strips legacy tuning fields for these newer models, so if the error still occurs "
            f"it is likely the live endpoint/account has not enabled that model yet. "
            f"Please verify the model is available for your current key on the active endpoint, or temporarily use `kling-v3`."
        ) from exc
    raise exc


def _raise_with_image_model_guidance(exc, model_name):
    if (
        isinstance(exc, KLingAPIError)
        and exc.code == 1201
        and isinstance(exc.message, str)
        and "model is not supported" in exc.message.lower()
    ):
        raise ValueError(
            f"Kling API returned `1201 model is not supported` for image model `{model_name}`. "
            f"On the Beijing endpoint this usually means the current key has not enabled that image model yet. "
            f"Models like `kling-v3` are recognized, while some newer image entries may still be unavailable on a given account."
        ) from exc
    raise exc


def _preferred_media_url(media_info, prefer_watermark=False):
    watermark_url = getattr(media_info, "watermark_url", None)
    if prefer_watermark and isinstance(watermark_url, str) and watermark_url.strip():
        return watermark_url.strip()

    for field_name in ("url", "video_url", "resource_url", "image_url"):
        candidate = getattr(media_info, field_name, None)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    if isinstance(watermark_url, str) and watermark_url.strip():
        return watermark_url.strip()

    return None


def _extract_first_video_result(response, task_name):
    task_status = getattr(response, "task_status", None)
    task_status_msg = getattr(response, "task_status_msg", None)
    task_result = getattr(response, "task_result", None)
    videos = getattr(task_result, "videos", None) or []

    if task_status not in (None, "", "succeed", "success", "completed"):
        details = f"{task_name} failed with task_status={task_status!r}"
        if task_status_msg:
            details += f": {task_status_msg}"
        raise ValueError(details)

    if not videos:
        details = f"{task_name} did not return any videos."
        if task_status:
            details += f" task_status={task_status!r}."
        if task_status_msg:
            details += f" Details: {task_status_msg}"
        raise ValueError(details)

    for video_info in videos:
        video_url = _preferred_media_url(video_info)
        if video_url:
            return video_url, getattr(video_info, "id", "")

    details = f"{task_name} completed but returned an empty video URL."
    if task_status:
        details += f" task_status={task_status!r}."
    if task_status_msg:
        details += f" Details: {task_status_msg}"
    raise ValueError(details)


def _log_final_unit_deduction(response, task_name):
    deduction = getattr(response, "final_unit_deduction", None)
    if deduction is not None:
        print(f"[{NODE_PREFIX}] final_unit_deduction | {task_name}: {deduction}")


def _collect_element_types(element_list):
    if not element_list:
        return []
    element_types = []
    for element in element_list:
        if isinstance(element, dict):
            element_types.append(element.get("type") or element.get("element_type"))
    return [element_type for element_type in element_types if element_type]


def _normalize_element_reference(element):
    if element is None:
        return None
    if isinstance(element, dict):
        element_id = element.get("element_id") or element.get("id")
        element_type = element.get("type") or element.get("element_type")
        if not element_id:
            raise ValueError("Element payload is missing element_id.")
        payload = {"element_id": element_id}
        if element_type:
            payload["type"] = element_type
        return payload
    if isinstance(element, str):
        element_id = element.strip()
        if not element_id:
            return None
        return {"element_id": element_id}
    raise ValueError("Element must be a dict or string.")


def _normalize_element_list(elements):
    if elements is None:
        return None
    if isinstance(elements, dict):
        elements = [elements]
    normalized = []
    for element in elements:
        payload = _normalize_element_reference(element)
        if payload:
            normalized.append(payload)
    return normalized or None


def _build_camera_control(camera_control_type, camera_control_config, camera_control_value):
    if camera_control_type == "None":
        return None

    camera_control = CameraControl()
    camera_control.type = camera_control_type

    if camera_control_type == "simple":
        camera_control.config = CameraControlConfig()
        setattr(camera_control.config, camera_control_config, camera_control_value)

    return camera_control


def _element_result_to_payload(data):
    if data is None:
        return None
    if hasattr(data, "dict"):
        return data.dict(exclude_none=True)
    if isinstance(data, dict):
        return {key: value for key, value in data.items() if value is not None}
    return data


def _extract_elements_from_response(data):
    if data is None:
        return []
    task_result = data.get("task_result") if isinstance(data, dict) else getattr(data, "task_result", None)
    if isinstance(task_result, dict):
        if task_result.get("elements"):
            return task_result["elements"]
        if task_result.get("element"):
            return [task_result["element"]]
    if task_result is not None:
        elements = getattr(task_result, "elements", None)
        if elements:
            return [_element_result_to_payload(element) for element in elements]
        element = getattr(task_result, "element", None)
        if element:
            return [_element_result_to_payload(element)]
    if isinstance(data, dict) and data.get("elements"):
        return data["elements"]
    if isinstance(data, dict) and data.get("element"):
        return [data["element"]]
    return []


def _load_audio_from_url(audio_url, save_directory, filename_prefix="audio"):
    try:
        response = requests.get(
            audio_url,
            timeout=30,
            stream=True,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        response.raise_for_status()

        parsed_url = urllib.parse.urlparse(audio_url)
        ext = Path(parsed_url.path).suffix or '.mp3'

        timestamp = int(time.time() * 1000)  # 毫秒级时间戳
        filename = f"{filename_prefix}_{timestamp}{ext}"

        file_path = os.path.join(save_directory, filename)

        os.makedirs(save_directory, exist_ok=True)

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return file_path  # 返回完整路径

    except requests.exceptions.Timeout:
        raise Exception(f"time out: {audio_url}")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"http error {e.response.status_code}: {audio_url}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"download failed: {e}")
    except IOError as e:
        raise Exception(f"save failed: {e}")
    except Exception as e:
        raise Exception(f"other failed: {e}")


def _saved_result(filename, subfolder, folder_type):
    return {
        "filename": filename,
        "subfolder": subfolder,
        "type": folder_type,
    }


def _register_output_asset(file_path):
    try:
        import app.assets.services.ingest as asset_ingest
    except Exception:
        return

    ingest_existing_file = getattr(asset_ingest, "ingest_existing_file", None)
    if not callable(ingest_existing_file):
        return

    try:
        ingest_existing_file(file_path)
    except Exception:
        return


def _build_local_media_view_url(filename, subfolder, folder_type):
    query = [
        f"type={urllib.parse.quote(str(folder_type), safe='')}",
        f"filename={urllib.parse.quote(str(filename), safe='')}",
    ]
    if subfolder:
        query.append(f"subfolder={urllib.parse.quote(str(subfolder), safe='')}")
    return "/api/view?" + "&".join(query)


def _normalize_tmpfiles_download_url(page_url):
    normalized = str(page_url or "").strip()
    if not normalized:
        raise ValueError("Upload service did not return a file URL.")

    parsed = urllib.parse.urlparse(normalized)
    if parsed.netloc.lower() != "tmpfiles.org":
        return normalized

    path = parsed.path.strip("/")
    if not path:
        raise ValueError("Upload service returned an invalid tmpfiles URL.")

    if path.startswith("dl/"):
        return f"https://tmpfiles.org/{path}"

    return f"https://tmpfiles.org/dl/{path}"


def _resolve_upload_file_path(file_path):
    normalized_path = os.path.abspath(os.fspath(file_path))
    if not os.path.exists(normalized_path):
        raise ValueError(f"Upload file does not exist: {normalized_path}")
    if not os.path.isfile(normalized_path):
        raise ValueError(f"Upload path is not a file: {normalized_path}")

    return normalized_path


def _normalize_catbox_upload_url(raw_url):
    normalized = str(raw_url or "").strip()
    if not normalized:
        raise ValueError("catbox.moe upload did not return a file URL.")
    if normalized.upper().startswith("ERROR"):
        raise ValueError(f"catbox.moe upload failed: {normalized}")

    parsed = urllib.parse.urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"catbox.moe upload returned an invalid URL: {normalized}")

    return normalized


def _is_http_url(value):
    parsed = urllib.parse.urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _config_or_env_value(config_data, json_key, env_key, default=""):
    if _json_value_present(config_data, json_key):
        return str(config_data[json_key]).strip()

    env_value = _load_env_value(env_key)
    if env_value:
        return env_value

    return default


def _normalize_oss_endpoint(endpoint):
    raw_endpoint = str(endpoint or "").strip().rstrip("/")
    if not raw_endpoint:
        raise ValueError("oss_endpoint is required.")

    if "://" not in raw_endpoint:
        raw_endpoint = f"https://{raw_endpoint}"

    parsed = urllib.parse.urlparse(raw_endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("oss_endpoint must be a valid OSS endpoint host or URL.")
    if parsed.path not in {"", "/"}:
        raise ValueError("oss_endpoint must not include a path.")

    return parsed.scheme, parsed.netloc


def _normalize_oss_prefix(prefix):
    normalized = str(prefix or "").strip().strip("/")
    return normalized or LOCAL_MEDIA_UPLOAD_SUBFOLDER


def _parse_oss_signed_url_expires(value):
    if value in (None, ""):
        return 24 * 60 * 60

    try:
        expires = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("oss_signed_url_expires must be an integer number of seconds.") from exc

    if expires <= 0:
        raise ValueError("oss_signed_url_expires must be greater than 0.")

    return expires


def _resolve_oss_upload_config():
    config_data = _load_json_config()
    endpoint = _config_or_env_value(config_data, "oss_endpoint", "OSS_ENDPOINT")
    access_key_id = _config_or_env_value(config_data, "oss_access_key_id", "OSS_ACCESS_KEY_ID")
    access_key_secret = _config_or_env_value(config_data, "oss_access_key_secret", "OSS_ACCESS_KEY_SECRET")
    bucket = _config_or_env_value(config_data, "oss_bucket", "OSS_BUCKET")
    prefix = _config_or_env_value(config_data, "oss_prefix", "OSS_PREFIX", LOCAL_MEDIA_UPLOAD_SUBFOLDER)
    signed_url_expires = _config_or_env_value(
        config_data,
        "oss_signed_url_expires",
        "OSS_SIGNED_URL_EXPIRES",
        24 * 60 * 60,
    )

    required_values = {
        "oss_endpoint": endpoint,
        "oss_access_key_id": access_key_id,
        "oss_access_key_secret": access_key_secret,
        "oss_bucket": bucket,
    }
    present_count = sum(1 for value in required_values.values() if value)
    if present_count == 0:
        return None

    missing_keys = [key for key, value in required_values.items() if not value]
    if missing_keys:
        raise ValueError(
            "OSS upload config is incomplete; set "
            + ", ".join(missing_keys)
            + " in config.local.json or environment variables."
        )

    scheme, endpoint_host = _normalize_oss_endpoint(endpoint)
    return {
        "scheme": scheme,
        "endpoint_host": endpoint_host,
        "access_key_id": access_key_id,
        "access_key_secret": access_key_secret,
        "bucket": str(bucket).strip(),
        "prefix": _normalize_oss_prefix(prefix),
        "signed_url_expires": _parse_oss_signed_url_expires(signed_url_expires),
    }


def _oss_signature(access_key_secret, string_to_sign):
    digest = hmac.new(
        access_key_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def _build_oss_object_key(file_path, prefix):
    filename = os.path.basename(os.fspath(file_path))
    safe_filename = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    if not safe_filename:
        safe_filename = "media"

    date_folder = time.strftime("%Y%m%d", time.gmtime())
    return f"{prefix}/{date_folder}/{uuid.uuid4().hex}-{safe_filename}"


def _build_oss_url(oss_config, object_key, query=None):
    quoted_key = urllib.parse.quote(object_key, safe="/")
    base_url = (
        f"{oss_config['scheme']}://{oss_config['bucket']}."
        f"{oss_config['endpoint_host']}/{quoted_key}"
    )
    if not query:
        return base_url

    return base_url + "?" + urllib.parse.urlencode(query)


def _build_oss_authorization_header(oss_config, method, object_key, content_type, date):
    string_to_sign = (
        f"{method}\n"
        f"\n"
        f"{content_type}\n"
        f"{date}\n"
        f"/{oss_config['bucket']}/{object_key}"
    )
    signature = _oss_signature(oss_config["access_key_secret"], string_to_sign)
    return f"OSS {oss_config['access_key_id']}:{signature}"


def _build_oss_signed_download_url(oss_config, object_key):
    expires = int(time.time()) + int(oss_config["signed_url_expires"])
    string_to_sign = f"GET\n\n\n{expires}\n/{oss_config['bucket']}/{object_key}"
    signature = _oss_signature(oss_config["access_key_secret"], string_to_sign)
    return _build_oss_url(
        oss_config,
        object_key,
        {
            "OSSAccessKeyId": oss_config["access_key_id"],
            "Expires": str(expires),
            "Signature": signature,
        },
    )


def _upload_file_to_oss(file_path, timeout=DEFAULT_UPLOAD_TIMEOUT, oss_config=None):
    normalized_path = _resolve_upload_file_path(file_path)
    oss_config = oss_config or _resolve_oss_upload_config()
    if not oss_config:
        raise ValueError("OSS upload config is not configured.")

    object_key = _build_oss_object_key(normalized_path, oss_config["prefix"])
    content_type = mimetypes.guess_type(normalized_path)[0] or "application/octet-stream"
    upload_url = _build_oss_url(oss_config, object_key)

    for attempt in range(1, TMPFILES_UPLOAD_RETRY_COUNT + 1):
        try:
            date = email.utils.formatdate(usegmt=True)
            authorization = _build_oss_authorization_header(
                oss_config,
                "PUT",
                object_key,
                content_type,
                date,
            )
            with open(normalized_path, "rb") as handle:
                response = requests.put(
                    upload_url,
                    data=handle,
                    headers={
                        "Authorization": authorization,
                        "Content-Type": content_type,
                        "Date": date,
                    },
                    timeout=float(timeout),
                )
            response.raise_for_status()
            return _build_oss_signed_download_url(oss_config, object_key)
        except requests.RequestException as exc:
            if attempt >= TMPFILES_UPLOAD_RETRY_COUNT:
                raise ConnectionError(
                    "OSS media upload failed after multiple attempts. "
                    f"Check OSS endpoint, bucket permissions, and network access: {exc}"
                ) from exc
            print(
                f"[{NODE_PREFIX}] OSS upload retry {attempt}/{TMPFILES_UPLOAD_RETRY_COUNT} "
                f"after transient error: {exc}"
            )
            time.sleep(TMPFILES_UPLOAD_RETRY_DELAY)

    raise ConnectionError("OSS media upload failed.")


def _upload_file_to_tmpfiles(file_path, timeout=DEFAULT_UPLOAD_TIMEOUT):
    normalized_path = _resolve_upload_file_path(file_path)

    file_size = os.path.getsize(normalized_path)
    if file_size > TMPFILES_MAX_SIZE_BYTES:
        raise ValueError("Local media file exceeds tmpfiles.org's 100 MB upload limit.")

    filename = os.path.basename(normalized_path)
    for attempt in range(1, TMPFILES_UPLOAD_RETRY_COUNT + 1):
        try:
            with open(normalized_path, "rb") as handle:
                response = requests.post(
                    TMPFILES_UPLOAD_API_URL,
                    files={"file": (filename, handle)},
                    timeout=float(timeout),
                )
            break
        except requests.RequestException as exc:
            if attempt >= TMPFILES_UPLOAD_RETRY_COUNT:
                raise ConnectionError(
                    "Temporary media upload failed after multiple attempts. "
                    f"tmpfiles.org may be temporarily unavailable: {exc}"
                ) from exc
            print(
                f"[{NODE_PREFIX}] tmpfiles upload retry {attempt}/{TMPFILES_UPLOAD_RETRY_COUNT} "
                f"after transient error: {exc}"
            )
            time.sleep(TMPFILES_UPLOAD_RETRY_DELAY)

    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ConnectionError(f"Temporary media upload failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("Temporary media upload returned invalid JSON.") from exc

    if payload.get("status") != "success":
        raise ValueError(f"Temporary media upload failed: {payload}")

    page_url = payload.get("data", {}).get("url")
    return _normalize_tmpfiles_download_url(page_url)


def _upload_file_to_catbox(file_path, timeout=DEFAULT_UPLOAD_TIMEOUT):
    normalized_path = _resolve_upload_file_path(file_path)

    filename = os.path.basename(normalized_path)
    for attempt in range(1, TMPFILES_UPLOAD_RETRY_COUNT + 1):
        try:
            with open(normalized_path, "rb") as handle:
                response = requests.post(
                    CATBOX_UPLOAD_API_URL,
                    data={"reqtype": "fileupload"},
                    files={"fileToUpload": (filename, handle)},
                    timeout=float(timeout),
                )
            break
        except requests.RequestException as exc:
            if attempt >= TMPFILES_UPLOAD_RETRY_COUNT:
                raise ConnectionError(
                    "Temporary media upload failed after multiple attempts. "
                    f"catbox.moe may be temporarily unavailable: {exc}"
                ) from exc
            print(
                f"[{NODE_PREFIX}] catbox upload retry {attempt}/{TMPFILES_UPLOAD_RETRY_COUNT} "
                f"after transient error: {exc}"
            )
            time.sleep(TMPFILES_UPLOAD_RETRY_DELAY)

    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ConnectionError(f"Temporary media upload failed: {exc}") from exc

    return _normalize_catbox_upload_url(response.text)


def _upload_file_to_temporary_media_host(file_path, timeout=DEFAULT_UPLOAD_TIMEOUT):
    normalized_path = _resolve_upload_file_path(file_path)
    file_size = os.path.getsize(normalized_path)
    failures = []
    uploaders = []

    try:
        oss_config = _resolve_oss_upload_config()
    except Exception as exc:
        oss_config = None
        failures.append(f"aliyun OSS: {exc}")

    if oss_config is not None:
        uploaders.append(
            (
                "aliyun OSS",
                lambda path, timeout=DEFAULT_UPLOAD_TIMEOUT, _oss_config=oss_config: _upload_file_to_oss(
                    path,
                    timeout=timeout,
                    oss_config=_oss_config,
                ),
            )
        )

    if file_size <= TMPFILES_MAX_SIZE_BYTES:
        uploaders.append(("tmpfiles.org", _upload_file_to_tmpfiles))
    else:
        failures.append("tmpfiles.org: skipped because the file exceeds the 100 MB upload limit")

    uploaders.append(("catbox.moe", _upload_file_to_catbox))

    for service_name, uploader in uploaders:
        try:
            url = uploader(normalized_path, timeout=timeout)
            if failures:
                print(f"[{NODE_PREFIX}] temporary media upload succeeded via {service_name}.")
            return url
        except Exception as exc:
            failures.append(f"{service_name}: {exc}")
            print(f"[{NODE_PREFIX}] temporary media upload via {service_name} failed: {exc}")

    raise ConnectionError(
        "Temporary media upload failed through all available upload services. "
        + " | ".join(failures)
    )


def _upload_video_reference(video):
    if video is None:
        raise ValueError("video is required.")

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
        temp_path = handle.name

    try:
        video.save_to(temp_path)
        return _upload_file_to_temporary_media_host(temp_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _upload_image_reference(image):
    if image is None:
        raise ValueError("image is required.")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        temp_path = handle.name

    try:
        first_frame = _tensor2images(image)[0]
        first_frame.save(temp_path, format="PNG")
        return _upload_file_to_temporary_media_host(temp_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _find_ffmpeg_path():
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        ffmpeg_path = get_ffmpeg_exe()
        if ffmpeg_path:
            return ffmpeg_path
    except Exception:
        pass

    ffmpeg_path = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if ffmpeg_path:
        return ffmpeg_path

    raise RuntimeError(
        "ffmpeg is required to encode reference_video_frames. Install imageio-ffmpeg or make ffmpeg available on PATH."
    )


def _resolve_reference_video_fps(reference_video_info=None):
    if isinstance(reference_video_info, dict):
        for key in ("loaded_fps", "source_fps"):
            value = reference_video_info.get(key)
            try:
                fps = float(value)
            except (TypeError, ValueError):
                continue
            if fps > 0:
                return fps
    return DEFAULT_REFERENCE_VIDEO_FPS


def _format_duration_value(seconds):
    value = float(seconds)
    if value <= 0:
        raise ValueError("duration must be greater than 0.")
    if value.is_integer():
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _resolve_motion_control_duration(
        duration,
        reference_video_input=None,
        reference_video_frames=None,
        reference_video_info=None,
):
    normalized = str(duration or "").strip() or "auto"
    if normalized != "auto":
        return normalized

    if isinstance(reference_video_info, dict):
        for key in ("loaded_duration", "source_duration"):
            value = reference_video_info.get(key)
            try:
                return _format_duration_value(value)
            except (TypeError, ValueError):
                continue

    if reference_video_input is not None and hasattr(reference_video_input, "get_duration"):
        try:
            return _format_duration_value(reference_video_input.get_duration())
        except Exception:
            pass

    if reference_video_frames is not None:
        frame_count = None
        shape = getattr(reference_video_frames, "shape", None)
        if shape and len(shape) > 0:
            try:
                frame_count = int(shape[0])
            except Exception:
                frame_count = None
        if frame_count is None:
            try:
                frame_count = len(reference_video_frames)
            except Exception:
                frame_count = None
        if frame_count and frame_count > 0:
            fps = _resolve_reference_video_fps(reference_video_info)
            return _format_duration_value(frame_count / fps)

    raise ValueError(
        "duration='auto' requires reference_video_input or reference_video_frames with usable duration metadata. "
        "Set duration explicitly when using a direct reference_video URL."
    )


def _encode_reference_video_frames_to_mp4(reference_video_frames, reference_video_info=None):
    images = _tensor2images(reference_video_frames)
    if not images:
        raise ValueError("reference_video_frames must contain at least one frame.")

    first_frame = images[0].convert("RGB")
    width, height = first_frame.size
    fps = _resolve_reference_video_fps(reference_video_info)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
        temp_path = handle.name

    ffmpeg_path = _find_ffmpeg_path()
    command = [
        ffmpeg_path,
        "-v",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{fps:.6f}",
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        temp_path,
    ]

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    try:
        for frame in images:
            rgb_frame = frame.convert("RGB")
            if rgb_frame.size != (width, height):
                raise ValueError("reference_video_frames must all have the same size.")
            process.stdin.write(rgb_frame.tobytes())
        process.stdin.close()
        stderr = process.stderr.read()
        return_code = process.wait()
    except Exception:
        process.kill()
        process.wait()
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

    if return_code != 0:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        error_message = stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"Failed to encode reference_video_frames with ffmpeg: {error_message or return_code}")

    return temp_path


def _upload_reference_video_frames(reference_video_frames, reference_video_info=None):
    temp_path = _encode_reference_video_frames_to_mp4(reference_video_frames, reference_video_info)
    try:
        return _upload_file_to_temporary_media_host(temp_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _resolve_motion_control_reference_video(
        reference_video,
        reference_video_input=None,
        reference_video_frames=None,
        reference_video_info=None,
):
    if reference_video_input is not None:
        return _upload_video_reference(reference_video_input)

    if reference_video_frames is not None:
        return _upload_reference_video_frames(reference_video_frames, reference_video_info)

    if isinstance(reference_video, str) and reference_video.strip():
        normalized = reference_video.strip()
        if _is_http_url(normalized):
            return normalized
        raise ValueError("reference_video must be an http(s) URL when provided.")

    return ""


class ImageGeneratorNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": (IMAGE_GENERATION_MODELS,),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "image": ("IMAGE",),
                "image_reference": (["None", "subject", "face"],),
                "image_fidelity": ("FLOAT", {
                    "default": 0.5,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "round": 0.01,
                    "display": "number",
                    "lazy": True
                }),
                "human_fidelity": ("FLOAT", {
                    "default": 0.45,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "round": 0.01,
                    "display": "number",
                    "lazy": True
                }),
                "image_num": ("INT", {
                    "default": 1,
                    "min": 0,
                    "max": 9,
                    "step": 1,
                    "display": "number",
                    "lazy": True
                }),
                "aspect_ratio": (EXTENDED_IMAGE_ASPECT_RATIOS,),
                "resolution": (DEFAULT_IMAGE_RESOLUTIONS,),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)

    FUNCTION = "generate"

    OUTPUT_NODE = False

    CATEGORY = NODE_CATEGORY

    def generate(self,
                 model,
                 prompt,
                 negative_prompt=None,
                 image=None,
                 image_reference="None",
                 image_fidelity=None,
                 human_fidelity=None,
                 resolution=None,
                 image_num=None,
                 aspect_ratio=None):
        has_input_image = image is not None
        capability = validate_image_generation_request(
            model_name=model,
            has_input_image=has_input_image,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            image_reference_mode=image_reference,
            image_fidelity=image_fidelity,
            human_fidelity=human_fidelity,
        )

        generator = ImageGenerator()
        generator.model_name = model
        _apply_prompt_controls(generator, capability, prompt=prompt, negative_prompt=negative_prompt)
        _set_if_present(generator, "resolution", resolution)
        _set_if_present(generator, "aspect_ratio", aspect_ratio)
        _set_if_present(generator, "n", image_num)

        if has_input_image:
            generator.image = _image_to_base64(image)

        if image_reference != 'None':
            generator.image_reference = image_reference

        if image_reference != 'None' and image_fidelity is not None:
            generator.image_fidelity = image_fidelity

        if image_reference != 'None' and human_fidelity is not None:
            generator.human_fidelity = human_fidelity

        try:
            with _runtime_client() as client:
                response = generator.run(client)
        except KLingAPIError as exc:
            _raise_with_image_model_guidance(exc, model)
        _log_final_unit_deduction(response, "image_generation")

        imgs = None
        for image_info in response.task_result.images:
            image_url = _preferred_media_url(image_info)
            img = _images2tensor(_decode_image(_fetch_image(image_url)))
            if imgs is None:
                imgs = img
            else:
                imgs = torch.cat([imgs, img], dim=0)
            print(f'KLing API output: {image_url}')

        return (imgs,)


class ImageExpanderNode:

    # TODO ?
    @classmethod
    def INPUT_TYPES(s):

        expansion_ratio_parameter = {
            "default": 0,
            "min": 0,
            "max": 2,
        }

        return {
            "required": {
                "image": ("IMAGE",),
                "up_expansion_ratio": ("FLOAT", expansion_ratio_parameter),
                "down_expansion_ratio": ("FLOAT", expansion_ratio_parameter),
                "left_expansion_ratio": ("FLOAT", expansion_ratio_parameter),
                "right_expansion_ratio": ("FLOAT", expansion_ratio_parameter),

            },
            "optional": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "image_num": ("INT", {
                    "default": 1,
                    "min": 0,
                    "max": 9,
                    "step": 1,
                    "display": "number",
                    "lazy": True
                }),
            }

        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)

    FUNCTION = "generate"

    OUTPUT_NODE = False

    CATEGORY = NODE_CATEGORY

    def generate(self,
                 image,
                 prompt=None,
                 image_num=None,
                 up_expansion_ratio=None,
                 down_expansion_ratio=None,
                 left_expansion_ratio=None,
                 right_expansion_ratio=None,
                 ):
        generator = ImageExpander()

        generator.image = _image_to_base64(image)
        generator.up_expansion_ratio = up_expansion_ratio
        generator.down_expansion_ratio = down_expansion_ratio
        generator.left_expansion_ratio = left_expansion_ratio
        generator.right_expansion_ratio = right_expansion_ratio
        generator.prompt = prompt
        generator.n = image_num
        with _runtime_client() as client:
            response = generator.run(client)

        imgs = None
        for image_info in response.task_result.images:
            img = _images2tensor(_decode_image(_fetch_image(image_info.url)))
            if imgs is None:
                imgs = img
            else:
                imgs = torch.cat([imgs, img], dim=0)

            print(f'KLing API output: {image_info.url}')

        return (imgs,)


class Image2VideoNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": (IMAGE_TO_VIDEO_MODELS,),
            },
            "optional": {
                "image": ("IMAGE",),
                "image_tail": ("IMAGE",),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "cfg_scale": ("FLOAT", {
                    "default": 0.5,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "round": 0.01,
                    "display": "number",
                    "lazy": True
                }),
                "mode": (DEFAULT_MODES,),
                "duration": (DEFAULT_VIDEO_DURATIONS,),
                "camera_control_type": (CAMERA_CONTROL_TYPES,),
                "camera_control_config": (CAMERA_CONTROL_CONFIGS,),
                "camera_control_value": ("FLOAT", {
                    "default": 0.5,
                    "min": -10.0,
                    "max": 10.0,
                    "step": 1.0,
                    "round": 1.0,
                    "display": "number",
                    "lazy": True
                }),
                "sound": (SOUND_OPTIONS,),
                "voice_preset": (VOICE_PRESET_OPTIONS, {"default": DEFAULT_VOICE_PRESET}),
                "shot_type": (SHOT_TYPES,),
                "image_list": ("IMAGE",),
                "element_list": (ELEMENT_LIST_TYPE,),
                "reference_video": ("STRING", {"multiline": False, "default": ""}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("url", "video_id")

    FUNCTION = "generate"

    OUTPUT_NODE = False

    CATEGORY = NODE_CATEGORY

    def generate(self,
                 model,
                 image=None,
                 image_tail=None,
                 prompt=None,
                 negative_prompt=None,
                 cfg_scale=None,
                 mode=None,
                 duration=None,
                 camera_control_type=None,
                 camera_control_config=None,
                 camera_control_value=None,
                 sound="off",
                 voice_preset=DEFAULT_VOICE_PRESET,
                 shot_type="single",
                 image_list=None,
                 element_list=None,
                 reference_video=""):
        capability = get_video_capability(model)
        mode = _normalize_requested_mode(model, capability, mode)
        normalized_element_list = _normalize_element_list(element_list)
        parsed_voice_list = _build_voice_list_from_preset(voice_preset)
        encoded_image_list = _image_batch_to_base64_list(image_list)
        has_reference_video = isinstance(reference_video, str) and bool(reference_video.strip())
        has_camera_control = camera_control_type not in (None, "None")

        if image is None and not has_reference_video and not encoded_image_list and not normalized_element_list:
            raise ValueError("Provide image, image_list, element_list, or reference_video for Image2Video.")

        if image_tail is not None and image is None:
            raise ValueError("image_tail requires image.")

        capability = validate_video_generation_request(
            task_name="image2video",
            model_name=model,
            mode=mode,
            duration=duration,
            shot_type=shot_type,
            has_image_tail=image_tail is not None,
            has_image_list=bool(encoded_image_list),
            has_element_list=bool(normalized_element_list),
            has_reference_video=has_reference_video,
            has_sound=sound == "on",
            has_voice_list=bool(parsed_voice_list),
            has_camera_control=has_camera_control,
            element_types=_collect_element_types(normalized_element_list),
        )

        generator = Image2Video()
        generator.model_name = model
        _apply_prompt_controls(generator, capability, prompt=prompt, negative_prompt=negative_prompt, cfg_scale=cfg_scale)
        _set_if_present(generator, "mode", mode)
        _set_if_present(generator, "duration", duration)

        if image is not None:
            generator.image = _image_to_base64(image)

        if image_tail is not None:
            generator.image_tail = _image_to_base64(image_tail)

        if has_camera_control:
            generator.camera_control = _build_camera_control(
                camera_control_type,
                camera_control_config,
                camera_control_value,
            )

        if sound == "on":
            generator.sound = sound

        if parsed_voice_list:
            generator.voice_list = parsed_voice_list

        if shot_type != "single":
            generator.shot_type = shot_type

        if encoded_image_list:
            generator.image_list = encoded_image_list

        if normalized_element_list:
            generator.element_list = normalized_element_list

        if has_reference_video:
            generator.reference_video = reference_video.strip()

        try:
            with _runtime_client() as client:
                response = generator.run(client)
        except KLingAPIError as exc:
            _raise_with_model_guidance(exc, model)
        _log_final_unit_deduction(response, "image2video")

        for video_info in response.task_result.videos:
            video_url = _preferred_media_url(video_info)
            print(f'KLing API output video id: {video_info.id}, url: {video_url}')
            return (video_url, video_info.id)

        return ('', '')


class Text2VideoNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": (TEXT_TO_VIDEO_MODELS,),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "cfg_scale": ("FLOAT", {
                    "default": 0.5,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "round": 0.01,
                    "display": "number",
                    "lazy": True
                }),
                "mode": (DEFAULT_MODES,),
                "aspect_ratio": (DEFAULT_VIDEO_ASPECT_RATIOS,),
                "duration": (DEFAULT_VIDEO_DURATIONS,),
                "camera_control_type": (CAMERA_CONTROL_TYPES,),
                "camera_control_config": (CAMERA_CONTROL_CONFIGS,),
                "camera_control_value": ("FLOAT", {
                    "default": 0.5,
                    "min": -10.0,
                    "max": 10.0,
                    "step": 1.0,
                    "round": 1.0,
                    "display": "number",
                    "lazy": True
                }),
                "sound": (SOUND_OPTIONS,),
                "voice_preset": (VOICE_PRESET_OPTIONS, {"default": DEFAULT_VOICE_PRESET}),
                "shot_type": (SHOT_TYPES,),
                "image_list": ("IMAGE",),
                "element_list": (ELEMENT_LIST_TYPE,),
                "reference_video": ("STRING", {"multiline": False, "default": ""}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("url", "video_id")

    FUNCTION = "generate"

    OUTPUT_NODE = False

    CATEGORY = NODE_CATEGORY

    def generate(self,
                 model,
                 prompt,
                 negative_prompt=None,
                 cfg_scale=None,
                 mode=None,
                 aspect_ratio=None,
                 duration=None,
                 camera_control_type=None,
                 camera_control_config=None,
                 camera_control_value=None,
                 sound="off",
                 voice_preset=DEFAULT_VOICE_PRESET,
                 shot_type="single",
                 image_list=None,
                 element_list=None,
                 reference_video=""):
        capability = get_video_capability(model)
        mode = _normalize_requested_mode(model, capability, mode)
        normalized_element_list = _normalize_element_list(element_list)
        parsed_voice_list = _build_voice_list_from_preset(voice_preset)
        encoded_image_list = _image_batch_to_base64_list(image_list)
        has_reference_video = isinstance(reference_video, str) and bool(reference_video.strip())
        has_camera_control = camera_control_type not in (None, "None")

        capability = validate_video_generation_request(
            task_name="text2video",
            model_name=model,
            mode=mode,
            duration=duration,
            shot_type=shot_type,
            has_image_tail=False,
            has_image_list=bool(encoded_image_list),
            has_element_list=bool(normalized_element_list),
            has_reference_video=has_reference_video,
            has_sound=sound == "on",
            has_voice_list=bool(parsed_voice_list),
            has_camera_control=has_camera_control,
            element_types=_collect_element_types(normalized_element_list),
        )

        generator = Text2Video()
        generator.model_name = model
        _apply_prompt_controls(generator, capability, prompt=prompt, negative_prompt=negative_prompt, cfg_scale=cfg_scale)
        _set_if_present(generator, "mode", mode)
        _set_if_present(generator, "aspect_ratio", aspect_ratio)
        _set_if_present(generator, "duration", duration)

        if has_camera_control:
            generator.camera_control = _build_camera_control(
                camera_control_type,
                camera_control_config,
                camera_control_value,
            )

        if sound == "on":
            generator.sound = sound

        if parsed_voice_list:
            generator.voice_list = parsed_voice_list

        if shot_type != "single":
            generator.shot_type = shot_type

        if encoded_image_list:
            generator.image_list = encoded_image_list

        if normalized_element_list:
            generator.element_list = normalized_element_list

        if has_reference_video:
            generator.reference_video = reference_video.strip()

        try:
            with _runtime_client() as client:
                response = generator.run(client)
        except KLingAPIError as exc:
            _raise_with_model_guidance(exc, model)
        _log_final_unit_deduction(response, "text2video")

        for video_info in response.task_result.videos:
            video_url = _preferred_media_url(video_info)
            print(f'KLing API output video id: {video_info.id}, url: {video_url}')
            return (video_url, video_info.id)

        return ('', '')


class KolorsVirtualTryOnNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model_name": (["kolors-virtual-try-on-v1", "kolors-virtual-try-on-v1-5"],),
                "human_image": ("IMAGE",),
                "cloth_image": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)

    FUNCTION = "generate"

    OUTPUT_NODE = False

    CATEGORY = NODE_CATEGORY

    def generate(self,
                 model_name,
                 human_image,
                 cloth_image=None):
        generator = KolorsVurtualTryOn()
        generator.model_name = model_name
        generator.human_image = _image_to_base64(human_image)
        generator.cloth_image = _image_to_base64(cloth_image)

        with _runtime_client() as client:
            response = generator.run(client)

        for image_info in response.task_result.images:
            img = _images2tensor(_decode_image(_fetch_image(image_info.url)))
            print(f'KLing API output: {image_info.url}')
            return (img,)


class PreviewVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_url": ("STRING", {"forceInput": True}),
            }
        }

    OUTPUT_NODE = True
    FUNCTION = "run"
    CATEGORY = NODE_CATEGORY

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("file_path",)

    def run(self, video_url, filename_prefix=DEFAULT_VIDEO_FILENAME_PREFIX, save_output=True):
        if not save_output:
            return {"ui": {"video_url": [video_url]}, "result": ('',)}

        output_dir = folder_paths.get_output_directory()
        (
            full_output_folder,
            filename,
            counter,
            subfolder,
            _,
        ) = folder_paths.get_save_image_path(filename_prefix, output_dir)
        file = f"{filename}_{counter:05}_.mp4"
        file_path = os.path.join(full_output_folder, file)
        preview_url = _build_local_media_view_url(file, subfolder, "output")

        if type(video_url) == list:
            video_url = video_url[0]
        video_url = str(video_url or "").strip()
        if not video_url:
            raise ValueError(
                "PreviewVideo received an empty video_url. "
                "The upstream node finished without a downloadable video URL."
            )
        with open(file_path, "wb") as handle:
            handle.write(_fetch_image(video_url))
        try:
            _register_output_asset(file_path)
        except Exception:
            pass

        return {
            "ui": {
                "images": [_saved_result(file, subfolder, "output")],
                "video_url": [preview_url],
                "animated": (True,),
            },
            "result": (file_path,),
        }


class PreviewAudio(LoadAudio):

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_url": ("STRING", {
                    "forceInput": True,
                    "default": ""
                }),
                "filename_prefix": ("STRING", {
                    "default": DEFAULT_FILENAME_PREFIX
                }),
                "save_output": ("BOOLEAN", {
                    "default": True
                }),
            }
        }

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audio", "file_path")
    FUNCTION = "run"
    CATEGORY = NODE_CATEGORY
    OUTPUT_NODE = True

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    def run(self, audio_url, filename_prefix, save_output):

        try:
            if not save_output:
                return {
                    "ui": {"audio_url": [audio_url]},
                    "result": (None, '')
                }

            output_directory = folder_paths.get_output_directory()
            (
                full_output_folder,
                filename,
                counter,
                subfolder,
                _,
            ) = folder_paths.get_save_image_path(filename_prefix, output_directory)

            saved_file_path = _load_audio_from_url(
                audio_url=audio_url,
                save_directory=full_output_folder,
                filename_prefix=f"{filename}_{counter:05}"
            )

            audio_result = super().load(saved_file_path)

            audio_data = audio_result[0]

            return {
                "ui": {
                    "audio": [_saved_result(Path(saved_file_path).name, subfolder, "output")]
                },
                "result": (audio_data, saved_file_path)
            }

        except Exception as e:
            error_msg = f"[PreviewAudio] Error: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)


class VideoExtendNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_id": ("STRING", {"multiline": False, "default": ""}),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
            }
        }

    OUTPUT_NODE = True
    FUNCTION = "run"
    CATEGORY = NODE_CATEGORY

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("url", "video_id")

    def run(self, video_id, prompt):
        generator = VideoExtend()
        generator.video_id = video_id
        generator.prompt = prompt

        with _runtime_client() as client:
            response = generator.run(client)

        for video_info in response.task_result.videos:
            print(f'KLing API output video id: {video_info.id}, url: {video_info.url}')
            return (video_info.url, video_info.id)

        return ('', '')


class LipSyncTextInputNode:
    audio_types = LIPSYNC_AUDIO_TYPES

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": ""}),
                "voice_id": (list(LipSyncTextInputNode.audio_types.keys()), {"multiline": False, "default": ""}),
                "voice_language": (["zh", "en"], {"default": "zh"}),
                "voice_speed": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.8,
                    "max": 2.0,
                    "step": 0.1,
                    "round": 0.01,
                    "display": "number",
                    "lazy": True
                })
            }
        }

    OUTPUT_NODE = True
    FUNCTION = "run"
    CATEGORY = NODE_CATEGORY

    RETURN_TYPES = (LIPSYNC_INPUT_TYPE,)
    RETURN_NAMES = ("input",)

    def run(self, text, voice_id, voice_language, voice_speed):
        input = LipSyncInput()
        input.mode = "text2video"
        input.text = text
        if voice_id in LipSyncTextInputNode.audio_types:
            input.voice_id = LipSyncTextInputNode.audio_types[voice_id]
        else:
            input.voice_id = voice_id

        input.voice_language = voice_language
        input.voice_speed = voice_speed

        return (input,)


class LipSyncAudioInputNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "audio_file": ("STRING", {"multiline": False, "default": ""}),
                "audio_url": ("STRING", {"multiline": False, "default": ""}),
            },
        }

    OUTPUT_NODE = True
    FUNCTION = "run"
    CATEGORY = NODE_CATEGORY

    RETURN_TYPES = (LIPSYNC_INPUT_TYPE,)
    RETURN_NAMES = ("input",)

    def run(self, audio_file, audio_url):
        input = LipSyncInput()
        input.mode = "audio2video"
        if audio_file is not None and len(audio_file) > 0:
            input.audio_type = "file"
            if os.path.exists(audio_file):
                with open(audio_file, 'rb') as file:
                    file_data = file.read()
                    input.audio_file = base64.b64encode(file_data).decode('utf-8')
            else:
                raise Exception(f"Audio file not found: {audio_file}")

        if audio_url is not None and len(audio_url) > 0:
            input.audio_type = "url"
            input.audio_url = audio_url

        return (input,)


class LipSyncNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input": (LIPSYNC_INPUT_TYPE,),
                "face_id": ("STRING", {"multiline": False, "default": ""})
            },
            "optional": {
                "video_id": ("STRING", {"multiline": False, "default": ""}),
                "video_url": ("STRING", {"multiline": False, "default": ""}),
            }
        }

    OUTPUT_NODE = True
    FUNCTION = "run"
    CATEGORY = NODE_CATEGORY

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("url", "video_id")

    def run(self, input, face_id, video_id=None, video_url=None):
        if not video_id and not video_url:
            raise Exception("Please input video_id or video_url.")

        generator = LipSync()
        input.video_id = video_id
        input.video_url = video_url
        if face_id:
            input.face_id = face_id
        generator.input = input

        with _runtime_client() as client:
            response = generator.run(client)

        for video_info in response.task_result.videos:
            print(f'KLing API output video id: {video_info.id}, url: {video_info.url}')
            return (video_info.url, video_info.id)

        return ('', '')


class EffectNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "effect_scene": (
                    ["baseball", "inner_voice", "a_list_look", "memory_alive", "trampoline", "trampoline_night",
                     "pucker_up", "guess_what", "feed_mooncake", "rampage_ape", "flyer", "dishwasher",
                     "pet_chinese_opera", "magic_fireball", "gallery_ring", "pet_moto_rider", "muscle_pet",
                     "squeeze_scream",
                     "pet_delivery", "running_man", "disappear", "mythic_style", "steampunk", "c4d_cartoon",
                     "3d_cartoon_1",
                     "3d_cartoon_2", "eagle_snatch", "hug_from_past", "firework", 'media_interview', "pet_lion",
                     "pet_chef",
                     "santa_gifts", "santa_hug", "girlfriend", "boyfriend", "heart_gesture_1", "pet_wizard",
                     "smoke_smoke", "thumbs_up",
                     "instant_kid", "dollar_rain", "cry_cry", "building_collapse", "gun_shot", "mushroom", "double_gun",
                     "pet_warrior",
                     "lightning_power", "jesus_hug", "shark_alert", "long_hair", "lie_flat", "polar_bear_hug",
                     "brown_bear_hug",
                     "jazz_jazz", "office_escape_plow", "fly_fly", "watermelon_bomb", "pet_dance", "boss_coming",
                     "wool_curly",
                     "pet_bee", "marry_me", "swing_swing", "day_to_night", "piggy_morph", "wig_out", "car_explosion",
                     "ski_ski",
                     "tiger_hug", "siblings", "construction_worker", "let’s_ride", "snatched", "magic_broom",
                     "felt_felt", "jumpdrop", "celebration", "splashsplash", "surfsurf", "fairy_wing", "angel_wing",
                     "dark_wing", "skateskate", "plushcut", "jelly_press", "jelly_slice", "jelly_squish",
                     "jelly_jiggle",
                     "pixelpixel", "yearbook", "instant_film", "anime_figure", "rocketrocket", "bloombloom",
                     "dizzydizzy", "fuzzyfuzzy",
                     "squish", "expansion", "hug", "kiss", "heart_gesture", "fight"
                     ],),
                "model_name": (["kling-v1", "kling-v1-5", "kling-v1-6"],),
                "mode": (["std", "pro"],),
                "duration": (["5", "10"],),
                "image0": ("IMAGE",),
            },
            "optional": {
                "image1": ("IMAGE",)
            }
        }

    OUTPUT_NODE = True
    FUNCTION = "run"
    CATEGORY = NODE_CATEGORY

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("url", "video_id")

    def run(self, effect_scene, model_name, mode, duration, image0, image1=None):

        generator = Effects()
        generator.effect_scene = effect_scene
        generator.input = EffectInput()
        if effect_scene in ["hug", "kiss", "heart_gesture", "fight"]:
            generator.input.model_name = 'kling-v1-6' if effect_scene == 'fight' else model_name
            generator.input.mode = mode
            generator.input.duration = duration
            if image1 == None or image0 == None:
                raise Exception("This effect needs two images.")
            generator.input.images = [_image_to_base64(image0), _image_to_base64(image1)]
        else:
            generator.input.mode = mode
            generator.input.duration = duration
            if image1 != None and image0 != None:
                raise Exception("This effect needs one image.")
            generator.input.image = _image_to_base64(image0) if image1 == None else _image_to_base64(image1)

        with _runtime_client() as client:
            response = generator.run(client)

        for video_info in response.task_result.videos:
            print(f'KLing API output video id: {video_info.id}, url: {video_info.url}')
            return (video_info.url, video_info.id)

        return ('', '')


class Video2AudioNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "video_id": ("STRING", {"multiline": False, "default": ""}),
                "video_url": ("STRING", {"multiline": False, "default": ""}),
            },
            "optional": {
                "sound_effect_prompt": ("STRING", {"multiline": True, "default": ""}),
                "bgm_prompt": ("STRING", {"multiline": True, "default": ""}),
                "asmr_mode": ("BOOLEAN", {"multiline": False, "default": False}),

            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("videos_id", "videos_url", "audio_id", "audio_url_mp3")

    FUNCTION = "generate"

    OUTPUT_NODE = False

    CATEGORY = NODE_CATEGORY

    def generate(self,
                 video_id,
                 video_url,
                 sound_effect_prompt=None,
                 bgm_prompt=None,
                 asmr_mode=False,
                 ):

        generator = Video2Audio()
        generator.video_id = video_id
        generator.video_url = video_url

        if not video_id and not video_url:
            raise Exception("Please input video_id or video_url")

        if video_id and video_url:
            raise Exception("Please input one of video_id or video_url")

        generator.sound_effect_prompt = sound_effect_prompt
        generator.bgm_prompt = bgm_prompt
        generator.asmr_mode = asmr_mode

        with _runtime_client() as client:
            response = generator.run(client)

        audio_info = response.task_result.audios[0]
        return (
            getattr(audio_info, "video_id", ""),
            getattr(audio_info, "video_url", ""),
            getattr(audio_info, "audio_id", ""),
            getattr(audio_info, "url_mp3", ""),
        )


class MultiImagesToVideoNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": (MULTI_IMAGE_TO_VIDEO_MODELS,),
                "image_list": ("IMAGE",),
            },
            "optional": {
                "image_tail": ("IMAGE",),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "mode": (DEFAULT_MODES,),
                "duration": (DEFAULT_VIDEO_DURATIONS,),
                "aspect_ratio": (EXTENDED_IMAGE_ASPECT_RATIOS[:-1],),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("url", "video_id")
    FUNCTION = "generate"
    OUTPUT_NODE = False
    CATEGORY = NODE_CATEGORY

    def generate(
            self,
            model,
            image_list,
            image_tail=None,
            prompt="",
            negative_prompt="",
            mode="std",
            duration="5",
            aspect_ratio="16:9",
    ):
        capability = get_video_capability(model)
        mode = _normalize_requested_mode(model, capability, mode)
        encoded_image_list = _image_batch_to_base64_list(image_list)
        if not encoded_image_list:
            raise ValueError("image_list must contain at least one image.")
        if len(encoded_image_list) < 2:
            raise ValueError("MultiImagesToVideo requires at least two images.")

        capability = validate_video_generation_request(
            task_name="multi_image2video",
            model_name=model,
            mode=mode,
            duration=duration,
            shot_type="single",
            has_image_tail=image_tail is not None,
            has_image_list=True,
            has_element_list=False,
            has_reference_video=False,
            has_sound=False,
            has_voice_list=False,
            has_camera_control=False,
        )

        generator = MultiImages2Video()
        generator.model_name = model
        generator.image = encoded_image_list[0]
        generator.image_list = encoded_image_list[1:]
        _apply_prompt_controls(generator, capability, prompt=prompt, negative_prompt=negative_prompt)
        _set_if_present(generator, "mode", mode)
        _set_if_present(generator, "duration", duration)
        _set_if_present(generator, "aspect_ratio", aspect_ratio)
        if image_tail is not None:
            generator.image_tail = _image_to_base64(image_tail)

        try:
            with _runtime_client() as client:
                response = generator.run(client)
        except KLingAPIError as exc:
            _raise_with_model_guidance(exc, model)
        _log_final_unit_deduction(response, "multi_image2video")

        for video_info in response.task_result.videos:
            video_url = _preferred_media_url(video_info)
            print(f'KLing API output video id: {video_info.id}, url: {video_url}')
            return (video_url, video_info.id)

        return ("", "")


class AdvancedCustomElementCreateNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "element_type": (["image_subject", "multi_image_subject", "video_character"],),
                "element_name": ("STRING", {"multiline": False, "default": ""}),
                "element_description": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "image": ("IMAGE",),
                "image_list": ("IMAGE",),
                "video_url": ("STRING", {"multiline": False, "default": ""}),
                "element_voice_id": ("STRING", {"multiline": False, "default": ""}),
                "extra_payload_json": ("STRING", {"multiline": True, "default": ""}),
            }
        }

    RETURN_TYPES = (ELEMENT_TYPE, "STRING", "STRING")
    RETURN_NAMES = ("element", "element_id", "element_json")
    FUNCTION = "create"
    OUTPUT_NODE = False
    CATEGORY = NODE_CATEGORY

    def create(
            self,
            element_type,
            element_name="",
            element_description="",
            image=None,
            image_list=None,
            video_url="",
            element_voice_id="",
            extra_payload_json="",
    ):
        generator = AdvancedCustomElements()
        element_name = (element_name or "").strip()
        element_description = (element_description or "").strip()

        generator.type = element_type
        generator.element_type = element_type
        generator.elementType = element_type

        # Keep the newer reference-style payload too for accounts using the upgraded schema.
        if element_type in ("image_subject", "multi_image_subject"):
            generator.reference_type = "image_refer"
        else:  # video_character
            generator.reference_type = "video_refer"

        merged_image_list = []
        if image is not None:
            merged_image_list.extend(_image_batch_to_base64_list(image))
        if image_list is not None:
            merged_image_list.extend(_image_batch_to_base64_list(image_list))

        if element_type in ("image_subject", "multi_image_subject"):
            # Kling's advanced element API requires one frontal image plus 1-3
            # additional reference images of the same subject. Background-only
            # or scene images do not satisfy this constraint.
            if len(merged_image_list) < 2:
                raise ValueError(
                    "Advanced custom elements require 1 frontal portrait in `image` plus 1-3 additional "
                    "reference photos of the same subject in `image_list`. "
                    "Background or scene images do not count as subject reference images."
                )
            if len(merged_image_list) > 4:
                raise ValueError(
                    "Advanced custom elements support at most 4 subject images total: "
                    "1 frontal image plus 1-3 additional reference images."
                )

        if element_type == "image_subject":
            element_image_list_payload = {
                "frontal_image": merged_image_list[0],
                "refer_images": [{"image_url": image_b64} for image_b64 in merged_image_list[1:]],
            }
            generator.image = merged_image_list[0]
            generator.image_list = merged_image_list
            generator.imageList = merged_image_list
            generator.element_image_list = element_image_list_payload
            generator.elementImageList = json.dumps(element_image_list_payload, ensure_ascii=False)
            generator.frontal_image = merged_image_list[0]
            generator.refer_images = merged_image_list[1:]
        elif element_type == "multi_image_subject":
            element_image_list_payload = {
                "frontal_image": merged_image_list[0],
                "refer_images": [{"image_url": image_b64} for image_b64 in merged_image_list[1:]],
            }
            generator.image = merged_image_list[0]
            generator.image_list = merged_image_list
            generator.imageList = merged_image_list
            generator.element_image_list = element_image_list_payload
            generator.elementImageList = json.dumps(element_image_list_payload, ensure_ascii=False)
            generator.frontal_image = merged_image_list[0]
            generator.refer_images = merged_image_list[1:]
        elif element_type == "video_character":
            if not video_url.strip():
                raise ValueError("video_character requires video_url.")
            element_video_list_payload = {
                "refer_videos": [{"video_url": video_url.strip()}],
            }
            generator.video_url = video_url.strip()
            generator.videoUrl = video_url.strip()
            generator.element_video_list = [video_url.strip()]
            generator.elementVideoList = json.dumps(element_video_list_payload, ensure_ascii=False)

        if element_voice_id.strip():
            generator.element_voice_id = element_voice_id.strip()
            generator.elementVoiceId = element_voice_id.strip()
            generator.voice_id = element_voice_id.strip()

        extra_payload = _parse_json_input(extra_payload_json, "extra_payload_json")
        if extra_payload:
            if not isinstance(extra_payload, dict):
                raise ValueError("extra_payload_json must decode to a JSON object.")
            for key, value in extra_payload.items():
                setattr(generator, key, value)

        if not element_description:
            element_description = str(
                getattr(generator, "description", "")
                or getattr(generator, "element_description", "")
                or getattr(generator, "elementDescription", "")
                or ""
            ).strip()

        if not element_description:
            raise ValueError("element_description is required for advanced element creation.")
        if len(element_description) > 100:
            raise ValueError(
                "element_description must be 100 characters or fewer for advanced element creation. "
                "This describes the reusable subject itself and is unrelated to the Image2Video voice mode."
            )

        if not element_name:
            element_name = str(
                getattr(generator, "name", "")
                or getattr(generator, "element_name", "")
                or getattr(generator, "elementName", "")
                or ""
            ).strip()

        if not element_name:
            raise ValueError("element_name is required for advanced element creation.")
        if len(element_name) > 20:
            raise ValueError("element_name must be 20 characters or fewer for advanced element creation.")

        generator.name = element_name
        generator.element_name = element_name
        generator.elementName = element_name
        generator.description = element_description
        generator.element_description = element_description
        generator.elementDescription = element_description

        with _runtime_client() as client:
            response = generator.run(client)
        _log_final_unit_deduction(response, "advanced_custom_element_create")

        elements = _extract_elements_from_response(response)
        if not elements:
            payload = {"task_id": getattr(response, "task_id", None)}
            return (
                payload,
                "",
                json.dumps(payload, ensure_ascii=False),
            )

        element_payload = _element_result_to_payload(elements[0])
        element_id = element_payload.get("element_id") or element_payload.get("id") or ""
        return (
            element_payload,
            element_id,
            json.dumps(element_payload, ensure_ascii=False),
        )


class AdvancedCustomElementQueryNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "query_mode": (["task_id", "element_id"],),
                "identifier": ("STRING", {"multiline": False, "default": ""}),
            }
        }

    RETURN_TYPES = (ELEMENT_TYPE, "STRING", "STRING")
    RETURN_NAMES = ("element", "element_id", "element_json")
    FUNCTION = "query"
    OUTPUT_NODE = False
    CATEGORY = NODE_CATEGORY

    def query(self, query_mode, identifier):
        identifier = identifier.strip()
        if not identifier:
            raise ValueError("identifier is required.")

        candidate_paths = []
        if query_mode == "task_id":
            candidate_paths.append(f"/v1/general/advanced-custom-elements/{identifier}")
        else:
            candidate_paths.extend([
                f"/v1/general/advanced-custom-elements/elements/{identifier}",
                f"/v1/general/advanced-custom-elements/{identifier}",
            ])

        last_error = None
        response = None
        with _runtime_client() as client:
            for path in candidate_paths:
                try:
                    response = client.request("GET", path)
                    break
                except Exception as exc:
                    last_error = exc

        if response is None:
            raise last_error

        data = response.get("data", {})
        elements = _extract_elements_from_response(data)
        if not elements and query_mode == "element_id":
            elements = [data]

        if not elements:
            payload = data if isinstance(data, dict) else {"identifier": identifier}
            return (
                payload,
                payload.get("element_id", identifier) if isinstance(payload, dict) else identifier,
                json.dumps(payload, ensure_ascii=False),
            )

        element_payload = _element_result_to_payload(elements[0])
        element_id = element_payload.get("element_id") or element_payload.get("id") or identifier
        return (
            element_payload,
            element_id,
            json.dumps(element_payload, ensure_ascii=False),
        )


class ElementListBuilderNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "element_1": (ELEMENT_TYPE,),
            },
            "optional": {
                "element_2": (ELEMENT_TYPE,),
                "element_3": (ELEMENT_TYPE,),
                "element_4": (ELEMENT_TYPE,),
                "extra_element_ids": ("STRING", {"multiline": True, "default": ""}),
            }
        }

    RETURN_TYPES = (ELEMENT_LIST_TYPE, "STRING")
    RETURN_NAMES = ("element_list", "element_list_json")
    FUNCTION = "build"
    OUTPUT_NODE = False
    CATEGORY = NODE_CATEGORY

    def build(self, element_1, element_2=None, element_3=None, element_4=None, extra_element_ids=""):
        element_refs = []
        for element in (element_1, element_2, element_3, element_4):
            if element is not None:
                element_refs.append(_normalize_element_reference(element))

        for raw_line in (extra_element_ids or "").replace(",", "\n").splitlines():
            identifier = raw_line.strip()
            if identifier:
                element_refs.append({"element_id": identifier})

        normalized = _normalize_element_list(element_refs)
        if not normalized:
            raise ValueError("At least one element is required.")

        return (
            normalized,
            json.dumps(normalized, ensure_ascii=False),
        )


class MotionControlNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_name": (MOTION_CONTROL_MODELS, {"default": "kling-v2-6"}),
                "reference_image": ("IMAGE",),
            },
            "optional": {
                "reference_video": ("STRING", {"multiline": False, "default": ""}),
                "reference_video_input": ("VIDEO",),
                "reference_video_frames": ("IMAGE",),
                "reference_video_info": ("VHS_VIDEOINFO",),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "mode": (DEFAULT_MODES,),
                "duration": (MOTION_CONTROL_DURATIONS, {"default": "auto"}),
                "character_orientation": (["video", "image"], {"default": "video"}),
                "keep_original_sound": ("BOOLEAN", {"default": True}),
                "element_list": (ELEMENT_LIST_TYPE,),
                "extra_payload_json": ("STRING", {"multiline": True, "default": ""}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("url", "video_id")
    FUNCTION = "generate"
    OUTPUT_NODE = False
    CATEGORY = NODE_CATEGORY

    def generate(
            self,
            model_name,
            reference_image,
            reference_video="",
            prompt="",
            negative_prompt="",
            mode="std",
            duration="auto",
            character_orientation="video",
            keep_original_sound=True,
            element_list=None,
            extra_payload_json="",
            reference_video_input=None,
            reference_video_frames=None,
            reference_video_info=None,
    ):
        model_name = (model_name or "kling-v2-6").strip() or "kling-v2-6"
        reference_video = _resolve_motion_control_reference_video(
            reference_video,
            reference_video_input=reference_video_input,
            reference_video_frames=reference_video_frames,
            reference_video_info=reference_video_info,
        )
        if not reference_video:
            raise ValueError(
                "reference_video, reference_video_input, or reference_video_frames is required for motion control."
            )
        duration = _resolve_motion_control_duration(
            duration,
            reference_video_input=reference_video_input,
            reference_video_frames=reference_video_frames,
            reference_video_info=reference_video_info,
        )

        normalized_element_list = _normalize_element_list(element_list)
        extra_payload = _parse_json_input(extra_payload_json, "extra_payload_json")
        if extra_payload and not isinstance(extra_payload, dict):
            raise ValueError("extra_payload_json must decode to a JSON object.")

        generator = MotionControl()
        generator.model_name = model_name
        generator.prompt = prompt
        generator.negative_prompt = negative_prompt
        generator.mode = mode
        generator.duration = duration
        generator.image_url = _upload_image_reference(reference_image)
        generator.video_url = reference_video
        generator.character_orientation = character_orientation
        generator.keep_original_sound = "yes" if keep_original_sound else "no"

        if normalized_element_list:
            generator.element_list = normalized_element_list

        for key, value in (extra_payload or {}).items():
            setattr(generator, key, value)

        with _runtime_client() as client:
            response = generator.run(client)
        _log_final_unit_deduction(response, "motion_control")
        video_url, video_id = _extract_first_video_result(response, "motion_control")
        print(f'KLing API output video id: {video_id}, url: {video_url}')
        return (video_url, video_id)


class TextToAudioNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "duration": ("FLOAT", {
                    "default": 3.0,
                    "min": 3.0,
                    "max": 10.0,
                    "step": 0.1,
                    "display": "number",
                },),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("id", "url")

    FUNCTION = "generate"

    OUTPUT_NODE = True

    CATEGORY = NODE_CATEGORY

    def generate(self,
                 prompt,
                 duration,
                 ):
        generator = Text2Audio()

        generator.prompt = prompt
        generator.duration = duration
        with _runtime_client() as client:
            response = generator.run(client)

        url_mp3 = getattr(response.task_result.audios[0], 'url_mp3', None)
        if not isinstance(url_mp3, str) or not url_mp3.strip():
            raise Exception(f"url_mp3 无效，当前值为：{url_mp3}")

        audio_id = getattr(response.task_result.audios[0], 'audio_id', None)
        print(f"成功提取：audio_id={audio_id}, url_mp3={url_mp3}")

        return (audio_id, url_mp3)
