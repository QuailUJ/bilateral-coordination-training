"""Fixed-duration bilateral scoring; each completion can be used only once."""
from collections import deque

DURATION_SECONDS = 60.0
PASS_SCORE = 8
SYNC_SECONDS = 0.30
RULE_VERSION = "timed_bilateral_v2"


class CompletionSync:
    def __init__(self):
        self.score = 0
        self.average_score = 0
        self.counts = [0, 0]
        self._pending_left = deque()
        self._pending_right = deque()
        self.events = []

    @property
    def completed_pairs(self):
        return self.score

    def update(self, now, left, right):
        before = self.score
        queues = (self._pending_left, self._pending_right)
        for i, count in enumerate((left, right)):
            for _ in range(max(0, count-self.counts[i])):
                queues[i].append(now)
            self.counts[i] = count
        while all(queues):
            l, r = queues[0][0], queues[1][0]
            if abs(l-r) <= SYNC_SECONDS + 1e-9:
                queues[0].popleft()
                queues[1].popleft()
                self.score += 1
                self.events.append({"t": now, "delta": 1, "difference": abs(l-r)})
            else:
                queues[0 if l < r else 1].popleft()
        for queue in queues:
            while queue and now-queue[0] > SYNC_SECONDS + 1e-9:
                queue.popleft()
        self.average_score = self.score
        return self.score > before
