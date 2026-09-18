import importlib
import sys
import unittest
from pathlib import Path
from unittest import mock

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = REPO_ROOT.parent.parent
for path in (COMFYUI_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

providers = importlib.import_module("py.api.providers")
video = importlib.import_module("py.api.providers.tencent_vod.video")


class TencentVodPollingTests(unittest.TestCase):
    def setUp(self):
        self.provider = video.TencentVodVideoProvider(providers.TencentVodVideoConfig(
            secret_id="test-id", secret_key="test-key", sub_app_id=1,
            poll_interval=1, max_wait_seconds=3,
        ))
        self.addCleanup(self.provider.close)
        self.now = 0.0
        self.clock = mock.Mock()
        self.clock.monotonic.side_effect = lambda: self.now
        self.clock.sleep.side_effect = self.advance_time
        clock_patch = mock.patch.object(video, "time", self.clock)
        clock_patch.start()
        self.addCleanup(clock_patch.stop)
        request_patch = mock.patch.object(self.provider._client, "request")
        self.request = request_patch.start()
        self.addCleanup(request_patch.stop)
        self.finished = {"AigcVideoTask": {
            "TaskId": "task-1", "Status": "FINISH", "ErrCode": 0,
            "Output": {"FileInfos": [{"FileUrl": "https://example.com/video.mp4"}]},
        }}

    def advance_time(self, seconds):
        self.now += seconds

    def test_read_timeout_retries_same_task_without_resubmitting(self):
        self.request.side_effect = [
            {"TaskId": "task-1"}, requests.exceptions.ReadTimeout("read timeout=120"),
            self.finished,
        ]

        result = self.provider._submit_video({"ModelName": "Kling"}, "image2video")

        self.assertEqual(result.task_id, "task-1")
        self.assertEqual(result.url, "https://example.com/video.mp4")
        self.assertEqual(self.request.call_args_list, [
            mock.call(video.CREATE_VIDEO_ACTION, {"ModelName": "Kling"}),
            mock.call(video.DESCRIBE_TASK_ACTION, {"TaskId": "task-1", "SubAppId": 1}),
            mock.call(video.DESCRIBE_TASK_ACTION, {"TaskId": "task-1", "SubAppId": 1}),
        ])
        self.clock.sleep.assert_called_once_with(1)

    def test_consecutive_query_timeouts_can_recover(self):
        self.request.side_effect = [
            requests.exceptions.ConnectTimeout("connect timeout"),
            requests.exceptions.ReadTimeout("read timeout"), self.finished,
        ]

        result = self.provider._wait_for_video("task-1")

        self.assertEqual(result.task_id, "task-1")
        self.assertEqual(self.request.call_count, 3)

    def test_persistent_timeout_obeys_wait_limit_and_preserves_cause(self):
        error = requests.exceptions.ReadTimeout("read timeout")
        self.request.side_effect = error

        with self.assertRaisesRegex(TimeoutError, "task-1.*3 seconds") as caught:
            self.provider._wait_for_video("task-1")

        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(self.request.call_count, 3)
        self.assertEqual(self.now, 3)

    def test_slow_timed_out_query_does_not_restart_wait_budget(self):
        def slow_query(*args):
            self.advance_time(4)
            raise requests.exceptions.ReadTimeout("read timeout")

        self.request.side_effect = slow_query

        with self.assertRaisesRegex(TimeoutError, "task-1"):
            self.provider._wait_for_video("task-1")

        self.request.assert_called_once()
        self.assertEqual(self.now, 4)

    def test_pending_task_does_not_poll_after_deadline(self):
        self.provider._config.poll_interval = 2
        self.request.return_value = {"AigcVideoTask": {"Status": "PROCESSING"}}

        with self.assertRaisesRegex(TimeoutError, "task-1"):
            self.provider._wait_for_video("task-1")

        self.assertEqual(self.request.call_count, 2)
        self.assertEqual(self.clock.sleep.call_args_list, [mock.call(2), mock.call(1)])

    def test_submission_timeout_is_not_retried(self):
        error = requests.exceptions.ReadTimeout("submission timeout")
        self.request.side_effect = error

        with self.assertRaises(requests.exceptions.ReadTimeout) as caught:
            self.provider._submit_video({}, "image2video")

        self.assertIs(caught.exception, error)
        self.request.assert_called_once_with(video.CREATE_VIDEO_ACTION, {})
        self.clock.sleep.assert_not_called()

    def test_api_error_is_not_retried(self):
        error = video.TencentVodError("AuthFailure")
        self.request.side_effect = error

        with self.assertRaises(video.TencentVodError) as caught:
            self.provider._wait_for_video("task-1")

        self.assertIs(caught.exception, error)
        self.request.assert_called_once()
        self.clock.sleep.assert_not_called()

    def test_failed_cloud_task_is_not_retried(self):
        self.request.return_value = {"AigcVideoTask": {
            "Status": "FAILED", "ErrCode": 1, "Message": "invalid input",
        }}

        with self.assertRaisesRegex(video.TencentVodError, "invalid input"):
            self.provider._wait_for_video("task-1")

        self.request.assert_called_once()
        self.clock.sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
