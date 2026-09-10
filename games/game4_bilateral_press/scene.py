"""
games/game4_bilateral_press/scene.py - 遊戲三「三角形」畫面

流程：GUIDE → LEVEL_SELECT → COUNTDOWN → PLAYING（左右各一輪三角形計時器）→
RESULT。三角形從畫面中間往左右兩側飄出，藍色可以吃（命中加分）、紅色不能吃
（誤觸扣分、斷連擊），跟 press_pin 原本 motor_plan.py 的配色語意一致。

【手勢】四指保持伸直，掌指關節同步彎曲才算按壓；任一指節彎曲則無效。

【左右手 vs 左右側】玩家實測比對過：畫面上看到哪一側的手，就控制哪一側的
三角形——MediaPipe 判定「Left」控制畫面左側、「Right」控制畫面右側，直接
對應，不做任何交叉。曾經比照「鏡像自拍視角」的理論加過交叉對應，但實測是
反的，已經改成直接對應。
"""

import math
import os
import random
from common import game_time as time

import cv2
import mediapipe as mp
import pygame

from common.camera_hand_tracker import draw_hand_skeleton, estimate_distance_hint
from common.cv_pygame import bgr_frame_to_surface
from common.straight_hand import hand_posture, HAND_SYNC_SECONDS
from common.paths import resource_path
from common.scene_manager import Scene, Transition
from common.arcade_recording import ArcadeRecording, record_triangles
from data_store import user_store
from common.background_persistence import begin_result_save
from games.game4_bilateral_press import config as cfg
from games.game4_bilateral_press import scoring
from ui.theme import get_font, COLOR_BG, COLOR_TEXT, COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARN, PADDING
from ui.widgets import Button, LevelSelect, InstructionPanel

GAME_ID = "game4_bilateral_press"
DISPLAY_NAME = "遊戲三．三角形"
DESCRIPTION = "四指伸直，同步彎動掌指關節接住藍色三角形，紅色不要碰"

# 接住藍色三角形的音效，沿用 press_pin 原本 motor_plan.py 的素材（只有接住
# 才播，跟舊版一樣沒有另外做誤觸/漏接音效）。缺檔時印警告並靜音繼續跑。
_SOUND_PATHS = {"hit": os.path.join("assets", "sound", "correct.wav"),
                "error": os.path.join("assets", "sound", "error.mp3")}


def _load_sound(key):
    path = resource_path(_SOUND_PATHS[key])
    if not os.path.exists(path):
        print(f"[game4_bilateral_press] 找不到音效檔: {path}，這個音效會靜音。")
        return None
    from common.audio import load_sound
    return load_sound(path)


_sound_cache = {}


def _get_sound(key):
    # 延遲載入：main.py 要先呼叫 pygame.mixer.init() 之後才能建立 Sound 物件，
    # 而這支檔案在那之前就會被 import。
    if key not in _sound_cache:
        _sound_cache[key] = _load_sound(key)
    return _sound_cache[key]


_DISTANCE_HINT_TEXT = {
    "too_close": "離攝影機太近了，請往後退一點",
    "too_far": "離攝影機太遠了，請往前靠近一點",
}

_INDEX_MCP, _INDEX_PIP, _INDEX_TIP = 5, 6, 8

_COUNTDOWN_SECONDS = 3.0

_BLUE = (80, 150, 240)
_RED = (220, 90, 90)
_COLOR_RGB = {"blue": _BLUE, "red": _RED}


def _is_hand_pressed(landmarks, aspect=1.0) -> bool:
    return hand_posture(landmarks, aspect)["pressed"]


class Triangle:
    def __init__(self, side, color, speed):
        self.side = side  # "left" | "right"（畫面上的側邊，不是手）
        self.color = color  # "blue" | "red"
        self.speed = speed  # 「每幀」單位常數，跟遊戲二 Marble 的 speed 是同一套換算慣例
        self.distance_px = 0.0  # 離畫面中線的距離（往自己那一側移動）
        self.resolved = False


class Game4Scene(Scene):
    def on_enter(self, ctx, **kwargs):
        if kwargs.get("resumed"):
            return

        self._username = ctx.current_user
        # 暫時解鎖全部關卡方便測試，見 game3_lightsaber_marble/scene.py 同樣的
        # 改動說明——正常規則是要先過關前一關才能選下一關，之後要恢復再說。
        self.level_options = [{**level, "unlocked": True} for level in cfg.LEVELS]
        self.selected_level = None

        w, h = ctx.screen.get_size()
        self._screen_size = (w, h)
        self.level_select_widget = LevelSelect(
            (w // 2 - 420, h // 2 - 40, 840, 100), self.level_options, self._on_level_selected)

        self.guide_panel = InstructionPanel(
            (w // 2 - 360, h // 2 - 230, 720, 420), DISPLAY_NAME,
            [
                "四指全程伸直，只彎動掌指關節；其中一指彎曲就不算按壓。",
                "雙藍必須兩手在 0.3 秒內一起按，每個 +1；雙紅都別按，誤觸每個 -1。",
                "左手負責畫面左側、右手負責畫面右側，跟畫面看到的方向直接對應。",
            ],
            self._on_guide_dismissed,
        )
        played_before = len(user_store.get_history_for_game(ctx.current_user, GAME_ID, limit=1)) > 0
        self.state = "level_select" if played_before else "guide"
        self.state_start_time = time.time()

        self.last_frame_id = -1
        self.display_frame = None
        self.left_landmarks = None
        self.right_landmarks = None
        self.distance_hint = None

        self.triangles = []
        self.play_start_time = None
        self.next_spawn_at = None
        self.combo_state = scoring.ComboState()
        self.session_result = None
        self.left_flash_until = 0.0
        self.right_flash_until = 0.0
        self._pending_transition = None

        self.retry_button = Button((w // 2 - 100, h - PADDING - 56, 200, 56), "再玩一次", on_click=lambda: self._on_level_selected(self.selected_level["level_id"]))
        self.back_button = Button((PADDING, h - PADDING - 56, 200, 56), "返回主選單", on_click=self._go_back)

    def _go_back(self):
        self._pending_transition = Transition("pop")

    def _on_guide_dismissed(self):
        self.state = "level_select"
        self.state_start_time = time.time()

    def _on_level_selected(self, level_id):
        self.selected_level = next(lv for lv in self.level_options if lv["level_id"] == level_id)
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
        # 按壓「確認」是一次性的脈衝，只能在偵測到的當下那個 pygame 影格生效。
        # 攝影機硬體幀率(~30fps)比 pygame 的畫面更新率(~60fps)低，很多影格根本
        # 沒有新的攝影機畫面可處理；如果 confirmed 旗標留著不重置，沒有新畫面
        # 的那幾格會沿用上一次的舊值，導致按壓事件「延續」到下一顆剛好飄進判定
        # 區的三角形，變成沒真的按也算命中。每幀一開始就重置，確保只有真的跑過
        # _process_frame() 且這幀剛好偵測到按壓，才會是 True。
        self.left_press_confirmed = False
        self.right_press_confirmed = False

        frame, self.last_frame_id, _cam_read_ms = ctx.camera.get_next(self.last_frame_id, timeout=0.0)
        if frame is not None:
            self._process_frame(frame, ctx.landmarker)

        self._advance_state(ctx, dt)

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

        left_landmarks = None  # MediaPipe "Left"（畫面左側）
        right_landmarks = None  # MediaPipe "Right"（畫面右側）
        if result.hand_landmarks:
            for i, landmarks in enumerate(result.hand_landmarks):
                label = "Unknown"
                if result.handedness and i < len(result.handedness):
                    label = result.handedness[i][0].category_name
                draw_hand_skeleton(frame, landmarks, label, w, h)
                if label == "Left":
                    left_landmarks = landmarks
                elif label == "Right":
                    right_landmarks = landmarks

        self.display_frame = frame
        self.left_landmarks = left_landmarks
        self.right_landmarks = right_landmarks

        hint_source = right_landmarks if right_landmarks is not None else left_landmarks
        if hint_source is not None:
            self.distance_hint = estimate_distance_hint(hint_source)

        if self.state != "playing":
            return

        # MediaPipe「Left」控制畫面左側，「Right」控制畫面右側，直接對應
        # （見檔頭說明）。每幀單獨判斷「現在食指是不是彎的」，不記錄歷史狀態，
        # 見 motion.py::is_finger_bent() 的說明。
        for side, landmarks in (("left", left_landmarks), ("right", right_landmarks)):
            posture = hand_posture(landmarks, w / h)
            self.hand_postures[side] = posture
            pulse = posture["pressed"] and self._press_armed[side]
            self._press_armed[side] = posture["valid"] and not posture["pressed"]
            setattr(self, side + "_press_confirmed", pulse)

        now = time.time()
        if self.left_press_confirmed:
            self.left_flash_until = now + cfg.PADDLE_FLASH_SEC
        if self.right_press_confirmed:
            self.right_flash_until = now + cfg.PADDLE_FLASH_SEC

    def _advance_state(self, ctx, dt):
        now = time.time()
        elapsed_in_state = now - self.state_start_time

        if self.state == "countdown":
            if elapsed_in_state >= _COUNTDOWN_SECONDS:
                self._start_playing(now)
        elif self.state == "playing":
            self._update_playing(ctx, dt, now)

    def _start_playing(self, now):
        self.state = "playing"
        self.state_start_time = now
        self.play_start_time = now
        self.triangles = []
        self.max_possible_score = 0
        self._pair_id = 0
        self._press_armed = {"left": False, "right": False}
        self.hand_postures = {}
        self.combo_state = scoring.ComboState()
        self.left_flash_until = 0.0
        self.right_flash_until = 0.0
        self._schedule_next_spawn(0.0)
        self.arcade_recording = ArcadeRecording(GAME_ID, now, self._screen_size, self.selected_level)
        record_triangles(self, now)

    def _schedule_next_spawn(self, elapsed_sec):
        self.next_spawn_at = elapsed_sec + self.selected_level["spawn_interval_sec"]

    def _random_color(self) -> str:
        return "red" if random.random() < self.selected_level["distractor_ratio"] else "blue"

    def _update_playing(self, ctx, dt, now):
        elapsed_sec = now - self.play_start_time
        level = self.selected_level

        if elapsed_sec >= level["duration_sec"]:
            self._finish_playing(ctx)
            return
        speed = level["triangle_speed"]
        travel = ctx.screen.get_width() * (cfg.PADDLE_OFFSET_RATIO + cfg.HIT_WINDOW_RATIO) / (speed * 60)
        if elapsed_sec >= self.next_spawn_at and elapsed_sec + travel < level["duration_sec"]:
            color = self._random_color()
            self._pair_id += 1
            for side in ("left", "right"):
                tri = Triangle(side, color, speed)
                tri.pair_id = self._pair_id
                tri.pressed_at = None
                self.triangles.append(tri)
            if color == "blue":
                self.max_possible_score += 2
            self._schedule_next_spawn(elapsed_sec)

        w, _ = ctx.screen.get_size()
        for tri in self.triangles:
            tri.distance_px += tri.speed * dt * 60.0  # 換算成跟影格率無關，同遊戲二 Marble 的慣例
        self._resolve_triangles("left", self.left_press_confirmed, w, now)
        self._resolve_triangles("right", self.right_press_confirmed, w, now)
        self.triangles = [t for t in self.triangles if not t.resolved]

        record_triangles(self, now)
        if elapsed_sec >= level["duration_sec"]:
            self._finish_playing(ctx)

    def _resolve_triangles(self, side, press_confirmed, screen_w, now=None):
        now = time.time() if now is None else now
        # 判定區是「非常接近手把」的窄範圍，不是手把到畫面邊緣那一大段——見
        # config.py::HIT_WINDOW_RATIO 的說明，避免同一側前後兩組三角形同時
        # 落在判定區內，一次按壓把兩組一起判定掉。
        paddle_offset = screen_w * cfg.PADDLE_OFFSET_RATIO
        window_px = screen_w * cfg.HIT_WINDOW_RATIO
        for tri in self.triangles:
            if tri.side != side or tri.resolved:
                continue
            in_zone = (paddle_offset - window_px) <= tri.distance_px <= (paddle_offset + window_px)
            if tri.color == "blue" and hasattr(tri, "pair_id"):
                partner = next(t for t in self.triangles if t is not tri and t.pair_id == tri.pair_id)
                if in_zone and press_confirmed and tri.pressed_at is None:
                    tri.pressed_at = now
                times = [t.pressed_at for t in (tri, partner) if t.pressed_at is not None]
                success = len(times) == 2 and abs(times[0]-times[1]) <= HAND_SYNC_SECONDS + 1e-9
                failed = ((times and now-min(times) > HAND_SYNC_SECONDS + 1e-9)
                          or tri.distance_px > paddle_offset + window_px)
                if success or failed:
                    for item in (tri, partner):
                        before = self.combo_state
                        self.combo_state = (scoring.apply_press_hit("blue", before) if success
                                            else scoring.apply_miss("blue", before))
                        item.resolved = True
                        self._record_triangle_event(item, now, before,
                            "雙手同步命中" if success else "雙手未同步／漏接（整組 0 分）")
                    if success:
                        sound = _get_sound("hit")
                        if sound is not None:
                            sound.play()
                continue
            before = self.combo_state
            if in_zone and press_confirmed:
                self.combo_state = scoring.apply_press_hit(tri.color, self.combo_state)
                tri.resolved = True
                self._record_triangle_event(tri, now, before, "命中藍色" if tri.color == "blue" else "誤觸紅色")
                sound = _get_sound("hit" if tri.color == "blue" else "error")
                if sound is not None:
                    sound.play()
            elif tri.distance_px >= (paddle_offset + window_px):
                self.combo_state = scoring.apply_miss(tri.color, self.combo_state)
                tri.resolved = True
                self._record_triangle_event(tri, now, before, "漏接藍色（斷連擊）" if tri.color == "blue" else "避開紅色（不加扣分）")

    def _record_triangle_event(self, tri, now, before, reason):
        recorder = self.arcade_recording
        recorder.event(now, reason, tri,
            recorder.point(self._triangle_x(tri, recorder.width), recorder.height * cfg.SPAWN_Y_RATIO),
            before.score, self.combo_state.score, side=tri.side, color=tri.color, pair_id=getattr(tri, "pair_id", None),
            combo_before=before.combo, combo_after=self.combo_state.combo)

    def _finish_playing(self, ctx):
        threshold = max(1, math.ceil(self.max_possible_score * 0.8))
        self.session_result = scoring.compute_session_result(self.combo_state, {**self.selected_level, "pass_score": threshold})
        details = self.session_result.to_details(self.selected_level["level_id"])
        details.update(rule_version="triangles_paired_v2", max_possible_score=self.max_possible_score,
                       pass_score=threshold, pass_ratio=0.8, sync_seconds=HAND_SYNC_SECONDS)
        details["arcade_replay"] = self.arcade_recording.data
        begin_result_save(self, ctx, GAME_ID, self.session_result.score, details)
        self.state_start_time = time.time()

    # ---- 畫面 ----

    def draw(self, ctx, surface):
        surface.fill(COLOR_BG)
        w, h = surface.get_size()

        title_font = get_font(32)
        title = title_font.render(DISPLAY_NAME, True, COLOR_TEXT)
        surface.blit(title, title.get_rect(centerx=w // 2, top=20))

        cam_rect = self._draw_camera_feed(surface, w)

        if self.state == "guide":
            self.guide_panel.draw(surface)
        elif self.state == "level_select":
            self._draw_level_select(surface, w)
        elif self.state == "countdown":
            self._draw_countdown(surface, w, h)
        elif self.state == "playing":
            self._draw_playing(surface, w, h)
            self._draw_distance_hint(surface, cam_rect)
        elif self.state == "result":
            self._draw_result(surface, w, h)

    def _draw_camera_feed(self, surface, w):
        if self.display_frame is None:
            return pygame.Rect(0, 0, 0, 0)
        frame_surface = bgr_frame_to_surface(self.display_frame)
        video_w = min(220, w // 6)
        video_h = int(video_w * self.display_frame.shape[0] / self.display_frame.shape[1])
        frame_surface = pygame.transform.smoothscale(frame_surface, (video_w, video_h))
        rect = frame_surface.get_rect(right=w - PADDING, top=70)
        surface.blit(frame_surface, rect)
        return rect

    def _draw_level_select(self, surface, w):
        font = get_font(24)
        msg = font.render("請選擇關卡：", True, COLOR_TEXT)
        surface.blit(msg, msg.get_rect(centerx=w // 2, top=200))
        self.level_select_widget.draw(surface)

    def _draw_distance_hint(self, surface, cam_rect):
        text = _DISTANCE_HINT_TEXT.get(self.distance_hint)
        if text is None or cam_rect.width == 0:
            return
        font = get_font(18)
        hint = font.render(text, True, COLOR_WARN)
        surface.blit(hint, hint.get_rect(right=cam_rect.right, top=cam_rect.bottom + 6))

    def _draw_countdown(self, surface, w, h):
        remaining = _COUNTDOWN_SECONDS - (time.time() - self.state_start_time)
        number = max(1, math.ceil(remaining))
        font = get_font(120)
        text = font.render(str(number), True, COLOR_ACCENT)
        surface.blit(text, text.get_rect(center=(w // 2, h // 2)))

    def _triangle_x(self, tri, w):
        half = w / 2.0
        return half - tri.distance_px if tri.side == "left" else half + tri.distance_px

    def _draw_hand_paddles(self, surface, w, spawn_y):
        """畫出左右手各自控制的「手把」，比照 press_pin 原本 Paddle 的畫法：
        灰色底座 + 疊在底座正上方的彩色手臂（手臂沒按壓時筆直站著，跟底座
        拼起來看像同一根直立的桿子），按壓確認的那一瞬間手臂繞著『底座頂端』
        這個支點往中線那一側甩開，兩側都是往中線甩、不是各自固定往同一個
        絕對方向甩（不然其中一側看起來會是往外甩，跟另一側方向不對稱）。
        手把位置放在判定區邊界，跟三角形進入判定區的位置對齊；左右 side 對應
        到哪隻手直接依畫面方向對應，不做鏡像交叉（見檔頭說明）。
        """
        now = time.time()
        half_w = w / 2.0
        hit_zone_px = w * cfg.PADDLE_OFFSET_RATIO
        pw, ph = cfg.PADDLE_WIDTH, cfg.PADDLE_HEIGHT
        # base_top_y 是底座頂端，也是手臂的旋轉支點；手臂疊在上面(往上長 ph)、
        # 底座在下面(往下長 ph)，讓整根手把(手臂+底座)以 spawn_y 為中心，跟
        # 三角形飛行的高度對齊。
        base_top_y = spawn_y

        for x, color, landmarks, flash_until, side in (
            (half_w - hit_zone_px, cfg.LEFT_HAND_COLOR, self.left_landmarks, self.left_flash_until, "left"),
            (half_w + hit_zone_px, cfg.RIGHT_HAND_COLOR, self.right_landmarks, self.right_flash_until, "right"),
        ):
            base_rect = pygame.Rect(int(x - pw / 2), int(base_top_y), pw, ph)
            pygame.draw.rect(surface, (180, 180, 180), base_rect)

            if landmarks is None:
                continue

            angle = 0.0
            if now < flash_until:
                # 左手把往右甩（正角度=逆時針=頂端往左，所以左手把要用負角度
                # 才會往中線/右邊甩）、右手把往左甩，兩側都是甩向中線。
                angle = -cfg.PADDLE_SWING_DEG if side == "left" else cfg.PADDLE_SWING_DEG

            arm_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
            arm_surf.fill(color)
            rotated = pygame.transform.rotate(arm_surf, angle)
            arm_rect = rotated.get_rect(midbottom=(int(x), int(base_top_y)))
            surface.blit(rotated, arm_rect)

    def _draw_playing(self, surface, w, h):
        spawn_y = int(h * cfg.SPAWN_Y_RATIO)
        size = cfg.TRIANGLE_SIZE
        for tri in self.triangles:
            x = self._triangle_x(tri, w)
            color = _COLOR_RGB[tri.color]
            pygame.draw.polygon(surface, color, [
                (x, spawn_y - size), (x - size, spawn_y + size), (x + size, spawn_y + size),
            ])

        self._draw_hand_paddles(surface, w, spawn_y)

        font = get_font(28)
        msg = font.render(
            f"分數 {self.combo_state.score}　連擊 {self.combo_state.combo}", True, COLOR_TEXT)
        surface.blit(msg, msg.get_rect(centerx=w // 2, top=90))

        elapsed = time.time() - self.play_start_time
        remaining = max(0.0, self.selected_level["duration_sec"] - elapsed)
        time_font = get_font(22)
        time_text = time_font.render(f"剩餘時間 {remaining:.0f}s", True, COLOR_TEXT)
        surface.blit(time_text, time_text.get_rect(centerx=w // 2, top=130))
        for i, side in enumerate(("left", "right")):
            posture = self.hand_postures.get(side, {"reason": "等待入鏡"})
            label = get_font(18).render(("左手：" if side == "left" else "右手：") + posture["reason"], True, COLOR_TEXT)
            surface.blit(label, (PADDING, 165 + i*26))

    def _draw_result(self, surface, w, h):
        score_font = get_font(72)
        score_text = score_font.render(f"{self.session_result.score} 分", True, COLOR_SUCCESS)
        surface.blit(score_text, score_text.get_rect(centerx=w // 2, top=h // 2 - 100))

        passed = self.session_result.passed
        pass_color = COLOR_SUCCESS if passed else COLOR_WARN
        pass_label = (f"{self.selected_level['label']} 過關！" if passed
                      else f"{self.selected_level['label']} 未過關，再試一次")
        info_font = get_font(26)
        info = info_font.render(
            f"最高連擊 {self.session_result.max_combo}　{pass_label}", True, pass_color)
        surface.blit(info, info.get_rect(centerx=w // 2, top=h // 2 - 10))

        threshold = max(1, math.ceil(self.max_possible_score * 0.8))
        rule = get_font(22).render(f"本局可得 {self.max_possible_score} 分　過關需 {threshold} 分（80%）", True, COLOR_TEXT)
        surface.blit(rule, rule.get_rect(centerx=w // 2, top=h // 2 + 50))
        self.back_button.draw(surface)
        self.retry_button.draw(surface)
