"""Single-hand tests count completed reps without inventing synchrony scores."""


class DisabledRecognition:
    completed = 0
    reference = None
    state = "disabled"
    feedback = "此手不使用"


class SingleHandTracker:
    def __init__(self, side):
        self.side = side
        self.score = 0

    def update(self, now, left, right):
        count = left if self.side == "left" else right
        changed = count > self.score
        self.score = count
        return changed
