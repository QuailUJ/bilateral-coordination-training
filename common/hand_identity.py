"""Conservative identity gate; uncertain observations never extend a trail.

Keep MediaPipe's existing Left/Right convention, but require spatial continuity,
unique labels and several stable frames to acquire/reacquire a hand. Both hands
must be visible to establish a fresh identity lock.
"""
import math


class HandIdentityTracker:
    def __init__(self, tip_id=12, confidence=0.75, stable_frames=3):
        self.tip_id = tip_id
        self.confidence = confidence
        self.stable_frames = stable_frames
        self.positions = {}
        self.tips = {}
        self.pending = {}
        self.active = set()
        self.last_good_t = None
        self.last_update_t = None
        self.validation_indices = range(21)
        self.required_hands = 2
        self.status = {side: {"reason": "no_detection", "accepted": False} for side in ("Left", "Right")}

    @staticmethod
    def _point(landmarks, index):
        return (landmarks[index].x, landmarks[index].y)

    def update(self, result, now):
        self.status = {side: {"reason": "no_detection", "accepted": False} for side in ("Left", "Right")}
        if self.last_update_t is not None and now - self.last_update_t > 0.35:
            self.active.clear()
            self.pending.clear()
        self.last_update_t = now
        candidates = {}
        duplicates = set()
        for landmarks, categories in zip(result.hand_landmarks or [], result.handedness or []):
            if not categories or len(landmarks) != 21:
                continue
            category = categories[0]
            label = category.category_name
            if label in self.status:
                self.status[label]["confidence"] = category.score if math.isfinite(category.score) else None
                for key, index in (("raw_wrist", 0), ("raw_tip", self.tip_id)):
                    point = self._point(landmarks, index)
                    if all(math.isfinite(value) for value in point):
                        self.status[label][key] = list(point)
            if label not in ("Left", "Right") or not math.isfinite(category.score) or category.score < self.confidence:
                if label in self.status:
                    self.status[label]["reason"] = "low_confidence"
                continue
            if not all(math.isfinite(landmarks[i].x) and math.isfinite(landmarks[i].y) and math.isfinite(getattr(landmarks[i], "z", 0.0)) for i in self.validation_indices):
                self.status[label]["reason"] = "invalid_coordinates"
                self.status[label].pop("raw_wrist", None)
                self.status[label].pop("raw_tip", None)
                continue
            if label in candidates:
                duplicates.add(label)
            candidates[label] = landmarks
        for label in duplicates:
            candidates.pop(label, None)
            self.status[label]["reason"] = "duplicate_label"

        # Overlap makes identity ambiguous even if the model emits two labels.
        if len(candidates) == 2 and math.dist(
                self._point(candidates["Left"], 0), self._point(candidates["Right"], 0)) < 0.10:
            for label in candidates:
                self.status[label]["reason"] = "hands_overlap"
            candidates = {}

        # A new location can be acquired after complete loss, but never from a
        # lone remaining hand whose handedness may have flipped.
        if self.last_good_t is not None and now - self.last_good_t > 1.0 and len(candidates) == 2:
            self.positions.clear()
            self.tips.clear()
            self.active.clear()
            self.last_good_t = None

        if not self.positions and len(candidates) != self.required_hands:
            for label in candidates:
                self.status[label]["reason"] = "need_both_hands"
            candidates = {}
        accepted = {}
        eligible = set()
        for label, landmarks in candidates.items():
            position = self._point(landmarks, 0)
            tip = self._point(landmarks, self.tip_id)
            other = "Right" if label == "Left" else "Left"
            if label in self.positions:
                distance = math.dist(position, self.positions[label])
                if distance > 0.18:
                    self.status[label]["reason"] = "wrist_jump"
                    continue
                if other in self.positions and math.dist(position, self.positions[other]) < distance + 0.025:
                    self.status[label]["reason"] = "identity_conflict"
                    continue
                if label in self.active and math.dist(tip, self.tips[label]) > 0.20:
                    self.status[label]["reason"] = "tip_jump"
                    continue
            eligible.add(label)
            if label not in self.active:
                previous, count = self.pending.get(label, (position, 0))
                count = count + 1 if math.dist(previous, position) < 0.06 else 1
                self.pending[label] = (position, count)
                if count < self.stable_frames:
                    self.status[label]["reason"] = "stabilizing"
                    continue
            accepted[label] = landmarks

        # Do not establish half a fresh lock if only one candidate was stable.
        if not self.positions and len(accepted) != self.required_hands:
            for label in accepted:
                self.status[label]["reason"] = "need_both_hands"
            accepted = {}
        for label, landmarks in accepted.items():
            self.status[label].update(reason="tracked", accepted=True)
            self.positions[label] = self._point(landmarks, 0)
            self.tips[label] = self._point(landmarks, self.tip_id)
        for label in list(self.pending):
            if label not in eligible:
                self.pending.pop(label)
        self.active = set(accepted)
        if accepted:
            self.last_good_t = now
        return accepted.get("Left"), accepted.get("Right")
