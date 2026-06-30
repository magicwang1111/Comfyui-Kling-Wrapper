import base64
import os
from pathlib import Path

from py.api import (
    AdvancedLipSync,
    AdvancedCustomElements,
    Avatar,
    Client,
    CustomVoiceCreate,
    FaceIdentify,
    Image2Video,
    ImageGenerator,
    MotionControl,
    MultiImages2Video,
    TTS,
    Text2Video,
)


def image_to_base64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("utf-8")


def build_client(in_china: bool = True) -> Client:
    access_key = os.environ["KLING_ACCESS_KEY"]
    secret_key = os.environ["KLING_SECRET_KEY"]
    return Client(access_key, secret_key, in_china=in_china, timeout=30, poll_interval=2.0)


def example_image_generation(client: Client):
    task = ImageGenerator()
    task.model_name = "kling-v3"
    task.prompt = "A cinematic editorial portrait with elegant framing and realistic skin texture."
    task.aspect_ratio = "16:9"
    task.resolution = "1k"
    return task.run(client)


def example_text2video_v3(client: Client):
    task = Text2Video()
    task.model_name = "kling-v3"
    task.prompt = "A traveler walks through an old alley at dusk with cinematic multi-shot storytelling."
    task.mode = "pro"
    task.aspect_ratio = "16:9"
    task.duration = "5"
    task.shot_type = "intelligence"
    return task.run(client)


def example_text2video_v26_sound(client: Client):
    task = Text2Video()
    task.model_name = "kling-v2-6"
    task.prompt = "A presenter speaks directly to camera in a clean studio."
    task.mode = "pro"
    task.aspect_ratio = "16:9"
    task.duration = "5"
    task.sound = "on"
    task.voice_list = [{"voice_id": "reader_en_m-v1"}]
    return task.run(client)


def example_create_advanced_element(client: Client, frontal_image_url: str, reference_image_urls: list[str]):
    if not 1 <= len(reference_image_urls) <= 3:
        raise ValueError("Provide 1-3 additional reference image URLs for the same subject.")
    task = AdvancedCustomElements()
    task.element_name = "demo_subject"
    task.element_description = "A clear portrait of the subject with consistent identity traits for reuse in video generation."
    task.reference_type = "image_refer"
    task.element_image_list = {
        "frontal_image": frontal_image_url,
        "refer_images": [{"image_url": url} for url in reference_image_urls],
    }
    return task.run(client)


def example_image2video_with_element(client: Client, image_path: str, element_id: str):
    task = Image2Video()
    task.model_name = "kling-v3"
    task.image = image_to_base64(image_path)
    task.prompt = "Keep the same subject identity while the camera slowly pushes in."
    task.mode = "pro"
    task.duration = "5"
    task.element_list = [{"element_id": element_id}]
    return task.run(client)


def example_multi_images_to_video(client: Client, image_paths: list[str]):
    if len(image_paths) < 2:
        raise ValueError("Provide at least two image paths.")
    task = MultiImages2Video()
    task.model_name = "kling-v3"
    encoded = [image_to_base64(path) for path in image_paths]
    task.image = encoded[0]
    task.image_list = encoded[1:]
    task.prompt = "Maintain the same identity across the shot with natural motion."
    task.mode = "pro"
    task.duration = "5"
    task.aspect_ratio = "16:9"
    return task.run(client)


def example_motion_control(client: Client, image_path: str, reference_video_url: str):
    task = MotionControl()
    task.model_name = "kling-v2-6"
    task.reference_image = image_to_base64(image_path)
    task.reference_video = reference_video_url
    task.prompt = "Transfer the motion naturally while keeping the subject stable and realistic."
    task.mode = "pro"
    task.duration = "5"
    return task.run(client)


def example_create_custom_voice(client: Client, voice_url: str):
    task = CustomVoiceCreate()
    task.voice_name = "Demo Voice"
    task.voice_url = voice_url
    return task.run(client)


def example_avatar(client: Client, image_path: str, audio_url: str):
    task = Avatar()
    task.image = image_to_base64(image_path)
    task.sound_file = audio_url
    task.prompt = "Speak naturally with subtle head movement and a friendly expression."
    task.mode = "std"
    return task.run(client)


def example_advanced_lip_sync(client: Client, video_url: str, audio_url: str, audio_duration_ms: int):
    identify = FaceIdentify()
    identify.video_url = video_url
    face_result = identify.run(client)
    if not face_result.face_data:
        raise ValueError("No face was detected in the source video.")

    task = AdvancedLipSync()
    task.session_id = face_result.session_id
    task.face_choose = [{
        "face_id": face_result.face_data[0].face_id,
        "sound_file": audio_url,
        "sound_start_time": 0,
        "sound_end_time": audio_duration_ms,
        "sound_insert_time": 0,
        "sound_volume": 1.0,
        "original_audio_volume": 1.0,
    }]
    return task.run(client)


def example_image2video_with_custom_voice(
        client: Client,
        image_path: str,
        voice_id: str,
        dialogue: str,
):
    task = Image2Video()
    task.model_name = "kling-v2-6"
    task.image = image_to_base64(image_path)
    task.prompt = f'Portrait subject <<<voice_1>>> says: "{dialogue}"'
    task.mode = "pro"
    task.duration = "10"
    task.sound = "on"
    task.voice_list = [{"voice_id": voice_id}]
    return task.run(client)


def example_tts_with_voice_id(client: Client, voice_id: str):
    task = TTS()
    task.text = "这是一段用于测试克隆声音效果的短句。"
    task.voice_id = voice_id
    task.voice_language = "zh"
    task.voice_speed = 1.0
    return task.run(client)


if __name__ == "__main__":
    print("Set KLING_ACCESS_KEY and KLING_SECRET_KEY before running these examples.")
    print("Import this file and call the helper that matches the workflow you want to test.")
