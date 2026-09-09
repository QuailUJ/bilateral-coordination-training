"""
common/app_context.py - 貫穿整個 App 生命週期的共用狀態

main.py 建立一次，往下傳給每個場景 (Scene)。場景可以讀/寫 current_user，但
screen/clock/camera/landmarker 這些資源只有 main.py 負責建立跟釋放。
"""

from dataclasses import dataclass
from typing import Optional

import pygame

from common.camera_hand_tracker import CameraStream


@dataclass
class AppContext:
    screen: pygame.Surface
    clock: pygame.time.Clock
    camera: CameraStream
    landmarker: object  # mediapipe.tasks.vision.HandLandmarker，型別故意不 import，避免 common 層綁死 mediapipe 版本細節
    current_user: Optional[str] = None
    camera_index: int = 0
    volume: float = 1.0
    camera_error: str = ""
    persistence: object = None

    def switch_camera(self, index):
        from common.camera_hand_tracker import open_camera
        if index == self.camera_index and self.camera.cap is not None:
            return
        cap, _ = open_camera(index=index)
        candidate = CameraStream(cap).start()
        frame, _, _ = candidate.get_next(-1, timeout=2.0)
        if frame is None:
            candidate.stop()
            cap.release()
            raise RuntimeError("攝影機沒有傳回影像，已保留原攝影機。")
        previous = self.camera
        self.camera = candidate
        self.camera_index = index
        self.camera_error = ""
        previous.stop()
        if previous.cap is not None:
            previous.cap.release()
