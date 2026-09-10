"""
elbow_angle_tracker.py - 即時攝影機手肘屈曲角度偵測（大手臂/小手臂骨架 + 角度顯示）

獨立小程式，沿用 common/camera_hand_tracker.py 同一套「攝影機環境」慣例：
CameraStream 背景執行緒讀攝影機、MediaPipe 偵測餵未翻轉畫面、偵測完才翻轉畫面
再疊字（避免鏡像反字），cv2.putText 不支援中文所以疊字一律用英文。

這裡改用 MediaPipe PoseLandmarker 抓身體關節點，只取左右肩、肘、腕三點畫出
上臂／前臂骨架並計算手肘屈曲角度。

手肘角度定義：使用三維世界座標，以手肘為頂點，量測向量（肘→肩）與（肘→腕）的夾角，
再用 180 度減去該夾角得到「屈曲角度」──手臂完全打直時兩向量幾乎共線（夾角
接近 180 度），算出來的屈曲角度就接近 0 度；手肘彎越多，屈曲角度越大。

直接執行：
    .venv/Scripts/python.exe elbow_angle_tracker.py
按 q 或 Esc 離開。
"""

import sys
import time
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.camera_hand_tracker import CameraStream, open_camera

MODEL_PATH = Path(__file__).resolve().parent / "model" / "pose_landmarker_full.task"

# PoseLandmarker 的身體關節點索引是依「畫面中人物自己的左右」判斷（跟
# camera_hand_tracker 的手部 handedness 判斷同一套邏輯），偵測完翻轉畫面後，
# 使用者自己的左手臂會顯示在螢幕左側，符合照鏡子的直覺，所以標籤不用再對調。
LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST = 11, 13, 15
RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST = 12, 14, 16

ARM_COLOR = (0, 230, 255)  # BGR 黃色
TEXT_COLOR = (0, 230, 255)
VISIBILITY_THRESHOLD = 0.5


def create_pose_landmarker(model_path, try_gpu=True):
    """建立 PoseLandmarker，先嘗試 GPU delegate，失敗就退回 CPU delegate
    （跟 camera_hand_tracker.create_hand_landmarker 同一套 retry 邏輯）。"""
    BaseOptions = mp.tasks.BaseOptions
    PoseLandmarker = mp.tasks.vision.PoseLandmarker
    PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    def build(delegate):
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path), delegate=delegate),
            running_mode=VisionRunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        return PoseLandmarker.create_from_options(options)

    if try_gpu:
        try:
            landmarker = build(BaseOptions.Delegate.GPU)
            print("[mediapipe] GPU delegate 啟用成功。")
            return landmarker
        except Exception as e:
            print(f"[mediapipe] GPU delegate 初始化失敗，改用 CPU delegate。原因: {e}")

    landmarker = build(BaseOptions.Delegate.CPU)
    print("[mediapipe] 使用 CPU delegate。")
    return landmarker


def to_pixel(landmark, frame_w, frame_h):
    """跟 camera_hand_tracker.to_pixel 同規則：畫面已水平鏡像，x 要跟著鏡像。"""
    return int((1.0 - landmark.x) * frame_w), int(landmark.y * frame_h)


def elbow_flexion_angle(shoulder, elbow, wrist):
    """輸入 pose_world_landmarks（公尺），回傳屈曲角度。伸直 = 0 度，上限 180 度。"""
    upper_arm = np.array([shoulder.x - elbow.x, shoulder.y - elbow.y, shoulder.z - elbow.z])
    forearm = np.array([wrist.x - elbow.x, wrist.y - elbow.y, wrist.z - elbow.z])
    denom = np.linalg.norm(upper_arm) * np.linalg.norm(forearm)
    if not np.isfinite(denom) or denom < 1e-9:
        return float("nan")
    cos_angle = np.clip(np.dot(upper_arm, forearm) / denom, -1.0, 1.0)
    interior_angle = np.degrees(np.arccos(cos_angle))
    return 180.0 - interior_angle


def is_visible(landmark):
    return landmark.visibility is None or landmark.visibility >= VISIBILITY_THRESHOLD


def draw_arm(frame, landmarks, world_landmarks, shoulder_i, elbow_i, wrist_i, label, w, h):
    shoulder, elbow, wrist = landmarks[shoulder_i], landmarks[elbow_i], landmarks[wrist_i]
    if not (is_visible(shoulder) and is_visible(elbow) and is_visible(wrist)):
        return

    sp, ep, wp = to_pixel(shoulder, w, h), to_pixel(elbow, w, h), to_pixel(wrist, w, h)
    cv2.line(frame, sp, ep, ARM_COLOR, 3)
    cv2.line(frame, ep, wp, ARM_COLOR, 3)
    for p in (sp, ep, wp):
        cv2.circle(frame, p, 5, (0, 0, 0), -1)
        cv2.circle(frame, p, 3, ARM_COLOR, -1)

    angle = elbow_flexion_angle(
        world_landmarks[shoulder_i], world_landmarks[elbow_i], world_landmarks[wrist_i]
    )
    text_pos = (ep[0] + 12, ep[1])
    text = f"{label}: {angle:.0f} deg (3D)" if np.isfinite(angle) else f"{label}: N/A"
    cv2.putText(frame, text, text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, TEXT_COLOR, 2, cv2.LINE_AA)


def main():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"找不到姿勢偵測模型：{MODEL_PATH}\n"
            "請先下載 pose_landmarker_full.task 放進 model/ 資料夾。"
        )

    camera_index = 0
    cap, backend_name = open_camera(index=camera_index)
    print(f"[camera] index={camera_index}, backend={backend_name}, reported={cap.get(cv2.CAP_PROP_FPS):.1f} FPS")
    stream = CameraStream(cap).start()

    with create_pose_landmarker(MODEL_PATH) as landmarker:
        cv2.namedWindow("Elbow Angle Tracker", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Elbow Angle Tracker", 960, 720)
        last_frame_id = -1
        last_timestamp_ms = -1
        prev_time = time.perf_counter()
        fps = 0.0
        inference_ms = 0.0

        while True:
            frame, last_frame_id, read_ms = stream.get_next(last_frame_id)
            if frame is None:
                continue

            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            timestamp_ms = max(last_timestamp_ms + 1, time.monotonic_ns() // 1_000_000)
            last_timestamp_ms = timestamp_ms
            inference_start = time.perf_counter()
            result = landmarker.detect_for_video(mp_image, timestamp_ms)
            inference_ms = 0.9 * inference_ms + 0.1 * (time.perf_counter() - inference_start) * 1000

            frame = cv2.flip(frame, 1)

            if result.pose_landmarks and result.pose_world_landmarks:
                landmarks = result.pose_landmarks[0]
                world_landmarks = result.pose_world_landmarks[0]
                draw_arm(frame, landmarks, world_landmarks, LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST, "L Elbow", w, h)
                draw_arm(frame, landmarks, world_landmarks, RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST, "R Elbow", w, h)

            now = time.perf_counter()
            fps = 0.9 * fps + 0.1 * (1.0 / max(now - prev_time, 1e-6))
            prev_time = now
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, f"Camera read: {read_ms:.1f} ms | Pose: {inference_ms:.1f} ms", (10, 48),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

            cv2.imshow("Elbow Angle Tracker", frame)
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break

    stream.stop()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
