import math

import pytest

from games.game3_lightsaber_marble import motion


def test_segment_angle_deg_pointing_right_is_zero():
    assert motion.segment_angle_deg((0, 0), (1, 0)) == pytest.approx(0.0)


def test_segment_angle_deg_pointing_up_is_90_because_y_axis_is_flipped():
    # MediaPipe 的 y 座標往下增大，「往上比」在畫面座標是 y 變小，角度應該算成 90 度。
    assert motion.segment_angle_deg((0, 0), (0, -1)) == pytest.approx(90.0)


def test_hand_pointing_angle_averages_two_segments():
    # 中指、小指都指向正上方 -> 平均角度也是 90 度。
    angle = motion.hand_pointing_angle_deg((0, 0), (0, -1), (0, 0), (0, -1))
    assert angle == pytest.approx(90.0)


def test_hand_pointing_angle_handles_wraparound_correctly():
    # 兩段線段分別接近 +179 度、-179 度：算術平均會得到 0 度（完全相反方向），
    # 但實際上這兩個角度只差 2 度，正確的圓周平均應該落在 180/-180 附近，不是 0。
    angle = motion.hand_pointing_angle_deg((0, 0), (-1, -0.017), (0, 0), (-1, 0.017))
    near_180 = min(abs(angle - 180), abs(angle + 180))
    assert near_180 < 5, f"預期落在 180 度附近，實際是 {angle}"


def test_is_within_active_arc():
    assert motion.is_within_active_arc(90, 15, 165) is True
    assert motion.is_within_active_arc(10, 15, 165) is False
    assert motion.is_within_active_arc(170, 15, 165) is False


def test_smooth_angle_towards_moves_partway_to_target():
    result = motion.smooth_angle_towards(0, 100, 0.5)
    assert result == pytest.approx(50.0)


def test_smooth_angle_towards_takes_shortest_path_across_wraparound():
    # 目前 350 度、目標 10 度：最短路徑是往前走 20 度到 360/0，不是往回繞 340 度。
    result = motion.smooth_angle_towards(350, 10, 1.0)
    assert result == pytest.approx(370.0)  # 370 % 360 == 10，等價於轉到 10 度




def test_is_marble_hit_within_angle_and_reach():
    assert motion.is_marble_hit(
        marble_angle_deg=90.0, marble_distance=100.0,
        sword_angle_deg=95.0, sword_length=150.0, angle_tolerance_deg=15.0) is True


def test_is_marble_hit_false_when_angle_diff_too_large():
    assert motion.is_marble_hit(
        marble_angle_deg=90.0, marble_distance=100.0,
        sword_angle_deg=120.0, sword_length=150.0, angle_tolerance_deg=15.0) is False


def test_is_marble_hit_false_when_still_out_of_reach():
    # 角度完全對齊，但彈珠還在光劍長度夠不到的地方，不該算命中——彈珠還在外圈
    # 飛，不能隔空打中。
    assert motion.is_marble_hit(
        marble_angle_deg=90.0, marble_distance=200.0,
        sword_angle_deg=90.0, sword_length=150.0, angle_tolerance_deg=15.0) is False


def test_is_marble_hit_handles_wraparound_boundary():
    # 光劍在 5 度、彈珠在 358 度，實際只差 7 度(跨過 0/360 邊界)，不是 353 度。
    assert motion.is_marble_hit(
        marble_angle_deg=358.0, marble_distance=100.0,
        sword_angle_deg=5.0, sword_length=150.0, angle_tolerance_deg=15.0) is True


def test_marble_spawn_angle_full_arc_uses_rng_range():
    level = {"full_arc": True}
    angle = motion.marble_spawn_angle_deg(level, 15, 165, rng=lambda a, b: (a, b))
    assert angle == (15, 165)


def test_marble_spawn_angle_discrete_lines_snaps_to_track():
    level = {"full_arc": False, "lines": 5}
    # 固定回傳 2 -> 應該落在第 3 條賽道 (index 2)，也就是 15~165 五等分的中間那條。
    angle = motion.marble_spawn_angle_deg(level, 15, 165, rng=lambda a, b: 2)
    assert angle == pytest.approx(90.0)


def test_marble_spawn_angle_discrete_clamps_out_of_range_rng():
    level = {"full_arc": False, "lines": 5}
    angle_low = motion.marble_spawn_angle_deg(level, 15, 165, rng=lambda a, b: -1)
    angle_high = motion.marble_spawn_angle_deg(level, 15, 165, rng=lambda a, b: 99)
    assert angle_low == pytest.approx(15.0)
    assert angle_high == pytest.approx(165.0)


def test_marble_speed_for_fixed_level_ignores_elapsed_time():
    level = {"marble_speed": 6.0, "full_arc": False}
    assert motion.marble_speed_for(level, 0) == 6.0
    assert motion.marble_speed_for(level, 999) == 6.0


def test_marble_speed_for_full_arc_ramps_up_over_time():
    level = {
        "marble_speed": 10.0, "full_arc": True,
        "speed_ramp_interval_sec": 10.0, "speed_ramp_step": 0.2, "speed_ramp_max_multiplier": 2.0,
    }
    assert motion.marble_speed_for(level, 0) == pytest.approx(10.0)
    assert motion.marble_speed_for(level, 10) == pytest.approx(12.0)
    assert motion.marble_speed_for(level, 25) == pytest.approx(14.0)


def test_marble_speed_for_full_arc_clamps_at_max_multiplier():
    level = {
        "marble_speed": 10.0, "full_arc": True,
        "speed_ramp_interval_sec": 1.0, "speed_ramp_step": 0.5, "speed_ramp_max_multiplier": 2.0,
    }
    assert motion.marble_speed_for(level, 1000) == pytest.approx(20.0)
