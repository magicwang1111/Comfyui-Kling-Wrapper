import base64
import os
from pathlib import Path

from py.api import AdvancedCustomElements, Client, Image2Video, ImageGenerator, MotionControl, MultiImages2Video, Text2Video


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


def example_create_advanced_element(client: Client, image_path: str):
    task = AdvancedCustomElements()
    task.type = "image_subject"
    task.name = "demo_subject"
    task.image = image_to_base64(image_path)
    task.image_list = [task.image]
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


if __name__ == "__main__":
    print("Set KLING_ACCESS_KEY and KLING_SECRET_KEY before running these examples.")
    print("Import this file and call the helper that matches the workflow you want to test.")
