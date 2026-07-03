# Comfyui-Kling-Wrapper 腾讯云 Provider 改造计划 v2

## 背景修正
上一版方案默认把腾讯云 provider 当作“首版受限能力”，在 `Image2Video` / `Text2Video` 上主动禁用了不少字段。

这与当前实际需求不符：
- 用户现有流程需要继续可用
- 腾讯文档覆盖范围并不只是最小图生视频/文生视频
- 腾讯侧能力至少已经覆盖：
  - 图生视频
  - 文生视频
  - 动作控制
  - 视频延长
  - 主体管理
  - 自定义音色
  - 多模态编辑
  - 多图参考生视频

因此 v2 的目标不再是“先禁掉复杂能力”，而是：

> **优先保证腾讯 provider 不破坏现有工作流输入；在节点层保留能力，在 provider 层做精确映射与渐进增强。**

---

## 总目标

### 1. 节点层目标
对用户来说，`provider=tencent_vod` 时：
- 不应因为实现保守而丢失日常可用字段
- `Image2VideoNode` / `Text2VideoNode` 现有输入尽量保持可用
- 能力缺口优先通过“映射/透传”解决，而不是直接报不支持

### 2. 架构目标
在现有 provider 抽象上继续演进：
- `official` 路径保持现状与兼容性
- `tencent_vod` 路径单独维护腾讯请求映射
- 把腾讯特有 payload 组装逻辑从 `py/nodes.py` 逐步下沉到：
  - `py/api/providers/tencent_vod/mapping.py`
  - 后续可再拆 `capabilities.py` / `schemas.py`

### 3. 产品目标
先把 **图生视频 / 文生视频** 做到“能承接完整工作流字段”，然后再扩展到：
- MotionControl
- VideoExtend
- Subject / AdvancedCustomElements
- CustomVoice
- MultiModal Edit
- MultiImagesToVideo

---

## 当前代码现状

### 已经具备
- provider 基础目录已建立：
  - `py/api/providers/base.py`
  - `py/api/providers/official/video.py`
  - `py/api/providers/tencent_vod/video.py`
- `py/nodes.py` 已有：
  - provider 配置解析
  - provider factory
  - `Image2VideoNode` / `Text2VideoNode` provider 分发入口
- 官方路径已能通过 provider 包装调用
- 腾讯路径已经能发起 `CreateAigcVideoTask` / `DescribeTaskDetail`

### 当前问题
- 早期腾讯逻辑过于保守，仍然带有“能力先禁用”的设计痕迹
- 腾讯 payload 组装逻辑仍不够精细
- 有些字段只是粗粒度 passthrough，还未转成腾讯最终字段结构
- 图/文视频之外的腾讯能力尚未纳入 provider 化
- 当前 shell Python 环境缺少 `torch`，无法直接完整跑 pytest

---

## v2 实施原则

### 原则 1：不轻易在节点层禁用字段
除非已经确定腾讯接口确实不支持，或当前字段会构造出无效请求，否则：
- 不在节点层报“不支持”
- 先保留输入
- 再在 provider 层做映射或透传

### 原则 2：节点是通用接口，provider 负责后端差异
节点层尽量继续表达统一业务语义，例如：
- `voice_list`
- `element_list`
- `camera_control`
- `reference_video`
- `image_tail`
- `shot_type`
- `sound`

这些差异应由 provider mapping 解释为腾讯 payload。

### 原则 3：先显式映射，再保底透传
对腾讯路径分两层处理：

1. **显式映射层**
   - 明确转成腾讯结构与字段名
2. **透传层**
   - 暂未最终建模的字段先通过 `extra_payload` / `extra_output_config` 带过去

这样既不阻塞现有流程，又为后续精细化收敛留下空间。

---

## 第一阶段范围：Image2Video / Text2Video 精确映射

这是当前最高优先级。

### A. Image2Video 目标
`provider=tencent_vod` 时，至少承接以下输入：
- `model`
- `image`
- `image_tail`
- `prompt`
- `negative_prompt`
- `cfg_scale`
- `mode`
- `duration`
- `sound`
- `voice_preset` / `custom_voice_id` -> `voice_list`
- `shot_type`
- `image_list`
- `element_list`
- `reference_video`
- `camera_control`

### B. Text2Video 目标
`provider=tencent_vod` 时，至少承接以下输入：
- `model`
- `prompt`
- `negative_prompt`
- `cfg_scale`
- `mode`
- `aspect_ratio`
- `duration`
- `sound`
- `voice_preset` -> `voice_list`
- `shot_type`
- `image_list`
- `element_list`
- `reference_video`
- `camera_control`

---

## 第一阶段技术方案

### 1. request 层扩展
继续使用 `py/api/providers/base.py` 的 request dataclass，补充腾讯映射所需字段。

#### Image2VideoRequest
保留/补充：
- `image_urls`
- `image_tail_url`
- `voice_list`
- `element_list`
- `reference_video`
- `camera_control`
- `extra_payload`
- `extra_output_config`

#### Text2VideoRequest
保留/补充：
- `image_list`
- `image_urls`
- `voice_list`
- `element_list`
- `reference_video`
- `camera_control`
- `extra_payload`
- `extra_output_config`

### 2. nodes 层职责
在 `py/nodes.py`：
- 继续负责把 ComfyUI 输入转成统一 request
- 上传图片/视频引用 URL
- 组装统一业务字段
- 不负责写腾讯最终 payload 结构

### 3. mapping 层职责
新增 / 使用：
- `py/api/providers/tencent_vod/mapping.py`

职责：
- `Image2VideoRequest -> Tencent payload`
- `Text2VideoRequest -> Tencent payload`
- `FileInfos` 组装
- `OutputConfig` 组装
- `sound / voice / element / camera / shot / reference` 映射
- `extra_payload` / `extra_output_config` 合并

### 4. provider 层职责
`py/api/providers/tencent_vod/video.py` 只负责：
- 签名
- HTTP 请求
- 轮询
- 调 mapping 产出 payload
- 响应解析

避免 provider 文件同时承载过多字段组装细节。

---

## 建议的腾讯映射分层

### 一、稳定显式映射（优先完成）
这些字段应尽量直接进入腾讯固定 payload：
- `ModelVersion`
- `GenerationMode`
- `Prompt`
- `NegativePrompt`
- `OutputConfig.Duration`
- `OutputConfig.AspectRatio`
- `OutputConfig.AudioGeneration`
- `OutputConfig.CfgScale`（若腾讯结构允许）
- `FileInfos`

### 二、结构化扩展映射（阶段内完成）
这些字段先用结构化 helper 明确装入 payload：
- `VoiceList`
- `ShotType`
- `ElementList`
- `CameraControl`
- `ReferenceVideo`
- `LastFrame`
- `ImageList` / 多图参考输入

### 三、保底透传（阶段内保留）
对于暂时还无法确认最终字段位置的能力：
- 允许通过 `extra_payload` / `extra_output_config` 合并
- 等拿到腾讯完整字段说明后再收敛成显式映射

---

## 第一阶段验收标准

### 功能验收
1. `Image2VideoNode(provider=tencent_vod)` 不再因为保守实现拒绝正常字段
2. `Text2VideoNode(provider=tencent_vod)` 不再因为保守实现拒绝正常字段
3. 图生视频支持：
   - 主图
   - 参考图
   - 末帧
   - 参考视频
4. 文生视频支持：
   - prompt
   - aspect_ratio
   - duration
   - 参考图/参考视频（如果腾讯 payload 接受）
5. 音频/主体/镜头相关字段至少能进入 provider payload

### 代码验收
1. 腾讯 payload 组装逻辑主要位于 `mapping.py`
2. `nodes.py` 不再堆积大量腾讯特判
3. `video.py` 主要聚焦请求/轮询逻辑

### 测试验收
新增/修改测试覆盖：
1. provider 选项仍然暴露正确
2. official 路径不回归
3. Tencent request 不再因为这些字段直接报错：
   - `sound`
   - `voice_list`
   - `shot_type`
   - `element_list`
   - `reference_video`
   - `camera_control`
   - `image_tail`
   - `image_list`
4. `mapping.py` 的 payload 结构正确
5. `FileInfos` / `OutputConfig` / extra merge 覆盖

---

## 第二阶段范围：扩展到其他腾讯能力节点

在图/文视频映射稳定后，进入第二阶段。

### 1. MotionControl
对应当前：
- `MotionControlNode`
- `py/api/motion_control.py`

目标：
- 让腾讯 provider 能承接动作控制业务语义
- 支持参考图 + 参考视频 + 保留原声 + element_list 等

### 2. VideoExtend
对应当前：
- `VideoExtendNode`

目标：
- 把视频延长纳入 provider 分发

### 3. Subject / AdvancedCustomElements
对应当前：
- `AdvancedCustomElementCreateNode`
- `AdvancedCustomElementQueryNode`

目标：
- 腾讯主体管理能力独立 provider 化
- 支持 `element_voice_id`

### 4. CustomVoice
对应当前：
- `CustomVoiceCreateNode`
- `CustomVoiceQueryNode`
- `TTSNode`

目标：
- 让自定义音色与图/文视频 voice 逻辑衔接

### 5. MultiImagesToVideo / MultiModalEdit
目标：
- 与腾讯多图参考、多模态编辑文档对齐

---

## 风险与处理策略

### 风险 1：腾讯文档当前无法完整抓取字段细节
处理：
- 先做“统一业务语义 + 显式映射 + 保底透传”
- 等补充更精确字段说明后再收敛

### 风险 2：节点语义与腾讯字段语义不完全一致
处理：
- 在 mapping 层做适配，不在节点层改用户输入语义

### 风险 3：测试环境缺依赖
处理：
- 当前先做 `py_compile`
- 完整 pytest 需要带 ComfyUI/torch 的 Python 环境运行

---

## 推荐实施顺序

### Step 1
完成 `Image2Video` / `Text2Video` 的腾讯 mapping 精细化：
- `mapping.py` 完整接管 payload 组装
- 减少节点层硬编码腾讯逻辑

### Step 2
修正测试：
- 去掉“腾讯应拒绝工作流字段”的旧断言
- 改成“腾讯 request 能承接并构造 payload”

### Step 3
在带依赖环境跑定向测试：
- `tests/test_backend_config.py`

### Step 4
进入第二阶段节点扩展：
- MotionControl
- VideoExtend
- Subject
- Voice
- Multi-image / Multi-modal

---

## 本计划对应产物

### 文档产物
- `docs/plan-v2.md`（本文件）

### 第一阶段目标代码文件
- `py/nodes.py`
- `py/api/providers/base.py`
- `py/api/providers/tencent_vod/mapping.py`
- `py/api/providers/tencent_vod/video.py`
- `tests/test_backend_config.py`

---

## 阶段结论
v2 的核心不是“再加几个 if”，而是把腾讯云路径从“受限首版”升级为：

> **可承接现有工作流输入的正式 provider 实现**

先完成图生视频 / 文生视频的精细映射，再向动作控制、主体管理、自定义音色、多图参考等腾讯能力扩展。