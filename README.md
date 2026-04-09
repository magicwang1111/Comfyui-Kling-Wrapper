# Comfyui-Kling-Wrapper

This is a custom node pack for ComfyUI that lets you call the Kling AI API directly inside ComfyUI.

The node pack has been upgraded for the new Kling API system and current 3.0-era models, including:

- Image generation: `kling-image-o1`, `kling-v3`, `kling-v3-omni`
- Video generation: `kling-v2-5-turbo`, `kling-v2-6`, `kling-video-o1`, `kling-v3`, `kling-v3-omni`
- New-system features: intelligent shot mode, reference video, element binding, motion control, and advanced custom elements

Official references:

- [Kling AI NEW API Specification](https://docs.qingque.cn/d/home/eZQDkhg4h2Qg8SEVSUTBdzYeY?identityId=2Cn18n4EIHT)
- [Kling AI Series 3.0 Model API Specification](https://docs.qingque.cn/d/home/eZQDkLsWj1-DlmBV0EQIOm9vu?identityId=2CFp2MveJ7c)
- [Kling Omni Model API Specification](https://docs.qingque.cn/d/home/eZQCRUy_LWt70n5Wz2sTiLV6J?identityId=1oEFzU43FYK)
- [Kling V2.6 Model API Specification](https://docs.qingque.cn/d/home/eZQB6Bbl5WgW8eIVN--duPVl1?identityId=1oEFzU43FYK)


## Requirements
Before using this node, you need to have [a KLing AI API key](https://docs.qingque.cn/d/home/eZQA6m4cRjTB1BBiE5eJ4lyvL?identityId=1oEER8VjdS8). 

## Installation

### Installing manually

1. Navigate to the `ComfyUI/custom_nodes` directory.

2. Clone this repository: `git clone https://github.com/KwaiVGI/ComfyUI-KLingAI-API`
  
3. Install the dependencies:
  - Windows (ComfyUI portable): `python -m pip install -r ComfyUI\custom_nodes\ComfyUI-KLingAI-API\requirements.txt`
  - Linux or MacOS: `cd ComfyUI-KLingAI-API && pip install -r requirements.txt`

4. If you don't want to expose your key, you can add it into the `config.ini` file and keep it empty in the node.

5. Start ComfyUI and search for nodes prefixed with `Comfyui-Kling-Wrapper`.

## Naming

All exported node names now use the `Comfyui-Kling-Wrapper` prefix and the category `Comfyui-Kling-Wrapper`.

## Nodes

Workflow JSON examples now live in [examples/README.md](./examples/README.md). The old screenshot-based examples have been replaced with importable ComfyUI workflows and updated Python API snippets.

### Client

This node is used to create a KLing AI client.

### Image Generator

This node is used to generate an image given a text prompt.

### Text2Video

This node is used to generate a video given a text prompt.

### Image2Video

This node is used to generate a video given an image.

### Multi Images To Video

This node is used to create a video from a batch of reference images.

### Kolors Virtual Try-On

This node is used to display the try-on effect.

### Video Extend
This node is used to extend a video.

### Lip Sync
This node is used to generate a lip sync video.

### Effects
You can achieve different special effects based on the effect_scene.

### ImageExpander

This node is used to expand a image.

###  Video2AudioNode

This node is used to generate a audio from video.

###  TextToAudioNode

This node is used to generate a audio from text.

### Advanced Element Create

Creates an advanced custom element with the new asynchronous `advanced-custom-elements` API.

### Advanced Element Query

Fetches an advanced custom element by task ID or element ID.

### Element List Builder

Builds an `element_list` payload that can be fed into the latest video-generation nodes.

### Motion Control

Creates motion-control videos with the new-system motion control API.

## Voice Presets

`Comfyui-Kling-Wrapper Text2Video` and `Comfyui-Kling-Wrapper Image2Video` now expose a `voice_preset` dropdown instead of requiring manual `voice_list` JSON input. The node sends the selected preset as:

```json
[{"voice_id":"..."}]
```

These built-in presets are intended for models that support `voice_list` on the active endpoint, and are especially useful with `kling-v2-6`:

- `Sunny`: `genshin_vindi2`
- `Sage`: `zhinen_xuesheng`
- `杩愬姩灏戝勾`: `tiyuxi_xuedi`
- `Blossom`: `ai_shatang`
- `Peppy`: `genshin_klee2`
- `鍏冩皵灏戝コ`: `guanxiaofang-v2`
- `Shine`: `ai_kaiya`
- `骞介粯灏忓摜`: `tiexin_nanyou`
- `Lyric`: `ai_chenjiahao_712`
- `鐢滅編閭诲`: `girlfriend_1_speech02`
- `Tender`: `chat1_female_new-3`
- `鑱屽満濂抽潚`: `girlfriend_2_speech02`
- `Zippy`: `cartoon-boy-07`
- `Sprite`: `cartoon-girl-01`
- `Rock`: `ai_huangyaoshi_712`
- `Helen`: `you_pingjing`
- `Titan`: `ai_laoguowang_712`
- `Grace`: `chengshu_jiejie`
- `鎱堢ゥ鐖风埛`: `zhuxi_speech02`
- `鍞犲彣鐖风埛`: `uk_oldman3`
- `Prattle`: `laopopo_speech02`
- `Hearth`: `heainainai_speech02`
- `涓滃寳鑰侀搧`: `dongbeilaotie_speech02`
- `閲嶅簡灏忎紮`: `chongqingxiaohuo_speech02`
- `鍥涘窛濡瑰瓙`: `chuanmeizi_speech02`
- `娼睍澶у彅`: `chaoshandashu_speech02`
- `鍙版咕鐢风敓`: `ai_taiwan_man2_speech02`
- `瑗垮畨鎺屾煖`: `xianzhanggui_speech02`
- `澶╂触濮愬`: `tianjinjiejie_speech02`
- `鏂伴椈鎾姤鐢穈: `diyinnansang_DB_CN_M_04-v2`
- `璇戝埗鐗囩敺`: `yizhipiannan-v1`
- `鎾掑▏濂冲弸`: `tianmeixuemei-v1`
- `鍒€鐗囩儫鍡揱: `daopianyansang-v1`
- `涔栧阀姝ｅお`: `mengwa-v1`
- `Ace`: `AOT`
- `Dove`: `genshin_kirara`
- `Anchor`: `oversea_male1`
- `Melody`: `girlfriend_4_speech02`
- `Siren`: `chat_0407_5-1`
- `Bud`: `uk_boy1`
- `Candy`: `PeppaPig_platform`
- `Beacon`: `ai_huangzhong_712`
- `Lore`: `calm_story1`
- `Crag`: `uk_man2`
- `The Reader`: `reader_en_m-v1`
- `Commercial Lady`: `commercial_lady_en_f-v1`

## Pricing

For pricing, follow [KLing AI Pricing](https://klingai.com/api/pricing). The nodes also log `final_unit_deduction` from API responses when the API returns it.
