import math
from types import SimpleNamespace as NS
import pytest
from common.fist_tracking import FistIdentityTracker, palm_center
from games.game1_bilateral_vertical.scene import _make_recognizer
from test_hand_identity import hand, result, acquire


def test_occluded_middle_tip_does_not_reject_palm():
    tracker = FistIdentityTracker()
    left, right = acquire(tracker)
    left[12].x = float("nan")
    assert tracker.update(result(("Left", left), ("Right", right)), 0.1) == (left, right)
    assert palm_center(left) == (0.75, 0.5)


def test_fast_fist_motion_with_slower_camera_is_accepted():
    tracker = FistIdentityTracker()
    left, right = acquire(tracker)
    moved = hand(.25, .75)
    assert tracker.update(result(("Left", moved), ("Right", right)), .16)[0] is moved
    assert tracker.status['Left']['displacement'] == pytest.approx(.25)
    assert tracker.status['Left']['movement_limit'] > .25


def test_same_jump_at_high_frame_rate_is_still_rejected():
    tracker = FistIdentityTracker()
    left, right = acquire(tracker)
    assert tracker.update(result(("Left", hand(.25, .75)), ("Right", right)), .07)[0] is None
    assert tracker.status['Left']['reason'] == 'wrist_jump'


def test_short_gap_does_not_require_three_stationary_frames():
    tracker = FistIdentityTracker()
    left, right = acquire(tracker)
    tracker.update(result(("Right", right)), .09)
    moved = hand(.25, .6)
    assert tracker.update(result(("Left", moved), ("Right", right)), .12)[0] is moved


def test_fast_motion_cannot_move_into_other_hands_identity():
    tracker = FistIdentityTracker()
    left, right = acquire(tracker)
    assert tracker.update(result(("Left", hand(.6)), ("Right", right)), .3)[0] is None
    assert tracker.status['Left']['reason'] == 'identity_conflict'


def test_conflict_requires_stable_reacquisition():
    tracker = FistIdentityTracker()
    left, right = acquire(tracker)
    tracker.update(result(("Left", right)), .09)
    assert tracker.update(result(("Left", left), ("Right", right)), .12)[0] is None
    assert tracker.update(result(("Left", left), ("Right", right)), .15)[0] is None
    assert tracker.update(result(("Left", left), ("Right", right)), .18)[0] is left


def test_one_side_recovers_far_from_old_anchor_while_other_keeps_tracking():
    tracker = FistIdentityTracker()
    left, right = acquire(tracker)
    moved = hand(0.25, 0.8)
    for i in range(1, 30):
        actual = tracker.update(result(("Left", moved), ("Right", right)), 0.06 + i * 0.03)
        assert actual[1] is right
    assert actual[0] is moved
    assert tracker.positions["Left"] == pytest.approx((0.25, 0.8))


def test_lone_mislabeled_hand_never_reacquires_missing_side():
    tracker = FistIdentityTracker()
    left, right = acquire(tracker)
    for i in range(100):
        assert tracker.update(result(("Left", right)), 0.1 + i * 0.1)[0] is None


@pytest.mark.parametrize("side", ["Left", "Right"])
def test_single_mode_accepts_only_selected_label_and_recovers(side):
    tracker = FistIdentityTracker(side)
    other = "Right" if side == "Left" else "Left"
    for i in range(5):
        assert tracker.update(result((other, hand(.3))), i*.03) == (None, None)
    for i in range(3):
        tracked = tracker.update(result((side, hand(.3))), .2+i*.03)
    assert tracked[0 if side == "Left" else 1] is not None
    for i in range(30):
        tracked = tracker.update(result((side, hand(.6))), .3+i*.03)
    assert tracked[0 if side == "Left" else 1] is not None
    assert tracker.status[other]["reason"] == "disabled"


@pytest.mark.parametrize("action", ["H", "V"])
def test_whole_fist_translation_counts_ten_groups(action):
    recognizer = _make_recognizer(action)
    recognizer.update(0, 0.3, 0.4, 0.3, 0.4)
    t = 1.0
    for _ in range(10):
        x, y = (0.42, 0.4) if action == "H" else (0.3, 0.52)
        # Wrist translates exactly with fist; previous tip-minus-wrist was zero.
        recognizer.update(t, x, y, x, y)
        recognizer.update(t + 0.4, 0.3, 0.4, 0.3, 0.4)
        t += 0.8
    # Confirm the final return endpoint with the start of the next outward leg.
    recognizer.update(t, x, y, x, y)
    assert recognizer.completed == 10
    assert recognizer.reference is None


def test_first_reversal_counts_without_calibration_or_return_to_start():
    r = _make_recognizer("V")
    r.update(0, 0.3, 0.4)
    r.update(0.3, 0.3, 0.52)
    r.update(0.4, 0.3, 0.50)
    assert r.half_swings == 1
    assert r.turning_point == (0.3, 0.52)
    # The other endpoint is .42, never the initial .40.
    r.update(0.7, 0.3, 0.42)
    r.update(0.8, 0.3, 0.44)
    assert r.completed == 1
    assert r.last_rep_duration == pytest.approx(0.7)
    assert r.last_rep_peak == pytest.approx(0.12)


def test_small_jitter_and_small_excursions_do_not_count():
    r = _make_recognizer("H")
    for i in range(300):
        r.update(i * 0.1, 0.4 + 0.02 * math.sin(i), 0.5)
    assert r.completed == 0
    assert r.half_swings == 0


def test_jitter_near_peak_does_not_duplicate_turn():
    r = _make_recognizer("H")
    for t, x in [(0, .3), (.3, .42), (.4, .416), (.5, .419), (.6, .415)]:
        r.update(t, x, .5)
    assert r.half_swings == 0
    r.update(.7, .40, .5)
    assert r.half_swings == 1


def test_changed_range_follows_new_extrema_without_returning_to_initial_position():
    r = _make_recognizer("H")
    for i, x in enumerate([.2, .35, .33, .25, .27, .43, .41, .32, .34]):
        r.update(i * .3, x, .5)
    assert r.completed == 2
    assert r.reference is None


@pytest.mark.parametrize("action", ["CW", "CCW"])
def test_whole_fist_circle_and_opposite_direction(action):
    for correct in (True, False):
        recognizer = _make_recognizer(action)
        recognizer.update(0, 0.3, 0.28)
        recognizer.update(0.31, 0.3, 0.28)
        sign = 1 if action == "CW" else -1
        if not correct:
            sign *= -1
        for i in range(1, 136):
            angle = -math.pi / 2 + sign * i / 120 * math.tau
            x, y = 0.3 + 0.12 * math.cos(angle), 0.4 + 0.12 * math.sin(angle)
            recognizer.update(0.31 + i / 30, x, y, x, y)
        assert recognizer.completed == (1 if correct else 0)
        if correct:
            assert recognizer.last_rep_quality > 99


def test_stationary_jitter_does_not_count_as_circles():
    recognizer = _make_recognizer("CW")
    recognizer.update(0, 0.3, 0.28)
    recognizer.update(0.31, 0.3, 0.28)
    for i in range(1000):
        recognizer.update(0.4 + i / 30, 0.3 + 0.003 * math.cos(i), 0.28 + 0.003 * math.sin(i))
    assert recognizer.completed == 0


@pytest.mark.parametrize("action, expected_x", [("CW", 70), ("CCW", -70)])
def test_demo_from_top_moves_to_correct_screen_side(action, expected_x):
    from games.game1_bilateral_vertical.scene import _demo_offset
    x, y = _demo_offset(action, .5)
    assert x == pytest.approx(expected_x)
    assert y == pytest.approx(0, abs=1e-8)


def test_video_router_monotonic_timestamp_and_resource_cleanup(monkeypatch):
    import common.camera_hand_tracker as module
    calls, closed = [], []
    def create(**options):
        return NS(detect=lambda image: "image", detect_for_video=lambda image, t: calls.append(t),
                  close=lambda: closed.append(options.get("video", False)))
    monkeypatch.setattr(module, "create_hand_landmarker", create)
    monkeypatch.setattr(module.time, "monotonic_ns", lambda: 100_000_000)
    with module.GameHandLandmarker("test") as detector:
        assert detector.detect(None) == "image"
        detector.detect_fists(None)
        detector.detect_fists(None)
    assert calls == [100, 101]
    assert closed == [True, False]
