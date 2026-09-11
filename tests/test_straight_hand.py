from types import SimpleNamespace
import math

import pytest
from common.straight_hand import hand_posture


def anatomical_pose(flex=0, aspect=4/3):
    """Uneven knuckle positions with four parallel, straight fingers."""
    pts = [SimpleNamespace(x=.5/aspect, y=.8, z=0) for _ in range(21)]
    for base, x, y in [(5,.43,.6), (9,.49,.57), (13,.55,.59), (17,.61,.64)]:
        for j in range(4):
            pts[base+j] = SimpleNamespace(x=x/aspect,
                y=y-j*.04*math.cos(math.radians(flex)),
                z=-j*.04*math.sin(math.radians(flex))/aspect)
    return pts


@pytest.mark.parametrize('aspect', [1, 4/3, 16/9])
def test_natural_knuckle_offsets_do_not_reject_parallel_fingers(aspect):
    relaxed = hand_posture(anatomical_pose(0, aspect), aspect)
    pressed = hand_posture(anatomical_pose(60, aspect), aspect)
    assert relaxed['valid'] and not relaxed['pressed']
    assert pressed['valid'] and pressed['pressed']


def test_missing_palm_direction_is_not_a_press():
    pts = anatomical_pose(60)
    pts[0] = pts[9]
    assert not hand_posture(pts, 4/3)['pressed']




def pose(pressed=False):
    pts = [SimpleNamespace(x=0.0, y=-1.0, z=0.0) for _ in range(21)]
    for i, x in zip((5, 9, 13, 17), (-.15, -.05, .05, .15)):
        for j in range(4):
            pts[i+j] = SimpleNamespace(x=x, y=0.0 if pressed else j*.2,
                                        z=j*.2 if pressed else 0.0)
    return pts


def test_straight_fingers_can_flex_only_at_mcp():
    assert hand_posture(pose())["valid"]
    assert not hand_posture(pose())["pressed"]
    assert hand_posture(pose(True))["pressed"]


@pytest.mark.parametrize("base", (5, 9, 13, 17))
def test_any_curled_finger_invalidates_whole_hand(base):
    pts = pose(True)
    pts[base+2].x += .4
    result = hand_posture(pts)
    assert not result["valid"]
    assert not result["pressed"]


def test_one_finger_mcp_moving_alone_is_invalid():
    pts = pose()
    bent = pose(True)
    pts[5:9] = bent[5:9]
    assert not hand_posture(pts)["valid"]


def test_missing_or_degenerate_hand_is_not_a_press():
    assert not hand_posture(None)["pressed"]
    assert not hand_posture([SimpleNamespace(x=0,y=0,z=0)]*21)["valid"]
