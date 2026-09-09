"""
games/game1_bilateral_vertical/motion.py - 純函式/純狀態機：水平/垂直擺動、
順時針/逆時針畫圓偵測

不 import pygame/cv2/mediapipe，只吃數字，方便單元測試（合成假的座標序列，
不需要真的接攝影機）。座標一律是已經「鏡像」過的正規化座標（x 取 1.0-x，
跟畫面顯示的鏡像視角一致），呼叫端（scene.py）負責做鏡像轉換，這裡只管數學。

兩種偵測器共用同一個介面：update(t_s, x, y) 餵一個時間點的座標，
`.completed` 是目前為止累積完成的次數（整數，只增不減）。scene.py 不用管
底層是哪一種演算法，只要看 completed 有沒有增加就知道這一手是否又完成了一次
目標動作。
"""

import math
from collections import deque


class AxisSwingRecognition:
    """水平或垂直方向的來回擺動偵測。axis="x" 用於水平(H)、axis="y" 用於垂直(V)。

    比照 BilateralCoordinationTraining 原版
    modes/game1/recognize_method.py 的 HorizontalRecognition/
    VerticalRecognition：用「跟原點的相對位移」做三態機（CENTER/POS/NEG）+
    兩段式門檻(amp_on 進入、amp_off 才能回到 CENTER，兩者不同值做 hysteresis
    避免在門檻邊緣抖動誤判)判斷「瞬間位移到了哪一側」；只要從 CENTER 擺到
    任一側就算一次「半擺動」，不管哪一側、也不管兩次半擺動的方向是否相同，
    累積滿兩次半擺動就算完成一組（min_interval_s 只用來擋「太短時間內連續
    計次」，不擋狀態本身的切換）。不要求「先往哪個方向」——曾經加過這個限制
    （2026-09-08 改版），但玩家實測覺得判斷方式很奇怪，改回這個原版邏輯。

    【2026-09-09 加上：完成一組時的統計數據，給左右手相似度計分用】
    每完成一組（兩次半擺動），額外記錄這一組的 last_rep_start_t（第一次
    半擺動離開中心的時間點）、last_rep_duration（從離開中心到這一組結束、
    共花了幾秒）、last_rep_peak（這一組期間離中心最遠的位移量，代表這組動作
    「舉多高/擺多遠」）。scoring.py::RepPairSyncTracker 會拿左右手這三個數字
    去比對「兩手是不是差不多同時開始、花的時間差不多、幅度也差不多」，不要求
    完全一樣、只是算出差距換算成分數。
    """

    def __init__(self, axis: str, amp_on: float, amp_off: float, min_interval_s: float):
        if axis not in ("x", "y"):
            raise ValueError(f"axis 必須是 'x' 或 'y'，收到 {axis!r}")
        self.axis = axis
        self.amp_on = amp_on
        self.amp_off = amp_off
        self.min_interval_s = min_interval_s

        self.state = "CENTER"
        self.half_swings = 0
        self.completed = 0
        self._last_count_t = -math.inf

        self._half_start_t = None
        self._half_peak = 0.0
        self._rep_start_t = None
        self._rep_peak = 0.0

        # 最近一次完成的完整一組（兩次半擺動）的統計數據，給配對計分用。
        self.last_rep_start_t = None
        self.last_rep_duration = None
        self.last_rep_peak = None

    def update(self, t_s: float, x: float, y: float, ref_x: float, ref_y: float):
        offset = (x - ref_x) if self.axis == "x" else (y - ref_y)
        self._update_offset(t_s, offset)

    def _update_offset(self, t_s: float, offset: float):
        prev_state = self.state
        if self.state == "CENTER":
            if offset >= self.amp_on:
                self.state = "POS"
            elif offset <= -self.amp_on:
                self.state = "NEG"
        elif self.state == "POS":
            self._half_peak = max(self._half_peak, offset)
            if offset <= self.amp_off:
                self.state = "CENTER"
        elif self.state == "NEG":
            self._half_peak = max(self._half_peak, -offset)
            if offset >= -self.amp_off:
                self.state = "CENTER"

        if prev_state == "CENTER" and self.state in ("POS", "NEG"):
            # 半擺動開始：記下起始時間跟起始位移量，之後在 POS/NEG 狀態期間
            # 持續更新 _half_peak 追蹤這一次半擺動的最大位移。
            self._half_start_t = t_s
            self._half_peak = abs(offset)
            return

        if prev_state in ("POS", "NEG") and self.state == "CENTER":
            # 半擺動結束(回到中心)：可能觸發計次，太短時間內連續回中心不算數。
            if (t_s - self._last_count_t) < self.min_interval_s:
                return
            self._last_count_t = t_s

            if self.half_swings == 0:
                # 這一組的第一次半擺動，記下這一組的起點。
                self._rep_start_t = self._half_start_t
                self._rep_peak = self._half_peak
            else:
                self._rep_peak = max(self._rep_peak, self._half_peak)

            self.half_swings += 1
            if self.half_swings >= 2:
                self.half_swings = 0
                self.completed += 1
                self.last_rep_start_t = self._rep_start_t
                self.last_rep_duration = t_s - self._rep_start_t
                self.last_rep_peak = self._rep_peak


def _is_near_angle(angle_deg: float, target_deg: float, tolerance_deg: float) -> bool:
    diff = (angle_deg - target_deg + 180) % 360 - 180
    return abs(diff) <= tolerance_deg


def circle_roundness_score(radii, cv_tolerance: float) -> float:
    """圓度分數(0~100)：半徑的變異程度越小，分數越高——完美的圓每一點離圓心
    (這裡是手腕)的距離完全不變，分數是 100；橢圓/畫歪的形狀半徑忽大忽小，
    變異係數(標準差/平均值)越大，分數越低。用「變異係數」而不是直接用標準差，
    這樣不管這一圈畫得多大，同樣的『相對』歪斜程度分數會一樣，不會因為圈畫
    得比較大就自動比較容易/比較難拿高分。cv_tolerance 是變異係數達到多少分數
    會趨近 0，先抓一個大概值，還沒經過真人測試校準。
    """
    n = len(radii)
    if n < 2:
        return 0.0
    mean_r = sum(radii) / n
    if mean_r <= 1e-9:
        return 0.0
    variance = sum((r - mean_r) ** 2 for r in radii) / n
    coefficient_of_variation = math.sqrt(variance) / mean_r
    return max(0.0, 100.0 * (1.0 - coefficient_of_variation / cv_tolerance))


class CircularRecognition:
    """順時針(CW)或逆時針(CCW)畫圓偵測，規定要「從 12 點鐘方向開始」畫一圈。

    以手腕為原點，追蹤點(中指指尖)相對手腕的位移算這一刻的角度(0 度朝右、
    逆時針為正，12 點鐘方向＝90 度)跟半徑(離手腕的距離)。兩段式狀態機：
        "await_start"：還沒開始畫，等追蹤點的角度接近 12 點鐘(容忍範圍
            start_angle_tolerance_deg)才會進入 "tracking"，開始這一圈的
            計時跟半徑取樣；不到 12 點鐘附近的晃動當雜訊忽略，不會被誤判成
            一圈的開始。
        "tracking"：累積「持續同方向轉動」的角度（atan2(cross, dot) 轉向角，
            取樣頻率無關，延續原本已驗證過的做法——cross product 原始值會
            隨取樣密度改變量級，用轉向角累積才不會受取樣頻率影響），一旦轉
            錯方向就把累積量歸零重算（避免手抖來回晃動被誤判成一直在畫圓）。
            累積角度達到 turn_threshold（弧度，一整圈是 2π≈6.28）就算完成
            一圈：記下這一圈的起始時間/花費時間/圓度分數，回到 "await_start"
            等下一圈重新從 12 點鐘開始。

    座標系是螢幕座標（y 往下增大、鏡像過的 x），角度的正負對應到「順時針/
    逆時針」哪一個方向，已經用單元測試釘住，這裡不用自己再猜一次。

    self.just_started_lap 給呼叫端（scene.py）用：這次 update() 呼叫如果剛好
    觸發「從 12 點鐘開始新的一圈」會是 True（只有那一幀），畫面上的手部軌跡線
    要在這個時間點清空重畫——需求是「軌跡持續顯示到開始畫下一圈」，不是「這一
    圈畫完就馬上清空」，所以清空時機是綁在「下一圈開始」而不是「這一圈完成」。
    """

    def __init__(self, direction: str, turn_threshold: float, history_len: int,
                 start_angle_tolerance_deg: float = 30.0, roundness_cv_tolerance: float = 0.5):
        if direction not in ("CW", "CCW"):
            raise ValueError(f"direction 必須是 'CW' 或 'CCW'，收到 {direction!r}")
        self.direction = direction
        self.turn_threshold = turn_threshold
        self.start_angle_tolerance_deg = start_angle_tolerance_deg
        self.roundness_cv_tolerance = roundness_cv_tolerance
        self.history = deque(maxlen=history_len)
        self.turn_acc = 0.0
        self.completed = 0
        self._phase = "await_start"
        self.just_started_lap = False

        self._radii = []
        self._lap_start_t = None

        # 最近一次完成的一圈的統計數據，給配對計分用（跟 AxisSwingRecognition
        # 的 last_rep_start_t/last_rep_duration 是同樣的概念；last_rep_quality
        # 這裡放的是圓度分數 0~100，不是像素幅度，見 scoring.py 的說明）。
        self.last_rep_start_t = None
        self.last_rep_duration = None
        self.last_rep_quality = None

    def update(self, t_s: float, x: float, y: float, ref_x: float, ref_y: float):
        self.just_started_lap = False
        offset_x = x - ref_x
        offset_y = y - ref_y
        radius = math.hypot(offset_x, offset_y)
        angle_deg = math.degrees(math.atan2(-offset_y, offset_x))

        if self._phase == "await_start":
            if radius <= 1e-6 or not _is_near_angle(angle_deg, 90.0, self.start_angle_tolerance_deg):
                return
            self._phase = "tracking"
            self.turn_acc = 0.0
            self.history.clear()
            self._radii = []
            self._lap_start_t = t_s
            self.just_started_lap = True

        self.history.append((offset_x, offset_y))
        self._radii.append(radius)
        if len(self.history) < 3:
            return

        p1, p2, p3 = self.history[-3], self.history[-2], self.history[-1]
        v1 = (p2[0] - p1[0], p2[1] - p1[1])
        v2 = (p3[0] - p2[0], p3[1] - p2[1])
        if v1 == (0.0, 0.0) or v2 == (0.0, 0.0):
            return  # 兩幀之間完全沒移動，這一步的轉向角算不出來，跳過不處理

        cross = v1[0] * v2[1] - v1[1] * v2[0]
        dot = v1[0] * v2[0] + v1[1] * v2[1]
        turn_angle = math.atan2(cross, dot)  # 這一步轉了幾弧度，正負代表方向

        # 螢幕座標系（y 往下）下，負角度代表順時針(CW)、正角度代表逆時針(CCW)
        # ——用合成圓形軌跡的單元測試釘住這個方向，不要憑直覺改動。
        turning_cw = turn_angle < 0
        wants_cw = (self.direction == "CW")

        if turning_cw == wants_cw:
            self.turn_acc += abs(turn_angle)
        else:
            self.turn_acc = 0.0

        if self.turn_acc >= self.turn_threshold:
            self.completed += 1
            self.last_rep_start_t = self._lap_start_t
            self.last_rep_duration = t_s - self._lap_start_t
            self.last_rep_quality = circle_roundness_score(self._radii, self.roundness_cv_tolerance)
            self.turn_acc = 0.0
            self._phase = "await_start"
