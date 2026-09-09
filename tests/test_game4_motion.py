import pytest

from games.game4_bilateral_press.motion import finger_straightness_deg, is_finger_bent


def test_finger_straightness_is_180_when_perfectly_straight():
    # MCP -> PIP -> TIP 三點共線（一直往上），夾角應該接近 180 度。
    angle = finger_straightness_deg((0, 3), (0, 2), (0, 0))
    assert angle == pytest.approx(180.0)


def test_finger_straightness_is_small_when_fully_curled():
    # TIP 折回 MCP 附近（往回彎），夾角應該接近 0 度。
    angle = finger_straightness_deg((0, 2), (0, 1), (0, 1.9))
    assert angle < 30


def test_is_finger_bent_threshold():
    # 手指打直(180度)不算彎折；折回去(接近0度)算彎折。
    assert is_finger_bent((0, 3), (0, 2), (0, 0), max_angle_deg=130) is False
    assert is_finger_bent((0, 2), (0, 1), (0, 1.9), max_angle_deg=130) is True


def test_is_finger_bent_does_not_depend_on_wrist_or_hand_movement():
    # 比照 press_pin 原本的手勢語意：只看食指自己的關節夾角，手腕/手掌怎麼移動
    # 都不影響判定——這裡把整組座標平移一大段模擬「手腕移動了」，判定結果應該
    # 完全不變。
    straight = (0, 3), (0, 2), (0, 0)
    bent = (0, 2), (0, 1), (0, 1.9)
    shift = (5.0, -3.0)

    def _shifted(points):
        return [(x + shift[0], y + shift[1]) for x, y in points]

    assert is_finger_bent(*_shifted(straight), max_angle_deg=130) is False
    assert is_finger_bent(*_shifted(bent), max_angle_deg=130) is True


def test_is_finger_bent_is_a_stateless_per_frame_check():
    # 不記錄歷史狀態：同一個彎曲姿勢連續呼叫幾次，每次都要回傳一樣的結果
    # （不是按一下放開才算一次的「事件」，是持續偵測當下姿勢），比照
    # press_pin 原本 hand_pressed() 的行為。
    bent = (0, 2), (0, 1), (0, 1.9)
    results = [is_finger_bent(*bent, max_angle_deg=130) for _ in range(5)]
    assert all(results)
