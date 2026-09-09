"""
games/game1_bilateral_vertical/scoring.py - 純函式：左右手「幾乎同時」各自
完成一次目標動作的同步計分

不 import pygame/cv2/mediapipe，只吃數字，方便單元測試。
"""

from dataclasses import dataclass


class ComboSyncTracker:
    """比照 BilateralCoordinationTraining 原版 Game1Scene 的同步判定方式：固定
    週期(window_sec)取一次「快照視窗」——視窗一開始記錄兩手當下各自的完成
    次數，視窗結束時比較兩手完成次數是不是都比視窗開始時增加了，只要這個
    週期內兩手都各自完成過至少一次動作就算「同步成功」一次。不要求兩次
    完成的確切時間點要多接近，比逐次比對兩個完成事件的時間戳寬鬆很多，也
    天生支援「左手水平、右手畫圓」這種不同動作類型組合（速度快慢不同也
    沒關係，只要都在同一個週期內各自完成過）。

    每一幀呼叫 update()，內部自己管理視窗的開始/結束，呼叫端不用自己算。
    """

    def __init__(self, window_sec: float):
        self.window_sec = window_sec
        self.window_start_t = None
        self._window_start_left = 0
        self._window_start_right = 0
        self.score = 0

    def update(self, t_s: float, left_completed: int, right_completed: int) -> bool:
        if self.window_start_t is None:
            self._start_window(t_s, left_completed, right_completed)
            return False

        if t_s - self.window_start_t < self.window_sec:
            return False

        synced = (left_completed > self._window_start_left and
                   right_completed > self._window_start_right)
        if synced:
            self.score += 1
        self._start_window(t_s, left_completed, right_completed)
        return synced

    def _start_window(self, t_s: float, left_completed: int, right_completed: int):
        self.window_start_t = t_s
        self._window_start_left = left_completed
        self._window_start_right = right_completed


def _tolerance_score(diff: float, tolerance: float) -> float:
    """差距為 0 分數是 100，差距達到 tolerance（含以上）分數是 0，中間線性
    遞減，不會變成負的。tolerance 是「差多少分數會趨近 0」的容忍值，不要求
    完全相等——這幾個容忍值目前都是先抓一個合理的初始值，還沒有實測校準過。
    """
    if tolerance <= 0:
        return 100.0 if diff <= 0 else 0.0
    return max(0.0, 100.0 * (1.0 - diff / tolerance))


class RepPairSyncTracker:
    """左右手各自完成動作依照『完成順序』配對——左手第 N 次配右手第 N 次，
    當作「第 N 組」，不要求兩手同時做完才配對。每一組依三項指標打 0~100 分：
        1. 同步性：兩手這組動作的開始時間差多少
        2. 速度相似度：兩手這組動作各自花了多久（起迄相同的完整一組時間）
        3. 第三項，依 third_mode 決定怎麼算：
            "diff"（水平/垂直擺動用）：兩手這組動作的「品質值」（例如最大
                位移量/幅度）差距換算成分數，是兩手互相比較的相對差距。
            "average"（畫圓用）：兩手這組動作各自的「品質值」已經是各自
                獨立算好的 0~100 分數（例如圓度分數），這裡直接取平均，不是
                比較兩手的差距——圓畫得夠不夠圓是各自的品質，不是比誰畫得
                比較圓。
    這一組的分數是三項的平均。玩滿 target_pairs 組之後，最終成績是這些分數
    的平均值，不是「同步幾次」這種計數。兩手速度差很多也沒關係，配對出來的
    時間差自然會很大、分數自然偏低，不用另外處理例外狀況。
    """

    def __init__(self, target_pairs: int, start_tolerance_s: float,
                 duration_tolerance_s: float, third_tolerance: float, third_mode: str = "diff"):
        if third_mode not in ("diff", "average"):
            raise ValueError(f"third_mode 必須是 'diff' 或 'average'，收到 {third_mode!r}")
        self.target_pairs = target_pairs
        self.start_tolerance_s = start_tolerance_s
        self.duration_tolerance_s = duration_tolerance_s
        self.third_tolerance = third_tolerance
        self.third_mode = third_mode
        self._pending_left = []
        self._pending_right = []
        self.pair_scores = []
        self.last_pair_detail = None

    def on_left_rep(self, start_t: float, duration: float, quality: float):
        self._pending_left.append((start_t, duration, quality))
        self._try_pair()

    def on_right_rep(self, start_t: float, duration: float, quality: float):
        self._pending_right.append((start_t, duration, quality))
        self._try_pair()

    def _try_pair(self):
        while (self._pending_left and self._pending_right
               and len(self.pair_scores) < self.target_pairs):
            left = self._pending_left.pop(0)
            right = self._pending_right.pop(0)
            self.pair_scores.append(self._score_pair(left, right))

    def _score_pair(self, left, right) -> float:
        l_start, l_duration, l_quality = left
        r_start, r_duration, r_quality = right

        start_score = _tolerance_score(abs(l_start - r_start), self.start_tolerance_s)
        duration_score = _tolerance_score(abs(l_duration - r_duration), self.duration_tolerance_s)

        if self.third_mode == "average":
            third_score = (l_quality + r_quality) / 2.0
        else:
            third_ref = max(l_quality, r_quality, 1e-6)
            third_diff_ratio = abs(l_quality - r_quality) / third_ref
            third_score = _tolerance_score(third_diff_ratio, self.third_tolerance)

        score = (start_score + duration_score + third_score) / 3.0
        self.last_pair_detail = {
            "start_diff_s": abs(l_start - r_start),
            "duration_diff_s": abs(l_duration - r_duration),
            "third_score": third_score,
            "score": score,
        }
        return score

    @property
    def completed_pairs(self) -> int:
        return len(self.pair_scores)

    @property
    def average_score(self) -> float:
        if not self.pair_scores:
            return 0.0
        return sum(self.pair_scores) / len(self.pair_scores)


class RepTrailRecorder:
    """記錄每一組配對(RepPairSyncTracker 產生的 pair)雙手各自完整的移動軌跡，
    給歷史紀錄回放用。呼叫端(scene.py)每幀把兩手目前正在做的這一組動作的
    軌跡點餵進來(record_left_point/record_right_point)，偵測到「這一組動作
    剛好完成」時呼叫 finish_left_rep()/finish_right_rep() 把目前累積的軌跡
    封存、清空給下一組用；跟 RepPairSyncTracker 一樣是 FIFO 配對——只要呼叫端
    在跟 sync_tracker.on_left_rep()/on_right_rep() 同一個時間點呼叫
    finish_left_rep()/finish_right_rep()，這裡配對出來的軌跡會跟
    RepPairSyncTracker 配對出來的分數自動對上同一組，不用另外傳索引比對。

    records（給存檔用的 list[dict]）：每次兩手都配對出新的一組，就會多兩筆
    {"round": 第幾組, "hand": "left"/"right", "score": 這組的分數,
     "trail": [[x,y], ...]}。
    """

    def __init__(self):
        self._current_left = []
        self._current_right = []
        self._pending_left = []
        self._pending_right = []
        self.records = []

    def record_left_point(self, point):
        self._current_left.append([point[0], point[1]])

    def record_right_point(self, point):
        self._current_right.append([point[0], point[1]])

    def finish_left_rep(self):
        self._pending_left.append(self._current_left)
        self._current_left = []

    def finish_right_rep(self):
        self._pending_right.append(self._current_right)
        self._current_right = []

    def discard_current(self, side):
        """Drop a broken, unfinished trail; keep completed reps queued for pairing."""
        if side == "left":
            self._current_left = []
        elif side == "right":
            self._current_right = []
        else:
            raise ValueError(side)

    def archive_pair_if_ready(self, round_no: int, pair_score: float):
        """在 sync_tracker 剛好配對出新的一組之後呼叫，把對應的兩手軌跡封存
        成 records。round_no 傳 sync_tracker.completed_pairs（配對後的組數，
        當作第幾輪），pair_score 傳 sync_tracker.pair_scores[-1]。"""
        if not self._pending_left or not self._pending_right:
            return  # 正常流程不會發生，呼叫端該在雙方都 finish 後才呼叫，這裡防呆而已
        left_trail = self._pending_left.pop(0)
        right_trail = self._pending_right.pop(0)
        score = round(pair_score, 1)
        self.records.append({"round": round_no, "hand": "left", "score": score, "trail": left_trail})
        self.records.append({"round": round_no, "hand": "right", "score": score, "trail": right_trail})


@dataclass
class SessionResult:
    score: int
    passed: bool

    def to_details(self, combo_id: str, reps: list = None) -> dict:
        details = {"level_id": combo_id, "passed": self.passed, "score": self.score}
        if reps is not None:
            details["reps"] = reps
        return details


def compute_session_result(score: int, completions_to_pass: int) -> SessionResult:
    return SessionResult(score=score, passed=score >= completions_to_pass)
