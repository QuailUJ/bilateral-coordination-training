"""
games/game4_bilateral_press/scoring.py - 純函式：命中/誤觸/漏接計分規則

藍色三角形可以吃（命中加分、連擊+1），紅色三角形不能吃（誤觸扣分、斷連擊），
跟 press_pin 原本的配色語意一致。沒有三角形在判定區時按壓是「空按」，不計分
也不斷連擊——只有真的跟畫面上的三角形互動到才會影響分數。
"""

from dataclasses import dataclass, asdict


@dataclass
class ComboState:
    score: int = 0
    combo: int = 0
    max_combo: int = 0


def apply_press_hit(triangle_color: str, state: ComboState) -> ComboState:
    """按壓當下，判定區內剛好有一顆三角形時呼叫。"""
    if triangle_color == "blue":
        combo = state.combo + 1
        return ComboState(score=state.score + 1, combo=combo, max_combo=max(state.max_combo, combo))
    # "red"：誤觸不能吃的三角形，扣分並斷連擊。
    return ComboState(score=state.score - 1, combo=0, max_combo=state.max_combo)


def apply_miss(triangle_color: str, state: ComboState) -> ComboState:
    """三角形飄到判定區外緣、沒被按到就消失時呼叫。藍色沒接到才斷連擊（漏接不
    扣分，只是連擊中斷）；紅色沒去碰它是正確反應，不處罰、不斷連擊。"""
    if triangle_color == "blue":
        return ComboState(score=state.score, combo=0, max_combo=state.max_combo)
    return state


@dataclass
class SessionResult:
    score: int
    max_combo: int
    passed: bool

    def to_details(self, level_id: str) -> dict:
        d = asdict(self)
        d["level_id"] = level_id
        return d


def compute_session_result(state: ComboState, level: dict) -> SessionResult:
    passed = state.score >= level["pass_score"]
    return SessionResult(score=state.score, max_combo=state.max_combo, passed=passed)
