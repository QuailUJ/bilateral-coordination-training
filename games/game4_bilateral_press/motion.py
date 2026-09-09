"""
games/game4_bilateral_press/motion.py - 純函式：手指彎曲判定

不 import pygame/cv2/mediapipe，只吃座標數字/tuple，方便單元測試（合成假的
關節點座標，不需要真的接攝影機）。

【手勢定義，比照 press_pin 原本的判定方式】手腕不用動、手指本身(MCP 那一段)
也不用動，純粹看食指有沒有彎折（PIP 關節夾角變小）就算一次按壓——不要求
手腕下壓，也不要求手指維持伸直。跟 press_pin 原本用「指尖 y 減 PIP y」比較
不同的地方是：這裡用 PIP 關節處的夾角，不是單純比較兩點的 y 座標，因為手腕/
手掌角度改變時「指尖 y 是否低於 PIP」這種寫法會失準，夾角則跟手掌朝向無關，
但判定的手勢語意（彎折食指、手不用移動）跟原版完全一致。
"""

import math


def finger_straightness_deg(mcp_xy, pip_xy, tip_xy) -> float:
    """算 PIP 關節處的夾角（度）：手指完全伸直時角度接近 180 度，彎曲時角度變小
    （完全握拳時可以趨近 0 度）。"""
    v1 = (mcp_xy[0] - pip_xy[0], mcp_xy[1] - pip_xy[1])
    v2 = (tip_xy[0] - pip_xy[0], tip_xy[1] - pip_xy[1])
    mag1 = math.hypot(*v1)
    mag2 = math.hypot(*v2)
    if mag1 == 0 or mag2 == 0:
        return 180.0  # 關節點重疊是不該發生的異常資料，防呆回傳「視為伸直」不誤觸發彎曲判定
    cos_angle = (v1[0] * v2[0] + v1[1] * v2[1]) / (mag1 * mag2)
    cos_angle = max(-1.0, min(1.0, cos_angle))
    return math.degrees(math.acos(cos_angle))


def is_finger_bent(mcp_xy, pip_xy, tip_xy, max_angle_deg: float) -> bool:
    """食指有沒有彎折到算一次按壓：PIP 關節夾角小於 max_angle_deg 就算彎曲。
    每一幀單獨判斷，不記錄歷史狀態——手指只要當下彎著就算「正在按」，跟
    press_pin 原本 hand_pressed() 的行為一致（不是按一下放開才算一次，是
    持續偵測當下的彎曲狀態）。"""
    return finger_straightness_deg(mcp_xy, pip_xy, tip_xy) <= max_angle_deg
