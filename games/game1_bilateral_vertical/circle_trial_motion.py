"""Clockwise loops split at observed upper reversals, without a preset center."""
import math
import numpy as np
from .motion import circle_roundness_score


class UpperReversalCircle:
    reference = None
    reversal = 0.012
    minimum_span = 0.06

    def __init__(self, direction="CW"):
        if direction not in ("CW", "CCW"):
            raise ValueError(direction)
        self.direction = direction
        self.sign = 1 if direction == "CW" else -1
        self.direction_label = "順時針" if direction == "CW" else "逆時針"
        self.depart_side = "右" if direction == "CW" else "左"
        self.return_side = "左" if direction == "CW" else "右"
        self.completed = 0
        self._phase = "start_top"
        self.feedback = f"拳頭放在上方起點，向{self.depart_side}開始{self.direction_label}畫圓"
        self.just_started_lap = False
        self._lap_start_t = None
        self.points = []
        self.bottom = self.top = 0
        self.turn_acc = 0.0
        self.last_rep_start_t = self.last_rep_duration = self.last_rep_quality = None
        self.last_record = None
        self.metrics = {"recognition": "upper_reversal_circle", "reversal_on": self.reversal,
                        "minimum_span": self.minimum_span}

    def pause(self):
        self.just_started_lap = False  # Preserve the phase across short gaps.

    @staticmethod
    def describe(points):
        xy = np.asarray([(p[1], p[2]) for p in points], dtype=float)
        mean = xy.mean(axis=0)
        centered = xy - mean
        matrix = np.column_stack((2*centered, np.ones(len(xy))))
        solution, _, rank, _ = np.linalg.lstsq(matrix, (centered**2).sum(axis=1), rcond=None)
        if rank < 3:
            return None
        center = solution[:2] + mean
        radii = np.linalg.norm(xy-center, axis=1)
        angles = np.unwrap(np.arctan2(xy[:, 1]-center[1], xy[:, 0]-center[0]))
        delta = np.diff(angles)
        winding = float(delta.sum())
        consistency = winding / max(float(np.abs(delta).sum()), 1e-9)
        return dict(center=center.tolist(), quality=circle_roundness_score(radii.tolist(), .5),
                    winding=winding, consistency=consistency,
                    closure_ratio=float(np.linalg.norm(xy[-1]-xy[0]) / max(float(radii.mean()), 1e-9)))

    def update(self, t, x, y, *unused):
        self.just_started_lap = False
        self.points.append((t, x, y))
        if self._lap_start_t is None:
            self._lap_start_t = t
            self.just_started_lap = True
            return
        first = self.points[0]
        if self._phase == "start_top":
            if self.sign*(x-first[1]) >= self.reversal and y-first[2] >= self.reversal:
                self._phase = "descending"
                self.bottom = len(self.points)-1
                self.feedback = f"沿{self.depart_side}側往下畫，接著繞向{self.return_side}側"
            return
        if self._phase == "descending":
            if y > self.points[self.bottom][2]:
                self.bottom = len(self.points)-1
            if self.points[self.bottom][2]-y >= self.reversal:
                self._phase = "ascending"
                self.top = len(self.points)-1
                self.feedback = f"沿{self.return_side}側回上方，再稍微向下即可結算"
            return
        if y < self.points[self.top][2]:
            self.top = len(self.points)-1
        reverse = y-self.points[self.top][2]
        self.metrics["reversal"] = reverse
        if reverse < self.reversal:
            return
        lap = self.points[:self.top+1]
        xs, ys = [p[1] for p in lap], [p[2] for p in lap]
        width, height = max(xs)-min(xs), max(ys)-min(ys)
        return_excursion = max(self.sign*(self.points[self.bottom][1]-p[1])
                               for p in self.points[self.bottom:self.top+1])
        path_ok = (width >= self.minimum_span and height >= self.minimum_span
                   and self.points[self.bottom][2]-self.points[self.top][2] >= self.minimum_span
                   and return_excursion > self.reversal)
        fit = self.describe(lap) if path_ok and len(lap) >= 8 else None
        valid = fit and self.sign*fit["winding"] >= math.pi*1.5 and self.sign*fit["consistency"] >= .65
        if valid:
            self.completed += 1
            self.last_rep_start_t = self._lap_start_t
            self.last_rep_duration = lap[-1][0]-self._lap_start_t
            self.last_rep_quality = fit["quality"]
            self.last_record = dict(round=self.completed, hand="right", score=fit["quality"],
                start_t=lap[0][0], end_t=lap[-1][0], duration=self.last_rep_duration,
                trail=[[p[1], p[2]] for p in lap], **fit)
            self.metrics.update(closure_ratio=fit["closure_ratio"], fitted_center=fit["center"],
                                winding_degrees=math.degrees(fit["winding"]))
            self.feedback = "上方反轉已確認：本圈完成，直接接下一圈"
        else:
            self.feedback = f"這段未形成{self.direction_label}繞行，從上方重新向{self.depart_side}畫"
        # The split belongs to the observed top, not the later confirmation frame.
        self.points = self.points[self.top:]
        self._lap_start_t = self.points[0][0]
        self.bottom = max(range(len(self.points)), key=lambda i: self.points[i][2])
        self.top = 0
        self._phase = "descending" if valid else "start_top"
        self.just_started_lap = True
