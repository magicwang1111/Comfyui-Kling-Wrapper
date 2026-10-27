# Comfyui-Kling-Wrapper Examples

This directory contains importable ComfyUI workflow JSON examples and small Python API snippets for `Comfyui-Kling-Wrapper`.

## Before running the workflows

### Kling 4.0 workflows

将下列 JSON 拖入 ComfyUI 或使用“打开”导入。每个示例均带中文说明、已填写的提示词及接好的 `Preview Video`，无需手动接线。替换占位素材后运行会提交真实生成任务。

| 示例 | 用途 | 运行前替换 |
|---|---|---|
| [kling4_text2video.json](kling4_text2video.json) | 文生视频 | 按需要修改提示词 |
| [kling4_image2video.json](kling4_image2video.json) | 单张图片动起来 | 首帧图片 |
| [kling4_omnivideo.json](kling4_omnivideo.json) | 人物外观参考 | 参考图片 |
| [kling4_motion_reference.json](kling4_motion_reference.json) | 自己的模特参考视频动作 | 模特图片、动作视频 |
| [kling4_video_edit.json](kling4_video_edit.json) | 修改原视频中的服装 | 服装参考图、待编辑视频 |
| [kling4_subject_voice.json](kling4_subject_voice.json) | 上传素材创建主体与音色，再生成视频 | 同一人物的正面照、另一角度参考照、单人说话音频 |
| [kling4_video_subject_voice.json](kling4_video_subject_voice.json) | 上传视频创建主体，配指定音色生成视频 | 主体参考视频、单人说话音频 |
| [kling4_keyframes.json](kling4_keyframes.json) | 首、中、尾帧控制 | 三张关键帧图片 |
| [kling4_multi_reference.json](kling4_multi_reference.json) | 动态双图＋原视频＋双特征视频 | 两张图片、三段视频 |

4.0 生成节点固定使用官方配置，不受 `provider_default` 影响。**主体配音范例中的创建节点会遵循 `provider_default`，运行前请将其设为 `official`，并配置同一官方账号及素材上传服务。** 在两个 `Load Image` 中上传同一人物的正面照和另一角度参考照，在 `Load Audio` 中上传单人说话音频，修改主体名称、描述及音色名称后运行。也可在 `Load Audio` 中选择支持的视频文件，提取其音轨作为音色参考。工作流会创建主体和音色，经列表节点自动接入全能生成节点，无需手填任务 ID。

图片、视频在对应 Load 节点上传或选择即可。动作参考视频连接 `feature_video`，待编辑原视频连接 `base_video`；两个例子都只有一个视频，因此均引用 `@video_1`。所有图片共用 image_N 编号：首帧→中间帧→尾帧→普通参考图。三关键帧范例依次为 @image_1、@image_2、@image_3，新增参考图会从 @image_4 起。示例已在本地 ComfyUI 中完成导入及 API 参数导出检查，未调用付费生成接口。

全能范例现改用动态 `image_1`、`feature_video_1` 接口，接满一项自动出现下一项。多参考范例包含 `base_video = @video_1`、`feature_video_1 = @video_2`、`feature_video_2 = @video_3`；删除原视频后，需按界面新标签修改提示词中的视频引用。占位图片和视频未替换时，ComfyUI 会提示文件不存在，这是示例的待填写项。

视频主体范例使用 `Load Video → Advanced Element Create.reference_video_input`，已选择 `video_character`。首次使用新增接口前，请重启 ComfyUI 并刷新页面。连接本地视频时会自动上传，优先于 `video_url`；不连接时仍可使用视频 URL。

### Other workflows

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
