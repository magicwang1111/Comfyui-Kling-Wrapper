import base64
import importlib
import io
import os
from pathlib import Path
import sys
import tempfile
import zlib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image
import torch


ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT.parent.parent, ROOT):
    sys.path.insert(0, str(directory))

from comfy.cli_args import args

args.cpu = True
import execution
import nodes as core_nodes
from comfy_execution.graph import DynamicPrompt
from comfy_extras.nodes_post_processing import BatchImagesNode

kling = importlib.import_module("py.nodes")
v4 = importlib.import_module("py.nodes_v4")
image_files = importlib.import_module("py.image_files")


class Collect:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"value": ("STRING",)}}

    RETURN_TYPES = ()
    FUNCTION = "collect"
    OUTPUT_NODE = True

    def collect(self, value):
        return {"ui": {"value": [value]}}


class OriginalImageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.owner = self.root / "alice"
        self.owner.mkdir()
        directory = patch.object(image_files.folder_paths, "get_input_directory", return_value=str(self.owner))
        directory.start()
        self.addCleanup(directory.stop)
        mapping = patch.dict(core_nodes.NODE_CLASS_MAPPINGS, {
            "BatchImagesNode": BatchImagesNode,
            "KlingElement": kling.AdvancedCustomElementCreateNode,
            "KlingOmni": v4.Kling4OmniVideo,
            "KlingImage": v4.Kling4Image2Video,
            "Collect": Collect,
        })
        mapping.start()
        self.addCleanup(mapping.stop)

    def picture(self, name="photo.jpg", size=(24, 16), mode="RGB", **options):
        path = self.owner / name
        Image.new(mode, size, "red").save(path, **options)
        return path

    def graph(self, filename="photo.jpg"):
        return {
            "source": {"class_type": "LoadImage", "inputs": {"image": filename}},
            "target": {"class_type": "KlingElement", "inputs": {"image": ["source", 0]}},
        }

    async def execute(self, prompt):
        prompt["collect"] = {"class_type": "Collect", "inputs": {"value": ["target", 0]}}
        server = SimpleNamespace(client_id=None, send_sync=Mock())
        executor = execution.PromptExecutor(server, cache_type=execution.CacheType.NONE,
                                            cache_args={"ram": 0, "ram_inactive": 0})
        await executor.execute_async(prompt, "original-image-test", execute_outputs=["collect"])
        self.assertTrue(executor.success, executor.status_messages)
        return executor

    def test_headers_only_and_original_bytes(self):
        for extension in ("jpg", "png"):
            with self.subTest(extension=extension):
                path = self.picture(f"photo.{extension}")
                graph = DynamicPrompt(self.graph(path.name))
                with patch.object(Image.Image, "load", side_effect=AssertionError("must not decode")):
                    paths = image_files.original_image_files(graph, "target", "image")
                self.assertEqual(paths, [str(path)])
                self.assertEqual(base64.b64decode(v4._encode_images(None, paths)[0]), path.read_bytes())

    def test_rotated_transparent_and_animated_images_fall_back(self):
        exif = Image.Exif()
        exif[274] = 8
        paths = [self.picture("rotated.jpg", exif=exif),
                 self.picture("alpha.png", mode="RGBA"),
                 self.picture("key.png", transparency=(255, 0, 0))]
        animated = self.owner / "animated.png"
        Image.new("RGB", (24, 16), "red").save(
            animated, save_all=True, append_images=[Image.new("RGB", (24, 16), "blue")])
        paths.append(animated)
        for path in paths:
            with self.subTest(path=path.name):
                self.assertIsNone(image_files.original_image_files(DynamicPrompt(self.graph(path.name)), "target", "image"))

    def test_png_exif_after_pixel_data_is_detected_without_decoding(self):
        path = self.picture("late-exif.png")
        exif = Image.Exif()
        exif[274] = 8
        data = exif.tobytes()[6:]
        chunk = b"eXIf" + data
        chunk = len(data).to_bytes(4, "big") + chunk + zlib.crc32(chunk).to_bytes(4, "big")
        original = path.read_bytes()
        path.write_bytes(original[:-12] + chunk + original[-12:])
        with patch.object(Image.Image, "load", side_effect=AssertionError("must not decode")):
            self.assertIsNone(image_files.original_image_files(DynamicPrompt(self.graph(path.name)), "target", "image"))

    def test_batch_order_duplicates_and_mixed_sizes(self):
        first = self.picture("a.png")
        second = self.picture("b.jpg")
        graph = self.graph("a.png")
        graph["second"] = {"class_type": "LoadImage", "inputs": {"image": "b.jpg"}}
        graph["batch"] = {"class_type": "BatchImagesNode", "inputs": {
            "images.image2": ["second", 0], "images.image0": ["source", 0], "images.image1": ["second", 0]}}
        graph["target"]["inputs"]["image"] = ["batch", 0]
        self.assertEqual(image_files.original_image_files(DynamicPrompt(graph), "target", "image"),
                         [str(first), str(second), str(second)])
        self.picture("b.jpg", size=(12, 8))
        self.assertIsNone(image_files.original_image_files(DynamicPrompt(graph), "target", "image"))

    def test_processed_missing_and_mask_inputs_fall_back(self):
        self.picture()
        for source in (
            {"class_type": "ImageScale", "inputs": {"image": ["source", 0]}},
            {"class_type": "LoadImage", "inputs": {"image": "missing.jpg"}},
        ):
            graph = self.graph()
            graph["processed"] = source
            graph["target"]["inputs"]["image"] = ["processed", 0]
            self.assertIsNone(image_files.original_image_files(DynamicPrompt(graph), "target", "image"))
        graph = self.graph()
        graph["target"]["inputs"]["image"] = ["source", 1]
        self.assertIsNone(image_files.original_image_files(DynamicPrompt(graph), "target", "image"))

    def test_current_account_directory_is_enforced(self):
        other = self.root / "bob"
        other.mkdir()
        path = other / "private.jpg"
        Image.new("RGB", (24, 16)).save(path)
        for filename in ("../bob/private.jpg", str(path)):
            with self.subTest(filename=filename), self.assertRaisesRegex(ValueError, "current input directory"):
                image_files.original_image_files(DynamicPrompt(self.graph(filename)), "target", "image")

    def test_symlink_cannot_escape_current_account(self):
        outside = self.root / "outside.jpg"
        Image.new("RGB", (24, 16)).save(outside)
        try:
            os.symlink(outside, self.owner / "link.jpg")
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaisesRegex(ValueError, "current input directory"):
            image_files.original_image_files(DynamicPrompt(self.graph("link.jpg")), "target", "image")

    async def test_subject_creation_skips_load_and_batch_and_uploads_original_files(self):
        path = self.picture()
        graph = self.graph()
        graph["batch"] = {"class_type": "BatchImagesNode", "inputs": {
            "images.image0": ["source", 0], "images.image1": ["source", 0]}}
        graph["target"]["inputs"].update(element_type="multi_image_subject", element_name="subject",
            element_description="subject description", image_list=["batch", 0])
        uploaded = []

        def upload(filename):
            uploaded.append(Path(filename).read_bytes())
            return "https://example.com/original.jpg"

        provider = Mock()
        provider.create_element.return_value = SimpleNamespace(
            element={"element_id": "element", "reference_type": "image_refer"}, element_id="element")
        with patch.object(core_nodes.LoadImage, "load_image", side_effect=AssertionError("LoadImage executed")), \
             patch.object(BatchImagesNode, "execute", side_effect=AssertionError("Batch executed")), \
             patch.object(kling, "_resolve_video_provider", return_value=kling.TENCENT_VOD_PROVIDER), \
             patch.object(kling, "_upload_file_to_temporary_media_host", side_effect=upload), \
             patch.object(kling, "_video_provider") as backend:
            backend.return_value.__enter__.return_value = provider
            await self.execute(graph)
        self.assertEqual(uploaded, [path.read_bytes()] * 3)
        self.assertTrue(path.exists())

    async def test_omni_skips_sources_and_keeps_dynamic_frame_order(self):
        path = self.picture()
        graph = self.graph()
        graph["target"] = {"class_type": "KlingOmni", "inputs": {
            "prompt": "@image_1", "resolution": "720p", "duration": "10", "aspect_ratio": "adaptive",
            "middle_frame.middle_frame_2": ["source", 0], "middle_frame.middle_frame_1": ["source", 0],
            "image_1": ["source", 0]}}
        with patch.object(core_nodes.LoadImage, "load_image", side_effect=AssertionError("LoadImage executed")), \
             patch.object(v4, "_run", return_value=("url", "id")) as run:
            await self.execute(graph)
        contents = run.call_args.args[5]
        self.assertEqual([item["type"] for item in contents], ["middle_frame", "middle_frame", "refer_image"])
        self.assertEqual([item["id"] for item in contents], ["image_1", "image_2", "image_3"])
        self.assertTrue(all(base64.b64decode(item["url"]) == path.read_bytes() for item in contents))

    async def test_rotated_photo_executes_existing_loader(self):
        exif = Image.Exif()
        exif[274] = 8
        self.picture(exif=exif)
        graph = self.graph()
        graph["target"] = {"class_type": "KlingImage", "inputs": {
            "prompt": "photo", "resolution": "720p", "duration": "10", "first_frame": ["source", 0]}}
        with patch.object(core_nodes.LoadImage, "load_image", autospec=True, return_value=(torch.ones(1, 24, 16, 3), None)) as load, \
             patch.object(v4, "_run", return_value=("url", "id")) as run:
            await self.execute(graph)
        load.assert_called_once()
        with Image.open(io.BytesIO(base64.b64decode(run.call_args.kwargs["contents"][0]["url"]))) as image:
            self.assertEqual(image.size, (16, 24))

    async def test_resize_in_dynamic_middle_frame_uses_processed_pixels(self):
        self.picture()
        graph = self.graph()
        graph["resize"] = {"class_type": "ImageScale", "inputs": {
            "image": ["source", 0], "upscale_method": "nearest-exact", "width": 8, "height": 8, "crop": "disabled"}}
        graph["target"] = {"class_type": "KlingImage", "inputs": {
            "prompt": "photo", "resolution": "720p", "duration": "10", "middle_frame.middle_frame_1": ["resize", 0]}}
        with patch.object(core_nodes.LoadImage, "load_image", autospec=True, return_value=(torch.ones(1, 16, 24, 3), None)) as load, \
             patch.object(v4, "_run", return_value=("url", "id")) as run:
            await self.execute(graph)
        load.assert_called_once()
        with Image.open(io.BytesIO(base64.b64decode(run.call_args.kwargs["contents"][0]["url"]))) as image:
            self.assertEqual(image.size, (8, 8))

    async def test_mixed_size_batch_keeps_existing_resize_behavior(self):
        self.picture("a.jpg")
        self.picture("b.jpg", size=(12, 8))
        graph = self.graph("a.jpg")
        graph["second"] = {"class_type": "LoadImage", "inputs": {"image": "b.jpg"}}
        graph["batch"] = {"class_type": "BatchImagesNode", "inputs": {
            "images.image0": ["source", 0], "images.image1": ["second", 0]}}
        graph["target"] = {"class_type": "KlingOmni", "inputs": {
            "prompt": "photo", "resolution": "720p", "duration": "10", "aspect_ratio": "adaptive",
            "reference_images": ["batch", 0]}}

        def load_image(instance, image):
            return torch.ones(1, 16, 24, 3) if image == "a.jpg" else torch.ones(1, 8, 12, 3), None

        with patch.object(core_nodes.LoadImage, "load_image", autospec=True, side_effect=load_image) as load, \
             patch.object(v4, "_run", return_value=("url", "id")) as run:
            await self.execute(graph)
        self.assertEqual(load.call_count, 2)
        contents = run.call_args.args[5]
        self.assertEqual(len(contents), 2)
        for item in contents:
            with Image.open(io.BytesIO(base64.b64decode(item["url"]))) as image:
                self.assertEqual(image.size, (24, 16))


if __name__ == "__main__":
    unittest.main()
