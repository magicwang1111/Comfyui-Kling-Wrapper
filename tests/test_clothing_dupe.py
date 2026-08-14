import importlib
import json
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import torch


REPO_ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = REPO_ROOT.parent.parent
for path in (COMFYUI_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

clothing_dupe = importlib.import_module("py.api.clothing_dupe")
kling_nodes = importlib.import_module("py.nodes")
kling_package = importlib.import_module("py")


class DummyClient:
    poll_interval = 0

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, path, **kwargs):
        self.requests.append((method, path, kwargs))
        return self.responses.pop(0)


class ClothingDupeApiTests(unittest.TestCase):
    def test_submit_polls_and_extracts_product_video(self):
        client = DummyClient([
            {"code": 0, "data": {"task_id": "task-1", "status": "submitted"}},
            {"code": 0, "data": [{"id": "task-1", "status": "processing"}]},
            {
                "code": 0,
                "data": [{
                    "id": "task-1",
                    "status": "succeeded",
                    "outputs": [
                        {"type": "product_image", "url": "https://example.com/image.png"},
                        {
                            "type": "product_video",
                            "url": "https://example.com/video.mp4",
                            "watermark_url": "https://example.com/watermark.mp4",
                        },
                    ],
                    "billing": [{"amount": "12"}],
                }],
            },
        ])

        with mock.patch.object(clothing_dupe.time, "sleep"):
            result = clothing_dupe.submit_and_wait(client, {"contents": []})

        self.assertEqual(result.video_url, "https://example.com/video.mp4")
        self.assertEqual(result.watermark_video_url, "https://example.com/watermark.mp4")
        self.assertEqual(result.task_id, "task-1")
        self.assertEqual(client.requests[0][1], "/solutions/e-commerce/clothing_dupe")
        self.assertEqual(client.requests[1][2]["params"], {"task_ids": "task-1"})

    def test_extract_task_id_keeps_documented_id_compatibility(self):
        self.assertEqual(
            clothing_dupe._extract_task_id({"data": {"id": "documented-task-id"}}),
            "documented-task-id",
        )

    def test_failed_task_preserves_server_message(self):
        client = DummyClient([
            {"code": 0, "data": {"id": "task-failed"}},
            {"code": 0, "data": [{"id": "task-failed", "status": "failed", "message": "bad asset"}]},
        ])
        with mock.patch.object(clothing_dupe.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "task-failed failed: bad asset"):
                clothing_dupe.submit_and_wait(client, {"contents": []})

    def test_succeeded_task_requires_nonempty_product_video(self):
        for outputs, expected in (([], "no product_video"), ([{"type": "product_video", "url": ""}], "empty product video URL")):
            client = DummyClient([
                {"code": 0, "data": {"id": "task-bad"}},
                {"code": 0, "data": [{"id": "task-bad", "status": "succeeded", "outputs": outputs}]},
            ])
            with mock.patch.object(clothing_dupe.time, "sleep"):
                with self.assertRaisesRegex(RuntimeError, expected):
                    clothing_dupe.submit_and_wait(client, {"contents": []})

    def test_unknown_status_fails_explicitly(self):
        client = DummyClient([
            {"code": 0, "data": {"id": "task-unknown"}},
            {"code": 0, "data": [{"id": "task-unknown", "status": "paused"}]},
        ])
        with mock.patch.object(clothing_dupe.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "unknown status 'paused'"):
                clothing_dupe.submit_and_wait(client, {"contents": []})


class ClothingDupeNodeTests(unittest.TestCase):
    @staticmethod
    @contextmanager
    def _client():
        yield object()

    def _run_node(self, **overrides):
        args = {
            "product_info": "Lightweight shirt",
            "source_video": object(),
            "product_image_1": torch.zeros((1, 300, 300, 3)),
            "resolution": "720p",
            "aspect_ratio": "auto",
            "voice_id": "无",
        }
        args.update(overrides)
        captured = {}

        def submit(client, payload):
            captured["client"] = client
            captured["payload"] = payload
            return clothing_dupe.ClothingDupeResult(
                video_url="https://example.com/video.mp4",
                watermark_video_url="",
                task_id="task-1",
                raw={"status": "succeeded", "billing": [{"amount": "5"}]},
            )

        with mock.patch.object(kling_nodes, "_runtime_client", self._client):
            with mock.patch.object(kling_nodes, "_resolve_video_provider", side_effect=AssertionError("provider routing used")):
                with mock.patch.object(kling_nodes, "_upload_video_reference", return_value="https://upload/video.mp4"):
                    with mock.patch.object(kling_nodes, "_upload_image_batch_references", side_effect=[
                        ["https://upload/product-1.png"],
                        ["https://upload/product-2.png"],
                        ["https://upload/model-1.png"],
                    ]):
                        with mock.patch.object(kling_nodes, "_upload_audio_reference", return_value="https://upload/bgm.wav"):
                            with mock.patch.object(kling_nodes, "submit_clothing_dupe", side_effect=submit):
                                result = kling_nodes.ClothingDupeNode().generate(**args)
        return captured, result

    def test_minimal_payload_uses_official_runtime_client(self):
        captured, result = self._run_node()
        self.assertEqual(
            captured["payload"],
            {
                "contents": [
                    {"type": "product_info", "text": "Lightweight shirt"},
                    {"type": "source_video", "url": "https://upload/video.mp4"},
                    {"type": "product_image", "url": "https://upload/product-1.png"},
                ],
                "settings": {"resolution": "720p"},
                "options": {"watermark_info": {"enabled": False}},
            },
        )
        self.assertEqual(result[:3], ("https://example.com/video.mp4", "", "task-1"))
        self.assertEqual(json.loads(result[3])["status"], "succeeded")

    def test_full_payload_maps_optional_inputs(self):
        captured, _ = self._run_node(
            product_image_2=torch.zeros((1, 300, 300, 3)),
            model_image_1=torch.zeros((1, 300, 300, 3)),
            bgm={"waveform": torch.zeros((1, 1, 100)), "sample_rate": 100},
            resolution="1080p",
            aspect_ratio="16:9",
            voice_id="平静带货女",
            watermark_enabled=True,
            callback_url="https://example.com/callback",
            external_task_id="external-1",
        )
        self.assertEqual(
            captured["payload"]["contents"][-4:],
            [
                {"type": "product_image", "url": "https://upload/product-2.png"},
                {"type": "model_image", "url": "https://upload/model-1.png"},
                {"type": "bgm", "url": "https://upload/bgm.wav"},
                {"type": "voice", "voice_id": "calm_sales_woman"},
            ],
        )
        self.assertEqual(captured["payload"]["settings"], {"resolution": "1080p", "aspect_ratio": "16:9"})
        self.assertEqual(
            captured["payload"]["options"],
            {
                "watermark_info": {"enabled": True},
                "callback_url": "https://example.com/callback",
                "external_task_id": "external-1",
            },
        )

    def test_validation_rejects_invalid_inputs_before_upload(self):
        node = kling_nodes.ClothingDupeNode()
        valid_images = torch.zeros((1, 300, 300, 3))
        cases = [
            ({"product_info": "", "source_video": object(), "product_image_1": valid_images}, "product_info is required"),
            ({"product_info": "x" * 2501, "source_video": object(), "product_image_1": valid_images}, "2500"),
            ({"product_info": "ok", "source_video": None, "product_image_1": valid_images}, "source_video is required"),
            ({"product_info": "ok", "source_video": object(), "product_image_1": torch.zeros((6, 300, 300, 3))}, "at most 5"),
            ({"product_info": "ok", "source_video": object(), "product_image_1": torch.zeros((1, 299, 300, 3))}, "at least 300px"),
        ]
        for values, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ValueError, expected):
                    node.generate(
                        resolution="720p",
                        aspect_ratio="auto",
                        voice_id="无",
                        **values,
                    )

        with self.assertRaisesRegex(ValueError, "official Clothing Dupe voice names"):
            node.generate(
                product_info="ok",
                source_video=object(),
                product_image_1=valid_images,
                resolution="720p",
                aspect_ratio="auto",
                voice_id="custom-voice",
            )

    def test_video_duration_is_validated_when_available(self):
        video = SimpleNamespace(get_duration=lambda: 4.9)
        with self.assertRaisesRegex(ValueError, "between 5 and 180 seconds"):
            kling_nodes._validate_clothing_dupe_video(video)

    def test_registration_and_interface_have_no_provider_widget(self):
        self.assertIn("Comfyui-Kling-Wrapper Clothing Dupe", kling_package.NODE_CLASS_MAPPINGS)
        input_types = kling_nodes.ClothingDupeNode.INPUT_TYPES()
        self.assertNotIn("provider", input_types["required"])
        self.assertNotIn("provider", input_types.get("optional", {}))
        self.assertEqual(input_types["required"]["source_video"], ("VIDEO",))
        self.assertEqual(input_types["required"]["product_image_1"], ("IMAGE",))
        for index in range(2, 6):
            self.assertEqual(input_types["optional"][f"product_image_{index}"], ("IMAGE",))
        for index in range(1, 6):
            self.assertEqual(input_types["optional"][f"model_image_{index}"], ("IMAGE",))
        self.assertEqual(input_types["optional"]["bgm"], ("AUDIO",))
        for hidden in ("watermark_enabled", "callback_url", "external_task_id"):
            self.assertNotIn(hidden, input_types["required"])
            self.assertNotIn(hidden, input_types["optional"])
        self.assertEqual(input_types["required"]["voice_id"][0][0], "无")
        self.assertIn("平静带货女", input_types["required"]["voice_id"][0])


if __name__ == "__main__":
    unittest.main()
