import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
NODE_PREFIX = "Comfyui-Kling-Wrapper"
CLIENT_TYPE = "COMFYUI_KLING_WRAPPER_API_CLIENT"
ELEMENT_TYPE = "COMFYUI_KLING_WRAPPER_ELEMENT"
ELEMENT_LIST_TYPE = "COMFYUI_KLING_WRAPPER_ELEMENT_LIST"
LIPSYNC_INPUT_TYPE = "COMFYUI_KLING_WRAPPER_LIPSYNC_INPUT"


def input_slot(name, type_name, link=None, shape=7):
    slot = {"name": name, "type": type_name, "link": link}
    if type_name in {"IMAGE", "MASK"}:
        slot["shape"] = shape
    return slot


def output_slot(name, type_name, links=None, slot_index=None):
    slot = {"name": name, "type": type_name, "links": links}
    if slot_index is not None:
        slot["slot_index"] = slot_index
    return slot


def node(node_id, type_name, pos, size, order, widgets_values, inputs=None, outputs=None):
    return {
        "id": node_id,
        "type": type_name,
        "pos": pos,
        "size": size,
        "flags": {},
        "order": order,
        "mode": 0,
        "inputs": inputs or [],
        "outputs": outputs or [],
        "properties": {"Node name for S&R": type_name},
        "widgets_values": widgets_values,
    }


def workflow(nodes, links):
    return {
        "id": "Comfyui-Kling-Wrapper-example",
        "revision": 0,
        "last_node_id": max(node["id"] for node in nodes),
        "last_link_id": max((link[0] for link in links), default=0),
        "nodes": nodes,
        "links": links,
        "groups": [],
        "config": {},
        "extra": {
            "ds": {
                "scale": 0.9,
                "offset": [0, 0],
            },
            "frontendVersion": "1.42.8",
        },
        "version": 0.4,
    }


def strip_client_dependency(data):
    data = json.loads(json.dumps(data))
    client_node_type = f"{NODE_PREFIX} Client"
    removed_link_ids = set()
    removed_node_ids = set()
    cleaned_nodes = []

    for workflow_node in data["nodes"]:
        if workflow_node.get("type") == client_node_type:
            removed_node_ids.add(workflow_node["id"])
            continue

        cleaned_inputs = []
        for node_input in workflow_node.get("inputs", []):
            if node_input.get("type") == CLIENT_TYPE or node_input.get("name") == "client":
                if node_input.get("link") is not None:
                    removed_link_ids.add(node_input["link"])
                continue
            cleaned_inputs.append(node_input)

        workflow_node["inputs"] = cleaned_inputs
        cleaned_nodes.append(workflow_node)

    cleaned_links = []
    for workflow_link in data.get("links", []):
        link_id, src_node, _, dst_node, _, link_type = workflow_link
        if link_type == CLIENT_TYPE or src_node in removed_node_ids or dst_node in removed_node_ids:
            removed_link_ids.add(link_id)
            continue
        cleaned_links.append(workflow_link)

    for workflow_node in cleaned_nodes:
        for node_input in workflow_node.get("inputs", []):
            if node_input.get("link") in removed_link_ids:
                node_input["link"] = None

        for node_output in workflow_node.get("outputs", []):
            links = node_output.get("links")
            if isinstance(links, list):
                links = [link_id for link_id in links if link_id not in removed_link_ids]
                node_output["links"] = links or None

    data["nodes"] = cleaned_nodes
    data["links"] = cleaned_links
    data["last_node_id"] = max((node["id"] for node in cleaned_nodes), default=0)
    data["last_link_id"] = max((link[0] for link in cleaned_links), default=0)
    return data


def client_node(node_id=1, order=0, area="china"):
    type_name = f"{NODE_PREFIX} Client"
    return node(
        node_id,
        type_name,
        [40, 60],
        [320, 210],
        order,
        ["", "", 1, 30, area],
        outputs=[output_slot("client", CLIENT_TYPE, slot_index=0)],
    )


def load_image_node(node_id, filename, pos, order):
    return node(
        node_id,
        "LoadImage",
        pos,
        [290, 340],
        order,
        [filename, "image"],
        outputs=[
            output_slot("IMAGE", "IMAGE", slot_index=0),
            output_slot("MASK", "MASK", slot_index=1),
        ],
    )


def load_video_node(node_id, filename, pos, order):
    return node(
        node_id,
        "LoadVideo",
        pos,
        [320, 120],
        order,
        [filename],
        outputs=[output_slot("VIDEO", "VIDEO", slot_index=0)],
    )


def save_image_node(node_id, filename_prefix, pos, order, link_id):
    return node(
        node_id,
        "SaveImage",
        pos,
        [320, 100],
        order,
        [filename_prefix],
        inputs=[input_slot("images", "IMAGE", link_id)],
    )


def preview_video_node(node_id, pos, order, link_id):
    type_name = f"{NODE_PREFIX} Preview Video"
    return node(
        node_id,
        type_name,
        pos,
        [430, 820],
        order,
        [NODE_PREFIX],
        inputs=[input_slot("video_url", "STRING", link_id)],
        outputs=[output_slot("file_path", "STRING", slot_index=0)],
    )


def preview_audio_node(node_id, pos, order, link_id):
    type_name = f"{NODE_PREFIX} Preview Audio"
    return node(
        node_id,
        type_name,
        pos,
        [360, 180],
        order,
        [NODE_PREFIX + "-audio", True],
        inputs=[input_slot("audio_url", "STRING", link_id)],
        outputs=[
            output_slot("audio", "AUDIO", slot_index=0),
            output_slot("file_path", "STRING", slot_index=1),
        ],
    )


def image_generator_node(node_id, pos, order):
    type_name = f"{NODE_PREFIX} Image Generator"
    return node(
        node_id,
        type_name,
        pos,
        [430, 370],
        order,
        [
            "kling-v3",
            "A fashion editorial portrait of a young woman in soft morning light, realistic skin texture, elegant framing, filmic color grading.",
            "",
            "None",
            0.5,
            0.45,
            1,
            "16:9",
            "1k",
        ],
        inputs=[input_slot("client", CLIENT_TYPE)],
        outputs=[output_slot("image", "IMAGE", slot_index=0)],
    )


def text2video_node(node_id, pos, order, model, prompt, mode="pro", aspect_ratio="16:9", duration="5",
                    sound="off", voice_preset="None", shot_type="single", reference_video=""):
    type_name = f"{NODE_PREFIX} Text2Video"
    return node(
        node_id,
        type_name,
        pos,
        [430, 520],
        order,
        [
            model,
            prompt,
            "",
            0.5,
            mode,
            aspect_ratio,
            duration,
            "None",
            "horizontal",
            0.5,
            sound,
            voice_preset,
            shot_type,
            reference_video,
        ],
        inputs=[input_slot("client", CLIENT_TYPE)],
        outputs=[
            output_slot("url", "STRING", slot_index=0),
            output_slot("video_id", "STRING", slot_index=1),
        ],
    )


def image2video_node(node_id, pos, order, model, prompt="", mode="pro", duration="5", shot_type="single",
                     reference_video=""):
    type_name = f"{NODE_PREFIX} Image2Video"
    return node(
        node_id,
        type_name,
        pos,
        [430, 520],
        order,
        [
            model,
            prompt,
            "",
            0.5,
            mode,
            duration,
            "None",
            "horizontal",
            0.5,
            "off",
            "None",
            shot_type,
            reference_video,
        ],
        inputs=[
            input_slot("client", CLIENT_TYPE),
            input_slot("image", "IMAGE"),
            input_slot("image_tail", "IMAGE", None),
        ],
        outputs=[
            output_slot("url", "STRING", slot_index=0),
            output_slot("video_id", "STRING", slot_index=1),
        ],
    )


def multi_images_to_video_node(node_id, pos, order):
    type_name = f"{NODE_PREFIX} Multi Images To Video"
    return node(
        node_id,
        type_name,
        pos,
        [430, 360],
        order,
        [
            "kling-v3",
            "Keep the same person identity across the shot while the subject turns toward camera and smiles naturally.",
            "",
            "pro",
            "5",
            "16:9",
        ],
        inputs=[
            input_slot("client", CLIENT_TYPE),
            input_slot("image_list", "IMAGE"),
            input_slot("image_tail", "IMAGE", None),
        ],
        outputs=[
            output_slot("url", "STRING", slot_index=0),
            output_slot("video_id", "STRING", slot_index=1),
        ],
    )


def image_batch_node(node_id, pos, order):
    return node(
        node_id,
        "ImageBatch",
        pos,
        [320, 120],
        order,
        [],
        inputs=[
            input_slot("image1", "IMAGE"),
            input_slot("image2", "IMAGE"),
        ],
        outputs=[output_slot("IMAGE", "IMAGE", slot_index=0)],
    )


def virtual_try_on_node(node_id, pos, order):
    type_name = f"{NODE_PREFIX} Virtual Try On"
    return node(
        node_id,
        type_name,
        pos,
        [360, 180],
        order,
        ["kolors-virtual-try-on-v1-5"],
        inputs=[
            input_slot("client", CLIENT_TYPE),
            input_slot("human_image", "IMAGE"),
            input_slot("cloth_image", "IMAGE"),
        ],
        outputs=[output_slot("image", "IMAGE", slot_index=0)],
    )


def image_expander_node(node_id, pos, order):
    type_name = f"{NODE_PREFIX} Image Expander"
    return node(
        node_id,
        type_name,
        pos,
        [360, 260],
        order,
        [0.25, 0.0, 0.0, 0.0, "Extend the background naturally with coherent lighting and scene details.", 1],
        inputs=[
            input_slot("client", CLIENT_TYPE),
            input_slot("image", "IMAGE"),
        ],
        outputs=[output_slot("image", "IMAGE", slot_index=0)],
    )


def video_extender_node(node_id, pos, order):
    type_name = f"{NODE_PREFIX} Video Extender"
    return node(
        node_id,
        type_name,
        pos,
        [360, 180],
        order,
        ["", "Continue the shot naturally for a few more moments, keeping the same scene and motion direction."],
        inputs=[
            input_slot("client", CLIENT_TYPE),
            input_slot("video_id", "STRING"),
        ],
        outputs=[
            output_slot("url", "STRING", slot_index=0),
            output_slot("video_id", "STRING", slot_index=1),
        ],
    )


def text_to_audio_node(node_id, pos, order):
    type_name = f"{NODE_PREFIX} TextToAudio"
    return node(
        node_id,
        type_name,
        pos,
        [360, 180],
        order,
        ["Generate a calm cinematic ambient track with gentle piano and soft pads.", 6.0],
        inputs=[input_slot("client", CLIENT_TYPE)],
        outputs=[
            output_slot("id", "STRING", slot_index=0),
            output_slot("url", "STRING", slot_index=1),
        ],
    )


def video_to_audio_node(node_id, pos, order):
    type_name = f"{NODE_PREFIX} Video2Audio"
    return node(
        node_id,
        type_name,
        pos,
        [390, 220],
        order,
        ["", "", "Footsteps on stone floor and distant city ambience.", "Cinematic ambient soundtrack with low strings.", False],
        inputs=[
            input_slot("client", CLIENT_TYPE),
            input_slot("video_id", "STRING"),
        ],
        outputs=[
            output_slot("videos_id", "STRING", slot_index=0),
            output_slot("videos_url", "STRING", slot_index=1),
            output_slot("audio_id", "STRING", slot_index=2),
            output_slot("audio_url_mp3", "STRING", slot_index=3),
        ],
    )


def lip_sync_text_input_node(node_id, pos, order):
    type_name = f"{NODE_PREFIX} Lip Sync Text Input"
    return node(
        node_id,
        type_name,
        pos,
        [360, 220],
        order,
        ["Welcome to Comfyui Kling Wrapper demo. This is a lip sync example generated from text.", "The Reader", "en", 1.0],
        outputs=[output_slot("input", LIPSYNC_INPUT_TYPE, slot_index=0)],
    )


def lip_sync_node(node_id, pos, order):
    type_name = f"{NODE_PREFIX} Lip Sync"
    return node(
        node_id,
        type_name,
        pos,
        [390, 220],
        order,
        ["", "", ""],
        inputs=[
            input_slot("client", CLIENT_TYPE),
            input_slot("input", LIPSYNC_INPUT_TYPE),
            input_slot("video_id", "STRING"),
        ],
        outputs=[
            output_slot("url", "STRING", slot_index=0),
            output_slot("video_id", "STRING", slot_index=1),
        ],
    )


def effects_node(node_id, pos, order):
    type_name = f"{NODE_PREFIX} Effects"
    return node(
        node_id,
        type_name,
        pos,
        [390, 220],
        order,
        ["yearbook", "kling-v1-6", "std", "5"],
        inputs=[
            input_slot("client", CLIENT_TYPE),
            input_slot("image0", "IMAGE"),
            input_slot("image1", "IMAGE", None),
        ],
        outputs=[
            output_slot("url", "STRING", slot_index=0),
            output_slot("video_id", "STRING", slot_index=1),
        ],
    )


def advanced_element_create_node(node_id, pos, order):
    type_name = f"{NODE_PREFIX} Advanced Element Create"
    return node(
        node_id,
        type_name,
        pos,
        [390, 278],
        order,
        [
            "image_subject",
            "demo_subject",
            "A clear portrait of the subject with consistent identity traits for reuse in video generation.",
            "",
            "",
            "",
        ],
        inputs=[
            input_slot("client", CLIENT_TYPE),
            input_slot("image", "IMAGE"),
            input_slot("image_list", "IMAGE", None),
        ],
        outputs=[
            output_slot("element", ELEMENT_TYPE, slot_index=0),
            output_slot("element_id", "STRING", slot_index=1),
            output_slot("element_json", "STRING", slot_index=2),
        ],
    )


def element_list_builder_node(node_id, pos, order):
    type_name = f"{NODE_PREFIX} Element List Builder"
    return node(
        node_id,
        type_name,
        pos,
        [340, 180],
        order,
        [""],
        inputs=[input_slot("element_1", ELEMENT_TYPE)],
        outputs=[
            output_slot("element_list", ELEMENT_LIST_TYPE, slot_index=0),
            output_slot("element_list_json", "STRING", slot_index=1),
        ],
    )


def motion_control_node(node_id, pos, order):
    type_name = f"{NODE_PREFIX} Motion Control"
    return node(
        node_id,
        type_name,
        pos,
        [430, 420],
        order,
        [
            "kling-v2-6",
            "Transfer the body motion naturally while keeping the subject stable and realistic.",
            "",
            "pro",
            "auto",
            "video",
            True,
            "",
        ],
        inputs=[
            input_slot("reference_image", "IMAGE"),
            input_slot("reference_video_input", "VIDEO"),
        ],
        outputs=[
            output_slot("url", "STRING", slot_index=0),
            output_slot("video_id", "STRING", slot_index=1),
        ],
    )


def link(link_id, src_node, src_slot, dst_node, dst_slot, type_name):
    return [link_id, src_node, src_slot, dst_node, dst_slot, type_name]


def write_json(name, data):
    (ROOT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_examples_readme():
    content = """# Comfyui-Kling-Wrapper Examples

This directory contains importable ComfyUI workflow JSON examples and small Python API snippets for `Comfyui-Kling-Wrapper`.

## Before running the workflows

- Create and fill in `config.local.json` in the repository root before importing the workflows.
- You can copy `config.example.json` in the repository root as a starting template.
- Replace placeholder filenames such as `example_portrait.png`, `example_subject_front.png`, `example_subject_ref_1.png`, `example_cloth.png`, and `example_scene.png` with files that exist in your ComfyUI input directory.
- Replace placeholder URLs such as `https://example.com/reference-motion.mp4` with real URLs when needed.
- Native `sound` and `voice_preset` support is currently only verified for `kling-v2-6`.
- Newer documented models such as `kling-video-o1` and `kling-v3-omni` are intentionally hidden from the visible dropdowns until live endpoint support is confirmed.

## Important workflow notes

- `05_comfyui_kling_wrapper_text2video_v26_sound.json` is the native audio example and is built around `kling-v2-6`.
- `06_comfyui_kling_wrapper_advanced_element_subject_to_image2video.json` requires 1 frontal portrait plus 1-3 additional photos of the same subject. Background or scene images do not count as advanced-element reference images.
- If you need both subject binding and speech, generate the bound video first and then add speech with the lip-sync or audio nodes.

## Included files

- `01_comfyui_kling_wrapper_image_generation_v3.json`: basic image generation with a verified `kling-v3` preset.
- `02_comfyui_kling_wrapper_text2video_v3_intelligence.json`: text-to-video with `kling-v3` intelligent multi-shot mode.
- `03_comfyui_kling_wrapper_image2video_v3.json`: single-image to video using the visible 3.0-era model set.
- `04_comfyui_kling_wrapper_multi_images_to_video_v3.json`: multi-image identity-consistent video generation.
- `05_comfyui_kling_wrapper_text2video_v26_sound.json`: `kling-v2-6` talking-head example with native voice presets.
- `06_comfyui_kling_wrapper_advanced_element_subject_to_image2video.json`: advanced custom element creation plus `element_list` binding in image-to-video.
- `07_comfyui_kling_wrapper_motion_control_v26.json`: motion-control workflow with a reference image and reference video.
- `08_comfyui_kling_wrapper_virtual_try_on.json`: virtual try-on image workflow.
- `09_comfyui_kling_wrapper_image_expand.json`: image expansion workflow.
- `10_comfyui_kling_wrapper_video_extend_chain.json`: clip generation followed by video extension.
- `11_comfyui_kling_wrapper_text_to_audio.json`: text-to-audio workflow.
- `12_comfyui_kling_wrapper_video_to_audio.json`: video-to-audio workflow.
- `13_comfyui_kling_wrapper_lip_sync_from_text.json`: lip-sync workflow driven by text input.
- `14_comfyui_kling_wrapper_effects_single_image.json`: single-image effects workflow.
- `api_examples.py`: small Python snippets that mirror the same upgraded API wrappers.
"""
    (ROOT / "README.md").write_text(content, encoding="utf-8")


def write_api_examples():
    content = '''import base64
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


def example_create_advanced_element(client: Client, frontal_image_path: str, reference_image_paths: list[str]):
    if not 1 <= len(reference_image_paths) <= 3:
        raise ValueError("Provide 1-3 additional reference images of the same subject.")
    task = AdvancedCustomElements()
    task.name = "demo_subject"
    task.description = "A clear portrait of the subject with consistent identity traits for reuse in video generation."
    task.reference_type = "image_refer"
    task.frontal_image = image_to_base64(frontal_image_path)
    task.refer_images = [image_to_base64(path) for path in reference_image_paths]
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
'''
    (ROOT / "api_examples.py").write_text(content, encoding="utf-8")


def generate_workflows():
    examples = {}

    nodes = [
        client_node(1, 0),
        image_generator_node(2, [430, 40], 1),
        save_image_node(3, "Comfyui-Kling-Wrapper-image-generation", [900, 60], 2, 2),
    ]
    links = [
        link(1, 1, 0, 2, 0, CLIENT_TYPE),
        link(2, 2, 0, 3, 0, "IMAGE"),
    ]
    nodes[1]["inputs"][0]["link"] = 1
    nodes[1]["outputs"][0]["links"] = [2]
    examples["01_comfyui_kling_wrapper_image_generation_v3.json"] = workflow(nodes, links)

    nodes = [
        client_node(1, 0),
        text2video_node(
            2,
            [430, 20],
            1,
            "kling-v3",
            "A traveler moves through an old alley at dusk, cinematic atmosphere, natural motion, evolving composition with coherent multi-shot storytelling.",
            mode="pro",
            shot_type="intelligence",
        ),
        preview_video_node(3, [910, 20], 2, 2),
    ]
    links = [
        link(1, 1, 0, 2, 0, CLIENT_TYPE),
        link(2, 2, 0, 3, 0, "STRING"),
    ]
    nodes[1]["inputs"][0]["link"] = 1
    nodes[1]["outputs"][0]["links"] = [2]
    examples["02_comfyui_kling_wrapper_text2video_v3_intelligence.json"] = workflow(nodes, links)

    nodes = [
        client_node(1, 0),
        load_image_node(2, "example_portrait.png", [60, 340], 1),
        image2video_node(
            3,
            [430, 200],
            2,
            "kling-v3",
            "A cinematic close-up portrait. The subject breathes naturally, hair and clothing move subtly in the wind, and the camera slowly pushes in.",
            mode="pro",
        ),
        preview_video_node(4, [920, 200], 3, 3),
    ]
    links = [
        link(1, 1, 0, 3, 0, CLIENT_TYPE),
        link(2, 2, 0, 3, 1, "IMAGE"),
        link(3, 3, 0, 4, 0, "STRING"),
    ]
    nodes[2]["inputs"][0]["link"] = 1
    nodes[2]["inputs"][1]["link"] = 2
    nodes[2]["outputs"][0]["links"] = [3]
    examples["03_comfyui_kling_wrapper_image2video_v3.json"] = workflow(nodes, links)

    nodes = [
        client_node(1, 0),
        load_image_node(2, "example_subject_a.png", [40, 330], 1),
        load_image_node(3, "example_subject_b.png", [40, 700], 2),
        image_batch_node(4, [370, 510], 3),
        multi_images_to_video_node(5, [700, 420], 4),
        preview_video_node(6, [1180, 420], 5, 5),
    ]
    links = [
        link(1, 1, 0, 5, 0, CLIENT_TYPE),
        link(2, 2, 0, 4, 0, "IMAGE"),
        link(3, 3, 0, 4, 1, "IMAGE"),
        link(4, 4, 0, 5, 1, "IMAGE"),
        link(5, 5, 0, 6, 0, "STRING"),
    ]
    nodes[3]["inputs"][0]["link"] = 2
    nodes[3]["inputs"][1]["link"] = 3
    nodes[4]["inputs"][0]["link"] = 1
    nodes[4]["inputs"][1]["link"] = 4
    nodes[4]["outputs"][0]["links"] = [5]
    examples["04_comfyui_kling_wrapper_multi_images_to_video_v3.json"] = workflow(nodes, links)

    nodes = [
        client_node(1, 0),
        text2video_node(
            2,
            [430, 20],
            1,
            "kling-v2-6",
            "A presenter speaks directly to camera in a clean studio, natural gestures, subtle head motion, clear talking-head composition.",
            mode="pro",
            sound="on",
            voice_preset="The Reader | reader_en_m-v1",
        ),
        preview_video_node(3, [910, 20], 2, 2),
    ]
    links = [
        link(1, 1, 0, 2, 0, CLIENT_TYPE),
        link(2, 2, 0, 3, 0, "STRING"),
    ]
    nodes[1]["inputs"][0]["link"] = 1
    nodes[1]["outputs"][0]["links"] = [2]
    examples["05_comfyui_kling_wrapper_text2video_v26_sound.json"] = workflow(nodes, links)

    nodes = [
        client_node(1, 0),
        load_image_node(2, "example_subject_front.png", [30, 100], 1),
        load_image_node(3, "example_subject_ref_1.png", [30, 470], 2),
        load_image_node(4, "example_subject_ref_2.png", [30, 840], 3),
        image_batch_node(5, [360, 640], 4),
        load_image_node(6, "example_scene.png", [360, 980], 5),
        advanced_element_create_node(7, [720, 180], 6),
        element_list_builder_node(8, [1160, 180], 7),
        image2video_node(
            9,
            [1160, 500],
            8,
            "kling-v3",
            "Keep the same subject identity while the camera slowly moves and the background remains coherent.",
            mode="pro",
        ),
        preview_video_node(10, [1640, 500], 9, 10),
    ]
    links = [
        link(1, 1, 0, 7, 0, CLIENT_TYPE),
        link(2, 2, 0, 7, 1, "IMAGE"),
        link(3, 3, 0, 5, 0, "IMAGE"),
        link(4, 4, 0, 5, 1, "IMAGE"),
        link(5, 5, 0, 7, 2, "IMAGE"),
        link(6, 7, 0, 8, 0, ELEMENT_TYPE),
        link(7, 1, 0, 9, 0, CLIENT_TYPE),
        link(8, 6, 0, 9, 1, "IMAGE"),
        link(9, 8, 0, 9, 4, ELEMENT_LIST_TYPE),
        link(10, 9, 0, 10, 0, "STRING"),
    ]
    nodes[6]["inputs"][0]["link"] = 1
    nodes[6]["inputs"][1]["link"] = 2
    nodes[6]["inputs"][2]["link"] = 5
    nodes[7]["inputs"][0]["link"] = 6
    nodes[8]["inputs"][0]["link"] = 7
    nodes[8]["inputs"][1]["link"] = 8
    nodes[8]["inputs"].append(input_slot("element_list", ELEMENT_LIST_TYPE, 9))
    nodes[8]["outputs"][0]["links"] = [10]
    examples["06_comfyui_kling_wrapper_advanced_element_subject_to_image2video.json"] = workflow(nodes, links)

    nodes = [
        load_image_node(2, "example_motion_subject.png", [40, 260], 1),
        load_video_node(3, "example_motion_reference.mp4", [40, 670], 2),
        motion_control_node(4, [460, 220], 3),
        preview_video_node(5, [980, 220], 4, 3),
    ]
    links = [
        link(1, 2, 0, 4, 0, "IMAGE"),
        link(2, 3, 0, 4, 1, "VIDEO"),
        link(3, 4, 0, 5, 0, "STRING"),
    ]
    nodes[2]["inputs"][0]["link"] = 1
    nodes[2]["inputs"][1]["link"] = 2
    nodes[2]["outputs"][0]["links"] = [3]
    examples["07_comfyui_kling_wrapper_motion_control_v26.json"] = workflow(nodes, links)

    nodes = [
        client_node(1, 0),
        load_image_node(2, "example_model.png", [40, 150], 1),
        load_image_node(3, "example_cloth.png", [40, 520], 2),
        virtual_try_on_node(4, [420, 310], 3),
        save_image_node(5, "Comfyui-Kling-Wrapper-virtual-try-on", [860, 320], 4, 4),
    ]
    links = [
        link(1, 1, 0, 4, 0, CLIENT_TYPE),
        link(2, 2, 0, 4, 1, "IMAGE"),
        link(3, 3, 0, 4, 2, "IMAGE"),
        link(4, 4, 0, 5, 0, "IMAGE"),
    ]
    nodes[3]["inputs"][0]["link"] = 1
    nodes[3]["inputs"][1]["link"] = 2
    nodes[3]["inputs"][2]["link"] = 3
    nodes[3]["outputs"][0]["links"] = [4]
    examples["08_comfyui_kling_wrapper_virtual_try_on.json"] = workflow(nodes, links)

    nodes = [
        client_node(1, 0),
        load_image_node(2, "example_expand.png", [40, 220], 1),
        image_expander_node(3, [430, 180], 2),
        save_image_node(4, "Comfyui-Kling-Wrapper-image-expand", [860, 190], 3, 3),
    ]
    links = [
        link(1, 1, 0, 3, 0, CLIENT_TYPE),
        link(2, 2, 0, 3, 1, "IMAGE"),
        link(3, 3, 0, 4, 0, "IMAGE"),
    ]
    nodes[2]["inputs"][0]["link"] = 1
    nodes[2]["inputs"][1]["link"] = 2
    nodes[2]["outputs"][0]["links"] = [3]
    examples["09_comfyui_kling_wrapper_image_expand.json"] = workflow(nodes, links)

    nodes = [
        client_node(1, 0),
        text2video_node(
            2,
            [420, 20],
            1,
            "kling-v3",
            "A quiet street scene at sunrise with subtle camera drift and natural environmental motion.",
            mode="pro",
        ),
        video_extender_node(3, [870, 40], 2),
        preview_video_node(4, [1290, 40], 3, 4),
    ]
    links = [
        link(1, 1, 0, 2, 0, CLIENT_TYPE),
        link(2, 1, 0, 3, 0, CLIENT_TYPE),
        link(3, 2, 1, 3, 1, "STRING"),
        link(4, 3, 0, 4, 0, "STRING"),
    ]
    nodes[1]["inputs"][0]["link"] = 1
    nodes[2]["inputs"][0]["link"] = 2
    nodes[2]["inputs"][1]["link"] = 3
    nodes[2]["outputs"][0]["links"] = [4]
    examples["10_comfyui_kling_wrapper_video_extend_chain.json"] = workflow(nodes, links)

    nodes = [
        client_node(1, 0),
        text_to_audio_node(2, [430, 80], 1),
        preview_audio_node(3, [870, 80], 2, 2),
    ]
    links = [
        link(1, 1, 0, 2, 0, CLIENT_TYPE),
        link(2, 2, 1, 3, 0, "STRING"),
    ]
    nodes[1]["inputs"][0]["link"] = 1
    nodes[1]["outputs"][1]["links"] = [2]
    examples["11_comfyui_kling_wrapper_text_to_audio.json"] = workflow(nodes, links)

    nodes = [
        client_node(1, 0),
        text2video_node(
            2,
            [420, 20],
            1,
            "kling-v3",
            "A person walks through an empty hall with slow cinematic movement.",
            mode="pro",
        ),
        video_to_audio_node(3, [880, 30], 2),
        preview_audio_node(4, [1330, 30], 3, 4),
    ]
    links = [
        link(1, 1, 0, 2, 0, CLIENT_TYPE),
        link(2, 1, 0, 3, 0, CLIENT_TYPE),
        link(3, 2, 1, 3, 1, "STRING"),
        link(4, 3, 3, 4, 0, "STRING"),
    ]
    nodes[1]["inputs"][0]["link"] = 1
    nodes[2]["inputs"][0]["link"] = 2
    nodes[2]["inputs"][1]["link"] = 3
    nodes[2]["outputs"][3]["links"] = [4]
    examples["12_comfyui_kling_wrapper_video_to_audio.json"] = workflow(nodes, links)

    nodes = [
        client_node(1, 0),
        text2video_node(
            2,
            [420, 20],
            1,
            "kling-v3",
            "A portrait subject looks at camera with subtle idle motion.",
            mode="pro",
        ),
        lip_sync_text_input_node(3, [420, 420], 2),
        lip_sync_node(4, [880, 240], 3),
        preview_video_node(5, [1320, 240], 4, 5),
    ]
    links = [
        link(1, 1, 0, 2, 0, CLIENT_TYPE),
        link(2, 1, 0, 4, 0, CLIENT_TYPE),
        link(3, 3, 0, 4, 1, LIPSYNC_INPUT_TYPE),
        link(4, 2, 1, 4, 3, "STRING"),
        link(5, 4, 0, 5, 0, "STRING"),
    ]
    nodes[1]["inputs"][0]["link"] = 1
    nodes[3]["inputs"][0]["link"] = 2
    nodes[3]["inputs"][1]["link"] = 3
    nodes[3]["inputs"][2]["link"] = 4
    nodes[3]["outputs"][0]["links"] = [5]
    examples["13_comfyui_kling_wrapper_lip_sync_from_text.json"] = workflow(nodes, links)

    nodes = [
        client_node(1, 0),
        load_image_node(2, "example_effect_input.png", [40, 220], 1),
        effects_node(3, [430, 180], 2),
        preview_video_node(4, [900, 180], 3, 3),
    ]
    links = [
        link(1, 1, 0, 3, 0, CLIENT_TYPE),
        link(2, 2, 0, 3, 1, "IMAGE"),
        link(3, 3, 0, 4, 0, "STRING"),
    ]
    nodes[2]["inputs"][0]["link"] = 1
    nodes[2]["inputs"][1]["link"] = 2
    nodes[2]["outputs"][0]["links"] = [3]
    examples["14_comfyui_kling_wrapper_effects_single_image.json"] = workflow(nodes, links)

    for name, data in examples.items():
        write_json(name, strip_client_dependency(data))


if __name__ == "__main__":
    write_examples_readme()
    write_api_examples()
    generate_workflows()
    print(f"Wrote refreshed examples into {ROOT}")
