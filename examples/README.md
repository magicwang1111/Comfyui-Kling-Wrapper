# Comfyui-Kling-Wrapper Examples

This directory contains importable ComfyUI workflow JSON examples and small Python API snippets for `Comfyui-Kling-Wrapper`.

## Before running the workflows

- Create and fill in `config.local.json` in the repository root before importing the workflows.
- You can copy `config.example.json` in the repository root as a starting template.
- The provider is configured globally in `config.local.json` and is intentionally not exposed as a node widget. Use `"provider_default": "official"` for Kling or `"provider_default": "tencent_vod"` for Tencent VOD.
- For Tencent VOD workflows, set `provider_default` to `tencent_vod` and configure `tencent_secret_id`, `tencent_secret_key`, and `tencent_sub_app_id`, or use the `TENCENTCLOUD_SECRET_ID` and `TENCENTCLOUD_SECRET_KEY` environment variables.
- Replace placeholder filenames such as `example_portrait.png`, `example_subject_front.png`, `example_subject_ref_1.png`, `example_cloth.png`, `example_scene.png`, `example_lipsync_source.mp4`, `example_lipsync_audio.wav`, and `example_voice_reference.mp3` with files that exist in your ComfyUI input directory.
- Replace placeholder URLs such as `https://example.com/reference-motion.mp4` with real URLs when needed.
- Native preset and cloned voices are available for `kling-v2-6`; the active API rejects `voice_list` for `kling-v3`.
- `kling-v3-omni` is visible in the video generation dropdowns for comparison with `kling-v3`; `kling-video-o1` remains hidden until live endpoint support is confirmed.

## Important workflow notes

- `05_comfyui_kling_wrapper_text2video_v26_sound.json` is the native audio example and is built around `kling-v2-6`.
- `06_comfyui_kling_wrapper_advanced_element_subject_to_image2video.json` requires 1 frontal portrait plus 1-3 additional photos of the same subject. Background or scene images do not count as advanced-element reference images.
- If you need both subject binding and speech, generate the bound video first and then add speech with the lip-sync or audio nodes.
- `kling-v3-omni` can combine `custom_voice_id` or `custom_voice_list` with `element_list`; older models still keep stricter local guards.
- `Motion Control` accepts either a direct http(s) reference-video URL or uploaded/local video workflow inputs. For local media, use a video loader node that provides either `VIDEO` or `reference_video_frames` plus `reference_video_info`. Set `duration` to `auto` if you want it to match the uploaded motion reference length.
- `Lip Sync` now calls `identify-face` and `advanced-lip-sync`; leave `face_id` empty to use the first detected face.
- `Avatar` accepts one and only one of `AUDIO`, `audio_id`, `audio_file`, or `audio_url`.
- `Image2Video.custom_voice_id` is the single-custom-voice path. For multiple voices, connect `Custom Voice List Builder.custom_voice_list` to `Image2Video.custom_voice_list`, set `sound=on`, and use ordered markers such as `<<<voice_1>>>` and `<<<voice_2>>>`.

## Included files

- `01_comfyui_kling_wrapper_image_generation_v3.json`: basic image generation with a verified `kling-v3` preset.
- `02_comfyui_kling_wrapper_text2video_v3_intelligence.json`: text-to-video with `kling-v3` intelligent multi-shot mode.
- `03_comfyui_kling_wrapper_image2video_v3.json`: single-image to video using the visible 3.0-era model set.
- `04_comfyui_kling_wrapper_multi_images_to_video_v3.json`: multi-image identity-consistent video generation.
- `05_comfyui_kling_wrapper_text2video_v26_sound.json`: `kling-v2-6` talking-head example with native voice presets.
- `06_comfyui_kling_wrapper_advanced_element_subject_to_image2video.json`: advanced custom element creation plus `element_list` binding in image-to-video.
- `07_comfyui_kling_wrapper_motion_control_v26.json`: motion-control workflow centered on a reference image plus uploaded reference-video inputs.
- `08_comfyui_kling_wrapper_virtual_try_on.json`: virtual try-on image workflow.
- `09_comfyui_kling_wrapper_image_expand.json`: image expansion workflow.
- `10_comfyui_kling_wrapper_video_extend_chain.json`: clip generation followed by video extension.
- `11_comfyui_kling_wrapper_text_to_audio.json`: text-to-audio workflow.
- `12_comfyui_kling_wrapper_video_to_audio.json`: video-to-audio workflow.
- `13_comfyui_kling_wrapper_lip_sync_from_text.json`: lip-sync workflow driven by text input.
- `14_comfyui_kling_wrapper_effects_single_image.json`: single-image effects workflow.
- `15_comfyui_kling_wrapper_advanced_element_subject_with_video2audio_music.json`: advanced subject binding followed by `Video2Audio` to add generated music/ambience to the result.
- `16_comfyui_kling_wrapper_video_character_to_image2video.json`: create a `video_character` element from a public `video_url`, then bind that element into `Image2Video`.
- `17_comfyui_kling_wrapper_lip_sync_from_uploaded_audio_video.json`: advanced lip-sync workflow using direct `LoadAudio` and `LoadVideo` uploads.
- `18_comfyui_kling_wrapper_custom_voice_tts_preview.json`: create a custom voice and preview its returned `trial_url`.
- `19_comfyui_kling_wrapper_avatar_from_uploaded_audio_image.json`: create an Avatar video from one image and uploaded audio.
- `20_comfyui_kling_wrapper_custom_voice_image2video.json`: clone a voice and connect its `voice_id` to Kling v2.6 image-to-video.
- `21_tencent_vod_text2video.json`: minimal Tencent VOD text-to-video workflow.
- `22_tencent_vod_image2video.json`: minimal Tencent VOD image-to-video workflow.
- `23_tencent_vod_multi_images_to_video.json`: Tencent VOD multi-image reference generation.
- `24_tencent_vod_motion_control.json`: Tencent VOD motion-control workflow.
- `25_tencent_vod_multimodal_video_edit.json`: Tencent VOD 3.0-Omni video editing with an image reference.
- `26_tencent_vod_advanced_element_create.json`: Tencent VOD advanced subject creation.
- `27_tencent_vod_custom_voice_create.json`: Tencent VOD custom voice creation and trial preview.
- `28_comfyui_kling_wrapper_clothing_dupe.json`: official Kling Clothing Dupe workflow using uploaded video, product/model images, and BGM audio.
- `api_examples.py`: small Python snippets that mirror the same upgraded API wrappers.
