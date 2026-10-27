# Comfyui-Kling-Wrapper

Comfyui-Kling-Wrapper is a ComfyUI custom node pack for calling the Kling AI API directly inside ComfyUI.

It bundles image generation, text-to-video, image-to-video, multi-image video, advanced custom elements, motion control, advanced lip sync, Avatar image-to-video, Clothing Dupe, text/video to audio, TTS, custom voice creation, effects, virtual try-on, image expansion, and local preview helpers under the `Comfyui-Kling-Wrapper` category.

## Highlights

- Direct Kling API access from ComfyUI workflows
- New-system features such as `element_list`, advanced custom elements, reference video, and motion control
- Built-in `voice_preset` dropdown for models that support native audio generation
- Custom voice creation plus returned trial audio preview flow
- Importable example workflows in [examples/README.md](./examples/README.md)

## Current model visibility

### Kling 4.0 独立节点

新增 `Comfyui-Kling-Wrapper / Kling 4.0` 分类：`Kling 4.0 Text2Video`、`Kling 4.0 Image2Video`、`Kling 4.0 OmniVideo`。重启 ComfyUI 后刷新浏览器即可搜索到。这三个节点固定调用官方接口，使用已有官方 `api_key` 或 AK/SK 配置，不跟随 `provider_default` 切换腾讯云或 Vapeur；旧节点继续沿用原有配置。

- 清晰度为 `720p / 1080p`，时长为 `auto / 3–30` 秒；`auto` 不发送时长参数，由接口按提示词和素材决定。
- 文生支持 `21:9 / 16:9 / 9:16 / 1:1`；全能参考另支持 `adaptive`；图生按输入帧确定画幅。
- 负向要求、镜头和声音写入提示词，不提供旧版 `cfg_scale`、`negative_prompt`、`camera_control`、`sound` 控件。
- 图生及全能节点保留原生提示词文本框，下方同步显示彩色引用预览；点击彩色按钮可在光标处插入引用。预览不是文本框内语法高亮；旧版关键帧别名会在提交时转换为统一 image_N；颜色仅区分素材类型，不代表素材已经连接或验证通过。
- 全能节点直接接现有 `Element List Builder`、`Custom Voice List Builder` 输出；主体及音色仍须在对应官方账号下可用。无需新建管理或素材构建节点。
- 输出仍为 `url / video_id`，可连接现有 `Preview Video`。任务提交后记录任务 ID；查询失败时保留 ID，便于先查询任务再决定是否重新生成。

| 输入 | 提示词引用 |
|---|---|
| `first_frame` 单张首帧 | 有输入时从 `@image_1` 开始 |
| 动态 `middle_frame_1`、`middle_frame_2`… | 连接后自动增加接口，支持单张或批次；接在首帧之后，每张占用一个 `image_N` |
| `last_frame` 单张尾帧 | 接在全部中间帧之后 |
| 动态 `image_1`、`image_2`…或旧 `reference_images` 批次 | 接在全部关键帧之后，查看接口旁实际引用号；接口名不等于最终 ID |
| 视频：`base_video` 或 `base_video_url`，然后 `feature_video`，然后 `feature_video_urls` 每行一个 URL | 按上述顺序编号 `@video_1`、`@video_2`… |
| `element_list` 主体列表 | `@element_1`、`@element_2`… |
| `custom_voice_list` 音色列表 | `@voice_1`、`@voice_2`… |

所有图片统一按首帧→中间帧→尾帧→参考图顺序连续编号，未连接的图片不占号。图生和全能节点均使用 ComfyUI 原生动态中间帧接口，无需先合并 Image Batch；旧工作流已连接的 `middle_frames` 批次仍可使用，排在动态中间帧之前。例如首中尾各一张，再接两张参考图，就是 image_1 到 image_5。待编辑视频只能选择 `base_video` 或 `base_video_url` 之一；VIDEO 输入沿用现有上传服务，图片通过 base64 发送。素材数量、视频规格等服务端限制以所附 4.0 文档为准。

全能节点现使用与 Seedance 相同的动态连接交互：接上 `image_1` 后自动出现下一个图片口，接上 `feature_video_1` 后自动出现下一个特征视频口。连接口旁显示真实 `@image_N / @video_N` 引用；移除中间图片时保留接口名称，但实际图片 ID 会重新连续分配；特征视频仍保留自身接口编号。增删关键帧、改变批次张数或参考图后，请按新标签检查提示词。接入或移除 `base_video`（包括 URL）会改变特征视频的引用偏移，界面会同步提示，请对应检查提示词。`base_video` 存在时固定为 `@video_1`，第一个特征视频为 `@video_2`；不存在时第一个特征视频为 `@video_1`。

旧工作流已经连接的 `reference_images` / `feature_video` 输入仍可使用，新节点不显示这些旧输入。旧图片批次与新动态图片不能同时使用。运行前校验总素材不超过 15，图片（含首中尾帧）不超过 10、视频不超过 5、主体不超过 7、音色不超过 3。已知视频角色主体最多 3 个，与参考视频（含 base_video）合计最多 5 个；base_video 最多 1 段。前端通过本地图片解码和 Image Batch 连接推导张数（含动图）；浏览器不支持或无法读取时保持未知。其他不确定批次及其后续图片显示“待执行确定”，不猜测引用号。主体/音色列表的实际长度及素材总数以执行前校验为准。

视频校验复用上传所需的临时文件，每段只保存一次；通过文件大小和有限的容器头探测检查 MP4/MOV、300 MB、单段 3–30 秒、宽高 700–4553 px、像素面积 ≤8294400、宽高比 2:5–5:2、输入帧率 24–60 fps。全部本地视频检查完成后才上传，成功或失败均清理临时文件。校验不调用逐帧解码、帧数扫描或额外转码，也不下载或探测远程 URL。主体创建／查询结果中的已知类型和秒数会保留到 Element List Builder，用于计算视频总时长（含视频角色主体，3–30 秒），不会额外查询主体 API。这些元数据不发送到生成接口；缺少类型或时长时由服务端补充校验，已知时长之和超过 30 秒仍会提前拦截。仅输入主体 ID 的旧工作流继续可用。

兼容旧提示词：当提示词包含已连接关键帧的 `@first_frame` / `@middle_frame_N` / `@last_frame` 时，按旧命名空间一次性转换这些别名及旧参考图 `@image_N`，不会连锁替换。新提示词只使用统一 `@image_N`。如果旧工作流同时有关键帧和参考图，或旧参考图接口编号存在空洞，却只写了 `@image_N` 而没有任何旧关键帧别名，无法自动判断其含义，需手动核对并更新；不要混用新编号和旧别名。

导入示例：[文生](examples/kling4_text2video.json)、[图生](examples/kling4_image2video.json)、[全能参考](examples/kling4_omnivideo.json)。后两个示例需要在 Load Image 中选择本地图片。离线测试及本地 UI 验证不等同于真实生成成功，实际可用性取决于账号权限与官方服务。

更多完整场景：[动作参考](examples/kling4_motion_reference.json)、[编辑原视频服装](examples/kling4_video_edit.json)、[图片创建主体与音色](examples/kling4_subject_voice.json)、[视频创建主体与音色](examples/kling4_video_subject_voice.json)、[首中尾帧](examples/kling4_keyframes.json)。各例包含中文说明和已接好的输入、预览节点，替换项见 [示例说明](examples/README.md#kling-40-workflows)。

### 旧版节点模型列表

The plugin keeps the visible model dropdowns aligned with models confirmed for the active integration paths.

Visible image generation models:

- `kling-v1`
- `kling-v1-5`
- `kling-v2`
- `kling-v2-new`
- `kling-v2-1`
- `kling-v3`

Visible text-to-video models:

- `kling-v1`
- `kling-v1-6`
- `kling-v2-master`
- `kling-v2-1-master`
- `kling-v2-5-turbo`
- `kling-v2-6`
- `kling-v3`
- `kling-v3-omni`

Visible image-to-video models:

- `kling-v1`
- `kling-v1-5`
- `kling-v1-6`
- `kling-v2-master`
- `kling-v2-1`
- `kling-v2-1-master`
- `kling-v2-5-turbo`
- `kling-v2-6`
- `kling-v3`
- `kling-v3-omni`

Visible multi-image video models:

- `kling-v2-1`
- `kling-v2-5-turbo`
- `kling-v3`
- `kling-v3-omni`

Visible video generation modes:

- `std`
- `pro`
- `4k` (`kling-v3` and `kling-v3-omni` text-to-video, image-to-video, and multi-image video; the API uses `mode: "4k"`)

Documented newer models such as `kling-image-o1` and `kling-video-o1` still exist in the internal capability map, but are hidden from the UI until live endpoint support is confirmed for normal accounts.

## Important limitations

- Native 4K video output is exposed through the video `mode` dropdown. Models that do not support `mode=4k` will be rejected by the node capability checks before submission.
- Native preset and cloned voices are available for `kling-v2-6`; `Image2Video.custom_voice_id` sends cloned voice control through `voice_list`. The active API rejects this field for `kling-v3`.
- `kling-v3-omni` is visible for text-to-video, image-to-video, and multi-image video comparison. It can combine `voice_list`/`custom_voice_id` with `element_list`; reference-video requests remain guarded because native audio and `mode=4k` are rejected when `reference_video` is provided.
- `kling-video-o1` remains hidden until live endpoint support is confirmed for normal accounts.
- `Advanced Element Create` requires 1 frontal subject image plus 1-3 additional reference images of the same subject. Background images do not count as reference images.
- `Advanced Element Create` also enforces `element_name <= 20` characters and `element_description <= 100` characters.
- If you need both strong subject consistency and voiced output, the reliable flow on the current endpoint is usually: generate the bound subject video first, then add speech with `Lip Sync`, `TextToAudio`, or `Video2Audio`.

## Requirements

Before using these nodes, you need a Kling API key:

- [Kling API key documentation](https://docs.qingque.cn/d/home/eZQA6m4cRjTB1BBiE5eJ4lyvL?identityId=1oEER8VjdS8)

Python dependencies are listed in [requirements.txt](./requirements.txt).

## Installation

### Manual installation

1. Open your `ComfyUI/custom_nodes` directory.
2. Clone this repository:

   ```bash
   git clone https://github.com/magicwang1111/Comfyui-Kling-Wrapper.git
   ```

3. Install dependencies:

   Windows (portable ComfyUI):

   ```bash
   python -m pip install -r ComfyUI\custom_nodes\Comfyui-Kling-Wrapper\requirements.txt
   ```

   Linux or macOS:

   ```bash
   cd Comfyui-Kling-Wrapper
   pip install -r requirements.txt
   ```

4. Create `config.local.json` in the repository root.

   You can copy [config.example.json](./config.example.json) and fill in your Kling credentials:

   ```json
   {
     "provider_default": "official",
     "api_key": "",
     "access_key": "",
     "secret_key": "",
     "poll_interval": 1.0,
     "request_timeout": 30,
     "area": "global",
     "oss_endpoint": "",
     "oss_access_key_id": "",
     "oss_access_key_secret": "",
     "oss_bucket": "",
     "oss_prefix": "kling_uploads",
     "oss_signed_url_expires": 86400,
     "vapeur_api_key": "",
     "vapeur_base_url": "https://api.vapeur.ai",
     "vapeur_poll_interval": 5.0,
     "vapeur_request_timeout": 120,
     "vapeur_max_wait_seconds": 3600
   }
   ```

   Notes:

   - `api_key` is the newer Kling official static Bearer token. When it is set, the official client uses `Authorization: Bearer <api_key>` and does not require `access_key`/`secret_key` JWT signing.
   - `provider_default` accepts `official`, `tencent_vod`, or `vapeur`. Provider selection remains backend-only and is not stored in ComfyUI workflows.
   - Vapeur uses only `vapeur_api_key` (or `VAPEUR_API_KEY`) and never falls back to official or Tencent credentials. Its default base URL is `https://api.vapeur.ai`.
   - Vapeur model IDs are isolated from official Kling model IDs. The verified catalog currently maps `kling-v2-6` to `kling-v2-6-cn` and `kling-v3` to `kling-v3-cn`; other models fail locally instead of submitting an unauthorized task.
   - Vapeur supports Text2Video, Image2Video, Multi Images To Video, Motion Control, Video Extender, Custom Voice Create/Query, and Advanced Element Create/Query. Nodes absent from the supplied Vapeur API, plus MultiModal Video Edit (`kling-v3-omni` is unavailable), image generation, image expansion, virtual try-on, lip sync, avatar, effects, audio generation, TTS, and element deletion, fail explicitly instead of falling back to another provider.
   - `access_key` and `secret_key` remain supported for the older AK/SK signing flow.
   - `config.local.json` is ignored by git and should hold your real private keys.
   - `config.example.json` is only a template and is never read as live config.
   - Legacy [config.ini](./config.ini) is still accepted as a fallback for `KLINGAI_API_ACCESS_KEY` and `KLINGAI_API_SECRET_KEY`.

5. Restart ComfyUI and search for nodes prefixed with `Comfyui-Kling-Wrapper`.

## Node list

- `Comfyui-Kling-Wrapper Image Generator`
- `Comfyui-Kling-Wrapper Image Expander`
- `Comfyui-Kling-Wrapper Text2Video`
- `Comfyui-Kling-Wrapper Image2Video`
- `Comfyui-Kling-Wrapper Multi Images To Video`
- `Comfyui-Kling-Wrapper Virtual Try On`
- `Comfyui-Kling-Wrapper Clothing Dupe`
- `Comfyui-Kling-Wrapper Video Extender`
- `Comfyui-Kling-Wrapper Lip Sync`
- `Comfyui-Kling-Wrapper Lip Sync Text Input`
- `Comfyui-Kling-Wrapper Lip Sync Audio Input`
- `Comfyui-Kling-Wrapper Avatar`
- `Comfyui-Kling-Wrapper Effects`
- `Comfyui-Kling-Wrapper TextToAudio`
- `Comfyui-Kling-Wrapper TTS`
- `Comfyui-Kling-Wrapper Custom Voice Create`
- `Comfyui-Kling-Wrapper Custom Voice Query`
- `Comfyui-Kling-Wrapper Custom Voice List Builder`
- `Comfyui-Kling-Wrapper Video2Audio`
- `Comfyui-Kling-Wrapper Advanced Element Create`
- `Comfyui-Kling-Wrapper Advanced Element Query`
- `Comfyui-Kling-Wrapper Element List Builder`
- `Comfyui-Kling-Wrapper Motion Control`
- `Comfyui-Kling-Wrapper Preview Video`
- `Comfyui-Kling-Wrapper Preview Audio`

## Lip sync notes

`Lip Sync` now calls `/v1/videos/identify-face` followed by `/v1/videos/advanced-lip-sync`. Leave `face_id` empty to select the first detected face, or enter a returned face ID explicitly.

`Lip Sync Audio Input` accepts exactly one of a ComfyUI `AUDIO` connection, Kling `audio_id`, local `audio_file`, or public `audio_url`. ComfyUI audio supplies its duration automatically; URL, file, and ID inputs must provide `sound_end_time_ms` when the duration cannot be inferred.

`Lip Sync` accepts generated `video_id`, public `video_url`, local `video_file`, ComfyUI `VIDEO`, or `video_frames` plus `video_info` from `VHS_LoadVideo`. Local video inputs are uploaded through the same temporary media relay used by motion control.

For a Video Helper Suite workflow, connect `LoadAudio` -> `Lip Sync Audio Input.audio`, then connect `VHS_LoadVideo.IMAGE` -> `Lip Sync.video_frames` and `VHS_LoadVideo.video_info` -> `Lip Sync.video_info`.

`Lip Sync Text Input` remains supported. The node first creates preset-voice audio through `/v1/audio/tts`, then sends the resulting `audio_id` to Advanced Lip Sync.

## Avatar notes

`Avatar` calls `/v1/videos/avatar/image2video` with one ComfyUI `IMAGE` and exactly one of `AUDIO`, `audio_id`, `audio_file`, or `audio_url`. Local ComfyUI audio is validated to be between 2 and 300 seconds before submission.

## Custom voice and TTS notes

`Custom Voice Create` accepts one source at a time: a ComfyUI `AUDIO` input, a local `voice_file`, a public `voice_url`, or a Kling `video_id`. Local audio/files are uploaded through the same temporary media relay used by other media inputs.

The custom voice API returns a reusable `voice_id` plus a `trial_url` when the task succeeds. To audition the cloned voice, connect `Custom Voice Create.trial_url` or `Custom Voice Query.trial_url` directly to `Preview Audio.audio_url`.

Kling currently returns `Voice id not found` when a custom voice ID from `Custom Voice Create` is sent to `/v1/audio/tts`. Use `TTS` with official or preset voice IDs; use `trial_url` to preview custom voices.

Kling requires clean single-speaker source media between 5 and 30 seconds for voice cloning.

Connect `Custom Voice Create.voice_id` to `Image2Video.custom_voice_id` and select `kling-v2-6` to use the cloned voice. Set `mode=pro`, `sound=on`, use a 5- or 10-second duration, and reference the voice as `<<<voice_1>>>` in the prompt. Custom voice mode rejects simultaneous `voice_preset` or `element_list` input.

## Motion control notes

`Motion Control` now accepts reference video only from workflow inputs:

- `reference_video_input`: connect a node that outputs `VIDEO`
- `reference_video_frames` + `reference_video_info`: connect an uploaded video loader that outputs decoded frames plus timing metadata
- `reference_video`: pass an existing public http(s) video URL directly

Reference images and local reference videos must be reachable by Kling before generation starts. If OSS settings are present in `config.local.json` or environment variables (`OSS_ENDPOINT`, `OSS_ACCESS_KEY_ID`, `OSS_ACCESS_KEY_SECRET`, `OSS_BUCKET`, `OSS_PREFIX`), the wrapper uploads media to Aliyun OSS first and sends Kling a signed temporary download URL. Without OSS, it falls back to public temporary hosts: `tmpfiles.org`, then `catbox.moe`.

The visible `model_name` dropdown for motion control is:

- `kling-v2-6`
- `kling-v3`

`duration` is now a dropdown with:

- `auto`
- `3`
- `5`
- `10`
- `15`
- `30`

When `duration` is set to `auto`, the node tries to match the uploaded reference video's duration using the connected video metadata or the `VIDEO` input object.

`character_orientation` controls whether subject orientation follows the reference image or the reference video:

- `image`: keep orientation from the reference image while transferring motion from the video
- `video`: follow both motion and orientation from the reference video

## Voice presets

`Text2Video` and `Image2Video` expose a `voice_preset` dropdown. `Image2Video` additionally accepts a connected `custom_voice_id` for one custom voice, or a connected `custom_voice_list` from `Custom Voice List Builder` for multiple custom voices.

The selected preset is converted to:

```json
[{"voice_id":"..."}]
```

These presets are mainly intended for models that support native audio generation on the active endpoint, especially `kling-v2-6`.

For multiple custom voices, connect one or more `Custom Voice Create.voice_id` outputs to `Custom Voice List Builder`, then connect its `custom_voice_list` output to `Image2Video.custom_voice_list`. Set `sound=on` and reference each voice in order with prompt markers such as `<<<voice_1>>>` and `<<<voice_2>>>`. `custom_voice_list`, `custom_voice_id`, and `voice_preset` are mutually exclusive.

For official or manually supplied preset voice IDs, use the dedicated `TTS` node. It calls `/v1/audio/tts` and returns an `audio_url` that can be saved or previewed with `Preview Audio`.

## Clothing Dupe notes

`Clothing Dupe` calls the official Kling `POST /solutions/e-commerce/clothing_dupe` endpoint and polls `GET /solutions` until the task completes. It always uses the official Kling credentials from `config.local.json` or environment variables, regardless of `provider_default`; Tencent VOD and Vapeur are not used by this node.

Connect one ComfyUI `VIDEO`, 1-5 product images through the separate `product_image_1` ... `product_image_5` sockets, and optionally up to 5 model images through `model_image_1` ... `model_image_5` plus one `AUDIO` input for BGM. The official API accepts exactly one source video and at most one BGM audio file. The wrapper uploads these inputs through the existing OSS or temporary-media upload chain before submitting the task. Product and model images must be at least 300px in both dimensions with an aspect ratio between `1:2.5` and `2.5:1`.

The node returns the normal product-video URL, the optional watermarked URL, the task ID, and the complete task result as JSON. Connect either non-empty video URL to `Preview Video` to save and preview the generated clip.

The `voice_id` dropdown shows the official voice library with Chinese display names. The wrapper maps the selected Chinese name to Kling's required English `voice_id` before submission.

Watermark, callback URL, and external task ID controls are intentionally hidden from the ComfyUI node. Front-end workflows submit with watermark disabled and without callback or external task identifiers.

## Kling v3 Turbo notes

`kling-v3-turbo` is available in the `Text2Video` and `Image2Video` model dropdowns for the official Kling provider. It uses the newer `/text-to-video/kling-3.0-turbo`, `/image-to-video/kling-3.0-turbo`, and `/tasks` API shape with static Bearer-token auth.

With `provider_default` set to `tencent_vod`, the same model maps to Tencent VOD `ModelVersion: "3.0-turbo"`. The Tencent path supports text-to-video and single-first-frame image-to-video, and rejects subject references for this model.

The node keeps the existing front-end `mode` values for workflow compatibility:

- `std` sends `settings.resolution=720p`
- `pro` sends `settings.resolution=1080p`
- `4k` is accepted but also sends `settings.resolution=1080p`, because the v3 Turbo API currently documents only `720p` and `1080p`

Use `duration` values from `3` through `15`. For multi-shot v3 Turbo prompts, write the shot structure directly in the prompt text; the older `shot_type=intelligence`, separate `negative_prompt`, `cfg_scale`, `camera_control`, `sound`, `voice_list`, `image_list`, `element_list`, and `reference_video` controls are not sent for this model.

## Examples

Example workflows and small Python snippets live in [examples/README.md](./examples/README.md).

The workflow JSON files no longer depend on a front-end `Client` node. Prepare `config.local.json` first, then import the workflow you want to run.

## Official references

- [Kling new-system API documentation](https://docs.qingque.cn/d/home/eZQAyImcbaS0fz-8ANjXvU5ed?identityId=2E1MlYrrPk4)
- [Kling TTS API documentation](https://klingai.com/document-api/apiReference/model/TTS)
- [Kling custom voice API documentation](https://klingai.com/document-api/apiReference/model/customVoices)
- [Kling advanced lip-sync API documentation](https://klingai.com/document-api/api/video/lip-sync)
- [Kling Avatar API documentation](https://klingai.com/document-api/api/video/avatar)
- [Kling Clothing Dupe API documentation](https://klingai.com/document-api/api/ecommerce-replication/apparel)
- [Kling 3.0 custom voice documentation](https://klingai.com/document-api/api/video/3-0-omni/voice-customization)
- [Kling 3.0 Turbo text-to-video documentation](https://klingai.com/document-api/api/video/3-0-turbo/text-to-video)
- [Kling 3.0 series capability map](https://docs.qingque.cn/d/home/eZQCedMeoI1MTquS1SFRihz4S?identityId=1oEFzU43FYK)
- [Kling V2.6 API documentation](https://docs.qingque.cn/d/home/eZQB6Bbl5WgW8eIVN--duPVl1?identityId=1oEFzU43FYK)
- [Kling pricing](https://klingai.com/api/pricing)

## Notes

The nodes log `final_unit_deduction` when the API returns billing information. This is useful when checking the real unit cost of newer Kling endpoints and workflows.
