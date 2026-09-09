import pytest

from games.game1_bilateral_vertical.scoring import (
    ComboSyncTracker, RepPairSyncTracker, RepTrailRecorder, compute_session_result,
)


def test_first_update_only_starts_the_window():
    tracker = ComboSyncTracker(window_sec=1.0)
    assert tracker.update(0.0, left_completed=0, right_completed=0) is False
    assert tracker.score == 0


def test_both_hands_complete_within_same_window_scores_a_point():
    tracker = ComboSyncTracker(window_sec=1.0)
    tracker.update(0.0, left_completed=0, right_completed=0)  # 視窗開始快照
    tracker.update(0.4, left_completed=1, right_completed=0)  # 視窗內左手完成一次
    tracker.update(0.8, left_completed=1, right_completed=1)  # 視窗內右手也完成一次
    # 視窗過了 1.0 秒才結算，這次呼叫兩手完成次數都比視窗開始時多，算同步成功。
    assert tracker.update(1.0, left_completed=1, right_completed=1) is True
    assert tracker.score == 1


def test_only_one_hand_completes_in_window_does_not_score():
    tracker = ComboSyncTracker(window_sec=1.0)
    tracker.update(0.0, left_completed=0, right_completed=0)
    tracker.update(0.5, left_completed=1, right_completed=0)  # 只有左手完成
    assert tracker.update(1.0, left_completed=1, right_completed=0) is False
    assert tracker.score == 0


def test_window_resets_after_check_regardless_of_result():
    tracker = ComboSyncTracker(window_sec=1.0)
    tracker.update(0.0, left_completed=0, right_completed=0)
    assert tracker.update(1.0, left_completed=1, right_completed=1) is True
    assert tracker.score == 1

    # 上一輪剛結算完，新視窗重新拿當下的完成次數當基準，不會延續舊視窗的
    # 「已經完成過」狀態一直重複計分。
    assert tracker.update(1.5, left_completed=1, right_completed=1) is False
    assert tracker.update(2.0, left_completed=1, right_completed=1) is False
    assert tracker.score == 1


def test_different_speed_actions_still_sync_if_both_finish_within_window():
    # 兩手動作類型不同、完成速度差很多也沒關係，只要都落在同一個週期內
    # 各自完成過至少一次就算數，不要求兩個完成事件的確切時間點多接近。
    tracker = ComboSyncTracker(window_sec=1.0)
    tracker.update(0.0, left_completed=0, right_completed=0)
    tracker.update(0.1, left_completed=1, right_completed=0)  # 左手很快就完成
    tracker.update(0.9, left_completed=1, right_completed=1)  # 右手拖到視窗快結束才完成
    assert tracker.update(1.0, left_completed=1, right_completed=1) is True
    assert tracker.score == 1


# ---- RepPairSyncTracker ----
# 左右手完成事件依「完成順序」配對(左手第N次配右手第N次)，每組依開始時間/
# 花費時間/第三項(third_mode="diff"時是比幅度差距、"average"時是兩手品質分數
# 平均)打 0~100 分，不要求完全一樣。

def _tracker(target_pairs=10, start_tol=0.5, duration_tol=0.5, third_tol=0.5, mode="diff"):
    return RepPairSyncTracker(target_pairs, start_tol, duration_tol, third_tol, third_mode=mode)


def test_single_hand_rep_waits_for_the_other_hand_to_pair():
    tracker = _tracker()
    tracker.on_left_rep(start_t=0.0, duration=0.4, quality=0.1)
    assert tracker.completed_pairs == 0
    assert tracker.pair_scores == []


def test_identical_pair_scores_100():
    tracker = _tracker()
    tracker.on_left_rep(start_t=0.0, duration=0.4, quality=0.1)
    tracker.on_right_rep(start_t=0.0, duration=0.4, quality=0.1)
    assert tracker.completed_pairs == 1
    assert tracker.pair_scores[0] == pytest.approx(100.0)


def test_pair_score_degrades_as_start_time_diff_grows():
    # 三項指標(同步性/速度/幅度)平均起來才是最終分數：這裡只讓「開始時間」
    # 這一項變差，其他兩項維持滿分，所以差距越大，同步性那一項趨近 0，
    # 但整體分數不會直接歸零(還有另外兩項滿分墊著)——差距超過容忍值(0.5)的
    # far 案例分數要比只差一半容忍值(0.25)的 close 案例低。
    close = _tracker(start_tol=0.5)
    close.on_left_rep(start_t=0.0, duration=0.4, quality=0.1)
    close.on_right_rep(start_t=0.25, duration=0.4, quality=0.1)

    far = _tracker(start_tol=0.5)
    far.on_left_rep(start_t=0.0, duration=0.4, quality=0.1)
    far.on_right_rep(start_t=0.6, duration=0.4, quality=0.1)

    assert 0.0 < close.pair_scores[0] < 100.0
    # far 的同步性分數是 0，但速度/幅度都滿分，三項平均 = (0+100+100)/3。
    assert far.pair_scores[0] == pytest.approx(200.0 / 3.0)
    assert far.pair_scores[0] < close.pair_scores[0]


def test_pairs_matched_by_completion_order_not_by_which_hand_is_faster():
    # 左手先完成兩次、右手才完成第一次——應該是左手第1次配右手第1次，
    # 左手第2次還沒配對到人，先留著等右手第2次出現。
    tracker = _tracker()
    tracker.on_left_rep(start_t=0.0, duration=0.4, quality=0.1)
    tracker.on_left_rep(start_t=1.0, duration=0.4, quality=0.1)
    assert tracker.completed_pairs == 0

    tracker.on_right_rep(start_t=0.05, duration=0.4, quality=0.1)
    assert tracker.completed_pairs == 1  # 配到左手第1次
    assert tracker.pair_scores[0] == pytest.approx(100.0, abs=5.0)


def test_average_score_is_mean_of_all_pair_scores():
    tracker = _tracker()
    tracker.on_left_rep(start_t=0.0, duration=0.4, quality=0.1)
    tracker.on_right_rep(start_t=0.0, duration=0.4, quality=0.1)  # 這組三項都滿分 = 100
    tracker.on_left_rep(start_t=10.0, duration=0.4, quality=0.1)
    # 這組三項差距都遠超過容忍值，三項都趨近 0 分。
    tracker.on_right_rep(start_t=20.0, duration=5.0, quality=10.0)
    assert tracker.completed_pairs == 2
    assert tracker.average_score == pytest.approx(50.0, abs=1.0)


def test_no_pairs_stops_forming_once_target_reached():
    tracker = _tracker(target_pairs=1)
    tracker.on_left_rep(start_t=0.0, duration=0.4, quality=0.1)
    tracker.on_right_rep(start_t=0.0, duration=0.4, quality=0.1)
    assert tracker.completed_pairs == 1

    # 已經湊滿 target_pairs，之後再來的完成事件不該再配對出新的一組。
    tracker.on_left_rep(start_t=5.0, duration=0.4, quality=0.1)
    tracker.on_right_rep(start_t=5.0, duration=0.4, quality=0.1)
    assert tracker.completed_pairs == 1


def test_average_mode_third_component_is_mean_of_both_hands_quality_not_a_diff():
    # third_mode="average"(畫圓用)：兩手各自的品質值(例如圓度分數)已經是
    # 0~100 的獨立分數，直接平均，不是比較兩手差距——就算兩手數值差很多，
    # 只要平均起來還可以，這一項分數就不會被判定成「差距太大」而趨近 0。
    tracker = _tracker(mode="average")
    tracker.on_left_rep(start_t=0.0, duration=0.4, quality=60.0)
    tracker.on_right_rep(start_t=0.0, duration=0.4, quality=100.0)
    assert tracker.completed_pairs == 1
    # start/duration 都滿分，第三項是 (60+100)/2=80，三項平均 = (100+100+80)/3。
    assert tracker.pair_scores[0] == pytest.approx((100.0 + 100.0 + 80.0) / 3.0)


def test_diff_mode_still_compares_the_two_hands_quality_values():
    # third_mode="diff"(水平/垂直擺動用，預設值)：兩手品質值(幅度)差距換算
    # 成分數，兩手數值差越多這一項分數越低，跟 average 模式行為不同。
    tracker = _tracker(mode="diff", third_tol=0.5)
    tracker.on_left_rep(start_t=0.0, duration=0.4, quality=0.1)
    tracker.on_right_rep(start_t=0.0, duration=0.4, quality=0.2)  # 差距100%，遠超容忍值
    assert tracker.pair_scores[0] < 100.0


# ---- RepTrailRecorder ----

def test_trail_recorder_archives_matching_pair_after_both_hands_finish():
    rec = RepTrailRecorder()
    rec.record_left_point((0.1, 0.2))
    rec.record_left_point((0.15, 0.25))
    rec.finish_left_rep()
    rec.record_right_point((0.5, 0.5))
    rec.finish_right_rep()

    rec.archive_pair_if_ready(round_no=1, pair_score=88.4)

    assert len(rec.records) == 2
    left_rec = next(r for r in rec.records if r["hand"] == "left")
    right_rec = next(r for r in rec.records if r["hand"] == "right")
    assert left_rec == {"round": 1, "hand": "left", "score": 88.4,
                         "trail": [[0.1, 0.2], [0.15, 0.25]]}
    assert right_rec == {"round": 1, "hand": "right", "score": 88.4, "trail": [[0.5, 0.5]]}


def test_trail_recorder_keeps_rounds_in_fifo_order_matching_completion_order():
    rec = RepTrailRecorder()
    # 左手先完成兩組，右手才追上完成第一組——應該配對成『左手第1組』+『右手
    # 第1組』，不是隨便配，順序要跟 RepPairSyncTracker 的 FIFO 邏輯一致。
    rec.record_left_point((0.1, 0.1))
    rec.finish_left_rep()
    rec.record_left_point((0.2, 0.2))
    rec.finish_left_rep()
    rec.record_right_point((0.9, 0.9))
    rec.finish_right_rep()

    rec.archive_pair_if_ready(round_no=1, pair_score=50.0)
    assert len(rec.records) == 2
    left_rec = next(r for r in rec.records if r["hand"] == "left")
    assert left_rec["trail"] == [[0.1, 0.1]]  # 配到左手第一組，不是第二組


def test_trail_recorder_does_nothing_if_a_side_has_no_pending_rep():
    rec = RepTrailRecorder()
    rec.record_left_point((0.1, 0.1))
    rec.finish_left_rep()
    # 右手還沒完成任何一組，archive 不該產生任何紀錄。
    rec.archive_pair_if_ready(round_no=1, pair_score=50.0)
    assert rec.records == []


def test_trail_recorder_current_points_reset_after_finish():
    rec = RepTrailRecorder()
    rec.record_left_point((0.1, 0.1))
    rec.finish_left_rep()
    rec.record_left_point((0.9, 0.9))  # 這是下一組的第一個點
    rec.finish_left_rep()
    rec.record_right_point((0.5, 0.5))
    rec.finish_right_rep()
    rec.archive_pair_if_ready(round_no=1, pair_score=0.0)
    left_rec = next(r for r in rec.records if r["hand"] == "left")
    assert left_rec["trail"] == [[0.1, 0.1]]  # 第一組不該混到第二組的點


def test_to_details_includes_reps_when_provided():
    from games.game1_bilateral_vertical.scoring import compute_session_result as _csr
    result = _csr(80, completions_to_pass=60)
    reps = [{"round": 1, "hand": "left", "score": 80, "trail": [[0.1, 0.1]]}]
    details = result.to_details("HH", reps=reps)
    assert details["reps"] == reps


def test_to_details_omits_reps_key_when_not_provided():
    result = compute_session_result(80, completions_to_pass=60)
    details = result.to_details("HH")
    assert "reps" not in details


def test_compute_session_result_pass_and_fail():
    assert compute_session_result(6, completions_to_pass=6).passed is True
    assert compute_session_result(5, completions_to_pass=6).passed is False


def test_to_details_shape():
    result = compute_session_result(8, completions_to_pass=6)
    assert result.to_details("HH") == {"level_id": "HH", "passed": True, "score": 8}
