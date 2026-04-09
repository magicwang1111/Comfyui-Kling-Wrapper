# Comfyui-Kling-Wrapper Examples

This directory contains refreshed ComfyUI workflow JSON examples for the upgraded `Comfyui-Kling-Wrapper` node pack.

Before running the workflows:

- Fill in `access_key` and `secret_key` in the `Comfyui-Kling-Wrapper Client` node, or keep them empty and use `config.ini`.
- Replace placeholder image filenames such as `example_portrait.png`, `example_subject_a.png`, `example_cloth.png`, and `example_scene.png` with files that exist in your ComfyUI input directory.
- Replace placeholder URLs such as `https://example.com/reference-motion.mp4` with real URLs when needed.
- If `kling-v3-omni`, `kling-video-o1`, or `kling-image-o1` return `1201 model is not supported`, verify the model is enabled for your key on the active endpoint. The official docs list newer models, but the live service can lag behind rollout on some accounts.

Included files:

- `01_comfyui_kling_wrapper_image_generation_v3.json`: basic image generation using a live-tested `kling-v3` image model preset.
- `02_comfyui_kling_wrapper_text2video_v3_intelligence.json`: text-to-video using `kling-v3` intelligent multi-shot mode.
- `03_comfyui_kling_wrapper_image2video_v3.json`: single-image to video with the 3.0 video family.
- `04_comfyui_kling_wrapper_multi_images_to_video_v3.json`: multi-image identity-consistent video generation.
- `05_comfyui_kling_wrapper_text2video_v26_sound.json`: `kling-v2-6` talking-head example using the node's built-in `voice_preset` dropdown.
- `06_comfyui_kling_wrapper_advanced_element_subject_to_image2video.json`: create an advanced element and bind it into image-to-video.
- `07_comfyui_kling_wrapper_motion_control_v26.json`: motion-control workflow with reference image and reference video.
- `08_comfyui_kling_wrapper_virtual_try_on.json`: virtual try-on image workflow.
- `09_comfyui_kling_wrapper_image_expand.json`: image expansion workflow.
- `10_comfyui_kling_wrapper_video_extend_chain.json`: generate a clip and extend it.
- `11_comfyui_kling_wrapper_text_to_audio.json`: text-to-audio workflow.
- `12_comfyui_kling_wrapper_video_to_audio.json`: extract or generate audio from a video clip.
- `13_comfyui_kling_wrapper_lip_sync_from_text.json`: lip-sync workflow driven by text input.
- `14_comfyui_kling_wrapper_effects_single_image.json`: single-image effect example.
- `api_examples.py`: small Python snippets for the same upgraded API wrappers.
