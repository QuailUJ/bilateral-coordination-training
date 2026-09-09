"""Whole-fist motion around a calibrated, stationary image reference."""
import math
from .motion import AxisSwingRecognition, CircularRecognition, circle_roundness_score

CALIBRATION_S = 0.3
CALIBRATION_JITTER = 0.02
CIRCLE_RADIUS = 0.12


class FixedReference:
    reference = None
    _anchor = None
    _anchor_t = None
    feedback = "雙拳停穩 0.3 秒設定起點"

    def calibrate(self, t, x, y, circle=False):
        if self.reference is not None:
            self.feedback = "移動整個拳頭，回到空心參考點" if not circle else "從上方起點沿參考圓畫一圈"
            return True
        if self._anchor is None or math.dist(self._anchor, (x, y)) > CALIBRATION_JITTER:
            self._anchor, self._anchor_t = (x, y), t
        if t - self._anchor_t < CALIBRATION_S:
            return False
        self.reference = (self._anchor[0], self._anchor[1] + (CIRCLE_RADIUS if circle else 0))
        self.feedback = "移動整個拳頭，回到空心參考點" if not circle else "從上方起點沿參考圓畫一圈"
        return True


class FistAxisRecognition(AxisSwingRecognition):
    """Two alternating, meaningful excursions form one rep at their reversals.

    The first observation starts the first excursion immediately. No neutral
    position or calibration hold is required. Extrema carry their observation
    timestamps; the small reversal confirmation delay is not scored as motion.
    """
    reference = None
    reversal_on = 0.012

    def __init__(self, *args):
        super().__init__(*args)
        self._origin = None
        self._extreme = None
        self._direction = 0
        self._last_counted_direction = 0
        self.turning_point = None
        self.feedback = "直接來回移動拳頭，反向時確認極限點"
        self.metrics = {"recognition": "reversal", "reversal_on": self.reversal_on}

    def update(self, t_s, x, y, ref_x=0, ref_y=0):
        if self.feedback == "短暫漏偵測，暫停動作判定":
            self.feedback = "追蹤恢復，繼續來回移動拳頭"
        point = (t_s, x, y)
        index = 1 if self.axis == "x" else 2
        value = point[index]
        if self._origin is None:
            self._origin = self._extreme = point
            return
        if self._direction == 0:
            delta = value - self._origin[index]
            if abs(delta) < self.reversal_on:
                return
            self._direction = 1 if delta > 0 else -1
            self._extreme = point
        if (value - self._extreme[index]) * self._direction > 0:
            self._extreme = point
        travel = abs(self._extreme[index] - self._origin[index])
        reversal = (self._extreme[index] - value) * self._direction
        self.state = "POS" if self._direction > 0 else "NEG"
        self.metrics.update(travel=travel, reversal=max(0, reversal))
        if reversal < self.reversal_on:
            return
        endpoint = self._extreme
        duration = endpoint[0] - self._origin[0]
        self.turning_point = endpoint[1:]
        self.metrics.update(turning_point=list(self.turning_point), turning_time=endpoint[0])
        if travel >= self.amp_on and duration >= self.min_interval_s:
            if self.half_swings == 0 or self._last_counted_direction == self._direction:
                self.half_swings = 1
                self._rep_start_t = self._origin[0]
                self._rep_peak = travel
            else:
                self.half_swings = 0
                self.completed += 1
                self.last_rep_start_t = self._rep_start_t
                self.last_rep_duration = endpoint[0] - self._rep_start_t
                self.last_rep_peak = max(self._rep_peak, travel)
            self._last_counted_direction = self._direction
            self.feedback = "已確認反向極限點，繼續來回移動"
        else:
            self.feedback = "這段幅度太小或太快，尚未計次"
        # Follow every confirmed turn, including small unscored ones, so a
        # changed range cannot trap the recognizer waiting for an old position.
        self._origin = endpoint
        self._extreme = point
        self._direction *= -1


class FistCircularRecognition(FixedReference, CircularRecognition):
    _previous_angle = None

    def pause(self):
        # No angular credit for the invisible segment.
        self._previous_angle = None

    def update(self, t_s, x, y, ref_x=0, ref_y=0):
        self.just_started_lap = False
        if not self.calibrate(t_s, x, y, circle=True):
            return
        dx, dy = x - self.reference[0], y - self.reference[1]
        radius = math.hypot(dx, dy)
        if radius < 0.04:
            self._previous_angle = None
            return
        angle = math.atan2(dy, dx)
        at_top = abs((angle + math.pi / 2 + math.pi) % (2 * math.pi) - math.pi) < math.radians(self.start_angle_tolerance_deg)
        if self._phase == "await_start":
            if not at_top:
                return
            self._phase = "tracking"
            self.turn_acc = 0.0
            self._radii = []
            self._lap_start_t = t_s
            self._previous_angle = angle
            self.just_started_lap = True
        previous = self._previous_angle
        delta = (angle - previous + math.pi) % (2 * math.pi) - math.pi if previous is not None else 0
        if abs(delta) > 0.65:
            self.pause()
            return
        # Display y increases downward: top -> right -> bottom is clockwise.
        progress = delta if self.direction == "CW" else -delta
        self.turn_acc = max(0, self.turn_acc + progress)
        self._previous_angle = angle
        self._radii.append(radius)
        if self.turn_acc + 1e-8 >= self.turn_threshold and at_top:
            self.completed += 1
            self.last_rep_start_t = self._lap_start_t
            self.last_rep_duration = t_s - self._lap_start_t
            self.last_rep_quality = circle_roundness_score(self._radii, self.roundness_cv_tolerance)
            self._phase = "await_start"
            self.turn_acc = 0.0
            self.pause()
