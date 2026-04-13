import importlib
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = REPO_ROOT.parent.parent
if str(COMFYUI_ROOT) not in sys.path:
    sys.path.insert(0, str(COMFYUI_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

kling_package = importlib.import_module("py")
kling_nodes = importlib.import_module("py.nodes")


ENV_KEYS = {
    "KLINGAI_API_ACCESS_KEY": "",
    "KLING_ACCESS_KEY": "",
    "KLINGAI_API_SECRET_KEY": "",
    "KLING_SECRET_KEY": "",
    "KLINGAI_AREA": "",
    "KLINGAI_POLL_INTERVAL": "",
    "KLINGAI_REQUEST_TIMEOUT": "",
}


class BackendConfigTests(unittest.TestCase):
    def test_node_mapping_hides_client_node(self):
        self.assertNotIn(
            "Comfyui-Kling-Wrapper Client",
            kling_package.NODE_CLASS_MAPPINGS,
        )
        self.assertNotIn("client", kling_nodes.ImageGeneratorNode.INPUT_TYPES()["required"])

    def test_runtime_client_prefers_config_local_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            json_path = tmpdir_path / "config.local.json"
            legacy_path = tmpdir_path / "config.ini"

            json_path.write_text(
                json.dumps(
                    {
                        "access_key": "json-ak",
                        "secret_key": "json-sk",
                        "poll_interval": 2.5,
                        "request_timeout": 45,
                        "area": "china",
                    }
                ),
                encoding="utf-8",
            )
            legacy_path.write_text(
                "[API]\nKLINGAI_API_ACCESS_KEY = legacy-ak\nKLINGAI_API_SECRET_KEY = legacy-sk\n",
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {**ENV_KEYS, "KLINGAI_API_ACCESS_KEY": "env-ak"}, clear=False):
                with mock.patch.object(kling_nodes, "CONFIG_JSON_PATH", json_path):
                    with mock.patch.object(kling_nodes, "LEGACY_CONFIG_PATH", legacy_path):
                        client = kling_nodes._create_runtime_client()

            self.assertEqual(client._access_key, "json-ak")
            self.assertEqual(client._secret_key, "json-sk")
            self.assertEqual(client._timeout, 45)
            self.assertEqual(client.poll_interval, 2.5)
            self.assertEqual(client._area.name, "CHINA")

    def test_runtime_client_falls_back_to_legacy_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            json_path = tmpdir_path / "missing-config.local.json"
            legacy_path = tmpdir_path / "config.ini"
            legacy_path.write_text(
                "[API]\nKLINGAI_API_ACCESS_KEY = legacy-ak\nKLINGAI_API_SECRET_KEY = legacy-sk\n",
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, ENV_KEYS, clear=False):
                with mock.patch.object(kling_nodes, "CONFIG_JSON_PATH", json_path):
                    with mock.patch.object(kling_nodes, "LEGACY_CONFIG_PATH", legacy_path):
                        client = kling_nodes._create_runtime_client()

            self.assertEqual(client._access_key, "legacy-ak")
            self.assertEqual(client._secret_key, "legacy-sk")
            self.assertEqual(client._timeout, kling_nodes.DEFAULT_REQUEST_TIMEOUT)
            self.assertEqual(client.poll_interval, kling_nodes.DEFAULT_POLL_INTERVAL)
            self.assertEqual(client._area.name, "GLOBAL")

    def test_video_extend_uses_backend_runtime_client(self):
        sentinel_client = object()

        @contextmanager
        def fake_runtime_client():
            yield sentinel_client

        class FakeVideoExtend:
            def __init__(self):
                self.video_id = None
                self.prompt = None

            def run(self, client):
                self.seen_client = client
                return SimpleNamespace(
                    task_result=SimpleNamespace(
                        videos=[SimpleNamespace(url="https://example.com/video.mp4", id="video-123")]
                    )
                )

        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes, "VideoExtend", FakeVideoExtend):
                node = kling_nodes.VideoExtendNode()
                url, video_id = node.run("video-001", "Continue the shot naturally.")

        self.assertEqual(url, "https://example.com/video.mp4")
        self.assertEqual(video_id, "video-123")

    def test_preview_video_returns_local_video_url_when_saved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            with mock.patch.object(kling_nodes.folder_paths, "get_output_directory", return_value=str(tmpdir_path)):
                with mock.patch.object(
                    kling_nodes.folder_paths,
                    "get_save_image_path",
                    return_value=(str(tmpdir_path), "Comfyui-Kling-Wrapper", 1, "", None),
                ):
                    with mock.patch.object(kling_nodes, "_fetch_image", return_value=b"video-bytes"):
                        result = kling_nodes.PreviewVideo().run(
                            "https://example.com/video.mp4",
                            "Comfyui-Kling-Wrapper",
                            True,
                        )

        self.assertEqual(
            result["ui"]["video_url"],
            ["/api/view?type=output&filename=Comfyui-Kling-Wrapper_00001_.mp4"],
        )
        self.assertEqual(
            result["ui"]["images"][0]["filename"],
            "Comfyui-Kling-Wrapper_00001_.mp4",
        )

    def test_examples_are_client_free_and_valid_json(self):
        examples_dir = REPO_ROOT / "examples"
        example_files = sorted(examples_dir.glob("*.json"))
        self.assertTrue(example_files)

        for example_path in example_files:
            content = example_path.read_text(encoding="utf-8")
            data = json.loads(content)
            self.assertIsInstance(data, dict)
            self.assertNotIn("Comfyui-Kling-Wrapper Client", content)
            self.assertNotIn("COMFYUI_KLING_WRAPPER_API_CLIENT", content)


if __name__ == "__main__":
    unittest.main()
