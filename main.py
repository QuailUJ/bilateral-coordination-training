"""
main.py - 雙側協調訓練遊戲 進入點

初始化 pygame（全螢幕）、攝影機、MediaPipe HandLandmarker，組出 AppContext，
push LoginScene 開始跑主迴圈。所有實際畫面邏輯都在 scenes/ 跟 games/ 底下，
這支檔案只負責把資源兜起來。
"""

import os
import sys

import pygame

from common.paths import resource_path
from common.camera_hand_tracker import CameraStream, GameHandLandmarker, open_camera
from common.scene_manager import SceneManager
from common.app_context import AppContext

MODEL_PATH = resource_path(os.path.join("model", "hand_landmarker.task"))


def main():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"找不到模型檔: {MODEL_PATH}\n"
            f"請確認 model/hand_landmarker.task 是否存在於這個資料夾底下。"
        )

    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass
    pygame.display.set_caption("雙側協調訓練遊戲")
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    clock = pygame.time.Clock()

    # 640x480 是實測過的甜蜜點：解析度再高對這兩顆鏡頭(外接/筆電內建)的 FPS
    # 上限沒有幫助（硬體卡在 ~30fps），維持這組設定讓偵測品質比較好。
    from data_store.settings_store import load_settings
    from common.audio import set_volume
    settings = load_settings()
    set_volume(settings["volume"])
    camera_error = ""
    try:
        cap, backend_name = open_camera(index=settings["camera_index"])
        camera = CameraStream(cap).start()
        print(f"[camera] backend={backend_name}")
    except RuntimeError as error:
        camera = CameraStream(None)
        camera_error = str(error)

    landmarker = GameHandLandmarker(MODEL_PATH, num_hands=2, try_gpu=True)
    ctx = AppContext(screen=screen, clock=clock, camera=camera, landmarker=landmarker,
                     camera_index=settings["camera_index"], volume=settings["volume"],
                     camera_error=camera_error)
    manager = SceneManager(ctx)
    from common.background_persistence import BackgroundPersistence
    ctx.persistence = BackgroundPersistence()

    from scenes.login_scene import LoginScene
    manager.push(LoginScene())

    try:
        with landmarker:
            running = True
            while running:
                dt = clock.tick(60) / 1000.0
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                        break
                    manager.handle_event(event)
                if not running or manager.is_empty:
                    break

                manager.update(dt)
                manager.draw(screen)
                pygame.display.flip()
    except SystemExit:
        pass
    finally:
        ctx.persistence.close()
        ctx.camera.stop()
        if ctx.camera.cap is not None:
            ctx.camera.cap.release()
        pygame.quit()


if __name__ == "__main__":
    main()
