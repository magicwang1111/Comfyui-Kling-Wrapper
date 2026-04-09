# Comfyui-Kling-Wrapper

Comfyui-Kling-Wrapper is a ComfyUI custom node pack for calling the Kling AI API directly inside ComfyUI.

It bundles image generation, text-to-video, image-to-video, multi-image video, advanced custom elements, motion control, lip sync, text/video to audio, effects, virtual try-on, image expansion, and local preview helpers under the `Comfyui-Kling-Wrapper` category.

## Highlights

- Direct Kling API access from ComfyUI workflows
- New-system features such as `element_list`, advanced custom elements, reference video, and motion control
- Built-in `voice_preset` dropdown for models that support native audio generation
- Importable example workflows in [examples/README.md](./examples/README.md)

## Current model visibility

The plugin keeps the visible model dropdowns aligned with models verified on the active endpoint.

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

Visible multi-image video models:

- `kling-v2-1`
- `kling-v2-5-turbo`
- `kling-v3`

Documented newer models such as `kling-image-o1`, `kling-video-o1`, and `kling-v3-omni` still exist in the internal capability map, but are hidden from the UI until live endpoint support is confirmed for normal accounts.

## Important limitations

- Native `sound` and `voice_preset` support is currently only verified for `kling-v2-6` on the active endpoint.
- `kling-v3`, `kling-v3-omni`, and `kling-video-o1` may appear in official docs, but the current public endpoint does not expose native sound control for them through this plugin.
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

4. Either:

   - fill `access_key` and `secret_key` directly in the `Comfyui-Kling-Wrapper Client` node, or
   - store them in [config.ini](./config.ini) and leave the node fields empty

5. Restart ComfyUI and search for nodes prefixed with `Comfyui-Kling-Wrapper`.

## Node list

- `Comfyui-Kling-Wrapper Client`
- `Comfyui-Kling-Wrapper Image Generator`
- `Comfyui-Kling-Wrapper Image Expander`
- `Comfyui-Kling-Wrapper Text2Video`
- `Comfyui-Kling-Wrapper Image2Video`
- `Comfyui-Kling-Wrapper Multi Images To Video`
- `Comfyui-Kling-Wrapper Virtual Try On`
- `Comfyui-Kling-Wrapper Video Extender`
- `Comfyui-Kling-Wrapper Lip Sync`
- `Comfyui-Kling-Wrapper Lip Sync Text Input`
- `Comfyui-Kling-Wrapper Lip Sync Audio Input`
- `Comfyui-Kling-Wrapper Effects`
- `Comfyui-Kling-Wrapper TextToAudio`
- `Comfyui-Kling-Wrapper Video2Audio`
- `Comfyui-Kling-Wrapper Advanced Element Create`
- `Comfyui-Kling-Wrapper Advanced Element Query`
- `Comfyui-Kling-Wrapper Element List Builder`
- `Comfyui-Kling-Wrapper Motion Control`
- `Comfyui-Kling-Wrapper Preview Video`
- `Comfyui-Kling-Wrapper Preview Audio`

## Voice presets

`Text2Video` and `Image2Video` expose a `voice_preset` dropdown instead of requiring manual `voice_list` JSON.

The selected preset is converted to:

```json
[{"voice_id":"..."}]
```

These presets are mainly intended for models that support native audio generation on the active endpoint, especially `kling-v2-6`.

## Examples

Example workflows and small Python snippets live in [examples/README.md](./examples/README.md).

## Official references

- [Kling new-system API documentation](https://docs.qingque.cn/d/home/eZQAyImcbaS0fz-8ANjXvU5ed?identityId=2E1MlYrrPk4)
- [Kling 3.0 series capability map](https://docs.qingque.cn/d/home/eZQCedMeoI1MTquS1SFRihz4S?identityId=1oEFzU43FYK)
- [Kling V2.6 API documentation](https://docs.qingque.cn/d/home/eZQB6Bbl5WgW8eIVN--duPVl1?identityId=1oEFzU43FYK)
- [Kling pricing](https://klingai.com/api/pricing)

## Notes

The nodes log `final_unit_deduction` when the API returns billing information. This is useful when checking the real unit cost of newer Kling endpoints and workflows.
