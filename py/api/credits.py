# KLing AI 积分消耗表
# 数据来源：可灵AI开放平台官方定价页面
# 注意：官方可能会调整定价，请以官方最新定价为准
# Reference: https://klingai.com/api/pricing

# ===================== 视频生成积分表 =====================
# 格式：model -> mode -> duration(秒) -> 积分
VIDEO_CREDITS = {
    "kling-v1": {
        "std": {"5": 1.5, "10": 3.0},
        "pro": {"5": 3.0, "10": 6.0},
    },
    "kling-v1-5": {
        "std": {"5": 3.0, "10": 6.0},
        "pro": {"5": 6.0, "10": 12.0},
    },
    "kling-v1-6": {
        "std": {"5": 3.0, "10": 6.0},
        "pro": {"5": 6.0, "10": 12.0},
    },
    "kling-v2-master": {
        "std": {"5": 6.0, "10": 12.0},
        "pro": {"5": 10.0, "10": 20.0},
    },
    "kling-v2-1": {
        "std": {"5": 5.0, "10": 10.0},
        "pro": {"5": 10.0, "10": 20.0},
    },
    "kling-v2-1-master": {
        "std": {"5": 10.0, "10": 20.0},
        "pro": {"5": 20.0, "10": 40.0},
    },
}

# ===================== 图片生成积分表 =====================
# 每张图片消耗积分
IMAGE_CREDITS = {
    "kling-v1": 0.35,
    "kling-v1-5": 0.35,
    "kling-v2": 0.5,
    "kling-v2-new": 0.5,
    "kling-v2-1": 0.5,
}

# ===================== 虚拟试穿积分表 =====================
VIRTUAL_TRY_ON_CREDITS = {
    "kolors-virtual-try-on-v1": 0.5,
    "kolors-virtual-try-on-v1-5": 1.0,
}

# ===================== 其他功能积分 =====================
IMAGE_EXPAND_CREDITS = 1.0       # 图片扩展，每次
VIDEO_EXTEND_CREDITS = 3.0       # 视频续写（约等于原视频 kling-v1-5 std 5s）
LIP_SYNC_CREDITS = 2.0           # 口型同步，每次
VIDEO_EFFECTS_CREDITS = 3.0      # 视频特效（约等于 std 5s）
VIDEO_TO_AUDIO_CREDITS = 1.0     # 视频生音频，每次
TEXT_TO_AUDIO_CREDITS = 0.5      # 文字生音频，每次


def calc_video_credits(model: str, mode: str, duration) -> float:
    """计算视频生成（图生视频/文生视频/视频特效）的积分消耗。"""
    mode = mode or "std"
    duration_str = str(duration) if duration else "5"
    model_table = VIDEO_CREDITS.get(model, {})
    mode_table = model_table.get(mode, {})
    return mode_table.get(duration_str, None)


def calc_image_credits(model: str, image_num: int = 1) -> float:
    """计算图片生成的积分消耗。"""
    per_image = IMAGE_CREDITS.get(model, None)
    if per_image is None:
        return None
    return per_image * max(image_num or 1, 1)


def calc_virtual_try_on_credits(model_name: str) -> float:
    """计算虚拟试穿的积分消耗。"""
    return VIRTUAL_TRY_ON_CREDITS.get(model_name, None)


def log_credit(task_name: str, credits):
    """将积分消耗打印到控制台。"""
    if credits is not None:
        print(f"[KLingAI] 积分消耗 | {task_name}: {credits} 积分")
    else:
        print(f"[KLingAI] 积分消耗 | {task_name}: 未知（请参考官方定价）")
