"""
games/game1_bilateral_vertical/config.py - 遊戲零可調參數

【2026-09-07 改版】遊戲零從單純的「雙手垂直同步」改成
BilateralCoordinationTraining 原版的「16 種左右手動作組合」玩法：左右手各自
獨立做水平(H)/垂直(V)/順時針(CW)/逆時針(CCW)四種動作之一，16 種組合直接當
「關卡」選（沿用 LevelSelect 的網格版面，一次選一種來玩，不像原版可以勾選
多個輪流出題——保持最小可用，不加這層複雜度）。示範用簡單的旋轉/擺動箭頭
圖示，不做影片示範。

追蹤點沿用 BilateralCoordinationTraining 的量測方式：以手腕(landmark 0)為
原點，中指指尖(landmark 12)為追蹤點，取兩者的相對位移判斷水平/垂直擺動或
畫圓方向。
"""

# ---- 16 種動作組合（沿用 BilateralCoordinationTraining 原版的完整清單）----
# 每一項用 combo_id 當存檔用的關卡 id（歷史紀錄相容），left/right 是各自要做
# 的動作類型："H"(水平) / "V"(垂直) / "CW"(順時針) / "CCW"(逆時針)。
ACTION_SETS = [
    {"combo_id": "HH", "left": "H", "right": "H", "label": "雙手水平"},
    {"combo_id": "VV", "left": "V", "right": "V", "label": "雙手垂直"},
    {"combo_id": "VH", "left": "V", "right": "H", "label": "左垂直＋右水平"},
    {"combo_id": "HV", "left": "H", "right": "V", "label": "左水平＋右垂直"},
    {"combo_id": "CCWCW", "left": "CCW", "right": "CW", "label": "左逆＋右順"},
    {"combo_id": "CCWCCW", "left": "CCW", "right": "CCW", "label": "左逆＋右逆"},
    {"combo_id": "CWCCW", "left": "CW", "right": "CCW", "label": "左順＋右逆"},
    {"combo_id": "CWCW", "left": "CW", "right": "CW", "label": "左順＋右順"},
    {"combo_id": "VCW", "left": "V", "right": "CW", "label": "左垂直＋右順"},
    {"combo_id": "VCCW", "left": "V", "right": "CCW", "label": "左垂直＋右逆"},
    {"combo_id": "CCWV", "left": "CCW", "right": "V", "label": "左逆＋右垂直"},
    {"combo_id": "CWV", "left": "CW", "right": "V", "label": "左順＋右垂直"},
    {"combo_id": "HCCW", "left": "H", "right": "CCW", "label": "左水平＋右逆"},
    {"combo_id": "CWH", "left": "CW", "right": "H", "label": "左順＋右水平"},
    {"combo_id": "HCW", "left": "H", "right": "CW", "label": "左水平＋右順"},
    {"combo_id": "CCWH", "left": "CCW", "right": "H", "label": "左逆＋右水平"},
]

ACTION_GRID_COLUMNS = 2  # 16 個組合排成 2 欄 8 列，比照企劃給的版面

# ---- 動作偵測門檻（正規化座標，以手腕為原點量測中指指尖的相對位移）----
HORIZONTAL_AMP_ON = 0.06
HORIZONTAL_AMP_OFF = 0.025
HORIZONTAL_MIN_INTERVAL_S = 0.25

VERTICAL_AMP_ON = 0.08
VERTICAL_AMP_OFF = 0.03
VERTICAL_MIN_INTERVAL_S = 0.25

# 畫圓判定：累積「持續同方向轉動」的角度（弧度）達到這個值算完成一圈，方向
# 錯了就歸零重算。一整圈是 2π≈6.28，這裡故意設得比一整圈略小一點，讓畫得不
# 夠圓/有點抖動也能過（憑經驗抓的粗略值，還沒經過真人測試調校）。
CIRCULAR_TURN_THRESHOLD = 5.5
CIRCULAR_HISTORY_LEN = 20
# 規定要「從12點鐘方向開始」畫一圈：指尖跟12點鐘方向(手腕正上方)差在這個
# 角度以內，才會被當成一圈的起點，開始累積轉動角度；先抓一個大概值，還沒
# 經過真人測試調校。
CIRCLE_START_ANGLE_TOLERANCE_DEG = 30.0
# 圓度分數用的變異係數容忍值，見 motion.py::circle_roundness_score()。
CIRCLE_ROUNDNESS_CV_TOLERANCE = 0.5

# ---- 局內流程 ----
# PLAY_DURATION_SEC / COMPLETIONS_TO_PASS 是遊戲一（手指版，
# games/game2_finger_vertical/）透過 shared_cfg 沿用的固定時長玩法，這兩個
# 值不能動，否則會連帶改到遊戲一的時長和過關門檻。
PLAY_DURATION_SEC = 30.0
SYNC_WINDOW_SEC = 1.0       # 左右手各自完成一次動作，間隔在這之內算「同步」
COMPLETIONS_TO_PASS = 6

# 遊戲零改成不再固定時長，兩手同步完成滿這麼多組就結束（原本是玩滿
# PLAY_DURATION_SEC 秒，見上面的改版說明）。只有遊戲零自己用這個常數。
TARGET_COMPLETIONS = 10

# ---- 左右手相似度計分（套用在「雙手都是水平/垂直」跟「雙手都是畫圓」的
# 組合，混合軸向+畫圓的組合暫時還沿用舊版 ComboSyncTracker，之後再處理，
# 見 scene.py::_pair_scoring_mode()、scoring.py::RepPairSyncTracker）----
# 下面幾個容忍值都是先抓一個合理的初始值，還沒有實測校準過，玩了覺得太嚴
# 或太鬆再調：差距達到這個值，對應那一項分數就會趨近 0（不是差一點就 0 分，
# 是線性遞減）。
PAIR_START_TOLERANCE_S = 0.5       # 兩手動作開始時間差到這麼多秒，同步性分數趨近 0
PAIR_DURATION_TOLERANCE_S = 0.5    # 兩手動作花費時間差到這麼多秒，速度分數趨近 0
PAIR_PEAK_TOLERANCE_RATIO = 0.5    # 水平/垂直用：兩手幅度的相對差距到這個比例，幅度分數趨近 0
PAIR_PASS_SCORE = 60               # 10 組平均分數要達到這個門檻才算過關

# ---- 視覺 ----
LEFT_HAND_COLOR = (90, 200, 230)   # 青色
RIGHT_HAND_COLOR = (240, 150, 60)  # 橘色
HAND_MARKER_RADIUS = 22


# PDF difficulty groups; every combination remains selectable for testing.
def training_levels():
    colors = [(70, 210, 90), (240, 215, 40), (65, 160, 245), (185, 95, 235), (160, 160, 160)]
    levels = []
    for action in ACTION_SETS:
        left, right = action["left"], action["right"]
        axes = left in ("H", "V") and right in ("H", "V")
        circles = left in ("CW", "CCW") and right in ("CW", "CCW")
        difficulty = (1 if left == right else 4) if axes else ((2 if left == right else 3) if circles else 5)
        levels.append(dict(level_id=action["combo_id"], label=f"Lv.{difficulty} {action['label']}",
                           difficulty=difficulty, color=colors[difficulty-1], unlocked=True))
    return sorted(levels, key=lambda item: item["difficulty"])
