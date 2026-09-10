"""
games/game3_lightsaber_marble/config.py - 遊戲二「光劍」可調參數

【控制範圍】右手橘劍只在左半邊，左手藍劍只在右半邊；中央按球色判定。
每球 +1，錯色 -1；過關門檻依當局可得分目標的 80% 計算。

角度定義沿用 BilateralCoordinationTraining 的量測方式：0 度朝右、逆時針為正、
攻擊弧只涵蓋上半圓（弧心在畫面下方，見 scene.py 的幾何設定）。
"""

# ---- 攻擊弧幾何／控制 ----
ACTIVE_ARC_MIN_DEG = 15.0
ACTIVE_ARC_MAX_DEG = 165.0

ANGLE_SMOOTH_LERP = 0.5  # 手指指向角度平滑趨近目標值的插值係數，越大反應越快但越抖動

# 光劍打中彈珠的角度容忍值：彈珠角度跟光劍角度差在這個範圍內（而且彈珠已經
# 飛進光劍夠得到的長度內）就算打中，見 motion.py::is_marble_hit()。
# 【2026-09-09 收窄回來】前一版加大到 35 度、畫面上還疊了一個半透明扇形標示
# 判定範圍，但玩家覺得那個框框太大、要拿掉，判定範圍改成只比劍身本身寬一點
# 點就好，不再額外畫框框（劍身圖片本身的寬度已經足以代表判定範圍）。
HIT_ANGLE_TOLERANCE_DEG = 10.0

# ---- 關卡 ----
# full_arc=False 的關卡怪物只會出現在固定 lines 條賽道上（角度平均分布在攻擊弧
# 範圍內）；full_arc=True（Lv.3）則整個弧形範圍內任何角度都可能出怪，並且速度
# 會隨時間變快（見 motion.py::marble_speed_for 的漸增規則）。
# 【2026-09-09 速度整體往下調一級】原本 Lv.1 的速度移到 Lv.2，Lv.1 換一個更慢
# 的速度，讓 Lv.1 對初學者更友善。
LEVELS = [
    {
        "level_id": "lv1", "label": "Lv.1", "description": "5 條賽道",
        "lines": 5, "full_arc": False,
        "marble_speed": 4.0, "spawn_interval_range_sec": (1.0, 2.0),
        "play_time_sec": 90.0, "pass_score": 300,
    },
    {
        "level_id": "lv2", "label": "Lv.2", "description": "5 條賽道．更快",
        "lines": 5, "full_arc": False,
        "marble_speed": 6.0, "spawn_interval_range_sec": (0.8, 1.6),
        "play_time_sec": 90.0, "pass_score": 350,
    },
    {
        "level_id": "lv3", "label": "Lv.3", "description": "整個弧形出怪．會變速",
        "lines": None, "full_arc": True,
        "marble_speed": 7.0, "spawn_interval_range_sec": (0.6, 1.3),
        "play_time_sec": 90.0, "pass_score": 475,
        "speed_ramp_interval_sec": 15.0,   # 每隔這麼久速度再往上調一階
        "speed_ramp_step": 0.15,           # 每一階增加的倍率
        "speed_ramp_max_multiplier": 2.0,  # 倍率上限，避免後期快到打不到
    },
]

HIT_SCORE = 1

# ---- 幾何/視覺（跟畫面尺寸的比例，實際像素在 scene.py 依螢幕大小換算） ----
OUTER_RADIUS_RATIO = 0.42   # 攻擊弧最外圈半徑 = min(螢幕寬,高) * 這個比例
INNER_RADIUS_RATIO = 0.20   # 圓心(光劍樞紐)半徑 = 外圈半徑 * 這個比例，弾珠飛到這裡沒被打到就算漏接
MARBLE_RADIUS = 16
SABER_WIDTH = 8
