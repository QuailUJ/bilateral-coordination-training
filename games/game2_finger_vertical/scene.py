"""遊戲一：以食指尖追蹤 16 種雙手動作組合。

水平／垂直使用獨立的握拳、食指伸展、收回判定；畫圓沿用圓形辨識器，
追蹤點改為食指尖。所有組合固定 60 秒，同步完成一組 +1 分，8 分過關並儲存回放。
左右手身分檢查與遊戲零共用，漏偵測時清除未完成動作，保留已完成組數。
"""

import math
from common import game_time as time
from common import timed_training
from collections import deque

import cv2
import mediapipe as mp
import pygame

from common.camera_hand_tracker import draw_hand_skeleton, estimate_distance_hint
from common.hand_identity import HandIdentityTracker
from common.training_tracking import interrupt_hand
from common.training_diagnostics import start_diagnostics, record_diagnostics, export_diagnostics
from ui.training_panels import training_layout, draw_training_panels, draw_training_view
from common.scene_manager import Scene, Transition
from data_store import user_store
from common.background_persistence import begin_result_save
from games.game1_bilateral_vertical import config as shared_cfg
from games.game1_bilateral_vertical import motion, scoring
from games.game2_finger_vertical import config as cfg
from games.game2_finger_vertical.motion import FingerExtensionRecognition
from ui.theme import get_font, COLOR_BG, COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARN, PADDING
from ui.widgets import Button, LevelSelect, InstructionPanel

GAME_ID = "game2_finger_vertical"
DISPLAY_NAME = "遊戲一．動作組合（手指）"
DESCRIPTION = "食指尖伸展與畫圓，60 秒內同步完成動作"

_WRIST = 0
_INDEX_TIP = 8

_COUNTDOWN_SECONDS = 3.0

_DISTANCE_HINT_TEXT = {
    "too_close": "離攝影機太近了，請往後退一點",
    "too_far": "離攝影機太遠了，請往前靠近一點",
}

_DEMO_PERIOD_SEC = {"H": 1.6, "V": 1.6, "CW": 2.0, "CCW": 2.0}
_DEMO_AMPLITUDE_PX = 70

_TRAIL_MAX_POINTS = 30  # 見 game1_bilateral_vertical/scene.py 同名常數的說明


def _mirrored_xy(landmark):
    return (1.0 - landmark.x, landmark.y)


def _make_recognizer(action_type):
    if action_type in ("H", "V"):
        return FingerExtensionRecognition(action_type)
    if action_type in ("CW", "CCW"):
        return motion.CircularRecognition(
            action_type, shared_cfg.CIRCULAR_TURN_THRESHOLD, shared_cfg.CIRCULAR_HISTORY_LEN,
            shared_cfg.CIRCLE_START_ANGLE_TOLERANCE_DEG, shared_cfg.CIRCLE_ROUNDNESS_CV_TOLERANCE)
    raise ValueError(f"未知的動作類型: {action_type}")


def _pair_scoring_mode(action):
    """軸向比較幅度；畫圓與混合組合取各手品質平均，皆以完成次數配對。"""
    left, right = action["left"], action["right"]
    if left in ("H", "V") and right in ("H", "V"):
        return "axis"
    if left in ("CW", "CCW") and right in ("CW", "CCW"):
        return "circular"
    return "mixed"


def _rep_quality(recognizer, mode="axis"):
    if isinstance(recognizer, FingerExtensionRecognition):
        return recognizer.last_rep_peak if mode == "axis" else recognizer.last_rep_quality
    if isinstance(recognizer, motion.AxisSwingRecognition):
        return recognizer.last_rep_peak
    return recognizer.last_rep_quality


def _demo_offset(action_type, t_s):
    period = _DEMO_PERIOD_SEC[action_type]
    phase = (t_s % period) / period * 2 * math.pi
    if action_type == "H":
        return _DEMO_AMPLITUDE_PX * (1 - math.cos(phase)) / 2, 0.0
    if action_type == "V":
        return 0.0, -_DEMO_AMPLITUDE_PX * (1 - math.cos(phase)) / 2
    angle = (-phase if action_type == "CW" else phase) - math.pi / 2
    return _DEMO_AMPLITUDE_PX * math.cos(angle), _DEMO_AMPLITUDE_PX * math.sin(angle)


def _recognizer_debug_text(recognizer):
    if recognizer is None:
        return "尚未偵測到手"
    if isinstance(recognizer, FingerExtensionRecognition):
        return f"完成{recognizer.completed}　{recognizer.feedback}"
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
    if sync_tracker is None or sync_tracker.window_start_t is None:
        return "同步視窗　尚未開始"
    remaining = sync_tracker.window_sec - (time.time() - sync_tracker.window_start_t)
    return f"同步視窗剩餘 {max(0.0, remaining):.1f}s"


def _pair_detail_debug_text(sync_tracker):
    detail = sync_tracker.last_pair_detail
    if detail is None:
        return "尚未配對出任何一組"
    return (f"上一組　開始差{detail['start_diff_s']:.2f}s　"
            f"時間差{detail['duration_diff_s']:.2f}s　"
            f"第三項{detail['third_score']:.0f}分　"
            f"得{detail['score']:.0f}分")


def _draw_dot_icon(surface, center, radius, color):
    """點點圖示，跟遊戲零的拳頭圖示做視覺區分——單純一個實心圓即可。"""
    pygame.draw.circle(surface, color, center, radius)


class Game2Scene(Scene):
    timed_session = True
    def on_enter(self, ctx, **kwargs):
        if kwargs.get("resumed"):
            return

        self._username = ctx.current_user
        self.level_options = shared_cfg.training_levels()
        self.selected_action = None

        w, h = ctx.screen.get_size()
        self.level_select_widget = LevelSelect(
            (40, 120, w - 80, h - 220), self.level_options, self._on_level_selected,
            font_size=20, columns=2)

        self.guide_panel = InstructionPanel(
            (w // 2 - 440, h // 2 - 230, 880, 460), DISPLAY_NAME,
            [
                "水平／垂直：先握拳，再伸出食指，最後收回握拳算一次。",
                "垂直向正上方伸，水平向側邊伸；手掌穩定、其餘手指握拳。",
                "食指中間和末端指節也要伸展，不能只轉動指根關節。",
                "畫圓：以食指尖從正上方開始，照指定方向畫一整圈。",
                "每局 60 秒，同步完成差在 0.3 秒內 +1 分，8 分過關。",
            ],
            self._on_guide_dismissed,
        )
        played_before = len(user_store.get_history_for_game(ctx.current_user, GAME_ID, limit=1)) > 0
        self.state = "level_select" if played_before else "guide"
        self.state_start_time = time.time()

        self.hand_identity = HandIdentityTracker(tip_id=8)
        self._missing_since = {}
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

        self.retry_button = Button((w // 2 - 100, h - PADDING - 56, 200, 56), "再玩一次", on_click=self._retry)
        self.back_button = Button((PADDING, h - PADDING - 56, 200, 56), "返回主選單", on_click=self._go_back)

    def _retry(self):
        self.state = "countdown"
        self.state_start_time = time.time()

    def _go_back(self):
        self._pending_transition = Transition("pop")

    def _on_guide_dismissed(self):
        self.state = "level_select"
        self.state_start_time = time.time()

    def _on_level_selected(self, combo_id):
        self.selected_action = next(a for a in shared_cfg.ACTION_SETS if a["combo_id"] == combo_id)
        self.state = "countdown"
        self.state_start_time = time.time()

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
        if self.state == "result":
            self.back_button.handle_event(event)
            self.retry_button.handle_event(event)
        return None

    def update(self, ctx, dt):
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
                    interrupt_hand(self, side, _make_recognizer)
                    self.hand_identity.status[side.title()] = {"reason": "camera_gap", "accepted": False}
                record_diagnostics(self, time.time(), source="camera_gap")

        self._advance_state(ctx)

        if self._pending_transition is not None:
            t, self._pending_transition = self._pending_transition, None
            return t
        return None

    def _process_frame(self, frame, landmarker):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect(mp_image)

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        self.raw_hand_count = len(result.hand_landmarks or [])
        left_landmarks, right_landmarks = self.hand_identity.update(result, time.time())
        for label, landmarks in (("Left", left_landmarks), ("Right", right_landmarks)):
            if landmarks is not None:
                draw_hand_skeleton(frame, landmarks, label, w, h)

        self.display_frame = frame
        self.left_landmarks = left_landmarks
        self.right_landmarks = right_landmarks

        hint_source = right_landmarks if right_landmarks is not None else left_landmarks
        self.distance_hint = estimate_distance_hint(hint_source) if hint_source is not None else None

        if self.state != "playing" or (self.timed_session and time.time() - self.state_start_time >= timed_training.DURATION_SECONDS):
            return

        for side, landmarks in (("left", left_landmarks), ("right", right_landmarks)):
            if landmarks is None:
                now = time.time()
                since = self._missing_since.setdefault(side, now)
                reason = self.hand_identity.status[side.title()]["reason"]
                # Brief detector gaps keep the unfinished gesture, never invent points.
                getattr(self, side + "_trail").clear()
                if reason not in ("no_detection", "stabilizing", "low_confidence") or now-since > 0.35:
                    interrupt_hand(self, side, _make_recognizer)
            else:
                self._missing_since.pop(side, None)
                self.tracking_lost[side] = False

        t_s = time.time()
        left_before = self.left_recognizer.completed
        right_before = self.right_recognizer.completed
        if left_landmarks is not None:
            wrist = _mirrored_xy(left_landmarks[_WRIST])
            tip = _mirrored_xy(left_landmarks[_INDEX_TIP])
            self.left_trail.append(tip)
            if self.pair_scoring_mode is not None:
                self.trail_recorder.record_left_point(tip)
            if isinstance(self.left_recognizer, FingerExtensionRecognition):
                self.left_recognizer.update_landmarks(t_s, left_landmarks, aspect=w / h)
            else:
                self.left_recognizer.update(t_s, tip[0], tip[1], wrist[0], wrist[1])
        if right_landmarks is not None:
            wrist = _mirrored_xy(right_landmarks[_WRIST])
            tip = _mirrored_xy(right_landmarks[_INDEX_TIP])
            self.right_trail.append(tip)
            if self.pair_scoring_mode is not None:
                self.trail_recorder.record_right_point(tip)
            if isinstance(self.right_recognizer, FingerExtensionRecognition):
                self.right_recognizer.update_landmarks(t_s, right_landmarks, aspect=w / h)
            else:
                self.right_recognizer.update(t_s, tip[0], tip[1], wrist[0], wrist[1])

        if self.pair_scoring_mode is not None:
            pairs_before = self.sync_tracker.completed_pairs
            if self.left_recognizer.completed > left_before:
                self.sync_tracker.on_left_rep(
                    self.left_recognizer.last_rep_start_t,
                    self.left_recognizer.last_rep_duration,
                    _rep_quality(self.left_recognizer, self.pair_scoring_mode))
                self.trail_recorder.finish_left_rep()
            if self.right_recognizer.completed > right_before:
                self.sync_tracker.on_right_rep(
                    self.right_recognizer.last_rep_start_t,
                    self.right_recognizer.last_rep_duration,
                    _rep_quality(self.right_recognizer, self.pair_scoring_mode))
                self.trail_recorder.finish_right_rep()
            synced = self.sync_tracker.completed_pairs > pairs_before
            if synced:
                self.trail_recorder.archive_pair_if_ready(
                    self.sync_tracker.completed_pairs, self.sync_tracker.pair_scores[-1])
        else:
            synced = self.sync_tracker.update(
                t_s, self.left_recognizer.completed, self.right_recognizer.completed)

        if self.pair_scoring_mode == "circular":
            if self.left_recognizer.just_started_lap:
                self.left_trail.clear()
            if self.right_recognizer.just_started_lap:
                self.right_trail.clear()
        elif synced:
            self.left_trail.clear()
            self.right_trail.clear()

        if synced:
            self.reward_until = t_s + 0.65
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
            if elapsed_in_state >= timed_training.DURATION_SECONDS:
                self._finish_playing(ctx)

    def _start_playing(self, now):
        self.state = "playing"
        self.state_start_time = now
        self.left_recognizer = _make_recognizer(self.selected_action["left"])
        self.right_recognizer = _make_recognizer(self.selected_action["right"])
        self.pair_scoring_mode = _pair_scoring_mode(self.selected_action)
        if self.pair_scoring_mode is not None:
            third_tolerance = (shared_cfg.PAIR_PEAK_TOLERANCE_RATIO if self.pair_scoring_mode == "axis" else 0.0)
            self.sync_tracker = scoring.RepPairSyncTracker(
                cfg.TARGET_COMPLETIONS, shared_cfg.PAIR_START_TOLERANCE_S,
                shared_cfg.PAIR_DURATION_TOLERANCE_S, third_tolerance,
                third_mode=("diff" if self.pair_scoring_mode == "axis" else "average"))
        else:
            self.sync_tracker = scoring.ComboSyncTracker(shared_cfg.SYNC_WINDOW_SEC)
        self.trail_recorder = scoring.RepTrailRecorder() if self.pair_scoring_mode is not None else None
        self.left_trail.clear()
        self.right_trail.clear()

        if self.timed_session:
            self.pair_scoring_mode = None
            self.sync_tracker = timed_training.CompletionSync()
            self.trail_recorder = None
        self._missing_since = {}
        self.reward_until = 0.0
        start_diagnostics(self, now)

    def _finish_playing(self, ctx):
        if self.timed_session:
            record_diagnostics(self, min(time.time(), self.state_start_time + timed_training.DURATION_SECONDS), source="result")
        if self.pair_scoring_mode is not None:
            final_score = round(self.sync_tracker.average_score)
            self.session_result = scoring.compute_session_result(final_score, shared_cfg.PAIR_PASS_SCORE)
            details = self.session_result.to_details(
                self.selected_action["combo_id"], reps=self.trail_recorder.records)
        else:
            self.session_result = scoring.compute_session_result(
                self.sync_tracker.score, cfg.TARGET_COMPLETIONS)
            details = self.session_result.to_details(self.selected_action["combo_id"])
        if self.timed_session:
            self.session_result = scoring.compute_session_result(self.sync_tracker.score, timed_training.PASS_SCORE)
            details = self.session_result.to_details(self.selected_action["combo_id"])
            details.update(rule_version=timed_training.RULE_VERSION, duration_sec=timed_training.DURATION_SECONDS,
                           pass_score=timed_training.PASS_SCORE, sync_seconds=timed_training.SYNC_SECONDS,
                           action_label=self.selected_action["label"])
        details["analysis"] = export_diagnostics(self, ctx)
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
        msg = font.render("請選擇動作組合：", True, COLOR_TEXT)
        surface.blit(msg, msg.get_rect(centerx=w // 2, top=80))
        self.level_select_widget.draw(surface)

    def _draw_camera_feed(self, surface, w, h):
        return draw_training_view(surface, self.display_frame)

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
        if self.timed_session:
            remaining = max(0, timed_training.DURATION_SECONDS - (time.time()-self.state_start_time))
            _, area, _ = training_layout(surface.get_size())
            text = f"剩餘 {remaining:.0f} 秒　{self.sync_tracker.score} 分／8 分過關"
            width = area.width - min(110, area.height // 4) * 4 // 3 - 18
            font_size = 22
            while font_size > 10 and get_font(font_size).size(text)[0] > width:
                font_size -= 1
            label = get_font(font_size).render(text, True, COLOR_TEXT)
            surface.blit(label, (area.left, area.top + 4))
            if time.time() < self.reward_until:
                label = get_font(26).render("同步完成 +1", True, COLOR_SUCCESS)
                surface.blit(label, (area.left, area.top + 40))


    def _draw_hand_trails(self, surface, video_rect):
        """畫出兩手「目前這一組」的移動軌跡線，見
        game1_bilateral_vertical/scene.py 同名方法的說明。"""
        if video_rect.width == 0 or self.display_frame is None:
            return
        frame_h, frame_w = self.display_frame.shape[:2]
        scale_x = video_rect.width / frame_w
        scale_y = video_rect.height / frame_h

        for trail, color in ((self.left_trail, cfg.LEFT_HAND_COLOR), (self.right_trail, cfg.RIGHT_HAND_COLOR)):
            if len(trail) < 2:
                continue
            points = [
                (video_rect.left + int(tip_x * frame_w * scale_x),
                 video_rect.top + int(tip_y * frame_h * scale_y))
                for tip_x, tip_y in trail
            ]
            pygame.draw.lines(surface, color, False, points, 3)

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
            lm = landmarks[_INDEX_TIP]
            px = (1.0 - lm.x) * frame_w
            py = lm.y * frame_h
            center = (video_rect.left + int(px * scale_x), video_rect.top + int(py * scale_y))
            _draw_dot_icon(surface, center, cfg.DOT_RADIUS, color)

    def _draw_demo_icons(self, surface, w, h):
        t_s = time.time()
        _, area, _ = training_layout((w, h))
        base_y = h - 120
        for side, action_type, color, base_x in (
            ("left", self.selected_action["left"], cfg.LEFT_HAND_COLOR, area.left + area.width * 0.22),
            ("right", self.selected_action["right"], cfg.RIGHT_HAND_COLOR, area.left + area.width * 0.72),
        ):
            dx, dy = _demo_offset(action_type, t_s)
            center = (int(base_x + dx), int(base_y + dy))
            pygame.draw.circle(surface, color, center, 14)
            pygame.draw.circle(surface, COLOR_TEXT, center, 14, width=2)

        label_font = get_font(20)
        left_label = label_font.render(f"左手：{self.selected_action['left']}", True, cfg.LEFT_HAND_COLOR)
        right_label = label_font.render(f"右手：{self.selected_action['right']}", True, cfg.RIGHT_HAND_COLOR)
        surface.blit(left_label, left_label.get_rect(centerx=int(area.left + area.width * 0.22), top=h - 48))
        surface.blit(right_label, right_label.get_rect(centerx=int(area.left + area.width * 0.72), top=h - 48))

    def _draw_result(self, surface, w, h):
        score_font = get_font(72)
        score_label = (f"平均 {self.session_result.score} 分" if self.pair_scoring_mode is not None
                       else f"{self.session_result.score} 次同步")
        if self.timed_session:
            score_label = f"{self.session_result.score} 分"
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
        self.retry_button.draw(surface)
