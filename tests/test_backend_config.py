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

import httpx
import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = REPO_ROOT.parent.parent
if str(COMFYUI_ROOT) not in sys.path:
    sys.path.insert(0, str(COMFYUI_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

kling_package = importlib.import_module("py")
kling_nodes = importlib.import_module("py.nodes")
kling_client = importlib.import_module("py.api.client")


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
                        with mock.patch.object(kling_nodes, "_register_output_asset"):
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

    def test_preview_video_registers_saved_file_as_asset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            with mock.patch.object(kling_nodes.folder_paths, "get_output_directory", return_value=str(tmpdir_path)):
                with mock.patch.object(
                    kling_nodes.folder_paths,
                    "get_save_image_path",
                    return_value=(str(tmpdir_path), "Comfyui-Kling-Wrapper", 1, "", None),
                ):
                    with mock.patch.object(kling_nodes, "_fetch_image", return_value=b"video-bytes"):
                        with mock.patch.object(kling_nodes, "_register_output_asset") as register_mock:
                            result = kling_nodes.PreviewVideo().run(
                                "https://example.com/video.mp4",
                                "Comfyui-Kling-Wrapper",
                                True,
                            )

        register_mock.assert_called_once_with(result["result"][0])

    def test_preview_video_keeps_result_when_asset_registration_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            with mock.patch.object(kling_nodes.folder_paths, "get_output_directory", return_value=str(tmpdir_path)):
                with mock.patch.object(
                    kling_nodes.folder_paths,
                    "get_save_image_path",
                    return_value=(str(tmpdir_path), "Comfyui-Kling-Wrapper", 1, "", None),
                ):
                    with mock.patch.object(kling_nodes, "_fetch_image", return_value=b"video-bytes"):
                        with mock.patch.object(kling_nodes, "_register_output_asset", side_effect=RuntimeError("boom")):
                            result = kling_nodes.PreviewVideo().run(
                                "https://example.com/video.mp4",
                                "Comfyui-Kling-Wrapper",
                                True,
                            )

                            self.assertTrue(Path(result["result"][0]).is_file())

    def test_preview_video_rejects_empty_video_url(self):
        with self.assertRaisesRegex(
            ValueError,
            "empty video_url",
        ):
            kling_nodes.PreviewVideo().run("", "Comfyui-Kling-Wrapper", True)

    def test_upload_file_to_tmpfiles_retries_transient_ssl_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "sample.mp4"
            file_path.write_bytes(b"video-bytes")

            success_response = mock.Mock()
            success_response.raise_for_status.return_value = None
            success_response.json.return_value = {
                "status": "success",
                "data": {"url": "https://tmpfiles.org/123/sample.mp4"},
            }

            with mock.patch.object(
                kling_nodes.requests,
                "post",
                side_effect=[
                    requests.exceptions.SSLError("EOF occurred in violation of protocol"),
                    success_response,
                ],
            ) as post_mock:
                url = kling_nodes._upload_file_to_tmpfiles(file_path)

        self.assertEqual(url, "https://tmpfiles.org/dl/123/sample.mp4")
        self.assertEqual(post_mock.call_count, 2)

    def test_motion_control_exposes_model_dropdown(self):
        input_types = kling_nodes.MotionControlNode.INPUT_TYPES()
        required = input_types["required"]
        model_options, metadata = required["model_name"]
        duration_options, duration_metadata = input_types["optional"]["duration"]

        self.assertEqual(model_options, kling_nodes.MOTION_CONTROL_MODELS)
        self.assertEqual(metadata["default"], "kling-v2-6")
        self.assertEqual(duration_options, kling_nodes.MOTION_CONTROL_DURATIONS)
        self.assertEqual(duration_metadata["default"], "auto")
        self.assertNotIn("reference_video", input_types["optional"])

    def test_motion_control_uploads_reference_video_frames(self):
        sentinel_client = object()

        @contextmanager
        def fake_runtime_client():
            yield sentinel_client

        class FakeMotionControl:
            last_instance = None

            def __init__(self):
                FakeMotionControl.last_instance = self

            def run(self, client):
                self.seen_client = client
                return SimpleNamespace(
                    final_unit_deduction=1.0,
                    task_result=SimpleNamespace(
                        videos=[SimpleNamespace(url="https://example.com/video.mp4", id="video-123")]
                    ),
                )

        fake_frames = object()

        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes, "MotionControl", FakeMotionControl):
                with mock.patch.object(kling_nodes, "_upload_image_reference", return_value="https://tmpfiles.org/dl/img/ref.png"):
                    with mock.patch.object(
                        kling_nodes,
                        "_upload_reference_video_frames",
                        return_value="https://tmpfiles.org/dl/123/reference.mp4",
                    ) as upload_mock:
                        url, video_id = kling_nodes.MotionControlNode().generate(
                            model_name="kling-v2-6",
                            reference_image=object(),
                            reference_video_frames=fake_frames,
                            reference_video_info={"loaded_duration": 12.5, "loaded_fps": 12.5},
                        )

        self.assertEqual(url, "https://example.com/video.mp4")
        self.assertEqual(video_id, "video-123")
        upload_mock.assert_called_once_with(fake_frames, {"loaded_duration": 12.5, "loaded_fps": 12.5})
        self.assertEqual(
            FakeMotionControl.last_instance.image_url,
            "https://tmpfiles.org/dl/img/ref.png",
        )
        self.assertEqual(
            FakeMotionControl.last_instance.video_url,
            "https://tmpfiles.org/dl/123/reference.mp4",
        )
        self.assertEqual(FakeMotionControl.last_instance.duration, "12.5")
        self.assertEqual(FakeMotionControl.last_instance.character_orientation, "video")
        self.assertEqual(FakeMotionControl.last_instance.keep_original_sound, "yes")
        self.assertEqual(FakeMotionControl.last_instance.seen_client, sentinel_client)

    def test_motion_control_uploads_video_input(self):
        sentinel_client = object()

        @contextmanager
        def fake_runtime_client():
            yield sentinel_client

        class FakeMotionControl:
            last_instance = None

            def __init__(self):
                FakeMotionControl.last_instance = self

            def run(self, client):
                self.seen_client = client
                return SimpleNamespace(
                    final_unit_deduction=1.0,
                    task_result=SimpleNamespace(
                        videos=[SimpleNamespace(url="https://example.com/video.mp4", id="video-123")]
                    ),
                )

        class FakeVideo:
            def get_duration(self):
                return 7.0

        fake_video = FakeVideo()

        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes, "MotionControl", FakeMotionControl):
                with mock.patch.object(kling_nodes, "_upload_image_reference", return_value="https://tmpfiles.org/dl/img/ref.png"):
                    with mock.patch.object(
                        kling_nodes,
                        "_upload_video_reference",
                        return_value="https://tmpfiles.org/dl/456/reference.mp4",
                    ) as upload_mock:
                        url, video_id = kling_nodes.MotionControlNode().generate(
                            model_name="kling-v2-6",
                            reference_image=object(),
                            reference_video_input=fake_video,
                        )

        self.assertEqual(url, "https://example.com/video.mp4")
        self.assertEqual(video_id, "video-123")
        upload_mock.assert_called_once_with(fake_video)
        self.assertEqual(
            FakeMotionControl.last_instance.video_url,
            "https://tmpfiles.org/dl/456/reference.mp4",
        )
        self.assertEqual(
            FakeMotionControl.last_instance.image_url,
            "https://tmpfiles.org/dl/img/ref.png",
        )
        self.assertEqual(FakeMotionControl.last_instance.duration, "7")

    def test_motion_control_accepts_alternate_video_url_fields(self):
        sentinel_client = object()

        @contextmanager
        def fake_runtime_client():
            yield sentinel_client

        class FakeMotionControl:
            last_instance = None

            def __init__(self):
                FakeMotionControl.last_instance = self

            def run(self, client):
                self.seen_client = client
                return SimpleNamespace(
                    final_unit_deduction=1.0,
                    task_status="succeed",
                    task_result=SimpleNamespace(
                        videos=[SimpleNamespace(video_url="https://example.com/video-from-alias.mp4", id="video-456")]
                    ),
                )

        class FakeVideo:
            def get_duration(self):
                return 7.0

        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes, "MotionControl", FakeMotionControl):
                with mock.patch.object(kling_nodes, "_upload_image_reference", return_value="https://tmpfiles.org/dl/img/ref.png"):
                    with mock.patch.object(
                        kling_nodes,
                        "_upload_video_reference",
                        return_value="https://tmpfiles.org/dl/456/reference.mp4",
                    ):
                        url, video_id = kling_nodes.MotionControlNode().generate(
                            model_name="kling-v2-6",
                            reference_image=object(),
                            reference_video_input=FakeVideo(),
                        )

        self.assertEqual(url, "https://example.com/video-from-alias.mp4")
        self.assertEqual(video_id, "video-456")

    def test_motion_control_raises_task_failure_details(self):
        sentinel_client = object()

        @contextmanager
        def fake_runtime_client():
            yield sentinel_client

        class FakeMotionControl:
            def run(self, client):
                return SimpleNamespace(
                    final_unit_deduction=0.0,
                    task_status="failed",
                    task_status_msg="reference video duration exceeds backend limit",
                    task_result=SimpleNamespace(videos=[]),
                )

        class FakeVideo:
            def get_duration(self):
                return 12.0

        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes, "MotionControl", FakeMotionControl):
                with mock.patch.object(kling_nodes, "_upload_image_reference", return_value="https://tmpfiles.org/dl/img/ref.png"):
                    with mock.patch.object(
                        kling_nodes,
                        "_upload_video_reference",
                        return_value="https://tmpfiles.org/dl/456/reference.mp4",
                    ):
                        with self.assertRaisesRegex(
                            ValueError,
                            "task_status='failed'.*reference video duration exceeds backend limit",
                        ):
                            kling_nodes.MotionControlNode().generate(
                                model_name="kling-v2-6",
                                reference_image=object(),
                                reference_video_input=FakeVideo(),
                            )

    def test_client_retries_transient_get_transport_error(self):
        first_client = mock.Mock()
        second_client = mock.Mock()
        ok_response = mock.Mock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"data": {"task_status": "submitted"}}

        first_client.request.side_effect = httpx.RemoteProtocolError(
            "Server disconnected without sending a response."
        )
        second_client.request.return_value = ok_response

        with mock.patch.object(kling_client.jwt, "encode", return_value="token"):
            with mock.patch.object(
                kling_client.httpx,
                "Client",
                side_effect=[first_client, second_client],
            ):
                client = kling_client.Client(
                    access_key="ak",
                    secret_key="sk",
                    in_china=True,
                    timeout=30,
                    poll_interval=0.01,
                )
                result = client.request("GET", "/v1/videos/motion-control/task-123")

        self.assertEqual(result, {"data": {"task_status": "submitted"}})
        self.assertEqual(first_client.request.call_count, 1)
        self.assertEqual(second_client.request.call_count, 1)

    def test_client_retries_transient_post_connect_error(self):
        first_client = mock.Mock()
        second_client = mock.Mock()
        ok_response = mock.Mock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"data": {"task_id": "task-123"}}

        first_client.request.side_effect = httpx.ConnectError(
            "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol"
        )
        second_client.request.return_value = ok_response

        with mock.patch.object(kling_client.jwt, "encode", return_value="token"):
            with mock.patch.object(
                kling_client.httpx,
                "Client",
                side_effect=[first_client, second_client],
            ):
                client = kling_client.Client(
                    access_key="ak",
                    secret_key="sk",
                    in_china=True,
                    timeout=30,
                    poll_interval=0.01,
                )
                result = client.request("POST", "/v1/videos/motion-control", json={"prompt": "test"})

        self.assertEqual(result, {"data": {"task_id": "task-123"}})
        self.assertEqual(first_client.request.call_count, 1)
        self.assertEqual(second_client.request.call_count, 1)

    def test_motion_control_rejects_direct_reference_video_url(self):
        with self.assertRaisesRegex(
            ValueError,
            "Direct reference_video URLs are no longer supported",
        ):
            kling_nodes.MotionControlNode().generate(
                model_name="kling-v2-6",
                reference_image=object(),
                reference_video="https://example.com/reference-motion.mp4",
            )

    def test_motion_control_auto_duration_requires_video_timing(self):
        with self.assertRaisesRegex(
            ValueError,
            "duration='auto' requires",
        ):
            with mock.patch.object(
                kling_nodes,
                "_upload_reference_video_frames",
                return_value="https://tmpfiles.org/dl/789/reference.mp4",
            ):
                with mock.patch.object(
                    kling_nodes,
                    "_upload_image_reference",
                    return_value="https://tmpfiles.org/dl/img/ref.png",
                ):
                    kling_nodes.MotionControlNode().generate(
                        model_name="kling-v2-6",
                        reference_image=object(),
                        reference_video_frames=object(),
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
            if example_path.name == "07_comfyui_kling_wrapper_motion_control_v26.json":
                self.assertIn("\"type\": \"LoadVideo\"", content)
                self.assertIn("\"reference_video_input\"", content)
                self.assertNotIn("reference-motion.mp4", content)


if __name__ == "__main__":
    unittest.main()
