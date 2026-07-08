import importlib
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = REPO_ROOT.parent.parent
if str(COMFYUI_ROOT) not in sys.path:
    sys.path.insert(0, str(COMFYUI_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _install_import_stubs():
    if "torch" not in sys.modules:
        sys.modules["torch"] = types.SimpleNamespace()
    if "comfy_extras.nodes_audio" not in sys.modules:
        audio_module = types.ModuleType("comfy_extras.nodes_audio")
        audio_module.LoadAudio = object
        sys.modules["comfy_extras.nodes_audio"] = audio_module


class V3OmniVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _install_import_stubs()
        cls.capabilities = importlib.import_module("py.api.capabilities")
        cls.client_module = importlib.import_module("py.api.client")
        cls.nodes = importlib.import_module("py.nodes")
        cls.tencent_video = importlib.import_module("py.api.providers.tencent_vod.video")

    def test_v3_omni_is_visible_for_video_comparison_nodes(self):
        for model_list_name in (
                "TEXT_TO_VIDEO_MODELS",
                "IMAGE_TO_VIDEO_MODELS",
                "MULTI_IMAGE_TO_VIDEO_MODELS",
        ):
            with self.subTest(model_list_name=model_list_name):
                self.assertIn(
                    "kling-v3-omni",
                    getattr(self.capabilities, model_list_name),
                )

    def test_tencent_vod_v3_omni_model_version_matches_docs(self):
        self.assertEqual(
            self.tencent_video.TencentVodVideoProvider._resolve_model_version("kling-v3-omni"),
            "3.0-Omni",
        )

    def test_v3_omni_reference_video_capability_stays_guarded(self):
        capability = self.capabilities.validate_video_generation_request(
            task_name="image2video",
            model_name="kling-v3-omni",
            mode="pro",
            duration="5",
            has_reference_video=True,
        )

        self.assertTrue(capability["supports_reference_video"])
        self.assertTrue(capability["supports_sound"])
        self.assertTrue(capability["supports_voice_list"])

    def test_v3_omni_allows_custom_voice_with_element_list(self):
        captured_requests = []

        class FakeProvider:
            def generate_image2video(self, request):
                captured_requests.append(request)
                return SimpleNamespace(
                    url="https://example.com/video.mp4",
                    video_id="video-omni",
                    final_unit_deduction=None,
                )

            def close(self):
                pass

        with mock.patch.object(self.nodes, "_create_video_provider", return_value=FakeProvider()):
            url, video_id = self.nodes.Image2VideoNode().generate(
                model="kling-v3-omni",
                provider="official",
                prompt='The subject <<<voice_1>>> says: "Hello."',
                mode="pro",
                duration="5",
                sound="on",
                custom_voice_id="voice-custom",
                element_list=[{"element_id": "element-123"}],
            )

        self.assertEqual(url, "https://example.com/video.mp4")
        self.assertEqual(video_id, "video-omni")
        self.assertEqual(captured_requests[0].voice_list, [{"voice_id": "voice-custom"}])
        self.assertEqual(captured_requests[0].element_list, [{"element_id": "element-123"}])

    def test_custom_voice_list_builder_collects_multiple_voice_ids(self):
        voice_list, voice_list_json = self.nodes.CustomVoiceListBuilderNode().build(
            voice_1="voice-a",
            voice_2="voice-b",
            extra_voice_ids="voice-c\nvoice-d",
        )

        self.assertEqual(
            voice_list,
            [
                {"voice_id": "voice-a"},
                {"voice_id": "voice-b"},
                {"voice_id": "voice-c"},
                {"voice_id": "voice-d"},
            ],
        )
        self.assertIn("voice-d", voice_list_json)

    def test_custom_voice_list_builder_is_registered(self):
        mappings = importlib.import_module("py").NODE_CLASS_MAPPINGS
        self.assertIn("Comfyui-Kling-Wrapper Custom Voice List Builder", mappings)

    def test_official_client_supports_context_manager(self):
        client = self.client_module.Client("ak", "sk")
        with mock.patch.object(client, "close") as close_mock:
            with client as active_client:
                self.assertIs(active_client, client)

        close_mock.assert_called_once_with()

    def test_v3_omni_custom_voice_list_sends_multiple_voices(self):
        captured_requests = []

        class FakeProvider:
            def generate_image2video(self, request):
                captured_requests.append(request)
                return SimpleNamespace(
                    url="https://example.com/video.mp4",
                    video_id="video-omni",
                    final_unit_deduction=None,
                )

            def close(self):
                pass

        custom_voice_list = [
            {"voice_id": "voice-a"},
            {"voice_id": "voice-b"},
        ]
        with mock.patch.object(self.nodes, "_create_video_provider", return_value=FakeProvider()):
            self.nodes.Image2VideoNode().generate(
                model="kling-v3-omni",
                provider="official",
                prompt='<<<voice_1>>> says hello. <<<voice_2>>> replies.',
                mode="pro",
                duration="5",
                sound="on",
                custom_voice_list=custom_voice_list,
                element_list=[{"element_id": "element-123"}],
            )

        self.assertEqual(captured_requests[0].voice_list, custom_voice_list)
        self.assertEqual(captured_requests[0].element_list, [{"element_id": "element-123"}])

    def test_custom_voice_list_requires_matching_prompt_markers(self):
        with self.assertRaisesRegex(ValueError, "<<<voice_2>>>"):
            self.nodes.Image2VideoNode().generate(
                model="kling-v3-omni",
                provider="official",
                prompt="<<<voice_1>>> says hello.",
                mode="pro",
                duration="5",
                sound="on",
                custom_voice_list=[{"voice_id": "voice-a"}, {"voice_id": "voice-b"}],
            )

    def test_older_custom_voice_models_still_reject_element_list(self):
        with self.assertRaisesRegex(ValueError, "cannot be used together with element_list"):
            self.nodes.Image2VideoNode().generate(
                model="kling-v2-6",
                provider="official",
                prompt='The subject <<<voice_1>>> says: "Hello."',
                mode="pro",
                duration="5",
                sound="on",
                custom_voice_id="voice-custom",
                element_list=[{"element_id": "element-123"}],
            )

        with self.assertRaisesRegex(ValueError, "custom_voice_list cannot be used together with element_list"):
            self.nodes.Image2VideoNode().generate(
                model="kling-v2-6",
                provider="official",
                prompt='<<<voice_1>>> says hello. <<<voice_2>>> replies.',
                mode="pro",
                duration="5",
                sound="on",
                custom_voice_list=[{"voice_id": "voice-a"}, {"voice_id": "voice-b"}],
                element_list=[{"element_id": "element-123"}],
            )


if __name__ == "__main__":
    unittest.main()
