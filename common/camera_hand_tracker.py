"""
common/camera_hand_tracker.py - 攝影機讀取 + MediaPipe 手部關節點偵測（共用模組）

這支檔案是把 NEW/main.py 最初那支「最基礎手部 21 關節點偵測 demo」裡驗證過的
核心邏輯搬出來，變成共用模組，讓登入後的每一款遊戲都能直接 import 使用，不用
各自複製貼上一份。行為完全不變，細節與踩過的坑見下方各函式/類別註解，也記錄
在 Project 筆記「既有程式分析」文件的第 5 節。

【一定要遵守的鏡像規則】（左右手判斷 + 顯示文字方向兩個坑都踩過一次）：
    1. landmarker.detect() 一定要餵「攝影機原始、未翻轉」的畫面。MediaPipe 的
       Left/Right handedness 分類是照原始畫面判斷的，先翻轉過的畫面會讓左右
       手判斷相反。
    2. 偵測完、拿到 landmark 結果之後，才把畫面 cv2.flip() 翻成鏡子視角，之後
       所有骨架/圓點/文字標註都畫在「已經翻好」的這張畫面上，這樣文字才不會
       變成鏡像反字。landmark 的 x 座標對應到畫面像素位置時要用 to_pixel()
       做鏡像換算。
    3. cv2.putText 不支援中文字型，任何要疊加在攝影機影格上的文字一律用英文。

【效能相關】：實測發現「讀攝影機」跟「MediaPipe 偵測」如果依序執行、時間會
    直接相加，卡在 ~30fps。CameraStream 把讀攝影機丟到背景執行緒，跟主執行緒
    的偵測平行跑，兩段時間取較慢者而不是相加。另外也實測確認過 GPU delegate
    在標準 PyPI mediapipe wheel 上是編譯時就關閉的（NotImplementedError: GPU
    processing is disabled in build flags），create_hand_landmarker 會自動
    retry 退回 CPU，不用特別處理。又，使用者的外接鏡頭跟筆電內建鏡頭都實測
    卡在硬體 30fps 上限，跟程式寫法無關，不用再花時間優化這段。
"""

import time
import threading

import cv2
import mediapipe as mp


# 手掌 21 個關節點之間的連線（畫成骨架用）。目前版本的 mediapipe 已經移除舊版
# mediapipe.solutions.hands 模組（沒有內建的 HAND_CONNECTIONS 常數可用），所以
# 這裡手動列出跟官方一致的拓樸。
HAND_CONNECTIONS = [
    # 掌心
    (0, 1), (0, 5), (5, 9), (9, 13), (13, 17), (0, 17),
    # 大拇指
    (1, 2), (2, 3), (3, 4),
    # 食指
    (5, 6), (6, 7), (7, 8),
    # 中指
    (9, 10), (10, 11), (11, 12),
    # 無名指
    (13, 14), (14, 15), (15, 16),
    # 小指
    (17, 18), (18, 19), (19, 20),
]

# 不同手的骨架顏色，方便同時看兩隻手時分辨左右 (BGR)
HAND_COLOR = {
    "Left": (255, 120, 0),
    "Right": (0, 0, 255),
    "Unknown": (200, 200, 200),
}

# 手部中心座標用的關節點：手腕 + 四指 MCP（見遊戲一設計，取平均值降低雜訊，
# 且刻意不用指尖，避免手指開合造成垂直座標雜訊）。
HAND_CENTER_LANDMARK_IDS = (0, 5, 9, 13, 17)


class CameraStream:
    """背景執行緒不斷讀攝影機，跟主執行緒的 MediaPipe 偵測平行跑。

    用法：
        stream = CameraStream(cap).start()
        frame, frame_id, read_ms = stream.get_next(last_frame_id)

    get_next() 會等到「比上次拿到的 frame_id 更新」的畫面才回傳，如果主執行緒
    處理一幀的時間比攝影機拍一幀還久，中間攝影機拍到的舊畫面會被直接跳過，
    永遠只處理「目前最新的一幀」——這對即時互動偵測是合理的取捨（寧可跳幀，
    也不要累積延遲）。
    """

    def __init__(self, cap):
        self.cap = cap
        self.cond = threading.Condition()
        self.latest_frame = None
        self.frame_id = 0
        self.read_ms = 0.0
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return self

    def _loop(self):
        while self.running:
            t0 = time.time()
            ret, frame = self.cap.read()
            t1 = time.time()
            if not ret:
                continue
            with self.cond:
                self.latest_frame = frame
                self.frame_id += 1
                self.read_ms = 0.9 * self.read_ms + 0.1 * (t1 - t0) * 1000
                self.cond.notify_all()

    def get_next(self, last_frame_id, timeout=1.0):
        if self.cap is None:
            return None, last_frame_id, 0.0
        with self.cond:
            got = self.cond.wait_for(lambda: self.latest_frame is not None and self.frame_id != last_frame_id, timeout=timeout)
            if not got:
                return None, last_frame_id, self.read_ms
            return self.latest_frame, self.frame_id, self.read_ms

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)


def create_hand_landmarker(model_path, num_hands=2, try_gpu=True, video=False):
    """建立 HandLandmarker，先嘗試 GPU delegate，失敗就自動退回 CPU delegate。

    已實測確認標準 PyPI mediapipe wheel 的 GPU 支援是編譯時就關閉的，這裡的
    try/except 只是「值得一試、失敗就安靜退回 CPU」，不是在處理什麼罕見例外。
    """
    BaseOptions = mp.tasks.BaseOptions
    HandLandmarker = mp.tasks.vision.HandLandmarker
    HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    def build(delegate):
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path, delegate=delegate),
            running_mode=VisionRunningMode.VIDEO if video else VisionRunningMode.IMAGE,
            num_hands=num_hands,
            min_hand_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        return HandLandmarker.create_from_options(options)

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


class GameHandLandmarker:
    """Keep existing IMAGE inference; lazily use VIDEO for game zero only."""
    def __init__(self, model_path, num_hands=2, try_gpu=True):
        self.options = dict(model_path=model_path, num_hands=num_hands, try_gpu=try_gpu)
        self.image_detector = create_hand_landmarker(**self.options)
        self.video_detector = None
        self.last_timestamp_ms = -1

    def detect(self, image):
        return self.image_detector.detect(image)

    def detect_fists(self, image):
        if self.video_detector is None:
            self.video_detector = create_hand_landmarker(**self.options, video=True)
        timestamp = max(self.last_timestamp_ms + 1, time.monotonic_ns() // 1_000_000)
        self.last_timestamp_ms = timestamp
        return self.video_detector.detect_for_video(image, timestamp)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        try:
            if self.video_detector is not None:
                self.video_detector.close()
        finally:
            self.image_detector.close()


def to_pixel(landmark, frame_w, frame_h):
    """把 MediaPipe 的正規化座標 (0~1) 換算成『已翻轉過』畫面上的像素座標。
    因為畫面已經水平鏡像過了，x 方向要跟著鏡像 (1 - x)，y 不受影響。
    """
    px = int((1.0 - landmark.x) * frame_w)
    py = int(landmark.y * frame_h)
    return px, py


def hand_center_y(landmarks, landmark_ids=HAND_CENTER_LANDMARK_IDS) -> float:
    """回傳關節點的正規化 y 座標平均值（0~1）。預設用 HAND_CENTER_LANDMARK_IDS
    （手掌中心，遊戲零的拳頭版追蹤點）；傳入單一關節點 id 的 tuple（例如
    `(8,)` 食指尖）就能重用同一套平均/正規化邏輯追蹤別的點（遊戲一的手指版）。
    刻意不用像素座標，這樣數學跟畫面解析度無關，換算成像素只在真的要畫圖的
    時候才做。
    """
    ys = [landmarks[i].y for i in landmark_ids]
    return sum(ys) / len(ys)


def hand_center_pixel(landmarks, frame_w, frame_h, landmark_ids=HAND_CENTER_LANDMARK_IDS):
    """跟 hand_center_y() 同樣的關節點平均（可傳自訂 landmark_ids），但換算成
    『已翻轉畫面』的像素座標，給需要在畫面上畫出追蹤點的地方用（遊戲零/一的 HUD）。
    """
    xs = [(1.0 - landmarks[i].x) for i in landmark_ids]
    ys = [landmarks[i].y for i in landmark_ids]
    cx = int((sum(xs) / len(xs)) * frame_w)
    cy = int((sum(ys) / len(ys)) * frame_h)
    return cx, cy


def draw_hand_skeleton(frame, landmarks, label, w, h):
    """在（已翻轉的）frame 上畫出一隻手的骨架連線 + 21 個圓點 + 左右手標籤。
    共用給任何需要顯示手部骨架的畫面用（demo、遊戲內 HUD）。"""
    color = HAND_COLOR.get(label, HAND_COLOR["Unknown"])

    for a, b in HAND_CONNECTIONS:
        xa, ya = to_pixel(landmarks[a], w, h)
        xb, yb = to_pixel(landmarks[b], w, h)
        cv2.line(frame, (xa, ya), (xb, yb), color, 2)

    for lm in landmarks:
        cx, cy = to_pixel(lm, w, h)
        cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)

    wx, wy = to_pixel(landmarks[0], w, h)
    cv2.putText(frame, label, (wx - 20, wy + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


# 單手 21 個關節點的正規化座標涵蓋範圍（bounding box 邊長），拿來粗略估計使用者
# 離攝影機的遠近。這兩個門檻是憑經驗抓的粗略值，還沒有大量實測不同身高/鏡頭調校過，
# 之後如果發現提示太敏感/太遲鈍，只需要調整這兩個常數，不用動呼叫端邏輯。
DISTANCE_TOO_CLOSE_SPAN = 0.55
DISTANCE_TOO_FAR_SPAN = 0.12


def estimate_distance_hint(landmarks):
    """依單一隻手的關節點涵蓋範圍估計「離攝影機太近 / 太遠 / 剛好」，回傳其中一個
    字串狀態，給各遊戲畫面轉換成中文提示文字用（這支不處理文字/中文，維持跟
    draw_hand_skeleton 一樣的「畫面上疊字只能用英文」限制無關，因為這裡只回狀態值）。
    手在畫面中佔比越大代表越靠近鏡頭，佔比越小代表越遠（或才剛伸進畫面邊緣）。
    """
    xs = [lm.x for lm in landmarks]
    ys = [lm.y for lm in landmarks]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    if span > DISTANCE_TOO_CLOSE_SPAN:
        return "too_close"
    if span < DISTANCE_TOO_FAR_SPAN:
        return "too_far"
    return "ok"


def open_camera(width=640, height=480, request_fps=120, use_dshow=True, index=0):
    """開攝影機並設定基本參數。回傳 (cap, backend_name)。

    2026-08-18 實測結論（同時測過外接鏡頭跟筆電內建鏡頭）：兩顆鏡頭都硬體卡在
    ~30fps，換解析度、換 backend (CAP_DSHOW / 系統預設 MSMF) 都沒用，是鏡頭
    硬體/韌體本身的上限，不是軟體或這裡的設定問題。640x480 對偵測品質比較好，
    解析度反正不影響 FPS 上限，所以維持這組預設值就好，不用再花時間調。
    """
    import sys

    if sys.platform.startswith("win") and use_dshow:
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        backend_name = "CAP_DSHOW"
    else:
        cap = cv2.VideoCapture(index)
        backend_name = "default"

    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"攝影機 {index} 開啟失敗，請確認連接及是否被占用。")

    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, request_fps)

    return cap, backend_name
