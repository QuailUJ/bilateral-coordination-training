from games.game3_lightsaber_marble import scoring

LEVEL = {"level_id": "lv1", "pass_score": 300}


def test_compute_session_result_passed_when_score_meets_threshold():
    result = scoring.compute_session_result(score=300, hits=30, misses=2, level=LEVEL)
    assert result.passed is True
    assert result.score == 300
    assert result.hits == 30
    assert result.misses == 2


def test_compute_session_result_failed_when_below_threshold():
    result = scoring.compute_session_result(score=299, hits=29, misses=10, level=LEVEL)
    assert result.passed is False


def test_to_details_includes_level_id_and_passed_flag():
    result = scoring.compute_session_result(score=350, hits=35, misses=1, level=LEVEL)
    details = result.to_details("lv1")
    assert details == {"level_id": "lv1", "passed": True, "hits": 35, "misses": 1}
