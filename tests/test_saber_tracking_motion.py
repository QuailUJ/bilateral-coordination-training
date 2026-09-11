import pytest

from games.game3_lightsaber_marble.scene import LightSword


def sword():
    item = LightSword((100, 100), 80, (255, 140, 90), None)
    item.allowed_arc = (90, 165)
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
