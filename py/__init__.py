from .api.capabilities import NODE_PREFIX
from .nodes_v4 import Kling4Text2Video, Kling4Image2Video, Kling4OmniVideo
from .nodes import AdvancedCustomElementCreateNode, AdvancedCustomElementDeleteNode, AdvancedCustomElementQueryNode, AvatarNode, ClothingDupeNode, CustomVoiceListBuilderNode, EffectNode, ElementListBuilderNode, \
    Image2VideoNode, ImageExpanderNode, ImageGeneratorNode, KolorsVirtualTryOnNode, LipSyncAudioInputNode, \
    LipSyncNode, LipSyncTextInputNode, MotionControlNode, MultiImagesToVideoNode, MultiModalVideoEditNode, PreviewAudio, PreviewVideo, Text2VideoNode, \
    TextToAudioNode, Video2AudioNode, VideoExtendNode, CustomVoiceCreateNode, CustomVoiceQueryNode, TTSNode


def _node_name(label):
    return f"{NODE_PREFIX} {label}"


NODE_CLASS_MAPPINGS = {
    _node_name("Kling 4.0 Text2Video"): Kling4Text2Video,
    _node_name("Kling 4.0 Image2Video"): Kling4Image2Video,
    _node_name("Kling 4.0 OmniVideo"): Kling4OmniVideo,
    _node_name("Image Generator"): ImageGeneratorNode,
    _node_name("Image Expander"): ImageExpanderNode,
    _node_name("TextToAudio"): TextToAudioNode,
    _node_name("TTS"): TTSNode,
    _node_name("Custom Voice Create"): CustomVoiceCreateNode,
    _node_name("Custom Voice Query"): CustomVoiceQueryNode,
    _node_name("Custom Voice List Builder"): CustomVoiceListBuilderNode,
    _node_name("Avatar"): AvatarNode,
    _node_name("Video2Audio"): Video2AudioNode,
    _node_name("Text2Video"): Text2VideoNode,
    _node_name("Image2Video"): Image2VideoNode,
    _node_name("Multi Images To Video"): MultiImagesToVideoNode,
    _node_name("Multi Modal Video Edit"): MultiModalVideoEditNode,
    _node_name("Virtual Try On"): KolorsVirtualTryOnNode,
    _node_name("Clothing Dupe"): ClothingDupeNode,
    _node_name("Preview Video"): PreviewVideo,
    _node_name("Preview Audio"): PreviewAudio,
    _node_name("Video Extender"): VideoExtendNode,
    _node_name("Lip Sync"): LipSyncNode,
    _node_name("Lip Sync Text Input"): LipSyncTextInputNode,
    _node_name("Lip Sync Audio Input"): LipSyncAudioInputNode,
    _node_name("Effects"): EffectNode,
    _node_name("Advanced Element Create"): AdvancedCustomElementCreateNode,
    _node_name("Advanced Element Query"): AdvancedCustomElementQueryNode,
    _node_name("Advanced Element Delete"): AdvancedCustomElementDeleteNode,
    _node_name("Element List Builder"): ElementListBuilderNode,
    _node_name("Motion Control"): MotionControlNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {key: key for key in NODE_CLASS_MAPPINGS}
