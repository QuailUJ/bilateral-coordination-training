"""Index fingertip extension: fist -> directed extension -> fist = one rep.

Uses fingertip displacement relative to the palm, plus PIP/DIP extension.
MCP-only rotation, whole-hand translation, wrong-axis motion and a stationary
extended finger cannot earn repetitions. Thresholds are gameplay heuristics,
not a clinical measurement of maximum range of motion.
"""
import math

from games.game2_finger_vertical import config as cfg


def _point(landmarks, index, aspect):
    p = landmarks[index]
    return (p.x * aspect, p.y, getattr(p, "z", 0.0) * aspect)


def _angle(a, b, c):
    u = tuple(x - y for x, y in zip(a, b))
    v = tuple(x - y for x, y in zip(c, b))
    length = math.sqrt(sum(x*x for x in u) * sum(x*x for x in v))
    if length < 1e-8:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x*y for x, y in zip(u, v)) / length))))


class FingerExtensionRecognition:
    def __init__(self, action):
        if action not in ("H", "V"):
            raise ValueError(action)
        self.action = action
        self.completed = 0
        self.last_rep_start_t = None
        self.last_rep_duration = None
        self.last_rep_peak = None
        self.last_rep_quality = None
        self.state = "await_fist"
        self.feedback = "先握拳，讓食指收回掌心"
        self._baseline = None
        self._ready_since = None
        self._extension_since = None
        self._start_t = None
        self._peak = 0.0
        self.metrics = {}

    def _reset(self, feedback):
        self.state = "await_fist"
        self.feedback = feedback
        self._baseline = None
        self._ready_since = None
        self._extension_since = None
        self._start_t = None
        self._peak = 0.0

    def update_landmarks(self, now, landmarks, aspect=1.0):
        self.metrics = {}
        points = [_point(landmarks, i, aspect) for i in range(21)]
        wrist, palm = points[0], points[9]
        palm_vector = (palm[0] - wrist[0], palm[1] - wrist[1])
        scale = math.hypot(*palm_vector)
        if scale < 0.025:
            self._reset("請靠近一點，讓食指與指節清楚入鏡")
            return
        pip = _angle(points[5], points[6], points[7])
        dip = _angle(points[6], points[7], points[8])
        others_curled = all(_angle(points[i], points[i+1], points[i+2]) < cfg.OTHER_FINGER_MAX_ANGLE
                            for i in (9, 13, 17))
        folded = pip <= cfg.FIST_PIP_MAX_ANGLE and dip <= cfg.FIST_DIP_MAX_ANGLE
        self.metrics.update(pip_angle=pip, dip_angle=dip, others_curled=others_curled, folded=folded,
                            travel_on=cfg.TIP_TRAVEL_RATIO, return_off=cfg.TIP_RETURN_RATIO,
                            pip_min=cfg.EXTENDED_PIP_MIN_ANGLE, dip_min=cfg.EXTENDED_DIP_MIN_ANGLE)
        # Mirrored screen coordinates, normalized by palm size for distance tolerance.
        tip = (-(points[8][0] - wrist[0]) / scale, (points[8][1] - wrist[1]) / scale)
        orientation = math.atan2(palm_vector[1], palm_vector[0])
        if not others_curled:
            self._reset("其餘手指保持握拳，只伸出食指")
            return
        if self._baseline is None:
            if not folded:
                self._ready_since = None
                self.feedback = "先握拳，讓食指中間與末端指節彎曲"
                return
            if self._ready_since is None:
                self._ready_since = now
            if now - self._ready_since < cfg.FIST_HOLD_S:
                return
            self._baseline = (tip, pip, dip, orientation, scale)
            self.state = "ready"
            self.feedback = "食指尖向正上方伸出" if self.action == "V" else "食指尖向水平方向伸出"
            return

        origin, initial_pip, initial_dip, initial_angle, initial_scale = self._baseline
        rotation = abs((orientation - initial_angle + math.pi) % (2 * math.pi) - math.pi)
        if rotation > math.radians(cfg.MAX_PALM_ROTATION_DEG) or not 0.7 < scale / initial_scale < 1.4:
            self._reset("手掌保持穩定，重新握拳準備")
            return
        dx, dy = tip[0] - origin[0], tip[1] - origin[1]
        primary = -dy if self.action == "V" else abs(dx)
        cross = abs(dx) if self.action == "V" else abs(dy)
        distance = math.hypot(dx, dy)
        self.metrics.update(primary=primary, cross_axis=cross, distance=distance,
                            pip_extension=pip-initial_pip, dip_extension=dip-initial_dip,
                            palm_rotation_deg=math.degrees(rotation))
        self._peak = max(self._peak, primary)
        if distance > cfg.TIP_RETURN_RATIO and self._start_t is None:
            self._start_t = now
        directed = primary >= cfg.TIP_TRAVEL_RATIO and cross <= primary * cfg.MAX_CROSS_AXIS_RATIO
        extended = (pip >= cfg.EXTENDED_PIP_MIN_ANGLE and dip >= cfg.EXTENDED_DIP_MIN_ANGLE
                    and pip - initial_pip >= cfg.MIN_PIP_EXTENSION_DEG
                    and dip - initial_dip >= cfg.MIN_DIP_EXTENSION_DEG)
        if self.state == "ready":
            if directed and extended:
                if self._extension_since is None:
                    self._extension_since = now
                if now - self._extension_since >= cfg.EXTENSION_HOLD_S:
                    self.state = "extended"
                    self.feedback = "已伸出，請收回食指握拳完成一次"
            else:
                self._extension_since = None
                self.feedback = ("食指中間與末端指節也要伸展" if directed else
                                 "食指尖向正上方伸出" if self.action == "V" else "食指尖向水平方向伸出")
            # Returning before valid extension starts a fresh attempt.
            if folded and distance <= cfg.TIP_RETURN_RATIO:
                self._start_t = None
                self._peak = 0.0
        elif folded and distance <= cfg.TIP_RETURN_RATIO:
            self.completed += 1
            self.last_rep_start_t = self._start_t
            self.last_rep_duration = now - self._start_t
            self.last_rep_peak = self._peak
            self.last_rep_quality = min(100.0, self._peak / cfg.TIP_TRAVEL_RATIO * 100.0)
            self._reset("完成一次，握拳準備下一次")
