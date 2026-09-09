from types import SimpleNamespace as NS

from common.hand_identity import HandIdentityTracker


def hand(x, y=0.5):
    return [NS(x=x, y=y, z=0.0) for _ in range(21)]


def result(*detections):
    return NS(hand_landmarks=[d[1] for d in detections],
              handedness=[[NS(category_name=d[0], score=d[2] if len(d) > 2 else 0.99)] for d in detections])


def acquire(tracker, now=0):
    left, right = hand(0.25), hand(0.75)
    for i in range(3):
        tracked = tracker.update(result(("Left", left), ("Right", right)), now + i * 0.03)
    assert tracked == (left, right)
    return left, right


def test_lone_hand_cannot_establish_new_identity():
    tracker = HandIdentityTracker()
    for i in range(8):
        assert tracker.update(result(("Left", hand(0.75))), i * 0.03) == (None, None)


def test_missing_left_and_mislabeled_right_never_moves_left_trail():
    tracker = HandIdentityTracker()
    left, right = acquire(tracker)
    assert tracker.update(result(("Right", right)), 0.1) == (None, right)
    for i in range(30):
        assert tracker.update(result(("Left", right)), 0.2 + i * 0.1) == (None, None)
    assert tracker.positions["Left"] == (0.25, 0.5)


def test_reacquisition_requires_consecutive_reliable_frames():
    tracker = HandIdentityTracker()
    left, right = acquire(tracker)
    tracker.update(result(("Right", right)), 0.1)
    assert tracker.update(result(("Left", left), ("Right", right)), 0.13)[0] is None
    assert tracker.update(result(("Left", left, 0.51), ("Right", right)), 0.16)[0] is None
    for i in range(2):
        assert tracker.update(result(("Left", left), ("Right", right)), 0.19 + i * 0.03)[0] is None
    assert tracker.update(result(("Left", left), ("Right", right)), 0.25)[0] is left


def test_swapped_labels_duplicate_labels_and_overlap_are_rejected():
    tracker = HandIdentityTracker()
    left, right = acquire(tracker)
    assert tracker.update(result(("Right", left), ("Left", right)), 0.1) == (None, None)
    assert tracker.update(result(("Left", left), ("Left", right)), 0.13) == (None, None)
    assert tracker.update(result(("Left", hand(0.49)), ("Right", hand(0.51))), 0.16) == (None, None)


def test_reversed_detection_order_does_not_swap_identity():
    tracker = HandIdentityTracker()
    left, right = acquire(tracker)
    assert tracker.update(result(("Right", right), ("Left", left)), 0.1) == (left, right)


def test_fingertip_teleport_is_rejected_even_when_wrist_is_stable():
    tracker = HandIdentityTracker()
    left, right = acquire(tracker)
    bad_left = hand(0.25)
    bad_left[12] = NS(x=0.75, y=0.5, z=0.0)
    assert tracker.update(result(("Left", bad_left), ("Right", right)), 0.1)[0] is None


def test_complete_loss_can_reacquire_both_at_new_position():
    tracker = HandIdentityTracker()
    acquire(tracker)
    tracker.update(result(), 0.1)
    left, right = hand(0.30, 0.2), hand(0.80, 0.2)
    for i in range(3):
        tracked = tracker.update(result(("Left", left), ("Right", right)), 1.2 + i * 0.03)
    assert tracked == (left, right)
