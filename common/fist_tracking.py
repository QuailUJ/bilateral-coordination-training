"""Palm geometry and independent reacquisition for the fist game."""
import math
from types import SimpleNamespace
from common.hand_identity import HandIdentityTracker

PALM_IDS = (0, 5, 9, 13, 17)
LOSS_GRACE_S = 0.35
REACQUIRE_S = 0.5
CONTINUITY_CONFIDENCE = 0.5
CONTINUITY_DISTANCE = 0.08


def palm_center(landmarks, mirrored=True):
    x = sum(landmarks[i].x for i in PALM_IDS) / len(PALM_IDS)
    y = sum(landmarks[i].y for i in PALM_IDS) / len(PALM_IDS)
    return (1 - x if mirrored else x, y)


class FistIdentityTracker(HandIdentityTracker):
    tracking_point_kind = "palm_center"

    def __init__(self, enabled_side=None):
        super().__init__(tip_id=0)
        self.validation_indices = PALM_IDS
        self.last_seen = {}
        self._continuity_labels = set()
        self._continuity_blocked = set()
        self.enabled_side = enabled_side
        self.required_hands = 1 if enabled_side else 2

    @staticmethod
    def _point(landmarks, index):
        # Both continuity gates use the palm, never an occluded fingertip.
        return palm_center(landmarks, mirrored=False)

    def _minimum_confidence(self, label, landmarks, now):
        if (label not in self.positions or now - self.last_seen.get(label, -math.inf) > LOSS_GRACE_S
                or label not in self._continuity_labels or label in self._continuity_blocked):
            return self.confidence
        point = palm_center(landmarks, False)
        distance = math.dist(point, self.positions[label])
        other = "Right" if label == "Left" else "Left"
        if (not all(math.isfinite(v) for v in point) or distance > CONTINUITY_DISTANCE
                or (other in self.positions and math.dist(point, self.positions[other]) < 0.18)):
            return self.confidence
        return CONTINUITY_CONFIDENCE

    def update(self, result, now):
        self._continuity_labels = {label for label, status in self.status.items()
                                   if status["reason"] in ("tracked", "tracked_by_position", "no_detection", "low_confidence")}
        if self.enabled_side:
            selected = [(lm, cat) for lm, cat in zip(result.hand_landmarks or [], result.handedness or [])
                        if cat and cat[0].category_name == self.enabled_side]
            result = SimpleNamespace(hand_landmarks=[p[0] for p in selected], handedness=[p[1] for p in selected])
            if now - self.last_seen.get(self.enabled_side, now) > REACQUIRE_S:
                self.positions.pop(self.enabled_side, None)
                self.tips.pop(self.enabled_side, None)
                self.active.discard(self.enabled_side)
        candidates = {}
        duplicate = set()
        for landmarks, categories in zip(result.hand_landmarks or [], result.handedness or []):
            if len(landmarks) != 21 or not categories:
                continue
            category = categories[0]
            label = category.category_name
            if label not in ("Left", "Right"):
                continue
            if label in candidates:
                duplicate.add(label)
            if not math.isfinite(category.score) or category.score < self._minimum_confidence(label, landmarks, now):
                continue
            point = palm_center(landmarks, False)
            if all(math.isfinite(v) for v in point):
                candidates[label] = point
        if len(candidates) == 2 and not duplicate:
            for label, point in candidates.items():
                other = "Right" if label == "Left" else "Left"
                # One healthy hand must not keep the other hand's old anchor
                # alive forever. Reacquire only with two separated observations,
                # away from the other hand's last accepted location.
                if (label in self.positions
                        and now - self.last_seen.get(label, now) > REACQUIRE_S
                        and math.dist(point, candidates[other]) >= 0.18
                        and other in self.positions
                        and math.dist(point, self.positions[other]) >= 0.18
                        and math.dist(candidates[other], self.positions[other]) < 0.18):
                    self.positions.pop(label)
                    self.tips.pop(label, None)
                    self.active.discard(label)
        # A brief detector dropout must not discard two more valid frames.
        # Reuse only a recent, established lock; the base class still checks
        # confidence, separation, jumps and conflicts before accepting a point.
        for label, seen_at in self.last_seen.items():
            if (label in self.positions and now - seen_at <= LOSS_GRACE_S
                    and label not in self._continuity_blocked
                    and self.status[label]["reason"] in ("no_detection", "low_confidence")):
                self.active.add(label)
        tracked = super().update(result, now)
        if self.enabled_side:
            disabled = "Right" if self.enabled_side == "Left" else "Left"
            self.status[disabled] = {"reason": "disabled", "accepted": False}
        for label, landmarks in zip(("Left", "Right"), tracked):
            if landmarks is not None:
                self.last_seen[label] = now
                self._continuity_blocked.discard(label)
                if self.status[label].get("confidence", 1) < self.confidence:
                    self.status[label]["reason"] = "tracked_by_position"
            elif self.status[label]["reason"] in ("identity_conflict", "wrist_jump", "tip_jump",
                                                  "hands_overlap", "duplicate_label", "invalid_coordinates"):
                self._continuity_blocked.add(label)
        return tracked
