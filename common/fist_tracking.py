"""Palm geometry and independent reacquisition for the fist game."""
import math
from types import SimpleNamespace
from common.hand_identity import HandIdentityTracker

PALM_IDS = (0, 5, 9, 13, 17)
LOSS_GRACE_S = 0.35
REACQUIRE_S = 0.5


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
        self.reacquire_blocked = set()
        self.enabled_side = enabled_side
        self.required_hands = 1 if enabled_side else 2

    @staticmethod
    def _point(landmarks, index):
        # Both continuity gates use the palm, never an occluded fingertip.
        return palm_center(landmarks, mirrored=False)

    def _movement_limits(self, label, now):
        # More elapsed time permits more real motion; identity-conflict and
        # overlap gates still apply before any point can enter the trail.
        elapsed = max(0.0, now - self.last_seen.get(label, now))
        limit = min(0.40, 0.18 + 2.0 * max(0.0, elapsed - 1.0/30))
        return limit, limit

    def _required_stable_frames(self, label, now):
        # A recent known hand need not stand still for another three frames.
        if (label not in self.reacquire_blocked and label in self.last_seen
                and 0 <= now-self.last_seen[label] <= LOSS_GRACE_S):
            return 1
        return self.stable_frames

    def update(self, result, now):
        for label, status in self.status.items():
            if status["reason"] in ("identity_conflict", "duplicate_label", "hands_overlap", "invalid_coordinates", "wrist_jump", "tip_jump"):
                self.reacquire_blocked.add(label)
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
            if not math.isfinite(category.score) or category.score < self.confidence:
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
        tracked = super().update(result, now)
        if self.enabled_side:
            disabled = "Right" if self.enabled_side == "Left" else "Left"
            self.status[disabled] = {"reason": "disabled", "accepted": False}
        for label, landmarks in zip(("Left", "Right"), tracked):
            if landmarks is not None:
                self.last_seen[label] = now
                self.reacquire_blocked.discard(label)
        return tracked
