# Kling 4.0 独立生成节点设计

用户于 2026-10-26 批准开始。仅新增 Text2Video、Image2Video、OmniVideo 三个生成节点，分类 Kling 4.0；复用现有主体、音色列表及预览，不新增素材构建或管理节点。

三个节点仅使用文档规定的 4.0 参数：720p/1080p、自动或 3–30 秒、对应接口画幅、可选回调/外部任务 ID/水印。官方客户端直接调用，旧模型及 provider 路由不变。输出 url/video_id。

Omni 接收 reference_images 图片批次、feature_video/base_video 的 VIDEO 或 URL、额外特征视频 URL 列表、element_list、custom_voice_list。参考图编号 image_1 起；视频按 base_video、feature_video、额外特征视频顺序编号 video_1 起；主体/音色分别 element_1、voice_1 起。关键帧固定 first_frame、middle_frame_1 起、last_frame，避免影响参考图编号。图片可按官方协议用 base64，视频复用上传。

前端保留原生 prompt 文本框，增加同步彩色预览及可点击引用按钮；不用 contenteditable 替换原输入框。预览是非序列化 UI，不增加 API 输入。提示词文字通过 textContent 渲染，不解释 HTML。工作流载入/克隆、编辑及移除需正确处理。

实现新增 py/api/video_v4.py、py/nodes_v4.py、web/js/kling4References.js，在 py/__init__.py 注册。测试请求、任务状态、素材映射、旧节点兼容；提供说明及 API 工作流示例。真实生成属于另一个验收层，未运行不得声称已通过。
