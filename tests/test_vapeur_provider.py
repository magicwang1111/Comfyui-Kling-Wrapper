import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx


REPO_ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = REPO_ROOT.parent.parent
for path in (COMFYUI_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

nodes = importlib.import_module("py.nodes")
providers = importlib.import_module("py.api.providers")
vapeur = importlib.import_module("py.api.providers.vapeur")


class VapeurProviderTests(unittest.TestCase):
    def make_provider(self, handler, **overrides):
        config = providers.VapeurVideoConfig(
            api_key="secret",
            poll_interval=0.001,
            max_wait_seconds=30,
            **overrides,
        )
        provider = vapeur.VapeurVideoProvider(config)
        provider._client.close()
        provider._client = httpx.Client(
            base_url=config.base_url,
            headers={"Authorization": f"Bearer {config.api_key}"},
            transport=httpx.MockTransport(handler),
        )
        self.addCleanup(provider.close)
        return provider

    def test_text_video_uses_bearer_pascal_case_and_polls(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.path.endswith("/submit"):
                body = json.loads(request.content)
                self.assertEqual(body["Model"], "kling-v3-cn")
                self.assertEqual(body["AspectRatio"], "16:9")
                self.assertNotIn("model_name", body)
                return httpx.Response(200, json={"Response": {"JobId": "job-1"}})
            return httpx.Response(200, json={"Response": {
                "Status": "DONE",
                "ResultVideoUrl": "https://example.com/result.mp4",
                "VideoId": "video-1",
                "FinalUnitDeduction": "2",
            }})

        provider = self.make_provider(handler)
        result = provider.generate_text2video(providers.Text2VideoRequest(
            model_name="kling-v3", prompt="hello", aspect_ratio="16:9", mode="pro", duration="5"
        ))
        self.assertEqual(result.url, "https://example.com/result.mp4")
        self.assertEqual(result.video_id, "video-1")
        self.assertEqual(result.final_unit_deduction, 2.0)
        self.assertEqual(requests[0].headers["Authorization"], "Bearer secret")
        self.assertEqual(requests[1].url.path, "/v1/kling/text-to-video/describe")
        self.assertEqual(json.loads(requests[1].content), {"JobId": "job-1"})

    def test_failed_task_reports_service_details(self):
        def handler(request):
            if request.url.path.endswith("/submit"):
                return httpx.Response(200, json={"Response": {"JobId": "job-bad"}})
            return httpx.Response(200, json={"Response": {
                "Status": "FAILED", "ErrorCode": "BadInput", "ErrorMessage": "invalid image"
            }})

        provider = self.make_provider(handler)
        with self.assertRaisesRegex(vapeur.VapeurError, "BadInput.*invalid image"):
            provider.generate_image2video(providers.Image2VideoRequest(
                model_name="kling-v3", image_base64="abc"
            ))

    def test_image_video_uses_oss_urls_after_node_upload(self):
        submitted = []

        def handler(request):
            if request.url.path.endswith("/submit"):
                submitted.append(json.loads(request.content))
                return httpx.Response(200, json={"Response": {"JobId": "job-url"}})
            return httpx.Response(200, json={"Response": {
                "Status": "DONE", "ResultVideoUrl": "https://example.com/result.mp4", "VideoId": "video-url"
            }})

        provider = self.make_provider(handler)
        provider.generate_image2video(providers.Image2VideoRequest(
            model_name="kling-v3",
            prompt="move",
            image_base64=None,
            image_urls=["https://oss.example/front.png", "https://oss.example/reference.png"],
            image_tail_url="https://oss.example/tail.png",
        ))

        self.assertEqual(submitted[0]["Image"], {"Url": "https://oss.example/front.png"})
        self.assertEqual(submitted[0]["ImageList"], [
            {"Image": {"Url": "https://oss.example/reference.png"}}
        ])
        self.assertEqual(submitted[0]["ImageTail"], {"Url": "https://oss.example/tail.png"})

    def test_extended_video_methods_use_documented_paths_and_shapes(self):
        submitted = []

        def handler(request):
            body = json.loads(request.content)
            if request.url.path.endswith("/submit"):
                submitted.append((request.url.path, body))
                return httpx.Response(200, json={"Response": {"JobId": f"job-{len(submitted)}"}})
            return httpx.Response(200, json={"Response": {
                "Status": "DONE", "ResultVideoUrl": "https://example.com/video.mp4", "VideoId": "video"
            }})

        provider = self.make_provider(handler)
        provider.generate_multi_images(providers.MultiImagesToVideoRequest(
            model_name="kling-v3", image_base64_list=["one", "two"], mode="pro", duration="5"
        ))
        provider.generate_motion_control(providers.MotionControlRequest(
            model_name="kling-v2-6", image_url="https://example.com/image.png",
            video_url="https://example.com/motion.mp4", element_list=[{"element_id": "element-1"}]
        ))
        provider.generate_video_extend("video-old", "continue")
        provider.generate_multimodal_edit(providers.MultiModalVideoEditRequest(
            model_name="kling-v3", video_url="https://example.com/input.mp4",
            prompt="edit", image_base64_list=["reference"], edit_mode="base", keep_original_sound=True
        ))

        self.assertEqual([item[0] for item in submitted], [
            "/v1/kling/multi-image-to-video/submit",
            "/v1/kling/video-motion-control/submit",
            "/v1/kling/video-extend/submit",
            "/v1/kling/video-edit/submit",
        ])
        self.assertEqual(submitted[0][1]["ImageList"], [
            {"Image": {"Base64": "one"}}, {"Image": {"Base64": "two"}}
        ])
        self.assertEqual(submitted[1][1]["ElementList"], [{"ElementId": "element-1"}])
        self.assertEqual(submitted[1][1]["KeepOriginalSound"], "yes")
        self.assertEqual(submitted[2][1], {"Model": "kling-v3-cn", "VideoId": "video-old", "Prompt": "continue"})
        self.assertEqual(submitted[3][1]["ImageList"], [{"Image": {"Base64": "reference"}}])
        self.assertEqual(submitted[3][1]["ReferType"], "base")
        self.assertEqual(submitted[3][1]["Sound"], "on")

    def test_voice_and_element_endpoints_parse_results(self):
        calls = []

        def handler(request):
            body = json.loads(request.content)
            calls.append((request.url.path, body))
            if request.url.path == "/v1/kling/voices":
                return httpx.Response(200, json={"Response": {"JobId": "voice-job"}})
            if request.url.path == "/v1/kling/voices/describe":
                return httpx.Response(200, json={"Response": {"VoicesList": [{
                    "TaskId": "voice-job", "TaskStatus": "succeed",
                    "Voices": [{"VoiceId": "voice-1", "VoiceName": "Sample", "TrialUrl": "https://example.com/trial.mp3"}],
                }]}})
            if request.url.path == "/v1/kling/elements":
                return httpx.Response(200, json={"Response": {"ElementId": "element-1", "JobId": "element-job"}})
            if request.url.path == "/v1/kling/elements/describe":
                return httpx.Response(200, json={"Response": {"ElementId": "element-1", "Name": "Subject", "Status": "succeed"}})
            raise AssertionError(request.url.path)

        provider = self.make_provider(handler)
        voice = provider.create_custom_voice(providers.CustomVoiceCreateRequest(
            voice_name="Sample", voice_url="https://example.com/voice.mp3"
        ))
        element = provider.create_element(providers.AdvancedElementCreateRequest(
            element_name="Subject", element_description="A subject", reference_type="image_refer",
            element_image_list={
                "frontal_image": "front",
                "refer_images": [{"image_url": "side"}],
            },
        ))
        detail = provider.query_element("task_id", "element-1")

        self.assertEqual(voice.voice["voice_id"], "voice-1")
        self.assertEqual(element.element_id, "element-1")
        self.assertEqual(detail.element_id, "element-1")
        element_payload = next(body for path, body in calls if path == "/v1/kling/elements")
        self.assertEqual(element_payload["ElementImageList"], {
            "FrontalImage": "front", "ReferImages": [{"ImageUrl": "side"}]
        })
        self.assertEqual(element_payload["Provider"], ["kling"])

    def test_config_factory_uses_independent_vapeur_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.local.json"
            path.write_text(json.dumps({
                "provider_default": "vapeur",
                "api_key": "official-key",
                "vapeur_api_key": "vapeur-key",
                "vapeur_base_url": "https://api.vapeur.ai/",
                "vapeur_request_timeout": 91,
                "vapeur_poll_interval": 2,
                "vapeur_max_wait_seconds": 120,
            }), encoding="utf-8")
            with mock.patch.object(nodes, "CONFIG_JSON_PATH", path):
                provider = nodes._create_video_provider("vapeur")
        self.addCleanup(provider.close)
        self.assertEqual(provider._config.api_key, "vapeur-key")
        self.assertEqual(provider._config.base_url, "https://api.vapeur.ai")
        self.assertEqual(provider._config.request_timeout, 91)
        self.assertEqual(provider._config.poll_interval, 2.0)
        self.assertEqual(provider._config.max_wait_seconds, 120)

    def test_missing_vapeur_key_does_not_fall_back_to_official_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.local.json"
            path.write_text(json.dumps({"provider_default": "vapeur", "api_key": "official-key"}), encoding="utf-8")
            with mock.patch.object(nodes, "CONFIG_JSON_PATH", path):
                with mock.patch.dict("os.environ", {"VAPEUR_API_KEY": ""}, clear=False):
                    with self.assertRaisesRegex(ValueError, "Vapeur provider requires"):
                        nodes._create_video_provider("vapeur")

    def test_vapeur_rejects_documented_missing_capabilities(self):
        with mock.patch.object(nodes, "_resolve_video_provider", return_value="vapeur"):
            with self.assertRaisesRegex(ValueError, "does not support text-to-speech"):
                nodes.TTSNode().generate("hello", "voice", "en", 1.0)
            with self.assertRaisesRegex(ValueError, "no delete endpoint"):
                nodes.AdvancedCustomElementDeleteNode().delete("element-1", provider="vapeur")
            with self.assertRaisesRegex(ValueError, "requires kling-v3-omni"):
                nodes.MultiModalVideoEditNode().generate(
                    model="kling-v3-omni",
                    prompt="edit",
                    reference_video="https://example.com/video.mp4",
                    provider="vapeur",
                )


if __name__ == "__main__":
    unittest.main()
