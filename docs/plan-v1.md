# Comfyui-Kling-Wrapper 腾讯云 provider 改造计划

## 目标
在节点层新增 provider 下拉（official / tencent_vod），并将腾讯云实现放入独立后端目录，避免与可灵官方实现混杂；第一版只覆盖 Image2Video 与 Text2Video。

## 现状确认
- 节点当前统一通过 `py/nodes.py` 中的 `_create_runtime_client()` / `_runtime_client()` 创建官方 `Client`，所有节点都直接实例化 `py/api/*` 下的官方请求对象后调用 `run(client)`。
- 当前配置只支持官方可灵字段：`access_key` / `secret_key` / `area` / `poll_interval` / `request_timeout`，位于 `config.local.json`。
- 现有节点范围中，Image2VideoNode 位于 `py/nodes.py:1772`，Text2VideoNode 位于 `py/nodes.py:1950`；它们都依赖 `py/api/prediction.py` 的通用轮询逻辑。
- 现有测试已覆盖配置优先级与部分节点行为，`tests/test_backend_config.py` 适合作为新增 provider 配置与节点切换测试入口。

## 第一版范围（已确认）
仅改造：
1. Image2Video
2. Text2Video

MotionControl、VideoExtend、主体管理、自定义音色、多模态编辑、多图参考放到后续迭代，复用本次 provider 架构。

## 目录与分层方案
新增独立 provider 目录，避免官方与腾讯云代码混放：
- `py/api/providers/__init__.py`
- `py/api/providers/base.py`：定义 provider 抽象接口/基础结果结构
- `py/api/providers/official/`：包装现有官方 Client 与请求对象（尽量薄封装）
- `py/api/providers/tencent_vod/`：腾讯云 VOD 的签名、提交、轮询、URL 输入构造

建议在节点层不要直接感知腾讯云细节，只通过 provider 工厂拿到统一后端对象。

## 配置方案
扩展 `D:/ComfyUI/custom_nodes/Comfyui-Kling-Wrapper/config.local.json`，保留现有官方字段，同时新增腾讯云字段：
- `provider_default`（可选，默认 official）
- `tencent_secret_id`
- `tencent_secret_key`
- `tencent_region`
- `tencent_sub_app_id`
- `tencent_poll_interval`
- `tencent_request_timeout`
- 复用现有 OSS 字段作为腾讯云 URL 输入上传配置

原则：
- 官方配置与腾讯云配置并存
- provider 选 official 时只校验官方字段
- provider 选 tencent_vod 时只校验腾讯云字段 + 必要 OSS 字段

## 节点层改造
### Image2VideoNode
新增 `provider` 下拉：
- `official`
- `tencent_vod`

行为：
- official：走现有 `Image2Video` 请求对象，保持原行为不变
- tencent_vod：走腾讯云 provider，节点输入仍尽量沿用当前图生视频字段，但第一版只映射腾讯云已验证稳定的最小集：
  - image
  - prompt
  - duration
  - mode（映射到腾讯云 generation mode / 或保守默认）
  - aspect ratio（按腾讯云支持范围约束）
  - sound（先按腾讯云支持情况做显式限制）

### Text2VideoNode
同样新增 `provider` 下拉，并分支到官方 / 腾讯云实现。

## 腾讯云 provider 第一版能力映射
优先做“能稳定跑通且不歧义”的映射：
- 提交：CreateAigcVideoTask
- 输入：优先走 OSS URL（已验证通）
- 输出：统一返回 `(url, video_id)`，与当前节点一致
- 轮询：DescribeTaskDetail，直到终态

第一版保守处理：
- 默认最低成本：3s / 720P / Standard / Temporary / Audio Disabled
- 某些官方高级能力（camera_control、element_list、voice_list、多图、多主体等）先在腾讯云 provider 下禁用或报清晰错误，避免“节点看起来能填、后端却不支持”的混乱

## 能力与校验策略
不要直接复用现有 `capabilities.py` 里的官方 capability 作为腾讯云 capability。建议：
- 保留现有官方 capability 不动
- 新增腾讯云 capability/映射模块，例如：
  - `py/api/providers/tencent_vod/capabilities.py`
- 节点根据 provider 选择不同的校验/参数规范

这样后续新增腾讯云动作控制等能力时，不会把官方规则与腾讯云规则缠在一起。

## 测试计划
新增/补充测试：
1. 配置读取
   - official 配置仍兼容
   - tencent_vod 配置能独立解析
2. 节点输入
   - Image2Video / Text2Video 暴露 provider 选项
3. provider 分发
   - provider=official 时继续调用官方后端
   - provider=tencent_vod 时调用腾讯云后端
4. 腾讯云 provider
   - URL 上传构造
   - 请求体映射
   - DescribeTaskDetail 轮询解析
5. 回归
   - 不传 provider 或选 official 时，现有官方行为不变

## 实施顺序
1. 抽离 provider 基础接口与工厂
2. 把官方现有路径包成 official provider（尽量不改现有请求对象）
3. 引入腾讯云 provider 的独立实现目录
4. 改造 Image2VideoNode / Text2VideoNode，新增 provider 下拉与分发
5. 扩展配置读取与测试
6. 运行定向测试，确认 official 不回归、tencent_vod 首版可用
