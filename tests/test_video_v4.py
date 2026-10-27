import importlib
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT.parent.parent, ROOT):
    sys.path.insert(0, str(path))

api = importlib.import_module('py.api.video_v4')
nodes = importlib.import_module('py.nodes_v4')
_io = importlib.import_module('comfy_api.latest._io')


class Client:
    poll_interval = 0

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return next(self.responses)


class VideoV4Tests(unittest.TestCase):
    def test_text_payload_automatic_duration(self):
        payload = api.build_payload('text', '你好', '1080p', 'auto', '21:9')
        self.assertEqual(payload['prompt'], '你好')
        self.assertEqual(payload['settings'], {'resolution': '1080p', 'aspect_ratio': '21:9'})
        self.assertNotIn('contents', payload)

    def test_image_payload_and_options(self):
        frames = [{'type': 'middle_frame', 'url': 'base64', 'id': 'middle_frame_1'}]
        p = api.build_payload('image', '移动', '720p', '30', contents=frames,
                              watermark=True, callback_url='https://example.com/cb', external_task_id='ours')
        self.assertEqual(p['contents'], [{'type': 'prompt', 'text': '移动'}, *frames])
        self.assertEqual(p['settings'], {'resolution': '720p', 'duration': 30})
        self.assertEqual(p['options']['external_task_id'], 'ours')
        self.assertTrue(p['options']['watermark_info']['enabled'])

    def test_invalid_resolution_and_duplicate_ids(self):
        with self.assertRaises(ValueError):
            api.build_payload('text', 'test', '4k', '10', '16:9')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            api.build_payload('omni', 'test', '1080p', '10', 'adaptive',
                              contents=[{'type': 'voice', 'voice_id': 'x', 'id': 'v'}] * 2)

    def test_poll_and_result(self):
        client = Client([{'code': 0, 'data': {'id': 't'}},
                         {'code': 0, 'data': [{'id': 't', 'status': 'processing'}]},
                         {'code': 0, 'data': [{'id': 't', 'status': 'succeeded', 'outputs': [
                             {'type': 'image', 'url': 'wrong'},
                             {'type': 'video', 'id': 'v', 'url': 'https://example.com/v.mp4'}]}]}])
        result = api.submit_and_wait(client, 'omni', {})
        self.assertEqual((result.url, result.video_id), ('https://example.com/v.mp4', 'v'))
        self.assertEqual(client.calls[0][1], '/omni-video/kling-4.0')
        self.assertEqual(client.calls[1][2]['params'], {'task_ids': 't'})

    def test_failures_are_explicit(self):
        for task, message in [({'status': 'failed', 'message': 'bad asset'}, 'bad asset'),
                              ({'status': 'succeeded', 'outputs': []}, 'video'),
                              ({'status': 'unexpected'}, 'status')]:
            with self.subTest(task=task):
                client = Client([{'data': {'id': 't'}}, {'data': [{'id': 't', **task}]}])
                with self.assertRaisesRegex(RuntimeError, message):
                    api.submit_and_wait(client, 'text', {})

    def test_nodes_have_no_legacy_parameters_and_are_registered(self):
        package = importlib.import_module('py')
        for label, cls in [('Text2Video', nodes.Kling4Text2Video), ('Image2Video', nodes.Kling4Image2Video),
                           ('OmniVideo', nodes.Kling4OmniVideo)]:
            self.assertIs(package.NODE_CLASS_MAPPINGS['Comfyui-Kling-Wrapper Kling 4.0 ' + label], cls)
            fields = {k for group in cls.INPUT_TYPES().values() for k in group}
            self.assertFalse(fields & {'cfg_scale', 'negative_prompt', 'camera_control', 'sound', 'mode', 'model'})
            self.assertEqual(tuple(cls.RETURN_NAMES), ('url', 'video_id'))

    def test_omni_reference_mapping_and_official_client(self):
        client = Client([{'data': {'id': 't'}}, {'data': [{'id': 't', 'status': 'succeeded',
                         'outputs': [{'type': 'video', 'id': 'v', 'url': 'result'}]}]}])

        @contextmanager
        def runtime():
            yield client

        with patch.object(nodes, '_runtime_client', runtime), \
             patch.object(nodes, '_image_batch_to_base64_list', return_value=['a', 'b']):
            result = nodes.Kling4OmniVideo().generate(
                '参考 @image_1，@element_1 用 @voice_1 说话', reference_images=object(),
                base_video_url='https://example.com/base.mp4',
                feature_video_urls='https://example.com/feature.mp4',
                element_list=[{'element_id': 'e'}], custom_voice_list=[{'voice_id': 'voice'}])
        self.assertEqual(result, ('result', 'v'))
        contents = client.calls[0][2]['json']['contents'][1:]
        self.assertEqual([c['id'] for c in contents],
                         ['image_1', 'image_2', 'video_1', 'video_2', 'element_1', 'voice_1'])
        self.assertEqual(contents[-1], {'type': 'voice', 'voice_id': 'voice', 'id': 'voice_1'})

    def test_keyframes_have_stable_names(self):
        with patch.object(nodes, '_image_batch_to_base64_list', side_effect=[['a'], ['b', 'c'], ['d']]):
            frames = nodes._frames(object(), object(), object())
        self.assertEqual([f['id'] for f in frames], ['first_frame', 'middle_frame_1', 'middle_frame_2', 'last_frame'])

    def test_first_frame_batch_is_not_silently_truncated(self):
        with patch.object(nodes, '_image_batch_to_base64_list', return_value=['a', 'b']):
            with self.assertRaisesRegex(ValueError, 'single image'):
                nodes._frames(object(), None, None)

    def test_autogrow_executes_in_numeric_order_with_batches_and_gaps(self):
        for cls in (nodes.Kling4Image2Video, nodes.Kling4OmniVideo):
            with self.subTest(node=cls.__name__):
                live = {'prompt': '@image_1 to @image_5', 'first_frame': ['first'],
                        'middle_frame.middle_frame_10': ['mid10'],
                        'middle_frame.middle_frame_2': ['mid2a', 'mid2b'], 'last_frame': ['last']}
                valid, _, v3_data = _io.get_finalized_class_inputs(cls.INPUT_TYPES(), live)
                self.assertEqual(valid['optional']['middle_frame.middle_frame_10'][0], 'IMAGE')
                nested = _io.build_nested_inputs(live, v3_data)
                with patch.object(nodes, '_image_batch_to_base64_list', side_effect=lambda x: x), patch.object(nodes, '_run', return_value=('url', 'id')) as run:
                    result = cls.execute(**nested)
                contents = run.call_args.kwargs.get('contents') or run.call_args.args[5]
                self.assertEqual([c['url'] for c in contents], ['first', 'mid2a', 'mid2b', 'mid10', 'last'])
                self.assertEqual([c['id'] for c in contents], [f'image_{n}' for n in range(1, 6)])
                self.assertEqual(result.result, ('url', 'id'))

    def test_legacy_middle_batch_precedes_dynamic_middle_frames(self):
        with patch.object(nodes, '_image_batch_to_base64_list', side_effect=lambda x: x):
            frames = nodes._frames(None, ['legacy1', 'legacy2'], ['last'], {'middle_frame_1': ['new']})
        self.assertEqual([c['url'] for c in frames], ['legacy1', 'legacy2', 'new', 'last'])
        self.assertEqual([c['id'] for c in frames], ['middle_frame_1', 'middle_frame_2', 'middle_frame_3', 'last_frame'])

    def test_autogrow_can_be_empty(self):
        for cls in (nodes.Kling4Image2Video, nodes.Kling4OmniVideo):
            live = {'prompt': 'test', 'first_frame': ['first']}
            _, _, v3_data = _io.get_finalized_class_inputs(cls.INPUT_TYPES(), live)
            nested = _io.build_nested_inputs(live, v3_data)
            self.assertEqual(nested['middle_frame'], {})
            with patch.object(nodes, '_image_batch_to_base64_list', side_effect=lambda x: x), patch.object(nodes, '_run', return_value=('url', 'id')):
                self.assertEqual(cls.execute(**nested).result, ('url', 'id'))

    def test_image_requires_material(self):
        with self.assertRaisesRegex(ValueError, 'keyframe'):
            api.build_payload('image', '', '1080p', '10')

    def test_timeout_keeps_task_id(self):
        client = Client([{'data': {'id': 'recover-me'}}])
        with self.assertRaisesRegex(TimeoutError, 'recover-me'):
            api.submit_and_wait(client, 'text', {}, max_wait_seconds=0)
        self.assertEqual(len(client.calls), 1)

    def test_cancel_before_submission(self):
        client = Client([])
        def cancel():
            raise InterruptedError('cancelled')
        with self.assertRaises(InterruptedError):
            api.submit_and_wait(client, 'text', {}, interrupt_check=cancel)
        self.assertEqual(client.calls, [])

    def test_selects_matching_task_in_batch(self):
        client = Client([{'data': {'id': 'wanted'}}, {'data': [
            {'id': 'other', 'status': 'failed'},
            {'id': 'wanted', 'status': 'succeeded', 'outputs': [{'type': 'video', 'url': 'correct'}]},
        ]}])
        self.assertEqual(api.submit_and_wait(client, 'image', {}).url, 'correct')

    def test_rejects_conflicting_or_local_video_source_before_upload(self):
        with patch.object(nodes, '_upload_video_reference') as upload:
            with self.assertRaisesRegex(ValueError, 'not both'):
                nodes.Kling4OmniVideo().generate('edit', base_video=object(), base_video_url='https://example.com/v.mp4')
            with self.assertRaisesRegex(ValueError, 'HTTP'):
                nodes.Kling4OmniVideo().generate('edit', feature_video_urls='file:///C:/video.mp4')
            upload.assert_not_called()

    def test_api_error_does_not_poll_or_resubmit(self):
        client = Client([{'code': 100, 'message': 'quota exhausted'}])
        with self.assertRaisesRegex(RuntimeError, 'quota exhausted'):
            api.submit_and_wait(client, 'text', {})
        self.assertEqual(len(client.calls), 1)

    def test_polling_failure_preserves_recoverable_task_id(self):
        client = Client([{'data': {'id': 'paid-task'}}, {'code': 500, 'message': 'temporarily unavailable'}])
        with self.assertRaisesRegex(RuntimeError, 'paid-task.*before resubmitting'):
            api.submit_and_wait(client, 'text', {})
        self.assertEqual(len(client.calls), 2)


    def test_dynamic_ids_preserve_gaps(self):
        with patch.object(nodes, '_image_batch_to_base64_list', return_value=['img']), patch.object(nodes, '_upload_video_reference', return_value='url'), patch.object(nodes, '_run') as run:
            nodes.Kling4OmniVideo().generate('ref', image_2=object(), feature_video_3=object(), base_video_url='https://example.com/v.mp4')
        self.assertEqual([c['id'] for c in run.call_args.args[5]], ['image_1', 'video_1', 'video_4'])

    def test_unified_images_include_all_keyframes_and_references(self):
        with patch.object(nodes, '_image_batch_to_base64_list', side_effect=[['first'], ['mid1', 'mid2'], ['last'], ['ref']]), patch.object(nodes, '_run') as run:
            nodes.Kling4OmniVideo().generate('@image_1 到 @image_5', first_frame=object(), middle_frames=object(), last_frame=object(), image_3=object())
        contents = run.call_args.args[5]
        self.assertEqual([c['id'] for c in contents], ['image_1', 'image_2', 'image_3', 'image_4', 'image_5'])
        self.assertEqual([c['url'] for c in contents], ['first', 'mid1', 'mid2', 'last', 'ref'])

    def test_legacy_frame_aliases_and_reference_ids_convert_simultaneously(self):
        with patch.object(nodes, '_image_batch_to_base64_list', side_effect=[['first'], ['ref']]), patch.object(nodes, '_run') as run:
            nodes.Kling4OmniVideo().generate('@first_frame的人穿@image_1的衣服', first_frame=object(), image_1=object())
        self.assertEqual(run.call_args.args[1], '@image_1的人穿@image_2的衣服')

    def test_image_node_uses_unified_frame_ids(self):
        with patch.object(nodes, '_image_batch_to_base64_list', side_effect=[['first'], ['mid'], ['last']]), patch.object(nodes, '_run') as run:
            nodes.Kling4Image2Video().generate('@first_frame 到 @middle_frame_1 到 @last_frame', first_frame=object(), middle_frames=object(), last_frame=object())
        self.assertEqual(run.call_args.kwargs['contents'][2]['id'], 'image_3')
        self.assertEqual(run.call_args.args[1], '@image_1 到 @image_2 到 @image_3')

    def test_total_limit_before_upload(self):
        with patch.object(nodes, '_image_batch_to_base64_list', return_value=['img'] * 10), patch.object(nodes, '_upload_video_reference') as upload, patch.object(nodes, '_run'):
            with self.assertRaisesRegex(ValueError, '15'):
                nodes.Kling4OmniVideo().generate('ref', reference_images=object(), feature_video=object(), element_list=[{'element_id': str(i)} for i in range(5)])
            upload.assert_not_called()

    def test_keyframes_count_towards_image_limit(self):
        contents = [{'type': 'refer_image', 'url': 'img', 'id': f'image_{i}'} for i in range(10)]
        contents.append({'type': 'first_frame', 'url': 'img', 'id': 'first_frame'})
        with self.assertRaisesRegex(ValueError, '10'):
            api.build_payload('omni', '', '1080p', '10', contents=contents)

    def test_dynamic_socket_rejects_batch(self):
        with patch.object(nodes, '_image_batch_to_base64_list', return_value=['a', 'b']):
            with self.assertRaisesRegex(ValueError, 'single image'):
                nodes.Kling4OmniVideo().generate('ref', image_1=object())

if __name__ == '__main__':
    unittest.main()
