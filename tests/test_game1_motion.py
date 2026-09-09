import math

import pytest

from games.game1_bilateral_vertical.motion import AxisSwingRecognition, CircularRecognition


# ---- AxisSwingRecognition ----
# 比照 BilateralCoordinationTraining 原版 HorizontalRecognition/
# VerticalRecognition：只看「有沒有從中心擺到任一側」，不要求先往哪個方向，
# 累積滿兩次半擺動（不管方向是否相同）就算完成一組。

def test_horizontal_swing_right_then_left_counts_one_rep():
    r = AxisSwingRecognition("x", amp_on=0.06, amp_off=0.025, min_interval_s=0.0)
    t = 0.0
    # 中心 -> 右(半擺動1) -> 中心 -> 左(半擺動2) = 1 組
    for x in [0.5, 0.62, 0.5, 0.38, 0.5]:
        r.update(t, x, 0.5, ref_x=0.5, ref_y=0.5)
        t += 0.05
    assert r.completed == 1


def test_horizontal_swing_left_then_right_also_counts_one_rep():
    # 順序反過來(先左再右)一樣要算成一組，不要求特定的起始方向。
    r = AxisSwingRecognition("x", amp_on=0.06, amp_off=0.025, min_interval_s=0.0)
    t = 0.0
    for x in [0.5, 0.38, 0.5, 0.62, 0.5]:
        r.update(t, x, 0.5, ref_x=0.5, ref_y=0.5)
        t += 0.05
    assert r.completed == 1


def test_vertical_swing_up_then_down_counts_one_rep():
    r = AxisSwingRecognition("y", amp_on=0.08, amp_off=0.03, min_interval_s=0.0)
    t = 0.0
    for y in [0.5, 0.35, 0.5, 0.65, 0.5]:
        r.update(t, 0.5, y, ref_x=0.5, ref_y=0.5)
        t += 0.05
    assert r.completed == 1


def test_axis_swing_two_half_swings_same_direction_also_counts_one_rep():
    # 兩次半擺動即使方向相同(都往同一側)也算完成一組，跟原版邏輯一致——
    # 這支 recognizer 只數「有沒有離開中心」，不管方向順序。
    r = AxisSwingRecognition("y", amp_on=0.08, amp_off=0.03, min_interval_s=0.0)
    t = 0.0
    for y in [0.5, 0.35, 0.5, 0.35, 0.5]:  # 上 -> 中心 -> 上(再一次) -> 中心
        r.update(t, 0.5, y, ref_x=0.5, ref_y=0.5)
        t += 0.05
    assert r.completed == 1


def test_axis_swing_records_rep_start_duration_and_peak_on_completion():
    # 完成一組(兩次半擺動)之後，last_rep_start_t/duration/peak 要能反映這一組
    # 實際的起始時間、總花費時間、期間離中心最遠的位移量——給
    # scoring.py::RepPairSyncTracker 拿去比對兩手相似度用。
    r = AxisSwingRecognition("y", amp_on=0.08, amp_off=0.03, min_interval_s=0.0)
    # t=0 中心 -> t=0.1 上到 -0.2(半擺動1，起點) -> t=0.2 回中心
    # -> t=0.3 下到 0.15(半擺動2) -> t=0.4 回中心(完成一組)
    for t, y in [(0.0, 0.5), (0.1, 0.3), (0.2, 0.5), (0.3, 0.65), (0.4, 0.5)]:
        r.update(t, 0.5, y, ref_x=0.5, ref_y=0.5)
    assert r.completed == 1
    assert r.last_rep_start_t == pytest.approx(0.1)
    assert r.last_rep_duration == pytest.approx(0.3)  # 0.4 - 0.1
    assert r.last_rep_peak == pytest.approx(0.2)  # max(|0.3-0.5|, |0.65-0.5|) = max(0.2, 0.15)


def test_axis_swing_requires_return_below_amp_off_before_recounting():
    r = AxisSwingRecognition("x", amp_on=0.06, amp_off=0.025, min_interval_s=0.0)
    t = 0.0
    # 進入 POS 之後停在 amp_off 跟 amp_on 之間（沒真的回到中心），不該又算一次。
    for x in [0.5, 0.62, 0.55, 0.62, 0.55]:
        r.update(t, x, 0.5, ref_x=0.5, ref_y=0.5)
        t += 0.05
    assert r.completed == 0  # 連一次完整擺動都還沒有（只完成了一次半擺動）


def test_axis_swing_respects_min_interval():
    r = AxisSwingRecognition("x", amp_on=0.06, amp_off=0.025, min_interval_s=1.0)
    # 兩次「進入 POS/NEG」之間如果間隔太短，第二次不該被計入半次擺動。
    r.update(0.0, 0.5, 0.5, 0.5, 0.5)
    r.update(0.1, 0.62, 0.5, 0.5, 0.5)   # 第一次半擺動 t=0.1
    r.update(0.2, 0.5, 0.5, 0.5, 0.5)    # 回中心
    r.update(0.25, 0.38, 0.5, 0.5, 0.5)  # 才過 0.15s，min_interval=1.0，不該觸發
    assert r.half_swings == 1
    assert r.completed == 0


def test_axis_swing_does_not_flip_left_right_asymmetrically():
    # 這是原本 BilateralCoordinationTraining VerticalRecognition 踩過的 bug
    # （CENTER 分支條件寫反，導致幾乎只會判斷成同一個方向）——POS/NEG 兩個方向
    # 都要能各自正確觸發，且觸發規則完全對稱。
    pos = AxisSwingRecognition("y", amp_on=0.08, amp_off=0.03, min_interval_s=0.0)
    pos.update(0.0, 0.5, 0.5, 0.5, 0.5)
    pos.update(0.1, 0.5, 0.65, 0.5, 0.5)
    assert pos.state == "POS"

    neg = AxisSwingRecognition("y", amp_on=0.08, amp_off=0.03, min_interval_s=0.0)
    neg.update(0.0, 0.5, 0.5, 0.5, 0.5)
    neg.update(0.1, 0.5, 0.35, 0.5, 0.5)
    assert neg.state == "NEG"


# ---- CircularRecognition ----
# 【2026-09-09 改版：要求從 12 點鐘方向開始】所以合成測試軌跡的第一個點都要
# 相對於 (cx, cy) 落在 12 點鐘位置（也就是 (cx, cy - radius)），並且 update()
# 一定要餵 ref_x/ref_y（手腕座標），不再是選填。

def _circle_points(n, cw: bool, radius=0.1, cx=0.5, cy=0.5):
    """產生一段圓形軌跡座標，第一個點(i=0)固定落在相對 (cx,cy) 的 12 點鐘方向
    （比照新版規定的起點）。畫面座標系 y 往下增大：在這個座標系下，角度隨時間
    「遞減」畫出的視覺路徑是順時針(CW)，角度「遞增」是逆時針(CCW)——跟一般數學
    座標系(y 往上)的直覺相反，這裡直接用畫面座標系的定義生成測試資料。"""
    points = []
    for i in range(n):
        angle = (i / n) * 2 * math.pi
        if cw:
            angle = -angle
        angle -= math.pi / 2  # 相位平移，讓 i=0 落在 12 點鐘方向 (cx, cy-radius)
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        points.append((x, y))
    return points


def _feed(recognizer, points, dt=0.02, t0=0.0, cx=0.5, cy=0.5):
    t = t0
    for x, y in points:
        recognizer.update(t, x, y, ref_x=cx, ref_y=cy)
        t += dt
    return t


def test_circular_cw_detects_clockwise_motion():
    r = CircularRecognition("CW", turn_threshold=5.5, history_len=20)
    _feed(r, _circle_points(40, cw=True))
    assert r.completed >= 1, "順時針軌跡應該要被 CW 偵測器判定完成至少一圈"


def test_circular_ccw_does_not_trigger_on_clockwise_motion():
    r = CircularRecognition("CCW", turn_threshold=5.5, history_len=20)
    _feed(r, _circle_points(40, cw=True))
    assert r.completed == 0, "順時針軌跡不該被 CCW 偵測器判定完成"


def test_circular_ccw_detects_counterclockwise_motion():
    r = CircularRecognition("CCW", turn_threshold=5.5, history_len=20)
    _feed(r, _circle_points(40, cw=False))
    assert r.completed >= 1, "逆時針軌跡應該要被 CCW 偵測器判定完成至少一圈"


def test_circular_cw_does_not_trigger_on_counterclockwise_motion():
    r = CircularRecognition("CW", turn_threshold=5.5, history_len=20)
    _feed(r, _circle_points(40, cw=False))
    assert r.completed == 0


def test_circular_requires_starting_near_12_oclock():
    # 起點規定在 12 點鐘(角度90度)附近，容忍範圍預設 30 度；手停在 3 點鐘方向
    # (角度0度，差了90度，遠超過容忍範圍)不動，不管餵幾幀都不該進入 tracking。
    r = CircularRecognition("CW", turn_threshold=5.5, history_len=20, start_angle_tolerance_deg=30.0)
    for i in range(20):
        r.update(0.02 * i, 0.6, 0.5, ref_x=0.5, ref_y=0.5)  # 固定在 (0.5+0.1, 0.5) = 3點鐘方向
    assert r.completed == 0
    assert r._phase == "await_start"


def test_circular_just_started_lap_flag_only_true_on_the_transition_frame():
    # 只走 30/40 圈(270度)：從12點鐘出發，還沒累積到完成一圈的門檻，也還沒
    # 繞回起點附近，這段路徑裡 just_started_lap 應該只有第一幀是 True。
    r = CircularRecognition("CW", turn_threshold=5.5, history_len=20)
    points = _circle_points(40, cw=True)[:30]
    t = 0.0
    flags = []
    for x, y in points:
        r.update(t, x, y, ref_x=0.5, ref_y=0.5)
        flags.append(r.just_started_lap)
        t += 0.02
    assert flags[0] is True, "第一個點剛好在12點鐘、觸發進入tracking，這一幀應該是True"
    assert all(f is False for f in flags[1:]), "還沒完成一圈、也還沒繞回起點附近，不該再觸發"
    assert r.completed == 0


def test_circular_starting_new_lap_again_when_path_closes_back_to_12_oclock():
    # 完成一圈之後，軌跡如果繼續往前走、剛好又繞回12點鐘附近，會立刻觸發下一圈
    # 的 just_started_lap——這是正確行為(不是bug)：判斷依據是『目前的絕對角度
    # 是不是接近12點鐘』，不是『跟起點差了幾幀』，一個真的封閉的圓本來就會在
    # 繞完一圈時再次通過起點附近。
    r = CircularRecognition("CW", turn_threshold=5.5, history_len=20)
    starts = []
    for i, (x, y) in enumerate(_circle_points(40, cw=True)):
        r.update(0.02 * i, x, y, ref_x=0.5, ref_y=0.5)
        if r.just_started_lap:
            starts.append(i)
    assert starts[0] == 0
    assert r.completed >= 1
    assert len(starts) >= 2, "封閉圓在繞完一圈接近終點時應該會再次觸發下一圈的起點"


def test_circular_resets_accumulator_on_direction_reversal():
    r = CircularRecognition("CW", turn_threshold=1e9, history_len=20)  # 門檻設超高，只測 turn_acc 行為
    t = _feed(r, _circle_points(10, cw=True))
    acc_after_cw = r.turn_acc
    assert acc_after_cw > 0

    _feed(r, _circle_points(10, cw=False), t0=t)
    # 反方向轉了幾步之後，累積量應該已經被歸零重算，不會是持續累加的大數字。
    assert r.turn_acc < acc_after_cw


def test_circular_completion_count_is_independent_of_sampling_density():
    # 這是修過的 bug：改用夾角(atan2)累積之前，取樣點越密、單步 cross product
    # 越小，同一個物理轉動動作在不同取樣頻率下會算出差異很大的總量。用同一個
    # turn_threshold，稀疏取樣(40 點/圈)跟密集取樣(200 點/圈，模擬更高的攝影機
    # fps)應該都要能偵測到完成一圈，次數不能差太多。
    sparse = CircularRecognition("CW", turn_threshold=5.5, history_len=250)
    _feed(sparse, _circle_points(40, cw=True))

    dense = CircularRecognition("CW", turn_threshold=5.5, history_len=250)
    _feed(dense, _circle_points(200, cw=True), dt=0.004)

    assert sparse.completed >= 1
    assert dense.completed >= 1
    assert abs(sparse.completed - dense.completed) <= 1, (
        f"取樣密度不該大幅影響完成次數，稀疏={sparse.completed} 密集={dense.completed}")


def test_circular_records_rep_start_duration_and_quality_on_completion():
    r = CircularRecognition("CW", turn_threshold=5.5, history_len=20)
    _feed(r, _circle_points(40, cw=True))
    assert r.completed == 1
    assert r.last_rep_start_t == pytest.approx(0.0)
    assert r.last_rep_duration is not None and r.last_rep_duration > 0
    # 合成的軌跡是精準的圓，半徑完全不變，圓度分數應該接近滿分。
    assert r.last_rep_quality == pytest.approx(100.0, abs=1.0)


# ---- circle_roundness_score ----

def test_circle_roundness_score_is_100_for_constant_radius():
    from games.game1_bilateral_vertical.motion import circle_roundness_score
    assert circle_roundness_score([0.1] * 20, cv_tolerance=0.5) == pytest.approx(100.0)


def test_circle_roundness_score_drops_as_radius_varies_more():
    from games.game1_bilateral_vertical.motion import circle_roundness_score
    steady = [0.1] * 20
    wobbly = [0.08, 0.12] * 10  # 半徑忽大忽小
    steady_score = circle_roundness_score(steady, cv_tolerance=0.5)
    wobbly_score = circle_roundness_score(wobbly, cv_tolerance=0.5)
    assert wobbly_score < steady_score
