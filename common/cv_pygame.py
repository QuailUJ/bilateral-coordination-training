"""
common/cv_pygame.py - OpenCV(BGR numpy) 影格轉 pygame Surface

遊戲進行中要即時把鏡頭畫面（已經用 cv2 畫好骨架/圓點/文字標註）顯示在 pygame
視窗裡，而不是像最初的 demo 那樣開一個獨立的 cv2.imshow 視窗。
"""

import cv2
import numpy as np
import pygame


def bgr_frame_to_surface(frame_bgr: np.ndarray) -> pygame.Surface:
    """把一張 BGR (OpenCV 格式) 影格轉成 pygame.Surface。

    用 pygame.image.frombuffer 而不是 pygame.surfarray.make_surface，因為
    frombuffer 不需要額外的軸轉置，640x480/30fps 下轉換成本可忽略。
    """
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    rgb = np.ascontiguousarray(rgb)
    h, w = rgb.shape[:2]
    return pygame.image.frombuffer(rgb.tobytes(), (w, h), "RGB")
