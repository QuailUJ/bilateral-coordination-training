"""
ui/theme.py - 顏色、字型、版面共用常數

pygame 畫面上的文字（跟 cv2.putText 不一樣）可以顯示中文，前提是要指定一個
含有中文字型的 .ttf/.ttc 檔案，不能用 pygame 內建預設字型（沒有中文字）。這裡
沿用舊專案 BilateralCoordinationTraining/assets/font/msjh.ttc（微軟正黑體）
的路徑慣例，部署時需要把這個字型檔複製到 NEW/assets/font/msjh.ttc。

如果字型檔還沒放好，get_font() 會印警告並退回 pygame 預設字型（會變成方塊或
無法顯示中文），方便開發過程中先跑起來，不會直接當掉。
"""

import os

import pygame

from common.paths import resource_path

FONT_PATH = resource_path(os.path.join("assets", "font", "msjh.ttc"))

# 顏色 (R, G, B) — pygame 用 RGB，跟 cv2 的 BGR 相反，寫的時候要注意別搞混。
COLOR_BG = (18, 18, 24)
COLOR_PANEL = (32, 32, 42)
COLOR_TEXT = (235, 235, 240)
COLOR_TEXT_MUTED = (150, 150, 160)
COLOR_ACCENT = (80, 160, 255)
COLOR_ACCENT_HOVER = (110, 185, 255)
COLOR_SUCCESS = (90, 200, 120)
COLOR_WARN = (230, 170, 60)
COLOR_DANGER = (220, 90, 90)

PADDING = 16
BUTTON_HEIGHT = 56

_font_cache = {}
_warned_missing_font = False


def get_font(size: int) -> pygame.font.Font:
    global _warned_missing_font
    key = size
    if key in _font_cache:
        return _font_cache[key]

    if os.path.exists(FONT_PATH):
        font = pygame.font.Font(FONT_PATH, size)
    else:
        if not _warned_missing_font:
            print(f"[ui.theme] 找不到中文字型檔: {FONT_PATH}，中文文字可能無法正確顯示。"
                  f"請把 msjh.ttc（或其他中文字型）複製到這個路徑。")
            _warned_missing_font = True
        font = pygame.font.Font(None, size)
    _font_cache[key] = font
    return font
