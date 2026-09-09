"""
games/game1_bilateral_vertical/scene.py - 遊戲零「16 種左右手動作組合」畫面

流程：GUIDE（操作說明，只有第一次玩才會出現）→ LEVEL_SELECT（16 種動作組合
排成 2 欄網格選一種）→ COUNTDOWN（3-2-1）→ PLAYING（左右手各自做自己的目標
動作，湊滿 TARGET_COMPLETIONS 組就結束，不再是固定時長）→ RESULT（顯示分數、
寫入歷史）。

【2026-09-09 計分方式分三種，見 _pair_scoring_mode()】雙手都是水平/垂直的
組合（例如 HH、VV、VH）用 scoring.py::RepPairSyncTracker，third_mode="diff"：
左右手各自完成的動作依完成順序配對，每組依「開始時間/花費時間/幅度」三項
算相似度分數（0~100，不用完全一樣），幅度是兩手互相比較的差距。雙手都是
畫圓的組合（CWCW、CCWCCW 等）也用 RepPairSyncTracker，但 third_mode="average"：
第三項改成「兩手圓度分數各自算好、直接平均」，不是互相比較差距（圓畫得
夠不夠圓是各自的品質，不是比誰畫得比較圓）。目標組數打完取平均當最終成績。
混合軸向+畫圓的組合（例如左垂直+右順時針）暫時還沒處理，維持原本
scoring.py::ComboSyncTracker 的同步視窗計數方式，之後再改。

【2026-09-07 改版】原本是單純「雙手垂直同步」，現在改成
BilateralCoordinationTraining 原版的完整 16 組合玩法：左右手各自獨立做
水平(H)/垂直(V)/順時針(CW)/逆時針(CCW)，示範用簡單的旋轉/擺動箭頭圖示（不做
影片示範）。GAME_ID 維持不變，歷史紀錄相容；details 裡的 "level_id" 現在存的
是動作組合的 combo_id（例如 "HH"、"CCWCW"）而不是原本的 "lv1"/"lv2"/"lv3"。

這支檔案是唯一會碰 CameraStream / HandLandmarker / pygame 畫面的地方；實際的
動作偵測/同步計分邏輯都委派給 motion.py / scoring.py 這兩支純函式模組。

跟遊戲一（手指版）共用配對計分、畫圓與追蹤防護；手指版的水平／垂直
使用獨立的食指伸展辨識器，本遊戲仍保留原本的擺動判定。
"""

import math
import copy
from common import game_time as time
from collections import deque

import cv2
import mediapipe as mp
import pygame

from common.cv_pygame import bgr_frame_to_surface
from common.fist_tracking import FistIdentityTracker, palm_center, PALM_IDS, LOSS_GRACE_S
from games.game1_bilateral_vertical.fist_motion import FistAxisRecognition, FistCircularRecognition, CIRCLE_RADIUS
from common.training_tracking import interrupt_hand
from common.training_diagnostics import start_diagnostics, record_diagnostics, export_diagnostics
from ui.training_panels import training_layout, draw_training_panels
from common.scene_manager import Scene, Transition
from data_store import user_store
from common.background_persistence import begin_result_save
from games.game1_bilateral_vertical import config as cfg
from games.game1_bilateral_vertical import motion, scoring
from ui.theme import get_font, COLOR_BG, COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARN, PADDING
from ui.widgets import Button, LevelSelect, InstructionPanel
from ui.hand_action_select import HandActionSelect, LABELS
from games.game1_bilateral_vertical.single_hand import DisabledRecognition, SingleHandTracker
from games.game1_bilateral_vertical.circle_trial_motion import UpperReversalCircle

GAME_ID = "game1_bilateral_vertical"
DISPLAY_NAME = "遊戲零．動作組合"
DESCRIPTION = "左右手各自水平/垂直/畫圓，練習雙側協調"

_WRIST = 0

_COUNTDOWN_SECONDS = 3.0

_DISTANCE_HINT_TEXT = {
    "too_close": "離攝影機太近了，請往後退一點",
    "too_far": "離攝影機太遠了，請往前靠近一點",
}

_DEMO_PERIOD_SEC = {"H": 1.6, "V": 1.6, "CW": 2.0, "CCW": 2.0}
_DEMO_AMPLITUDE_PX = 70

# 手部軌跡線：兩手同步成功、進入下一組的瞬間會整個清空重畫（見 _process_frame
# 裡 sync_tracker 記到分之後的清空邏輯），但如果一直沒同步成功，軌跡會一直
# 累積到這個上限才停止變長，畫面上會拖著一條停留很久的長尾巴——改小這個上限，
# 讓軌跡變成只顯示「最近一小段」的短尾巴，不會整組動作做到一半就已經拖得
# 老長。
_TRAIL_MAX_POINTS = 30


def _mirrored_xy(landmark):
    """跟畫面顯示的鏡像視角一致的座標（x 取 1.0-x）。水平/畫圓的方向判斷要用
    這個，不然方向會跟畫面上看到的相反（見 motion.py 的座標系說明）。"""
    return (1.0 - landmark.x, landmark.y)


def _make_recognizer(action_type):
    if action_type == "N":
        return DisabledRecognition()
    if action_type == "H":
        return FistAxisRecognition(
            "x", cfg.HORIZONTAL_AMP_ON, cfg.HORIZONTAL_AMP_OFF, cfg.HORIZONTAL_MIN_INTERVAL_S)
    if action_type == "V":
        return FistAxisRecognition(
            "y", cfg.VERTICAL_AMP_ON, cfg.VERTICAL_AMP_OFF, cfg.VERTICAL_MIN_INTERVAL_S)
    if action_type in ("CW", "CCW"):
        return UpperReversalCircle(action_type)
    raise ValueError(f"未知的動作類型: {action_type}")


def _pair_scoring_mode(action):
    """回傳這個組合該用哪一種配對計分模式，或者 None 代表沿用舊版
    ComboSyncTracker：
        "axis"：兩手都是水平/垂直，配對的第三項比「幅度差距」。
        "circular"：兩手都是畫圓，配對的第三項是「兩手圓度分數的平均」。
        None：混合軸向+畫圓的組合，暫時還沒處理，之後再改。
    """
    left, right = action["left"], action["right"]
    if left in ("H", "V") and right in ("H", "V"):
        return "axis"
    if left in ("CW", "CCW") and right in ("CW", "CCW"):
        return "circular"
    return None


def _rep_quality(recognizer):
    """取出這個 recognizer 最近一次完成動作的『第三項品質值』，不管底層是
    AxisSwingRecognition(幅度)還是 CircularRecognition(圓度分數)，呼叫端不用
    自己判斷型別。"""
    if isinstance(recognizer, motion.AxisSwingRecognition):
        return recognizer.last_rep_peak
    return recognizer.last_rep_quality


def _demo_offset(action_type, t_s):
    """示範圖示這一刻該在的相對位移 (dx, dy)，純時間驅動、跟真實手部資料無關，
    只是給玩家看的動作示範動畫（取代原本規劃的影片示範，保持最小可用）。
    """
    period = _DEMO_PERIOD_SEC[action_type]
    phase = (t_s % period) / period * 2 * math.pi
    if action_type == "H":
        return _DEMO_AMPLITUDE_PX * math.sin(phase), 0.0
    if action_type == "V":
        return 0.0, -_DEMO_AMPLITUDE_PX * math.sin(phase)
    # CW/CCW：規定要從12點鐘方向開始畫（見 motion.py::CircularRecognition），
    # 示範動畫的起點要對得上，所以相位平移 -90 度，phase=0 時落在正上方。
    angle = (phase if action_type == "CW" else -phase) - math.pi / 2
    return _DEMO_AMPLITUDE_PX * math.cos(angle), _DEMO_AMPLITUDE_PX * math.sin(angle)


def _recognizer_debug_text(recognizer):
    """給除錯 HUD 用：不管是 AxisSwingRecognition 還是 CircularRecognition，都印出
    「完成幾次」+ 各自類型專屬的內部進度，這樣才看得出動作有沒有被判定成
    「往正確方向動了一下」，而不是完全沒反應。"""
    if recognizer is None:
        return "尚未偵測到手"
    if isinstance(recognizer, motion.AxisSwingRecognition):
        text = f"完成{recognizer.completed}　半擺動{recognizer.half_swings}　狀態{recognizer.state}"
        if recognizer.last_rep_duration is not None:
            text += f"　上組耗時{recognizer.last_rep_duration:.2f}s　幅度{recognizer.last_rep_peak:.2f}"
        return text
    if isinstance(recognizer, motion.CircularRecognition):
        text = (f"完成{recognizer.completed}　{recognizer._phase}　"
                f"累積角度{math.degrees(recognizer.turn_acc):.0f}°")
        if recognizer.last_rep_quality is not None:
            text += f"　上圈耗時{recognizer.last_rep_duration:.2f}s　圓度{recognizer.last_rep_quality:.0f}分"
        return text
    return ""


def _sync_window_debug_text(sync_tracker):
    """給除錯 HUD 用：印出目前同步視窗還剩幾秒才會結算，方便看到「不是沒同步，
    只是視窗還沒到」。"""
    if sync_tracker is None or sync_tracker.window_start_t is None:
        return "同步視窗　尚未開始"
    remaining = sync_tracker.window_sec - (time.time() - sync_tracker.window_start_t)
    return f"同步視窗剩餘 {max(0.0, remaining):.1f}s"


def _pair_detail_debug_text(sync_tracker):
    """給除錯 HUD 用：印出最近一組配對的分數細節，方便看出是哪一項（同步性/
    速度/第三項）差距太大，之後要調整 config.py 的容忍值時有個依據。第三項
    在 axis 模式是「幅度差距換算的分數」，circular 模式是「兩手圓度分數的
    平均」，數字本身已經是 0~100 分，兩種模式都能直接看。"""
    detail = sync_tracker.last_pair_detail
    if detail is None:
        return "尚未配對出任何一組"
    return (f"上一組　開始差{detail['start_diff_s']:.2f}s　"
            f"時間差{detail['duration_diff_s']:.2f}s　"
            f"第三項{detail['third_score']:.0f}分　"
            f"得{detail['score']:.0f}分")


def _draw_marker_icon(surface, center, radius, color):
    """畫一個簡化的拳頭圖示：一個主體圓再疊幾個小圓當指節。遊戲一（手指版）用
    的是點點圖示，見 games/game2_finger_vertical/scene.py::_draw_dot_icon。"""
    cx, cy = center
    pygame.draw.circle(surface, color, (cx, cy), radius)
    knuckle_r = max(3, radius // 4)
    for dx in (-radius * 0.5, -radius * 0.17, radius * 0.17, radius * 0.5):
        pygame.draw.circle(surface, color, (int(cx + dx), int(cy - radius * 0.55)), knuckle_r)


class Game1Scene(Scene):
    make_recognizer = staticmethod(_make_recognizer)
    target_completions = cfg.TARGET_COMPLETIONS

    def on_enter(self, ctx, **kwargs):
        if kwargs.get("resumed"):
            return  # 這個場景不會被「resume」，這裡只是防呆

        self._username = ctx.current_user
        self.level_options = [
            {"level_id": a["combo_id"], "label": a["label"], "unlocked": True}
            for a in cfg.ACTION_SETS
        ]
        self.selected_action = None
        self.single_side = None

        w, h = ctx.screen.get_size()
        self.level_select_widget = HandActionSelect((w, h), self._on_actions_selected)

        self.guide_panel = InstructionPanel(
            (w // 2 - 360, h // 2 - 230, 720, 420), DISPLAY_NAME,
            [
                "左右手各選一項動作；選不使用即可只測試另一隻手。",
                "水平／垂直直接來回移動拳頭：反向時記錄極限點，兩段算一組，不必回固定點。",
                "畫圓從上方開始，繞回上方再稍微向下便結算；不用接回原點或固定圓心。",
                "單手測試完成十組結束；雙手依所選動作進行配對或同步計分。",
            ],
            self._on_guide_dismissed,
        )
        played_before = len(user_store.get_history_for_game(ctx.current_user, GAME_ID, limit=1)) > 0
        self.state = "level_select" if played_before else "guide"
        self.state_start_time = time.time()

        self.hand_identity = FistIdentityTracker()
        self._missing_since = {}
        self._last_points = {}
        self.last_sample_time = time.time()
        self.last_frame_id = -1
        self.display_frame = None
        self.left_landmarks = None
        self.right_landmarks = None
        self.distance_hint = None

        self.left_recognizer = None
        self.right_recognizer = None
        self.sync_tracker = None
        self.pair_scoring_mode = None
        self.trail_recorder = None
        self.left_trail = deque(maxlen=_TRAIL_MAX_POINTS)
        self.right_trail = deque(maxlen=_TRAIL_MAX_POINTS)
        self.session_result = None
        self._pending_transition = None

        self.back_button = Button((PADDING, h - PADDING - 56, 200, 56), "返回主選單", on_click=self._go_back)

    def _go_back(self):
        self._pending_transition = Transition("pop")

    def _on_guide_dismissed(self):
        self.state = "level_select"
        self.state_start_time = time.time()

    def _on_level_selected(self, combo_id):
        self.selected_action = next(a for a in cfg.ACTION_SETS if a["combo_id"] == combo_id)
        self.state = "countdown"
        self.state_start_time = time.time()

    def _on_actions_selected(self, choices):
        if not any(action != "N" for action in choices.values()):
            return
        self.selected_action = dict(choices, combo_id=choices["left"] + choices["right"],
            label=f"左手：{LABELS[choices['left']]}＋右手：{LABELS[choices['right']]}")
        self.state = "countdown"
        self.state_start_time = time.time()
        active = [side for side in ("left", "right") if choices[side] != "N"]
        self.single_side = active[0] if len(active) == 1 else None
        self.hand_identity = FistIdentityTracker(self.single_side.title() if self.single_side else None)

    # ---- 事件 / 每幀更新 ----

    def handle_event(self, ctx, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._go_back()
        if self.state == "guide":
            self.guide_panel.handle_event(event)
        if self.state == "level_select":
            self.level_select_widget.handle_event(event)
            self.back_button.handle_event(event)
        if self.state == "result":
            self.back_button.handle_event(event)
        return None

    def update(self, ctx, dt):
        if getattr(self, "_camera_index", ctx.camera_index) != ctx.camera_index:
            self.hand_identity = FistIdentityTracker(self.single_side.title() if self.single_side else None)
            self._missing_since.clear()
            self._last_points.clear()
            self.last_frame_id = -1
            if self.state == "playing":
                for side in ("left", "right"):
                    if self.selected_action[side] == "N":
                        continue
                    interrupt_hand(self, side, self.make_recognizer)
        self._camera_index = ctx.camera_index
        frame, self.last_frame_id, _cam_read_ms = ctx.camera.get_next(self.last_frame_id, timeout=0.0)
        if frame is not None:
            self.last_sample_time = time.time()
            self._process_frame(frame, ctx.landmarker)
        elif time.time() - self.last_sample_time > 0.35:
            self.left_landmarks = self.right_landmarks = None
            self.hand_identity.active.clear()
            self.hand_identity.pending.clear()
            if self.state == "playing":
                for side in ("left", "right"):
                    if self.selected_action[side] == "N":
                        continue
                    interrupt_hand(self, side, self.make_recognizer)
                    self.hand_identity.status[side.title()] = {"reason": "camera_gap", "accepted": False}
                record_diagnostics(self, time.time(), source="camera_gap")

        self._advance_state(ctx)

        if self._pending_transition is not None:
            t, self._pending_transition = self._pending_transition, None
            return t
        return None

    def _process_frame(self, frame, landmarker):
        # 偵測一定要用原始、未翻轉的畫面（見 common.camera_hand_tracker 檔頭說明）。
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = getattr(landmarker, "detect_fists", landmarker.detect)(mp_image)

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        left_landmarks, right_landmarks = self.hand_identity.update(result, time.time())
        for label, landmarks in (("Left", left_landmarks), ("Right", right_landmarks)):
            if landmarks is not None:
                points = [tuple(map(int, ((1-landmarks[i].x)*w, landmarks[i].y*h))) for i in PALM_IDS]
                color = (255, 120, 0) if label == "Left" else (0, 0, 255)
                for a, b in zip(points, points[1:] + points[:1]):
                    cv2.line(frame, a, b, color, 2)

        self.display_frame = frame
        self.left_landmarks = left_landmarks
        self.right_landmarks = right_landmarks

        # Palm size changes with fist orientation: avoid the open-hand distance
        # warning based on occluded fingertips in this mode.
        self.distance_hint = None

        if self.state != "playing":
            return

        for side, landmarks in (("left", left_landmarks), ("right", right_landmarks)):
            if self.selected_action[side] == "N":
                continue
            if landmarks is None:
                now = time.time()
                since = self._missing_since.setdefault(side, now)
                recognizer = getattr(self, side + "_recognizer")
                trail = getattr(self, side + "_trail")
                if self.selected_action[side] in ("CW", "CCW"):
                    if trail and trail[-1] is not None:
                        trail.append(None)
                else:
                    trail.clear()
                if hasattr(recognizer, "pause"):
                    recognizer.pause()
                reason = self.hand_identity.status[side.title()]["reason"]
                hard_loss = reason in ("identity_conflict", "wrist_jump", "hands_overlap", "duplicate_label", "invalid_coordinates")
                if hard_loss or now - since > LOSS_GRACE_S:
                    interrupt_hand(self, side, self.make_recognizer)
                else:
                    recognizer.feedback = "短暫漏偵測，暫停動作判定"
            else:
                if side in self._missing_since:
                    gap = time.time() - self._missing_since.pop(side)
                    old = self._last_points.get(side)
                    if gap > LOSS_GRACE_S or (old is not None and math.dist(old, palm_center(landmarks)) > 0.08):
                        interrupt_hand(self, side, self.make_recognizer)
                self.tracking_lost[side] = False
                self._last_points[side] = palm_center(landmarks)

        t_s = time.time()
        left_before = self.left_recognizer.completed
        right_before = self.right_recognizer.completed
        if left_landmarks is not None:
            wrist = _mirrored_xy(left_landmarks[_WRIST])
            tip = palm_center(left_landmarks)
            self.left_trail.append(tip)
            if self.pair_scoring_mode is not None:
                self.trail_recorder.record_left_point(tip)
            self.left_recognizer.update(t_s, tip[0], tip[1], wrist[0], wrist[1])
        if right_landmarks is not None:
            wrist = _mirrored_xy(right_landmarks[_WRIST])
            tip = palm_center(right_landmarks)
            self.right_trail.append(tip)
            if self.pair_scoring_mode is not None:
                self.trail_recorder.record_right_point(tip)
            self.right_recognizer.update(t_s, tip[0], tip[1], wrist[0], wrist[1])

        for side, before in (("left", left_before), ("right", right_before)):
            recognizer = getattr(self, side + "_recognizer")
            if isinstance(recognizer, UpperReversalCircle) and recognizer.completed > before:
                record = copy.deepcopy(recognizer.last_record)
                record["hand"] = side
                for key in ("start_t", "end_t"):
                    record[key] -= self.diagnostics["time_origin"]
                self.circle_records_by_hand[side].append(record)
                if self.trail_recorder is not None:
                    setattr(self.trail_recorder, "_current_" + side, copy.deepcopy(record["trail"]))

        if self.pair_scoring_mode is not None:
            # 配對計分：左右手各自完成一組動作時，把這一組的起始時間/花費
            # 時間/第三項品質值餵給 RepPairSyncTracker，讓它照完成順序配對
            # 打分數，見 scoring.py::RepPairSyncTracker 的說明。同一時間點也
            # 把目前累積的軌跡封存進 trail_recorder，兩邊都是 FIFO，配對出來
            # 的軌跡自然會對上同一組分數，給歷史紀錄回放用。
            pairs_before = self.sync_tracker.completed_pairs
            if self.left_recognizer.completed > left_before:
                self.sync_tracker.on_left_rep(
                    self.left_recognizer.last_rep_start_t,
                    self.left_recognizer.last_rep_duration,
                    _rep_quality(self.left_recognizer))
                self.trail_recorder.finish_left_rep()
            if self.right_recognizer.completed > right_before:
                self.sync_tracker.on_right_rep(
                    self.right_recognizer.last_rep_start_t,
                    self.right_recognizer.last_rep_duration,
                    _rep_quality(self.right_recognizer))
                self.trail_recorder.finish_right_rep()
            synced = self.sync_tracker.completed_pairs > pairs_before
            if synced:
                self.trail_recorder.archive_pair_if_ready(
                    self.sync_tracker.completed_pairs, self.sync_tracker.pair_scores[-1])
        else:
            # 同步判定固定每 SYNC_WINDOW_SEC 檢查一次視窗，不是逐次比對兩手
            # 完成事件的時間戳，見 scoring.py::ComboSyncTracker 的說明。
            synced = self.sync_tracker.update(
                t_s, self.left_recognizer.completed, self.right_recognizer.completed)

        for side in ("left", "right"):
            recognizer = getattr(self, side + "_recognizer")
            trail = getattr(self, side + "_trail")
            if self.selected_action[side] in ("CW", "CCW"):
                if recognizer.just_started_lap:
                    trail.clear()
                    if isinstance(recognizer, UpperReversalCircle):
                        trail.extend((p[1], p[2]) for p in recognizer.points)
                        self.trail_start_times[side] = recognizer._lap_start_t
                        if self.trail_recorder is not None:
                            setattr(self.trail_recorder, "_current_" + side, [[p[1], p[2]] for p in recognizer.points])
            elif synced:
                trail.clear()

        if self.single_circle:
            records = self.circle_records_by_hand[self.single_side]
            self.sync_tracker.average_score = sum(r["quality"] for r in records)/len(records) if records else 0
        record_diagnostics(self, t_s)

    def _advance_state(self, ctx):
        now = time.time()
        elapsed_in_state = now - self.state_start_time

        if self.state == "countdown":
            if elapsed_in_state >= _COUNTDOWN_SECONDS:
                self._start_playing(now)
        elif self.state == "playing":
            completed_pairs = (self.sync_tracker.completed_pairs if self.pair_scoring_mode is not None
                                else self.sync_tracker.score)
            if completed_pairs >= self.target_completions:
                self._finish_playing(ctx)

    def _start_playing(self, now):
        self.circle_records_by_hand = {"left": [], "right": []}
        active = [side for side in ("left", "right") if self.selected_action[side] != "N"]
        if not active:
            raise ValueError("至少啟用一隻手")
        self.single_side = active[0] if len(active) == 1 else None
        self.single_circle = bool(self.single_side and self.selected_action[self.single_side] in ("CW", "CCW"))
        if self.single_circle:
            self.score_kind = "circle_quality"
        else:
            self.__dict__.pop("score_kind", None)
        self.hand_identity = FistIdentityTracker(self.single_side.title() if self.single_side else None)
        self.state = "playing"
        self.state_start_time = now
        self.left_recognizer = self.make_recognizer(self.selected_action["left"])
        self.right_recognizer = self.make_recognizer(self.selected_action["right"])
        self.pair_scoring_mode = _pair_scoring_mode(self.selected_action)
        if self.single_side:
            self.sync_tracker = SingleHandTracker(self.single_side)
        elif self.pair_scoring_mode is not None:
            third_tolerance = (cfg.PAIR_PEAK_TOLERANCE_RATIO if self.pair_scoring_mode == "axis" else 0.0)
            self.sync_tracker = scoring.RepPairSyncTracker(
                cfg.TARGET_COMPLETIONS, cfg.PAIR_START_TOLERANCE_S,
                cfg.PAIR_DURATION_TOLERANCE_S, third_tolerance,
                third_mode=("diff" if self.pair_scoring_mode == "axis" else "average"))
        else:
            self.sync_tracker = scoring.ComboSyncTracker(cfg.SYNC_WINDOW_SEC)
        self.trail_recorder = scoring.RepTrailRecorder() if self.pair_scoring_mode is not None else None
        self.trail_start_times = {"left": now, "right": now}
        for side in ("left", "right"):
            circular = self.selected_action[side] in ("CW", "CCW")
            setattr(self, side + "_trail", deque(maxlen=None if circular else _TRAIL_MAX_POINTS))

        start_diagnostics(self, now)

    def _finish_playing(self, ctx):
        if self.single_circle:
            self.session_result = scoring.SessionResult(round(self.sync_tracker.average_score),
                                                       self.sync_tracker.score >= self.target_completions)
            details = self.session_result.to_details(self.selected_action["combo_id"],
                reps=self.circle_records_by_hand[self.single_side])
            details.update(score_kind="mean_circle_roundness", completed_circles=self.sync_tracker.score)
        elif self.pair_scoring_mode is not None:
            final_score = round(self.sync_tracker.average_score)
            self.session_result = scoring.compute_session_result(final_score, cfg.PAIR_PASS_SCORE)
            details = self.session_result.to_details(
                self.selected_action["combo_id"], reps=self.trail_recorder.records)
        else:
            self.session_result = scoring.compute_session_result(
                self.sync_tracker.score, cfg.TARGET_COMPLETIONS)
            details = self.session_result.to_details(self.selected_action["combo_id"])
        details["analysis"] = export_diagnostics(self, ctx)
        details["action_label"] = self.selected_action["label"]
        details["training_mode"] = "single" if self.single_side else "bilateral"
        if self.single_circle:
            details["training_mode"] = "single_circle"
        details["circle_records"] = self.circle_records_by_hand
        details["enabled_hands"] = [side for side in ("left", "right") if self.selected_action[side] != "N"]
        begin_result_save(self, ctx, GAME_ID, self.session_result.score, details)
        self.state_start_time = time.time()

    # ---- 畫面 ----

    def draw(self, ctx, surface):
        surface.fill(COLOR_BG)
        w, h = surface.get_size()

        title_font = get_font(32)
        title = title_font.render(DISPLAY_NAME, True, COLOR_TEXT)
        surface.blit(title, title.get_rect(centerx=w // 2, top=20))

        if self.state == "guide":
            self.guide_panel.draw(surface)
        elif self.state == "level_select":
            self._draw_level_select(surface, w)
            self.back_button.draw(surface)
        else:
            video_rect = self._draw_camera_feed(surface, w, h)
            if self.state == "countdown":
                self._draw_countdown(surface, w, h)
            elif self.state == "playing":
                self._draw_playing_hud(surface, w, video_rect)
                self._draw_hand_trails(surface, video_rect)
                self._draw_hand_markers(surface, video_rect)
                self._draw_demo_icons(surface, w, h)
            elif self.state == "result":
                self._draw_result(surface, w, h)

    def _draw_level_select(self, surface, w):
        font = get_font(24)
        msg = font.render("左右手分別勾選動作，再開始測試", True, COLOR_TEXT)
        surface.blit(msg, msg.get_rect(centerx=w // 2, top=80))
        self.level_select_widget.draw(surface)

    def _draw_camera_feed(self, surface, w, h):
        _, area, _ = training_layout((w, h))
        if self.display_frame is None:
            return area
        frame_surface = bgr_frame_to_surface(self.display_frame)
        image_h, image_w = self.display_frame.shape[:2]
        scale = min(area.width / image_w, area.height / image_h)
        size = (max(1, int(image_w * scale)), max(1, int(image_h * scale)))
        frame_surface = pygame.transform.smoothscale(frame_surface, size)
        rect = frame_surface.get_rect(center=area.center)
        surface.blit(frame_surface, rect)
        return rect

    def _draw_countdown(self, surface, w, h):
        remaining = _COUNTDOWN_SECONDS - (time.time() - self.state_start_time)
        number = max(1, math.ceil(remaining))
        font = get_font(120)
        text = font.render(str(number), True, COLOR_ACCENT)
        surface.blit(text, text.get_rect(center=(w // 2, h // 2 + 100)))

        hint_font = get_font(24)
        hint = hint_font.render(f"準備開始：{self.selected_action['label']}", True, COLOR_TEXT_MUTED)
        surface.blit(hint, hint.get_rect(centerx=w // 2, top=h // 2 + 220))

    def _draw_playing_hud(self, surface, w, video_rect):
        draw_training_panels(surface, self.debug_snapshot)

    def _draw_hand_trails(self, surface, video_rect):
        """畫出兩手「目前這一組」的移動軌跡線。軌跡點在 _process_frame 裡累積，
        兩手同步成功、進入下一組的瞬間會被清空，所以畫面上任何時刻看到的都是
        當下這一組從頭到現在的完整路徑，不會累積成一團亂線。"""
        if video_rect.width == 0 or self.display_frame is None:
            return
        frame_h, frame_w = self.display_frame.shape[:2]
        scale_x = video_rect.width / frame_w
        scale_y = video_rect.height / frame_h

        for trail, color in ((self.left_trail, cfg.LEFT_HAND_COLOR), (self.right_trail, cfg.RIGHT_HAND_COLOR)):
            if len(trail) < 2:
                continue
            points = []
            for point in list(trail) + [None]:
                if point is None:
                    if len(points) >= 2:
                        pygame.draw.lines(surface, color, False, points, 3)
                    points = []
                else:
                    points.append((video_rect.left + int(point[0] * video_rect.width),
                                   video_rect.top + int(point[1] * video_rect.height)))

    def _draw_hand_markers(self, surface, video_rect):
        if video_rect.width == 0 or self.display_frame is None:
            return
        frame_h, frame_w = self.display_frame.shape[:2]
        scale_x = video_rect.width / frame_w
        scale_y = video_rect.height / frame_h

        for landmarks, color in (
            (self.left_landmarks, cfg.LEFT_HAND_COLOR),
            (self.right_landmarks, cfg.RIGHT_HAND_COLOR),
        ):
            if landmarks is None:
                continue
            x, y = palm_center(landmarks)
            px = x * frame_w
            py = y * frame_h
            center = (video_rect.left + int(px * scale_x), video_rect.top + int(py * scale_y))
            _draw_marker_icon(surface, center, cfg.HAND_MARKER_RADIUS, color)

        for recognizer, color in ((self.left_recognizer, cfg.LEFT_HAND_COLOR), (self.right_recognizer, cfg.RIGHT_HAND_COLOR)):
            endpoint = getattr(recognizer, "turning_point", None)
            if endpoint is not None:
                point = (video_rect.left + int(endpoint[0] * video_rect.width), video_rect.top + int(endpoint[1] * video_rect.height))
                pygame.draw.circle(surface, color, point, 5, 1)
            if recognizer is None or recognizer.reference is None:
                continue
            x, y = recognizer.reference
            center = (video_rect.left + int(x * video_rect.width), video_rect.top + int(y * video_rect.height))
            pygame.draw.circle(surface, color, center, 9, 2)
            if isinstance(recognizer, FistCircularRecognition):
                rect = pygame.Rect(0, 0, int(CIRCLE_RADIUS * 2 * video_rect.width), int(CIRCLE_RADIUS * 2 * video_rect.height))
                rect.center = center
                pygame.draw.ellipse(surface, color, rect, 1)

    def _draw_demo_icons(self, surface, w, h):
        """左右兩側各畫一個示範箭頭，跟著目標動作的節奏動，給玩家看要跟著做
        什麼動作（取代影片示範）。"""
        t_s = time.time()
        _, area, _ = training_layout((w, h))
        base_y = h - 120
        for side, action_type, color, base_x in (
            ("left", self.selected_action["left"], cfg.LEFT_HAND_COLOR, area.left + area.width * 0.22),
            ("right", self.selected_action["right"], cfg.RIGHT_HAND_COLOR, area.left + area.width * 0.72),
        ):
            if action_type == "N":
                continue
            dx, dy = _demo_offset(action_type, t_s)
            center = (int(base_x + dx), int(base_y + dy))
            pygame.draw.circle(surface, color, center, 14)
            pygame.draw.circle(surface, COLOR_TEXT, center, 14, width=2)

        label_font = get_font(20)
        left_label = label_font.render(f"左手：{LABELS[self.selected_action['left']]}", True, cfg.LEFT_HAND_COLOR)
        right_label = label_font.render(f"右手：{LABELS[self.selected_action['right']]}", True, cfg.RIGHT_HAND_COLOR)
        surface.blit(left_label, left_label.get_rect(centerx=int(area.left + area.width * 0.22), top=h - 48))
        surface.blit(right_label, right_label.get_rect(centerx=int(area.left + area.width * 0.72), top=h - 48))

    def _draw_result(self, surface, w, h):
        score_font = get_font(72)
        score_label = f"平均 {self.session_result.score} 分" if self.pair_scoring_mode is not None else f"{self.session_result.score} 次同步"
        if self.single_side:
            score_label = f"完成 {self.session_result.score} 組"
        if self.single_circle:
            score_label = f"完成 {self.sync_tracker.score} 圈　平均圓度 {self.session_result.score} 分"
        score_text = score_font.render(score_label, True, COLOR_SUCCESS)
        surface.blit(score_text, score_text.get_rect(centerx=w // 2, top=h // 2 - 80))

        passed = self.session_result.passed
        pass_color = COLOR_SUCCESS if passed else COLOR_WARN
        pass_label = (f"{self.selected_action['label']}　過關！" if passed
                      else f"{self.selected_action['label']}　未過關，再試一次")
        info_font = get_font(28)
        info = info_font.render(pass_label, True, pass_color)
        surface.blit(info, info.get_rect(centerx=w // 2, top=h // 2 + 10))

        self.back_button.draw(surface)
