import importlib
import json
import os
import sys
import tempfile
import unittest
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace
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
kling_capabilities = importlib.import_module("py.api.capabilities")
kling_client = importlib.import_module("py.api.client")


ENV_KEYS = {
    "KLINGAI_API_ACCESS_KEY": "",
    "KLING_ACCESS_KEY": "",
    "KLINGAI_API_SECRET_KEY": "",
    "KLING_SECRET_KEY": "",
    "KLINGAI_AREA": "",
    "KLINGAI_POLL_INTERVAL": "",
    "KLINGAI_REQUEST_TIMEOUT": "",
    "OSS_ENDPOINT": "",
    "OSS_ACCESS_KEY_ID": "",
    "OSS_ACCESS_KEY_SECRET": "",
    "OSS_BUCKET": "",
    "OSS_PREFIX": "",
    "OSS_SIGNED_URL_EXPIRES": "",
}


class BackendConfigTests(unittest.TestCase):
    def test_node_mapping_hides_client_node(self):
        self.assertNotIn(
            "Comfyui-Kling-Wrapper Client",
            kling_package.NODE_CLASS_MAPPINGS,
        )
        self.assertNotIn("client", kling_nodes.ImageGeneratorNode.INPUT_TYPES()["required"])

    def test_video_generation_nodes_expose_4k_mode(self):
        self.assertIn("4k", kling_nodes.Text2VideoNode.INPUT_TYPES()["optional"]["mode"][0])
        self.assertIn("4k", kling_nodes.Image2VideoNode.INPUT_TYPES()["optional"]["mode"][0])
        self.assertIn("4k", kling_nodes.MultiImagesToVideoNode.INPUT_TYPES()["optional"]["mode"][0])
        self.assertNotIn("4k", kling_nodes.MotionControlNode.INPUT_TYPES()["optional"]["mode"][0])

    def test_kling_v3_accepts_4k_video_mode(self):
        capability = kling_capabilities.validate_video_generation_request(
            task_name="text2video",
            model_name="kling-v3",
            mode="4k",
            duration="3",
        )

        self.assertIn("4k", capability["modes"])

    def test_non_4k_models_reject_4k_video_mode(self):
        with self.assertRaisesRegex(ValueError, "kling-v2-6 only supports modes: pro"):
            kling_capabilities.validate_video_generation_request(
                task_name="text2video",
                model_name="kling-v2-6",
                mode="4k",
                duration="5",
            )

    def test_omni_reference_video_rejects_4k_mode(self):
        with self.assertRaisesRegex(ValueError, "does not support mode=4k with reference_video"):
            kling_capabilities.validate_video_generation_request(
                task_name="image2video",
                model_name="kling-v3-omni",
                mode="4k",
                duration="5",
                has_reference_video=True,
            )

    def test_lip_sync_nodes_expose_direct_audio_and_video_inputs(self):
        audio_inputs = kling_nodes.LipSyncAudioInputNode.INPUT_TYPES()["optional"]
        video_inputs = kling_nodes.LipSyncNode.INPUT_TYPES()["optional"]

        self.assertEqual(audio_inputs["audio"][0], "AUDIO")
        self.assertEqual(video_inputs["video_input"][0], "VIDEO")
        self.assertEqual(video_inputs["video_frames"][0], "IMAGE")
        self.assertEqual(video_inputs["video_info"][0], "VHS_VIDEOINFO")

    def test_lip_sync_audio_input_accepts_comfy_audio(self):
        fake_audio = {"waveform": object(), "sample_rate": 44100}

        with mock.patch.object(kling_nodes, "_upload_audio_reference", return_value="https://example.com/audio.wav") as upload_mock:
            lip_sync_input, = kling_nodes.LipSyncAudioInputNode().run(audio=fake_audio)

        upload_mock.assert_called_once_with(fake_audio)
        self.assertEqual(lip_sync_input.mode, "audio2video")
        self.assertEqual(lip_sync_input.audio_type, "url")
        self.assertEqual(lip_sync_input.audio_url, "https://example.com/audio.wav")

    def test_lip_sync_audio_input_uploads_audio_file(self):
        with mock.patch.object(
            kling_nodes,
            "_upload_file_to_temporary_media_host",
            return_value="https://example.com/local-audio.wav",
        ) as upload_mock:
            lip_sync_input, = kling_nodes.LipSyncAudioInputNode().run(audio_file="D:/input/local-audio.wav")

        upload_mock.assert_called_once_with("D:/input/local-audio.wav")
        self.assertEqual(lip_sync_input.audio_type, "url")
        self.assertEqual(lip_sync_input.audio_url, "https://example.com/local-audio.wav")

    def test_lip_sync_audio_input_rejects_multiple_sources(self):
        with self.assertRaisesRegex(ValueError, "Provide only one"):
            kling_nodes.LipSyncAudioInputNode().run(
                audio={"waveform": object(), "sample_rate": 44100},
                audio_url="https://example.com/audio.mp3",
            )

    def test_custom_voice_create_accepts_comfy_audio(self):
        sentinel_client = object()
        captured = {}

        @contextmanager
        def fake_runtime_client():
            yield sentinel_client

        def fake_run(generator, client):
            captured["client"] = client
            captured["payload"] = generator.to_dict()
            return SimpleNamespace(
                task_id="task-voice-123",
                task_status="succeed",
                task_status_msg="",
                final_unit_deduction="1.0",
                task_result=SimpleNamespace(
                    voices=[
                        SimpleNamespace(
                            voice_id="voice-123",
                            voice_name="Demo Voice",
                            trial_url="https://example.com/trial.mp3",
                            owned_by="creator",
                        )
                    ]
                ),
            )

        fake_audio = {"waveform": object(), "sample_rate": 44100}
        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes.CustomVoiceCreate, "run", fake_run):
                with mock.patch.object(
                    kling_nodes,
                    "_upload_audio_reference",
                    return_value="https://example.com/reference.wav",
                ) as upload_mock:
                    voice_id, voice_name, trial_url, task_id, voice_json = (
                        kling_nodes.CustomVoiceCreateNode().create(
                            voice_name="Demo Voice",
                            audio=fake_audio,
                            external_task_id="external-123",
                        )
                    )

        upload_mock.assert_called_once_with(fake_audio)
        self.assertIs(captured["client"], sentinel_client)
        self.assertEqual(
            captured["payload"],
            {
                "external_task_id": "external-123",
                "voice_name": "Demo Voice",
                "voice_url": "https://example.com/reference.wav",
            },
        )
        self.assertEqual(voice_id, "voice-123")
        self.assertEqual(voice_name, "Demo Voice")
        self.assertEqual(trial_url, "https://example.com/trial.mp3")
        self.assertEqual(task_id, "task-voice-123")
        self.assertEqual(json.loads(voice_json)["voice"]["voice_id"], "voice-123")

    def test_custom_voice_create_uploads_voice_file(self):
        sentinel_client = object()
        captured = {}

        @contextmanager
        def fake_runtime_client():
            yield sentinel_client

        def fake_run(generator, client):
            captured["payload"] = generator.to_dict()
            return SimpleNamespace(
                task_id="task-file-123",
                task_status="succeed",
                task_result=SimpleNamespace(
                    voices=[SimpleNamespace(voice_id="voice-file", voice_name="File Voice", trial_url="")]
                ),
            )

        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes.CustomVoiceCreate, "run", fake_run):
                with mock.patch.object(
                    kling_nodes,
                    "_upload_file_to_temporary_media_host",
                    return_value="https://example.com/local-reference.mp3",
                ) as upload_mock:
                    kling_nodes.CustomVoiceCreateNode().create(
                        voice_name="File Voice",
                        voice_file="D:/input/reference.mp3",
                    )

        upload_mock.assert_called_once_with("D:/input/reference.mp3")
        self.assertEqual(
            captured["payload"],
            {
                "voice_name": "File Voice",
                "voice_url": "https://example.com/local-reference.mp3",
            },
        )

    def test_custom_voice_create_rejects_missing_or_multiple_sources(self):
        with self.assertRaisesRegex(ValueError, "Provide audio"):
            kling_nodes.CustomVoiceCreateNode().create(voice_name="Demo Voice")

        with self.assertRaisesRegex(ValueError, "Provide only one"):
            kling_nodes.CustomVoiceCreateNode().create(
                voice_name="Demo Voice",
                voice_url="https://example.com/audio.mp3",
                video_id="video-123",
            )

    def test_custom_voice_create_rejects_long_name(self):
        with self.assertRaisesRegex(ValueError, "20 characters"):
            kling_nodes.CustomVoiceCreateNode().create(
                voice_name="x" * 21,
                voice_url="https://example.com/audio.mp3",
            )

    def test_custom_voice_query_parses_voice_result(self):
        sentinel_client = object()
        captured = {}

        @contextmanager
        def fake_runtime_client():
            yield sentinel_client

        def fake_run(generator, client):
            captured["client"] = client
            captured["identifier"] = generator.identifier
            return SimpleNamespace(
                task_id="task-query-123",
                task_status="succeed",
                task_result=SimpleNamespace(
                    voices=[
                        SimpleNamespace(
                            voice_id="voice-query",
                            voice_name="Query Voice",
                            trial_url="https://example.com/query.mp3",
                            owned_by="creator",
                        )
                    ]
                ),
            )

        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes.CustomVoiceQuery, "run", fake_run):
                voice_id, voice_name, trial_url, task_id, voice_json = (
                    kling_nodes.CustomVoiceQueryNode().query("external-123")
                )

        self.assertIs(captured["client"], sentinel_client)
        self.assertEqual(captured["identifier"], "external-123")
        self.assertEqual(voice_id, "voice-query")
        self.assertEqual(voice_name, "Query Voice")
        self.assertEqual(trial_url, "https://example.com/query.mp3")
        self.assertEqual(task_id, "task-query-123")
        self.assertEqual(json.loads(voice_json)["voice"]["voice_name"], "Query Voice")

    def test_tts_node_builds_payload_and_returns_audio_url(self):
        sentinel_client = object()
        captured = {}

        @contextmanager
        def fake_runtime_client():
            yield sentinel_client

        def fake_run(generator, client):
            captured["client"] = client
            captured["payload"] = generator.to_dict()
            return SimpleNamespace(
                task_id="task-tts-123",
                task_status="succeed",
                task_result=SimpleNamespace(
                    audios=[
                        SimpleNamespace(
                            id="audio-123",
                            url="https://example.com/output.mp3",
                            duration="3.2",
                        )
                    ]
                ),
                final_unit_deduction="0.5",
            )

        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes.TTS, "run", fake_run):
                audio_id, audio_url, duration, audio_json = kling_nodes.TTSNode().generate(
                    text="Hello from a cloned voice.",
                    voice_id="voice-123",
                    voice_language="en",
                    voice_speed=1.2,
                )

        self.assertIs(captured["client"], sentinel_client)
        self.assertEqual(
            captured["payload"],
            {
                "text": "Hello from a cloned voice.",
                "voice_id": "voice-123",
                "voice_language": "en",
                "voice_speed": 1.2,
            },
        )
        self.assertEqual(audio_id, "audio-123")
        self.assertEqual(audio_url, "https://example.com/output.mp3")
        self.assertEqual(duration, "3.2")
        self.assertEqual(json.loads(audio_json)["audio"]["url"], "https://example.com/output.mp3")

    def test_tts_node_uses_zh_for_chinese_text_even_if_en_selected(self):
        captured = {}

        @contextmanager
        def fake_runtime_client():
            yield object()

        def fake_run(generator, client):
            captured["payload"] = generator.to_dict()
            return SimpleNamespace(
                task_id="task-tts-zh",
                task_status="succeed",
                task_result=SimpleNamespace(
                    audios=[SimpleNamespace(id="audio-zh", url="https://example.com/zh.mp3", duration="2.0")]
                ),
            )

        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes.TTS, "run", fake_run):
                kling_nodes.TTSNode().generate(
                    text="二十岁有二十岁的迷茫。",
                    voice_id="voice-zh",
                    voice_language="en",
                    voice_speed=1.0,
                )

        self.assertEqual(captured["payload"]["voice_language"], "zh")

    def test_preview_audio_fingerprint_accepts_audio_url_inputs(self):
        first = kling_nodes.PreviewAudio.fingerprint_inputs(
            audio_url="https://example.com/a.mp3",
            filename_prefix="demo",
            save_output=True,
        )
        second = kling_nodes.PreviewAudio.fingerprint_inputs(
            audio_url="https://example.com/a.mp3",
            filename_prefix="demo",
            save_output=True,
        )

        self.assertEqual(first, second)
        self.assertIsInstance(first, str)

    def test_custom_voice_and_tts_nodes_are_registered(self):
        self.assertIn("Comfyui-Kling-Wrapper Custom Voice Create", kling_package.NODE_CLASS_MAPPINGS)
        self.assertIn("Comfyui-Kling-Wrapper Custom Voice Query", kling_package.NODE_CLASS_MAPPINGS)
        self.assertIn("Comfyui-Kling-Wrapper TTS", kling_package.NODE_CLASS_MAPPINGS)

    def test_lip_sync_uploads_video_frames(self):
        sentinel_client = object()

        @contextmanager
        def fake_runtime_client():
            yield sentinel_client

        class FakeLipSync:
            last_instance = None

            def __init__(self):
                FakeLipSync.last_instance = self

            def run(self, client):
                self.seen_client = client
                return SimpleNamespace(
                    task_status="succeed",
                    task_result=SimpleNamespace(
                        videos=[SimpleNamespace(url="https://example.com/lipsync.mp4", id="video-123")]
                    ),
                )

        fake_frames = object()
        fake_info = {"loaded_fps": 25.0}
        lip_sync_input = SimpleNamespace(mode="audio2video", audio_type="file", audio_file="encoded-audio")

        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes, "LipSync", FakeLipSync):
                with mock.patch.object(
                    kling_nodes,
                    "_upload_reference_video_frames",
                    return_value="https://tmpfiles.org/dl/123/source.mp4",
                ) as upload_mock:
                    url, video_id = kling_nodes.LipSyncNode().run(
                        lip_sync_input,
                        face_id="",
                        video_frames=fake_frames,
                        video_info=fake_info,
                    )

        upload_mock.assert_called_once_with(fake_frames, fake_info)
        self.assertEqual(url, "https://example.com/lipsync.mp4")
        self.assertEqual(video_id, "video-123")
        self.assertEqual(FakeLipSync.last_instance.input.video_id, "")
        self.assertEqual(FakeLipSync.last_instance.input.video_url, "https://tmpfiles.org/dl/123/source.mp4")
        self.assertEqual(FakeLipSync.last_instance.seen_client, sentinel_client)

    def test_lip_sync_uploads_video_input_object(self):
        sentinel_client = object()

        @contextmanager
        def fake_runtime_client():
            yield sentinel_client

        class FakeLipSync:
            last_instance = None

            def __init__(self):
                FakeLipSync.last_instance = self

            def run(self, client):
                self.seen_client = client
                return SimpleNamespace(
                    task_status="succeed",
                    task_result=SimpleNamespace(
                        videos=[SimpleNamespace(url="https://example.com/lipsync.mp4", id="video-456")]
                    ),
                )

        fake_video = object()
        lip_sync_input = SimpleNamespace(mode="audio2video", audio_type="file", audio_file="encoded-audio")

        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes, "LipSync", FakeLipSync):
                with mock.patch.object(
                    kling_nodes,
                    "_upload_video_reference",
                    return_value="https://tmpfiles.org/dl/456/source.mp4",
                ) as upload_mock:
                    url, video_id = kling_nodes.LipSyncNode().run(
                        lip_sync_input,
                        face_id="face-1",
                        video_input=fake_video,
                    )

        upload_mock.assert_called_once_with(fake_video)
        self.assertEqual(url, "https://example.com/lipsync.mp4")
        self.assertEqual(video_id, "video-456")
        self.assertEqual(FakeLipSync.last_instance.input.video_url, "https://tmpfiles.org/dl/456/source.mp4")
        self.assertEqual(FakeLipSync.last_instance.input.face_id, "face-1")

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

    def test_advanced_element_image_subject_sends_minimal_payload(self):
        sentinel_client = object()
        captured = {}

        @contextmanager
        def fake_runtime_client():
            yield sentinel_client

        def fake_run(generator, client):
            captured["client"] = client
            captured["payload"] = generator.to_dict()
            return SimpleNamespace(task_id="task-123", final_unit_deduction=1.0)

        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes.AdvancedCustomElements, "run", fake_run):
                with mock.patch.object(
                    kling_nodes,
                    "_upload_image_batch_references",
                    side_effect=[
                        ["https://cdn.example.com/front.png"],
                        [
                            "https://cdn.example.com/left.png",
                            "https://cdn.example.com/right.png",
                            "https://cdn.example.com/rear.png",
                        ],
                    ],
                ):
                    payload, element_id, element_json = kling_nodes.AdvancedCustomElementCreateNode().create(
                        element_type="image_subject",
                        element_name="shoe",
                        element_description="Nike Kobe Air Force 1 Low",
                        image=object(),
                        image_list=object(),
                        element_voice_id="voice-123",
                    )

        self.assertEqual(
            captured["payload"],
            {
                "reference_type": "image_refer",
                "element_image_list": {
                    "frontal_image": "https://cdn.example.com/front.png",
                    "refer_images": [
                        {"image_url": "https://cdn.example.com/left.png"},
                        {"image_url": "https://cdn.example.com/right.png"},
                        {"image_url": "https://cdn.example.com/rear.png"},
                    ],
                },
                "element_voice_id": "voice-123",
                "element_name": "shoe",
                "element_description": "Nike Kobe Air Force 1 Low",
            },
        )
        self.assertIs(captured["client"], sentinel_client)
        self.assertEqual(payload, {"task_id": "task-123"})
        self.assertEqual(element_id, "")
        self.assertEqual(json.loads(element_json), payload)

    def test_advanced_element_video_subject_sends_minimal_payload(self):
        sentinel_client = object()
        captured = {}

        @contextmanager
        def fake_runtime_client():
            yield sentinel_client

        def fake_run(generator, client):
            captured["client"] = client
            captured["payload"] = generator.to_dict()
            return SimpleNamespace(task_id="task-456", final_unit_deduction=1.0)

        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes.AdvancedCustomElements, "run", fake_run):
                kling_nodes.AdvancedCustomElementCreateNode().create(
                    element_type="video_character",
                    element_name="actor",
                    element_description="Character reference",
                    video_url=" https://example.com/reference.mp4 ",
                )

        self.assertEqual(
            captured["payload"],
            {
                "reference_type": "video_refer",
                "element_video_list": {
                    "refer_videos": [{"video_url": "https://example.com/reference.mp4"}],
                },
                "element_name": "actor",
                "element_description": "Character reference",
            },
        )
        self.assertIs(captured["client"], sentinel_client)

    def test_preview_video_returns_local_video_url_when_saved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            with mock.patch.object(kling_nodes.folder_paths, "get_output_directory", return_value=str(tmpdir_path)):
                with mock.patch.object(
                    kling_nodes.folder_paths,
                    "get_save_image_path",
                    return_value=(str(tmpdir_path), "timeline", 1, "video", None),
                ) as save_path_mock:
                    with mock.patch.object(kling_nodes, "_fetch_image", return_value=b"video-bytes"):
                        with mock.patch.object(kling_nodes, "_register_output_asset"):
                            result = kling_nodes.PreviewVideo().run(
                                "https://example.com/video.mp4",
                            )

        save_path_mock.assert_called_once_with(kling_nodes.DEFAULT_VIDEO_FILENAME_PREFIX, str(tmpdir_path))
        self.assertEqual(
            result["ui"]["video_url"],
            ["/api/view?type=output&filename=timeline_00001_.mp4&subfolder=video"],
        )
        self.assertEqual(
            result["ui"]["images"][0]["filename"],
            "timeline_00001_.mp4",
        )
        self.assertEqual(result["ui"]["images"][0]["subfolder"], "video")

    def test_preview_video_filename_controls_are_not_user_toggleable(self):
        required = kling_nodes.PreviewVideo.INPUT_TYPES()["required"]

        self.assertNotIn("save_output", required)
        self.assertNotIn("filename_prefix", required)

    def test_preview_video_registers_saved_file_as_asset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            with mock.patch.object(kling_nodes.folder_paths, "get_output_directory", return_value=str(tmpdir_path)):
                with mock.patch.object(
                    kling_nodes.folder_paths,
                    "get_save_image_path",
                    return_value=(str(tmpdir_path), "timeline", 1, "video", None),
                ):
                    with mock.patch.object(kling_nodes, "_fetch_image", return_value=b"video-bytes"):
                        with mock.patch.object(kling_nodes, "_register_output_asset") as register_mock:
                            result = kling_nodes.PreviewVideo().run(
                                "https://example.com/video.mp4",
                            )

        register_mock.assert_called_once_with(result["result"][0])

    def test_preview_video_skips_missing_asset_ingest_function(self):
        fake_app_module = ModuleType("app")
        fake_assets_module = ModuleType("app.assets")
        fake_services_module = ModuleType("app.assets.services")
        fake_ingest_module = ModuleType("app.assets.services.ingest")
        fake_ingest_module.ingest_existing_file = None

        with mock.patch.dict(
            sys.modules,
            {
                "app": fake_app_module,
                "app.assets": fake_assets_module,
                "app.assets.services": fake_services_module,
                "app.assets.services.ingest": fake_ingest_module,
            },
        ):
            kling_nodes._register_output_asset("example.mp4")

    def test_preview_video_silences_broken_asset_ingest_function(self):
        fake_app_module = ModuleType("app")
        fake_assets_module = ModuleType("app.assets")
        fake_services_module = ModuleType("app.assets.services")
        fake_ingest_module = ModuleType("app.assets.services.ingest")

        def broken_ingest(_file_path):
            raise TypeError("'NoneType' object is not callable")

        fake_ingest_module.ingest_existing_file = broken_ingest

        with mock.patch.dict(
            sys.modules,
            {
                "app": fake_app_module,
                "app.assets": fake_assets_module,
                "app.assets.services": fake_services_module,
                "app.assets.services.ingest": fake_ingest_module,
            },
        ):
            with mock.patch("builtins.print") as print_mock:
                kling_nodes._register_output_asset("example.mp4")

        print_mock.assert_not_called()

    def test_preview_video_keeps_result_when_asset_registration_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            with mock.patch.object(kling_nodes.folder_paths, "get_output_directory", return_value=str(tmpdir_path)):
                with mock.patch.object(
                    kling_nodes.folder_paths,
                    "get_save_image_path",
                    return_value=(str(tmpdir_path), "timeline", 1, "video", None),
                ):
                    with mock.patch.object(kling_nodes, "_fetch_image", return_value=b"video-bytes"):
                        with mock.patch.object(kling_nodes, "_register_output_asset", side_effect=RuntimeError("boom")):
                            result = kling_nodes.PreviewVideo().run(
                                "https://example.com/video.mp4",
                            )

                            self.assertTrue(Path(result["result"][0]).is_file())

    def test_preview_video_rejects_empty_video_url(self):
        with self.assertRaisesRegex(
            ValueError,
            "empty video_url",
        ):
            kling_nodes.PreviewVideo().run("")

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

    def test_upload_image_batch_references_uploads_each_frame_and_removes_temp_files(self):
        uploaded_paths = []

        class FakeFrame:
            def save(self, path, format):
                self.path = path
                self.format = format
                Path(path).write_bytes(b"png-bytes")

        frames = [FakeFrame(), FakeFrame()]

        def fake_upload(path):
            uploaded_paths.append(path)
            self.assertTrue(Path(path).is_file())
            return f"https://cdn.example.com/{len(uploaded_paths)}.png"

        with mock.patch.object(kling_nodes, "_tensor2images", return_value=frames):
            with mock.patch.object(
                kling_nodes,
                "_upload_file_to_temporary_media_host",
                side_effect=fake_upload,
            ):
                urls = kling_nodes._upload_image_batch_references(object())

        self.assertEqual(
            urls,
            [
                "https://cdn.example.com/1.png",
                "https://cdn.example.com/2.png",
            ],
        )
        self.assertEqual([frame.format for frame in frames], ["PNG", "PNG"])
        self.assertTrue(all(not Path(path).exists() for path in uploaded_paths))

    def test_upload_file_to_oss_returns_signed_download_url(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "sample.mp4"
            file_path.write_bytes(b"video-bytes")

            ok_response = mock.Mock()
            ok_response.raise_for_status.return_value = None
            oss_config = {
                "scheme": "https",
                "endpoint_host": "oss-cn-hangzhou.aliyuncs.com",
                "access_key_id": "access-key-id",
                "access_key_secret": "access-key-secret",
                "bucket": "example-bucket",
                "prefix": "GouMei-Video-Cut",
                "signed_url_expires": 3600,
            }

            with mock.patch.object(kling_nodes, "_build_oss_object_key", return_value="GouMei-Video-Cut/sample.mp4"):
                with mock.patch.object(kling_nodes.time, "time", return_value=1000):
                    with mock.patch.object(kling_nodes.requests, "put", return_value=ok_response) as put_mock:
                        url = kling_nodes._upload_file_to_oss(file_path, oss_config=oss_config)

        put_mock.assert_called_once()
        self.assertEqual(
            put_mock.call_args.args[0],
            "https://example-bucket.oss-cn-hangzhou.aliyuncs.com/GouMei-Video-Cut/sample.mp4",
        )
        self.assertIn("Authorization", put_mock.call_args.kwargs["headers"])
        self.assertTrue(put_mock.call_args.kwargs["headers"]["Authorization"].startswith("OSS access-key-id:"))

        parsed_url = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed_url.query)
        self.assertEqual(parsed_url.scheme, "https")
        self.assertEqual(parsed_url.netloc, "example-bucket.oss-cn-hangzhou.aliyuncs.com")
        self.assertEqual(parsed_url.path, "/GouMei-Video-Cut/sample.mp4")
        self.assertEqual(query["OSSAccessKeyId"], ["access-key-id"])
        self.assertEqual(query["Expires"], ["4600"])
        self.assertIn("Signature", query)

    def test_oss_upload_config_reads_environment_variables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "missing-config.local.json"
            env_values = {
                **ENV_KEYS,
                "OSS_ENDPOINT": "oss-cn-hangzhou.aliyuncs.com",
                "OSS_ACCESS_KEY_ID": "access-key-id",
                "OSS_ACCESS_KEY_SECRET": "access-key-secret",
                "OSS_BUCKET": "example-bucket",
                "OSS_PREFIX": "GouMei-Video-Cut",
                "OSS_SIGNED_URL_EXPIRES": "7200",
            }

            with mock.patch.dict(os.environ, env_values, clear=False):
                with mock.patch.object(kling_nodes, "CONFIG_JSON_PATH", json_path):
                    config = kling_nodes._resolve_oss_upload_config()

        self.assertEqual(config["scheme"], "https")
        self.assertEqual(config["endpoint_host"], "oss-cn-hangzhou.aliyuncs.com")
        self.assertEqual(config["access_key_id"], "access-key-id")
        self.assertEqual(config["access_key_secret"], "access-key-secret")
        self.assertEqual(config["bucket"], "example-bucket")
        self.assertEqual(config["prefix"], "GouMei-Video-Cut")
        self.assertEqual(config["signed_url_expires"], 7200)

    def test_temporary_media_upload_falls_back_to_catbox(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "sample.mp4"
            file_path.write_bytes(b"video-bytes")

            catbox_response = mock.Mock()
            catbox_response.raise_for_status.return_value = None
            catbox_response.text = "https://files.catbox.moe/sample.mp4"

            with mock.patch.object(kling_nodes.time, "sleep"):
                with mock.patch.object(kling_nodes, "_resolve_oss_upload_config", return_value=None):
                    with mock.patch.object(
                        kling_nodes.requests,
                        "post",
                        side_effect=[
                            requests.exceptions.ConnectionError("reset"),
                            requests.exceptions.ConnectionError("reset"),
                            requests.exceptions.ConnectionError("reset"),
                            catbox_response,
                        ],
                    ) as post_mock:
                        url = kling_nodes._upload_file_to_temporary_media_host(file_path)

        self.assertEqual(url, "https://files.catbox.moe/sample.mp4")
        self.assertEqual(post_mock.call_count, 4)
        self.assertEqual(
            [call.args[0] for call in post_mock.call_args_list],
            [
                kling_nodes.TMPFILES_UPLOAD_API_URL,
                kling_nodes.TMPFILES_UPLOAD_API_URL,
                kling_nodes.TMPFILES_UPLOAD_API_URL,
                kling_nodes.CATBOX_UPLOAD_API_URL,
            ],
        )

    def test_motion_control_exposes_model_dropdown(self):
        input_types = kling_nodes.MotionControlNode.INPUT_TYPES()
        required = input_types["required"]
        model_options, metadata = required["model_name"]
        duration_options, duration_metadata = input_types["optional"]["duration"]

        self.assertEqual(model_options, kling_nodes.MOTION_CONTROL_MODELS)
        self.assertEqual(metadata["default"], "kling-v2-6")
        self.assertEqual(duration_options, kling_nodes.MOTION_CONTROL_DURATIONS)
        self.assertEqual(duration_metadata["default"], "auto")
        self.assertIn("reference_video", input_types["optional"])

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

    def test_motion_control_accepts_direct_reference_video_url(self):
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

        reference_video_url = "https://example.com/reference-motion.mp4"
        with mock.patch.object(kling_nodes, "_runtime_client", fake_runtime_client):
            with mock.patch.object(kling_nodes, "MotionControl", FakeMotionControl):
                with mock.patch.object(
                    kling_nodes,
                    "_upload_image_reference",
                    return_value="https://tmpfiles.org/dl/img/ref.png",
                ):
                    url, video_id = kling_nodes.MotionControlNode().generate(
                        model_name="kling-v2-6",
                        reference_image=object(),
                        reference_video=reference_video_url,
                        duration="5",
                    )

        self.assertEqual(url, "https://example.com/video.mp4")
        self.assertEqual(video_id, "video-123")
        self.assertEqual(FakeMotionControl.last_instance.video_url, reference_video_url)
        self.assertIs(FakeMotionControl.last_instance.seen_client, sentinel_client)

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
            if example_path.name == "18_comfyui_kling_wrapper_custom_voice_tts_preview.json":
                node_by_type = {node["type"]: node for node in data["nodes"]}
                self.assertIn("LoadAudio", node_by_type)
                self.assertIn("Comfyui-Kling-Wrapper Custom Voice Create", node_by_type)
                self.assertIn("Comfyui-Kling-Wrapper Preview Audio", node_by_type)
                self.assertNotIn("Comfyui-Kling-Wrapper TTS", node_by_type)

                custom_voice_node = node_by_type["Comfyui-Kling-Wrapper Custom Voice Create"]
                audio_input = next(
                    node_input
                    for node_input in custom_voice_node["inputs"]
                    if node_input["name"] == "audio"
                )
                self.assertIsNotNone(audio_input["link"])
                self.assertEqual(custom_voice_node["widgets_values"][1], "")

                preview_audio_node = node_by_type["Comfyui-Kling-Wrapper Preview Audio"]
                preview_audio_link = next(
                    node_input["link"]
                    for node_input in preview_audio_node["inputs"]
                    if node_input["name"] == "audio_url"
                )
                source_link = next(link for link in data["links"] if link[0] == preview_audio_link)
                self.assertEqual(source_link[2], 2)


if __name__ == "__main__":
    unittest.main()
