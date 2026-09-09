"""
games/game3_lightsaber_marble/scoring.py - 純函式：命中計分、關卡過關判斷

實際加分本身很單純（命中一顆怪物固定 +HIT_SCORE 分），真正需要獨立出來測試的
是「這個分數算不算過關」跟「這局要存進歷史紀錄的 details 長什麼樣子」，維持跟
其他遊戲一致的 game_id/timestamp/score/details 存檔慣例（見
data_store/schema.py）。
"""

from dataclasses import dataclass


@dataclass
class SessionResult:
    score: int
    hits: int
    misses: int
    passed: bool

    def to_details(self, level_id: str) -> dict:
        return {
            "level_id": level_id,
            "passed": self.passed,
            "hits": self.hits,
            "misses": self.misses,
        }


def compute_session_result(score: int, hits: int, misses: int, level: dict) -> SessionResult:
    passed = score >= level["pass_score"]
    return SessionResult(score=score, hits=hits, misses=misses, passed=passed)
