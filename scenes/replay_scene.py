"""歷史軌跡與判定資訊回放。

新紀錄使用 details.analysis.frames 的共同時間軸，兩側顯示當時的判定資料，
支援定位、慢速播放與狀態事件跳轉。拒收／缺失影格不連接軌跡。
舊紀錄只含 details.reps，保留逐組等比例動畫並明確標示沒有真實時間與判定資訊。
"""

from bisect import bisect_right

import pygame

from common.scene_manager import Scene, Transition
from games.game1_bilateral_vertical.config import ACTION_SETS
from ui.theme import get_font, COLOR_BG, COLOR_PANEL, COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_ACCENT, COLOR_SUCCESS, PADDING
from ui.widgets import Button, ScrollList
from ui.training_panels import training_layout, draw_training_panels, draw_panel

_LEFT_COLOR = (90, 200, 230)   # 跟遊戲零/遊戲一的 LEFT_HAND_COLOR 一致
_RIGHT_COLOR = (240, 150, 60)  # 跟遊戲零/遊戲一的 RIGHT_HAND_COLOR 一致

PLAYBACK_DURATION_SEC = 2.5

_COMBO_LABELS = {a["combo_id"]: a["label"] for a in ACTION_SETS}


class ReplayScene(Scene):
    def on_enter(self, ctx, record, **kwargs):
        if kwargs.get("resumed"):
            return

        self.record = record
        self.arcade = bool((record.get("details") or {}).get("arcade_replay"))
        self.analysis = ((record.get("details") or {}).get("arcade_replay") if self.arcade else (record.get("details") or {}).get("analysis")) or {}
        self.frames = self.analysis.get("frames") or []
        self.times = [frame["t"] for frame in self.frames]
        self.duration = self.times[-1] if self.times else PLAYBACK_DURATION_SEC
        self.speed = 1.0
        self.dragging = False
        self.event_times = [0.0]
        previous = None
        for frame in ([] if self.arcade else self.frames):
            state = tuple((frame[side]["completed"], frame[side]["state"], frame[side]["tracking"]["reason"])
                          for side in ("left", "right"))
            if previous is not None and state != previous:
                self.event_times.append(frame["t"])
            previous = state
        if self.arcade:
            self.event_times = sorted(set([0.0] + [event["t"] for event in self.analysis["events"]]))
        reps = (record.get("details") or {}).get("reps") or []
        self.rounds = sorted({r["round"] for r in reps})
        self._reps_by_round = {}
        for round_no in self.rounds:
            round_reps = [r for r in reps if r["round"] == round_no]
            left = next((r for r in round_reps if r["hand"] == "left"), None)
            right = next((r for r in round_reps if r["hand"] == "right"), None)
            self._reps_by_round[round_no] = (left, right)

        combo_id = (record.get("details") or {}).get("level_id", "")
        self.combo_label = _COMBO_LABELS.get(combo_id, combo_id)
        self.combo_label = (record.get("details") or {}).get("action_label", self.combo_label)
        if self.arcade:
            game_name = "光劍" if self.analysis["game_id"] == "game3_lightsaber_marble" else "三角形"
            self.combo_label = game_name + "　" + self.analysis["level"].get("label", combo_id)

        w, h = ctx.screen.get_size()
        _, center, _ = training_layout((w, h))
        frame_size = self.analysis.get("frame_size") or [1, 1]
        ratio = frame_size[0] / max(1, frame_size[1])
        available = pygame.Rect(center.x, 130, center.width, max(100, h - 320))
        canvas_w = min(available.width, int(available.height * ratio))
        canvas_h = int(canvas_w / ratio)
        self.canvas_rect = pygame.Rect(0, 0, canvas_w, canvas_h)
        self.canvas_rect.center = available.center
        self.timeline_rect = pygame.Rect(center.x + 10, h - 166, center.width - 20, 20)

        if self.arcade:
            _, _, right = training_layout((w, h))
            self.event_list = ScrollList((right.x+5, right.y+48, right.width-10, right.height-58),
                font_size=15, row_height=68, on_select=self._select_score_event)
            events = self.analysis["events"]
            rows = []
            for event in events:
                side = {"left": "左手", "right": "右手", None: ""}.get(event["side"], "")
                rows.append((f"{event['t']:.2f}s {event['delta']:+g} {event['reason']}",
                    f"{side} x:{event['position'][0]:.2f} y:{event['position'][1]:.2f} 分數:{event['score_after']}"))
            self.event_list.set_items(rows, records=events)

        self.round_index = 0
        self._pending_transition = None
        self._restart_playback()
        gap = 8
        width = (center.width - 4 * gap) // 5
        y = h - 124
        def rect(index):
            return (center.x + index * (width + gap), y, width, 44)
        self.prev_button = Button(rect(0), "前個事件" if self.frames else "上一輪", self._prev_round, font_size=18)
        self.next_button = Button(rect(1), "後個事件" if self.frames else "下一輪", self._next_round, font_size=18)
        self.pause_button = Button(rect(2), "暫停", self._toggle_play, font_size=18)
        self.replay_button = Button(rect(3), "重播", self._restart_playback, font_size=18)
        self.speed_button = Button(rect(4), "1x", self._change_speed, font_size=18)
        self.back_button = Button((PADDING, h - PADDING - 56, 200, 56), "返回歷史紀錄", on_click=self._go_back)

    def _select_score_event(self, event):
        self._seek(event["t"])
        self.playing = False

    def _toggle_play(self):
        self.playing = not self.playing

    def _change_speed(self):
        choices = [0.25, 0.5, 1.0, 2.0, 4.0]
        self.speed = choices[(choices.index(self.speed) + 1) % len(choices)]
        self.speed_button.label = f"{self.speed:g}x"

    def _seek(self, value):
        self.playback_t = max(0.0, min(value, self.duration))

    def _current_frame_index(self):
        return max(0, bisect_right(self.times, self.playback_t) - 1)

    def _current_reps(self):
        if not self.rounds:
            return None, None
        return self._reps_by_round[self.rounds[self.round_index]]

    def _restart_playback(self):
        self.playback_t = 0.0
        self.playing = True

    def _prev_round(self):
        if self.frames:
            self._seek(max((t for t in self.event_times if t < self.playback_t - 0.001), default=0.0))
            self.playing = False
            return
        if self.round_index > 0:
            self.round_index -= 1
            self._restart_playback()

    def _next_round(self):
        if self.frames:
            self._seek(next((t for t in self.event_times if t > self.playback_t + 0.001), self.duration))
            self.playing = False
            return
        if self.round_index < len(self.rounds) - 1:
            self.round_index += 1
            self._restart_playback()

    def _go_back(self):
        self._pending_transition = Transition("pop")

    # ---- 事件 / 每幀更新 ----

    def handle_event(self, ctx, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._go_back()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self._toggle_play()
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self._seek(self.playback_t + (-0.1 if event.key == pygame.K_LEFT else 0.1))
                self.playing = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.timeline_rect.collidepoint(event.pos):
            self.dragging = True
            self.playing = False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        if self.dragging and event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION):
            self._seek((event.pos[0] - self.timeline_rect.x) / self.timeline_rect.width * self.duration)
        if self.arcade:
            self.event_list.handle_event(event)
        self.pause_button.handle_event(event)
        self.speed_button.handle_event(event)
        self.prev_button.handle_event(event)
        self.next_button.handle_event(event)
        self.replay_button.handle_event(event)
        self.back_button.handle_event(event)
        return None

    def update(self, ctx, dt):
        if self.playing:
            self.playback_t += dt * self.speed
            if self.playback_t >= self.duration:
                self.playback_t = self.duration
                self.playing = False
        if self._pending_transition is not None:
            t, self._pending_transition = self._pending_transition, None
            return t
        return None

    # ---- 畫面 ----

    def draw(self, ctx, surface):
        surface.fill(COLOR_BG)
        w, _ = surface.get_size()

        title_font = get_font(32)
        title = title_font.render(f"軌跡回放　{self.combo_label}", True, COLOR_TEXT)
        surface.blit(title, title.get_rect(centerx=w // 2, top=20))

        if self.frames:
            if self.arcade:
                from ui.arcade_replay import draw_arcade_replay
                draw_arcade_replay(self, surface)
            else:
                self._draw_timed_replay(surface)
            self._draw_controls(surface)
            return

        if not self.rounds:
            empty_font = get_font(24)
            empty = empty_font.render("這筆紀錄沒有軌跡資料。", True, COLOR_TEXT_MUTED)
            surface.blit(empty, empty.get_rect(center=(w // 2, self.canvas_rect.centery)))
            self.back_button.draw(surface)
            return

        round_no = self.rounds[self.round_index]
        left_rep, right_rep = self._current_reps()
        score = (left_rep or right_rep)["score"]

        header_font = get_font(24)
        header = header_font.render(
            f"第 {round_no} / {self.rounds[-1]} 輪　分數 {score:.0f} 分", True, COLOR_TEXT)
        surface.blit(header, header.get_rect(centerx=w // 2, top=70))

        pygame.draw.rect(surface, COLOR_PANEL, self.canvas_rect, border_radius=10)
        pygame.draw.rect(surface, COLOR_ACCENT, self.canvas_rect, width=2, border_radius=10)

        progress = 1.0 if PLAYBACK_DURATION_SEC <= 0 else min(1.0, self.playback_t / PLAYBACK_DURATION_SEC)
        self._draw_rep_trail(surface, left_rep, _LEFT_COLOR, progress)
        self._draw_rep_trail(surface, right_rep, _RIGHT_COLOR, progress)

        label_font = get_font(20)
        left_label = label_font.render("左手", True, _LEFT_COLOR)
        right_label = label_font.render("右手", True, _RIGHT_COLOR)
        surface.blit(left_label, (self.canvas_rect.left, self.canvas_rect.top - 28))
        surface.blit(right_label, (self.canvas_rect.right - right_label.get_width(), self.canvas_rect.top - 28))

        left, _, right = training_layout(surface.get_size())
        for rect, label, rep, color in ((left, "左手", left_rep, _LEFT_COLOR), (right, "右手", right_rep, _RIGHT_COLOR)):
            draw_panel(surface, rect, label, ["舊紀錄：僅有軌跡座標", "沒有逐幀時間或判定資訊", "兩手各自壓縮成 2.5 秒", "播放速度不代表實際速度", f"此段軌跡點：{len((rep or {}).get('trail', []))}", "漏偵測原因：未記錄", "指尖相對手腕位移：未記錄"], color)
        self._draw_controls(surface)

    def _draw_controls(self, surface):
        if self.frames:
            self.prev_button.enabled = self.playback_t > 0
            self.next_button.enabled = self.playback_t < self.duration
        else:
            self.prev_button.enabled = self.round_index > 0
            self.next_button.enabled = self.round_index < len(self.rounds) - 1
        self.pause_button.label = "暫停" if self.playing else "播放"
        for button in (self.prev_button, self.next_button, self.pause_button, self.replay_button, self.speed_button, self.back_button):
            button.draw(surface)
        pygame.draw.rect(surface, COLOR_PANEL, self.timeline_rect, border_radius=8)
        progress = self.playback_t / self.duration if self.duration else 0
        x = self.timeline_rect.x + int(progress * self.timeline_rect.width)
        pygame.draw.circle(surface, COLOR_ACCENT, (x, self.timeline_rect.centery), 8)
        text = get_font(16).render(f"{self.playback_t:.2f} / {self.duration:.2f} 秒　拖曳定位｜空白鍵播放｜方向鍵 ±0.1 秒", True, COLOR_TEXT_MUTED)
        surface.blit(text, text.get_rect(centerx=self.timeline_rect.centerx, bottom=self.timeline_rect.top - 5))

    def _draw_timed_replay(self, surface):
        index = self._current_frame_index()
        frame = self.frames[index]
        draw_training_panels(surface, frame)
        header = get_font(20).render(f"實際時間 {self.playback_t:.2f} 秒｜第 {frame['paired']} / {self.analysis.get('target_pairs', 10)} 組", True, COLOR_TEXT)
        surface.blit(header, header.get_rect(centerx=self.canvas_rect.centerx, top=75))
        legend = "實心：拳心　空心：固定基準" if self.analysis.get("tracking_point_kind") == "palm_center" else "實心：指尖　空心：手腕"
        if self.analysis.get("reference_kind") == "axis_reversal_circle_fixed":
            legend = "拳心軌跡　小圈：極限點　空心：畫圓基準"
        elif self.analysis.get("reference_kind") == "observed_top_reversal":
            legend = "拳心軌跡｜上方反轉切圈"
        scope = "畫圓保留當圈" if any("trail_start_t" in frame[side] for side in ("left", "right")) else "最近 3 秒軌跡"
        hint = get_font(16).render(scope + "｜" + legend + "　叉號：拒收點", True, COLOR_TEXT_MUTED)
        surface.blit(hint, hint.get_rect(centerx=self.canvas_rect.centerx, top=105))
        pygame.draw.rect(surface, COLOR_PANEL, self.canvas_rect, border_radius=10)
        clip = surface.get_clip()
        surface.set_clip(self.canvas_rect)
        start = bisect_right(self.times, self.playback_t - 3.0)
        for side, color in (("left", _LEFT_COLOR), ("right", _RIGHT_COLOR)):
            segment = []
            lap_start = frame[side].get("trail_start_t")
            side_start = max(0, bisect_right(self.times, lap_start) - 1) if lap_start is not None else start
            for sample in self.frames[side_start:index+1]:
                item = sample[side]
                if item.get("tip") is None or not item["tracking"].get("accepted"):
                    if len(segment) > 1:
                        pygame.draw.lines(surface, color, False, segment, 3)
                    segment = []
                else:
                    segment.append(self._to_canvas_px(item["tip"]))
            if len(segment) > 1:
                pygame.draw.lines(surface, color, False, segment, 3)
            current = frame[side]
            if current.get("turning_point") is not None:
                pygame.draw.circle(surface, color, self._to_canvas_px(current["turning_point"]), 5, width=1)
            if current.get("tip") is not None:
                pygame.draw.circle(surface, color, self._to_canvas_px(current["tip"]), 7)
                if current.get("wrist") is not None:
                    pygame.draw.circle(surface, color, self._to_canvas_px(current["wrist"]), 9, width=2)
            elif current["tracking"].get("raw_tip"):
                x, y = self._to_canvas_px(current["tracking"]["raw_tip"])
                pygame.draw.line(surface, color, (x-6, y-6), (x+6, y+6), 2)
                pygame.draw.line(surface, color, (x-6, y+6), (x+6, y-6), 2)
        surface.set_clip(clip)

    def _draw_rep_trail(self, surface, rep, color, progress):
        if rep is None:
            return
        trail = rep["trail"]
        if not trail:
            return
        shown_count = max(1, int(len(trail) * progress))
        points = [self._to_canvas_px(p) for p in trail[:shown_count]]
        if len(points) >= 2:
            pygame.draw.lines(surface, color, False, points, 3)
        pygame.draw.circle(surface, color, points[-1], 8)
        pygame.draw.circle(surface, COLOR_SUCCESS if progress >= 1.0 else COLOR_TEXT, points[-1], 8, width=2)

    def _to_canvas_px(self, normalized_xy):
        x, y = normalized_xy
        px = self.canvas_rect.left + int(x * self.canvas_rect.width)
        py = self.canvas_rect.top + int(y * self.canvas_rect.height)
        return px, py
