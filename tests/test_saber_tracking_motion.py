import pytest

from games.game3_lightsaber_marble.scene import LightSword
from games.game3_lightsaber_marble import config as cfg


def sword():
    item = LightSword((100, 100), 80, (255, 140, 90), None)
    item.allowed_arc = (90, cfg.SABER_ARC_MAX_DEG)
    return item


def test_saber_continues_moving_between_camera_samples():
    item = sword()
    item.set_target(150)
    item.advance(1/60)
    first = item.angle_deg
    item.advance(1/60)  # No second camera observation.
    assert 90 < first < item.angle_deg < 150
    assert item.active


def test_saber_smoothing_is_independent_of_ui_frame_rate():
    results = []
    for fps in (30, 60, 120):
        item = sword()
        item.set_target(150)
        for _ in range(fps // 10):
            item.advance(1/fps)
        results.append(item.angle_deg)
    assert results == pytest.approx([142.5]*3)


def test_invalid_posture_can_move_saber_but_cannot_enable_scoring():
    item = sword()
    item.set_target(150, allow_scoring=False)
    item.advance(.1)
    assert item.angle_deg > 90
    assert not item.active
    item.set_target(None, False)
    previous = item.angle_deg
    item.advance(.1)
    assert item.angle_deg == previous
    assert not item.active


def test_stationary_saber_reuses_rendered_surface():
    item = sword()
    item.set_target(90)
    item.advance(.1)
    image = item.image
    item.advance(.1)
    assert item.image is image


@pytest.mark.parametrize('target', [180, -180])
def test_right_hand_sword_reaches_left_horizontal(target):
    item = sword()
    item.set_target(target)
    item.advance(2)
    assert item.angle_deg == pytest.approx(180)
    assert item.active


def test_left_hand_sword_reaches_right_horizontal():
    item = sword()
    item.allowed_arc = (cfg.SABER_ARC_MIN_DEG, 90)
    item.set_target(0)
    item.advance(2)
    assert item.angle_deg == pytest.approx(0)
    assert item.active


def test_crossing_left_horizontal_wrap_does_not_snap_to_vertical():
    item = sword()
    item.angle_deg = 179
    item.set_target(-179)
    item.advance(.1)
    assert 179 < item.angle_deg <= 180
    assert not item.active  # Below the horizontal still cannot score.


@pytest.mark.parametrize('aspect', [4/3, 16/9])
@pytest.mark.parametrize('target', [0, 45, 90, 135, 180])
def test_camera_aspect_ratio_preserves_screen_direction(aspect, target):
    import math
    from types import SimpleNamespace
    from games.game3_lightsaber_marble.scene import _hand_pointing_angle
    points = [SimpleNamespace(x=.5, y=.5) for _ in range(21)]
    for tip in (12, 20):
        points[tip] = SimpleNamespace(x=.5-.1*math.cos(math.radians(target))/aspect,
                                     y=.5-.1*math.sin(math.radians(target)))
    difference = (_hand_pointing_angle(points, aspect) - target + 180) % 360 - 180
    assert difference == pytest.approx(0, abs=1e-9)
