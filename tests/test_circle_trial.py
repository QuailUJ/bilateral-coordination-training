import math
import pytest
from games.game1_bilateral_vertical.circle_trial_motion import UpperReversalCircle


def trace(recognizer, radius=.08, drift=0, sign=1, missing=()):
    for i in range(650):
        if i in missing:
            recognizer.pause()
            continue
        angle = -math.pi/2 + sign*i*math.tau/120
        recognizer.update(i/30, .35+radius*math.cos(angle)+drift*i/120, .4+radius*math.sin(angle))


@pytest.mark.parametrize("radius,drift", [(.04,0),(.08,0),(.12,0),(.06,.03)])
def test_different_sizes_and_unclosed_drifting_loops_count_five(radius, drift):
    r = UpperReversalCircle()
    trace(r, radius, drift)
    assert r.completed == 5
    assert r.reference is None
    assert r.last_rep_duration == pytest.approx(4, abs=.1)
    if drift:
        assert r.last_record["closure_ratio"] > .2
    else:
        assert r.last_rep_quality > 99


def test_counterclockwise_vertical_and_jitter_are_not_circles():
    r = UpperReversalCircle()
    trace(r, sign=-1)
    assert r.completed == 0
    for radius_x in (0, .003):
        r = UpperReversalCircle()
        for i in range(650):
            r.update(i/30, .4+radius_x*math.sin(i/10), .4+.1*math.cos(i/10))
        assert r.completed == 0


def test_top_confirmation_splits_at_extreme_not_later_frame():
    r = UpperReversalCircle()
    for i in range(121):
        angle=-math.pi/2+i*math.tau/120
        r.update(i/30,.4+.08*math.cos(angle),.4+.08*math.sin(angle))
    assert r.completed == 0  # Back at top, no downward reversal yet.
    for i in range(121,135):
        angle=-math.pi/2+i*math.tau/120
        r.update(i/30,.4+.08*math.cos(angle),.4+.08*math.sin(angle))
    assert r.completed == 1
    assert r.last_record["end_t"] == pytest.approx(4)
    assert r._lap_start_t == pytest.approx(4)


def test_brief_missing_observations_do_not_require_extra_turn():
    r = UpperReversalCircle()
    trace(r, missing=(58,59,60))
    assert r.completed == 5


@pytest.mark.parametrize("direction,sign", [("CW",1),("CCW",-1)])
@pytest.mark.parametrize("radius,drift", [(.04,0),(.06,.03)])
def test_production_directions_share_trial_rules(direction,sign,radius,drift):
    from games.game1_bilateral_vertical.scene import _make_recognizer
    r=_make_recognizer(direction)
    assert isinstance(r,UpperReversalCircle)
    trace(r,radius,drift,sign)
    assert r.completed==5
    assert r.reference is None
