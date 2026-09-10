"""
games/game4_bilateral_press/config.py - 遊戲三「三角形」可調參數

四指伸直並同步彎動掌指關節；參數位於 common/straight_hand.py。
雙側同色：雙藍同步按壓才得分，雙紅都不按。每關 90 秒，80% 過關。
"""

# ---- 手勢判定 ----
# 食指 MCP-PIP-TIP 夾角小於這個值就算彎折成一次按壓（180 度是完全打直，越小
# 代表彎得越深）。先抓一個大概的中間值，還沒經過真人測試校準。
FINGER_BENT_MAX_DEG = 130.0

# ---- 場景/物件幾何 ----
SPAWN_Y_RATIO = 0.45   # 三角形出生點的垂直位置（畫面高度比例）
# 【2026-09-09 加大】原本 0.12 讓手把擠在畫面正中央附近，三角形沒飛多遠就到
# 判定區，畫面看起來很擠、也沒有反應空間。改成 0.40，比照 press_pin 原本手把
# 放在畫面邊緣附近（WINDOW_W 兩側各留約 120px）的配置，讓三角形有足夠的飛行
# 距離，手把也移到接近畫面邊緣的位置。
PADDLE_OFFSET_RATIO = 0.40  # 手把離畫面中線多遠（畫面寬度比例）

# 【2026-09-09 補上，修一個 bug】三角形是不是「進入判定區」原本直接沿用
# PADDLE_OFFSET_RATIO 當門檻，等於整段從手把位置到畫面邊緣都算判定區——這段
# 拉得太長，同一側前後兩組三角形常常同時都落在判定區裡，按一次壓就把兩組一起
# 判定掉（玩家會看到「打掉第一組，第二組也跟著消失」）。改成只有『非常接近
# 手把』的窄範圍才算判定區，比照 press_pin 原本 hit_zone=150px（相對於
# WINDOW_W=1280，約整個畫面寬度的 12%）抓的窄範圍，這樣同一側前後兩組同時
# 落在窄範圍內的機率非常低。
HIT_WINDOW_RATIO = 0.06  # 三角形要多接近手把（畫面寬度比例）才算進入判定區
TRIANGLE_SIZE = 32

# ---- 左右手「手把」視覺回饋 ----
# 比照 press_pin 原本 motor_plan.py 的 Paddle：畫一塊立在判定區邊界上的手把，
# 灰色底座 + 疊在底座上方的彩色「手臂」，按壓確認的瞬間手臂像壓下的槓桿一樣
# 往中線那一側甩開（PADDLE_SWING_DEG 度，持續 PADDLE_FLASH_SEC 秒）。跟舊版
# 一樣兩隻手用同一個顏色，不特別區分左右手。
LEFT_HAND_COLOR = (60, 220, 60)   # 綠色，跟 press_pin 原本手把顏色一致
RIGHT_HAND_COLOR = (60, 220, 60)
PADDLE_WIDTH = 40
PADDLE_HEIGHT = 100
PADDLE_SWING_DEG = 50.0
PADDLE_FLASH_SEC = 0.15

# ---- 關卡 ----
# distractor_ratio：新生成的三角形有多少機率是紅色（不能吃）。
LEVELS = [
    {"level_id": "lv1", "label": "Lv.1", "description": "慢速．少誘餌",
     "spawn_interval_sec": 1.6, "triangle_speed": 4.0, "distractor_ratio": 0.2,
     "duration_sec": 90.0, "pass_score": 15},
    {"level_id": "lv2", "label": "Lv.2", "description": "中速．誘餌變多",
     "spawn_interval_sec": 1.2, "triangle_speed": 5.5, "distractor_ratio": 0.4,
     "duration_sec": 90.0, "pass_score": 25},
    {"level_id": "lv3", "label": "Lv.3", "description": "快速．誘餌最多",
     "spawn_interval_sec": 0.9, "triangle_speed": 7.0, "distractor_ratio": 0.5,
     "duration_sec": 90.0, "pass_score": 35},
]
