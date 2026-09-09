from games.game4_bilateral_press.scoring import (
    ComboState, apply_press_hit, apply_miss, compute_session_result,
)

LEVEL = {"level_id": "lv1", "pass_score": 15}


def test_hitting_blue_triangle_scores_and_builds_combo():
    state = ComboState()
    state = apply_press_hit("blue", state)
    state = apply_press_hit("blue", state)
    assert state.score == 2
    assert state.combo == 2
    assert state.max_combo == 2


def test_hitting_red_triangle_penalizes_and_breaks_combo():
    state = ComboState(score=5, combo=3, max_combo=3)
    state = apply_press_hit("red", state)
    assert state.score == 4
    assert state.combo == 0
    assert state.max_combo == 3  # max_combo 是歷史紀錄，不會因為斷連擊而下降


def test_missing_blue_triangle_breaks_combo_without_score_penalty():
    state = ComboState(score=5, combo=4, max_combo=4)
    state = apply_miss("blue", state)
    assert state.score == 5  # 漏接不扣分
    assert state.combo == 0


def test_leaving_red_triangle_alone_has_no_effect():
    state = ComboState(score=5, combo=4, max_combo=4)
    state = apply_miss("red", state)
    assert state == ComboState(score=5, combo=4, max_combo=4)


def test_session_result_pass_and_fail():
    assert compute_session_result(ComboState(score=15, combo=0, max_combo=10), LEVEL).passed is True
    assert compute_session_result(ComboState(score=14, combo=0, max_combo=10), LEVEL).passed is False


def test_session_result_to_details():
    result = compute_session_result(ComboState(score=20, combo=0, max_combo=8), LEVEL)
    assert result.to_details("lv1") == {
        "score": 20, "max_combo": 8, "passed": True, "level_id": "lv1",
    }
