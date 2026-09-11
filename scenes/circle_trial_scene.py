"""Isolated five-loop experiment, launched from login."""
import copy
from collections import deque
import pygame
from common import game_time as time
from common.scene_manager import Transition
from common.training_diagnostics import export_diagnostics
from data_store import user_store
from common.background_persistence import begin_result_save
from games.game1_bilateral_vertical.scene import Game1Scene, GAME_ID, _make_recognizer
from games.game1_bilateral_vertical.circle_trial_motion import UpperReversalCircle
from games.game1_bilateral_vertical.scoring import SessionResult
from ui.widgets import InstructionPanel, Button
from ui.theme import get_font, COLOR_BG, COLOR_TEXT, COLOR_SUCCESS


class CircleTrialScene(Game1Scene):
    timed_session = False
    target_completions = 5
    score_kind = "circle_quality"

    @staticmethod
    def make_recognizer(action):
        return UpperReversalCircle() if action == "CW" else _make_recognizer(action)

    def on_enter(self, ctx, **kwargs):
        if kwargs.get("resumed"):
            return
        super().on_enter(ctx, **kwargs)
        self.back_button.label = "返回登入畫面"
        self._on_actions_selected({"left": "N", "right": "CW"})
        self.state = "guide"
        w, h = ctx.screen.get_size()
        self.guide_panel = InstructionPanel((w//2-360, h//2-230, 720, 420), "測試版右手畫圓",
            ["右拳從預計的 12 點鐘位置開始，向右順時針畫圈。",
             "右側往下、左側回上方，再稍微向下，確認上方極限點。",
             "不用接回原本位置；上方極限點結算一圈，直接開始下一圈。",
             "完成五圈結束，第五圈回到上方後也要稍微向下。",
             "保存每圈圓度、耗時、起終點距離與回放；不計左右手同步分數。"], self._on_guide_dismissed)
        self.replay_button = Button((w//2-150, h-90, 300, 52), "回放這次測試", self._replay)

    def _on_guide_dismissed(self):
        self.state = "countdown"
        self.state_start_time = time.time()

    def _start_playing(self, now):
        self.circle_records = []
        super()._start_playing(now)
        self.sync_tracker.average_score = 0.0
        self.diagnostics.update(algorithm="upper_reversal_circle_v1", reference_kind="observed_top_reversal",
                                target_pairs=5)
        self.diagnostics["parameters"]["circle_trial"] = dict(reversal=.012, minimum_span=.06,
            minimum_winding_degrees=270, minimum_direction_consistency=.65)
        self.diagnostics["parameters"]["fist"].pop("circle_turn_threshold", None)
        self.diagnostics["parameters"]["fist"]["calibration_s"] = 0

    def _process_frame(self, frame, landmarker, result=None):
        before = self.right_recognizer.completed if self.right_recognizer is not None else 0
        super()._process_frame(frame, landmarker, result)
        if self.state != "playing":
            return
        recognizer = self.right_recognizer
        if recognizer.completed > len(self.circle_records):
            record = copy.deepcopy(recognizer.last_record)
            for key in ("start_t", "end_t"):
                record[key] -= self.diagnostics["time_origin"]
            self.circle_records.append(record)
        if recognizer.just_started_lap and recognizer.points and recognizer.completed > before:
            self.right_trail = deque((p[1], p[2]) for p in recognizer.points)
            self.trail_start_times["right"] = recognizer._lap_start_t
            self.debug_snapshot["right"]["trail_start_t"] = recognizer._lap_start_t-self.diagnostics["time_origin"]
        self.sync_tracker.average_score = (sum(r["quality"] for r in self.circle_records)/len(self.circle_records)
                                           if self.circle_records else 0)
        self.debug_snapshot.update(average_score=self.sync_tracker.average_score, score_kind="circle_quality")

    def _finish_playing(self, ctx):
        self.session_result = SessionResult(round(self.sync_tracker.average_score), len(self.circle_records) >= 5)
        details = self.session_result.to_details("trial_right_CW_5", reps=self.circle_records)
        details.update(analysis=export_diagnostics(self, ctx), action_label="測試版右手畫圓（五圈）",
                       training_mode="single_circle_trial", enabled_hands=["right"],
                       algorithm="upper_reversal_circle_v1", completed_circles=len(self.circle_records),
                       score_kind="mean_circle_roundness")
        begin_result_save(self, ctx, GAME_ID, self.session_result.score, details)
        # Use the same payload for immediate replay, independent of store return type.
        self.replay_record = dict(game_id=GAME_ID, score=self.session_result.score, details=details)
        self.state_start_time = time.time()

    def _draw_result(self, surface, w, h):
        text = get_font(44).render(f"完成 {len(self.circle_records)} / 5 圈　平均圓度 {self.session_result.score} 分", True, COLOR_SUCCESS)
        surface.blit(text, text.get_rect(center=(w//2, h//2)))
        self.back_button.draw(surface)
        self.replay_button.draw(surface)

    def _replay(self):
        from scenes.replay_scene import ReplayScene
        self._pending_transition = Transition("push", ReplayScene(), {"record": self.replay_record})

    def handle_event(self, ctx, event):
        super().handle_event(ctx, event)
        if self.state == "result":
            self.replay_button.handle_event(event)

    def draw(self, ctx, surface):
        super().draw(ctx, surface)
        pygame.draw.rect(surface, COLOR_BG, (0, 0, surface.get_width(), 65))
        title = get_font(30).render("測試版右手畫圓 · 五圈", True, COLOR_TEXT)
        surface.blit(title, title.get_rect(centerx=surface.get_width()//2, top=20))
