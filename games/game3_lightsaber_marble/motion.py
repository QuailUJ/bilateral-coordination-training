"""
games/game3_lightsaber_marble/motion.py - 純函式：手指指向角度、攻擊區域判定、怪物出生規則

不 import pygame/cv2/mediapipe，只吃數字/tuple，方便單元測試（合成假的關節點
座標，不需要真的接攝影機）。座標一律是 (x, y) 的 tuple，y 座標往下增大
（MediaPipe 的慣例），角度計算時會自己把 y 反過來，讓角度符合一般直覺
（往上比較大）。
"""

import math
import random


def segment_angle_deg(base_xy, tip_xy) -> float:
    """算一段線段 (base -> tip) 的角度（度），0 度朝右、逆時針為正。"""
    dx = tip_xy[0] - base_xy[0]
    dy = -(tip_xy[1] - base_xy[1])  # MediaPipe y 座標往下增大，反過來才符合直覺
    return math.degrees(math.atan2(dy, dx))


def _average_angles_deg(angles_deg) -> float:
    """角度平均要先轉成單位向量加總再轉回角度，不能直接算術平均——例如 179 度
    跟 -179 度其實只差 2 度，直接加總平均會算出完全相反的方向。"""
    x = sum(math.cos(math.radians(a)) for a in angles_deg)
    y = sum(math.sin(math.radians(a)) for a in angles_deg)
    return math.degrees(math.atan2(y, x))


def hand_pointing_angle_deg(mid_base_xy, mid_tip_xy, pinky_base_xy, pinky_tip_xy) -> float:
    """手指指向角度＝中指、小指兩段角度的平均（沿用 BilateralCoordinationTraining
    的量測邏輯：兩指一起看比單一手指穩定，比較不受單一關節誤判影響）。"""
    mid_angle = segment_angle_deg(mid_base_xy, mid_tip_xy)
    pinky_angle = segment_angle_deg(pinky_base_xy, pinky_tip_xy)
    return _average_angles_deg([mid_angle, pinky_angle])


def is_within_active_arc(angle_deg, min_deg, max_deg) -> bool:
    """手指指向角度是否在攻擊弧的可動範圍內；不在範圍內時光劍應該視覺上淡出/
    不參與碰撞判定（見 scene.py），避免手放下、角度跑到奇怪方向時誤判命中。"""
    return min_deg <= angle_deg <= max_deg


def smooth_angle_towards(current_deg, target_deg, lerp_factor) -> float:
    """讓光劍角度平滑趨近偵測到的目標角度，走最短路徑（跨過 0/360 邊界時不會
    反方向繞一大圈）。lerp_factor 越接近 1 反應越快、越接近 0 越平滑但越lag。"""
    diff = (target_deg - current_deg + 180) % 360 - 180
    return current_deg + diff * lerp_factor


def is_marble_hit(marble_angle_deg, marble_distance, sword_angle_deg, sword_length,
                   angle_tolerance_deg) -> bool:
    """判斷光劍有沒有打中彈珠：彈珠角度要落在光劍角度 ± angle_tolerance_deg 以內
    （用最短角度差，不會被 0/360 邊界卡住），而且彈珠要已經飛進光劍夠得到的
    長度內（distance <= sword_length）。

    【取代原本 pygame.sprite.collide_mask 像素遮罩碰撞的原因】手部追蹤的更新
    頻率比畫面渲染慢很多，快速揮動光劍時角度可能一格影格就跳過好幾度——像素
    遮罩要求「剛好某一幀畫面上有重疊」，取樣間隔一大就容易整支劍「劃過」彈珠
    卻沒有任何一幀真的疊到像素，玩家會覺得「明明碰到了卻沒消失」。角度判定
    不依賴幀與幀之間的畫面連續性，只要彈珠此刻的角度落在容忍範圍內就算數，
    不會有這個問題。
    """
    diff = (marble_angle_deg - sword_angle_deg + 180) % 360 - 180
    return abs(diff) <= angle_tolerance_deg and marble_distance <= sword_length


def marble_spawn_angle_deg(level, arc_min_deg, arc_max_deg, rng=random.uniform) -> float:
    """決定新怪物要出現的角度。非 full_arc 關卡只在固定 `lines` 條賽道（角度平均
    分布在攻擊弧內）擇一出生；full_arc 關卡（Lv.3）整個弧形範圍內連續角度都可能
    出生。rng 讓呼叫端可以在測試時注入固定回傳值的假函式，不用真的驗證隨機性。
    """
    if level.get("full_arc"):
        return rng(arc_min_deg, arc_max_deg)

    lines = level["lines"]
    if lines <= 1:
        return (arc_min_deg + arc_max_deg) / 2.0
    step = (arc_max_deg - arc_min_deg) / (lines - 1)
    # rng(0, lines) 統一用跟 full_arc 分支一樣的 uniform(a, b) 介面（回傳 [0, lines]
    # 之間的浮點數），截斷成整數當賽道編號，避免另外要求呼叫端提供第二種介面的 rng。
    track_index = int(rng(0, lines))
    track_index = max(0, min(lines - 1, track_index))
    return arc_min_deg + step * track_index


def marble_speed_for(level, elapsed_sec) -> float:
    """怪物移動速度。非 full_arc 關卡固定；full_arc 關卡（Lv.3）隨經過時間每隔
    `speed_ramp_interval_sec` 秒往上調一階，clamp 在 `speed_ramp_max_multiplier`
    倍以內，避免後期快到理論上打不到。"""
    base = level["marble_speed"]
    if not level.get("full_arc"):
        return base
    steps = elapsed_sec // level["speed_ramp_interval_sec"]
    multiplier = 1.0 + steps * level["speed_ramp_step"]
    multiplier = min(multiplier, level["speed_ramp_max_multiplier"])
    return base * multiplier
