"""
games/game3_lightsaber_marble/scene.py - 遊戲二「光劍」畫面

流程：GUIDE → LEVEL_SELECT → COUNTDOWN → PLAYING → RESULT。

【控制範圍】右手橘劍只在左半邊、左手藍劍只在右半邊，兩把劍不能跨中線。
中央球依顏色判定；錯色扣一分。四指需伸直並同步彎動掌指關節才有效。

【2026-09-09 改用角度判定取代像素遮罩碰撞】原本用 pygame.sprite.collide_mask
判斷光劍圖形有沒有跟彈珠圖形疊到像素，但手部追蹤更新頻率比畫面渲染慢很多，
快速揮劍時角度可能一格影格跳過好幾度，導致整支劍「劃過」彈珠卻沒有任何一幀
真的疊到像素、玩家明明打中卻沒有反應。改用 motion.py::is_marble_hit() 純角度
+ 距離判定，不依賴幀與幀之間畫面有沒有連續重疊。

【同一天，判定角度容忍值先加大後又收窄】一開始 15 度太窄常打不到，一度加大
到 35 度並在畫面上疊一個半透明扇形標示判定範圍；後來玩家覺得那個扇形框框
太大、要拿掉，改成 10 度（大概比劍身本身寬一點點），不再額外畫框框——劍身
圖片本身的寬度已經足以代表判定範圍。

角度量測用「已鏡像」的座標（x 取 1.0-x，跟畫面顯示的鏡像視角一致），這樣手在
畫面上看起來往右指，算出來的角度方向也會跟畫面上光劍轉動的方向對得上。

採交叉控制：右手控制畫面左側橘劍，左手控制畫面右側藍劍。

【2026-09-09 換上 BilateralCoordinationTraining 原版的美術素材】彈珠/光劍
改用 assets/image/lightsaber/ 底下的圖片（從舊專案複製過來），缺檔時會印警告
並退回原本的原生圖形畫，不會直接壞掉（見 _get_image()）。光劍圖片是「朝上、
劍柄在下緣正中央」畫的，用 _blit_hilt_anchored() 繞劍柄旋轉、不是繞圖片幾何
中心，劍柄才會穩穩對齊 pivot；彈珠打中的瞬間會換成碎裂圖原地淡出
（Marble.hit()/fade()），不是立刻消失，讓玩家看得到「真的打中了」的回饋。
"""

import math
import random
from common import game_time as time

import os

import cv2
import mediapipe as mp
from common.camera_hand_tracker import get_hand_frame
import pygame

from common.camera_hand_tracker import draw_hand_skeleton, estimate_distance_hint
from common.cv_pygame import bgr_frame_to_surface
from common.straight_hand import hand_posture
from common.paths import resource_path
from common.scene_manager import Scene, Transition
from common.arcade_recording import ArcadeRecording, record_sabers
from data_store import user_store
from common.background_persistence import begin_result_save
from games.game3_lightsaber_marble import config as cfg
from games.game3_lightsaber_marble import motion, scoring
from ui.theme import get_font, COLOR_BG, COLOR_TEXT, COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARN, PADDING
from ui.widgets import Button, LevelSelect, InstructionPanel

GAME_ID = "game3_lightsaber_marble"
DISPLAY_NAME = "遊戲二．光劍"
DESCRIPTION = "轉動手腕揮動光劍，攔截飛向中心的彈珠"

# 打中彈珠/漏接的音效，沿用 BilateralCoordinationTraining 原本 Game2 的素材
# （sword.wav 打中、error.mp3 漏接）。缺檔時印警告並靜音繼續跑，不擋開發流程。
_SOUND_PATHS = {"hit": os.path.join("assets", "sound", "sword.wav"),
                "miss": os.path.join("assets", "sound", "error.mp3")}


def _load_sound(key):
    path = resource_path(_SOUND_PATHS[key])
    if not os.path.exists(path):
        print(f"[game3_lightsaber_marble] 找不到音效檔: {path}，這個音效會靜音。")
        return None
    from common.audio import load_sound
    return load_sound(path)


_sound_cache = {}


def _get_sound(key):
    # 延遲載入：main.py 要先呼叫 pygame.mixer.init() 之後才能建立 Sound 物件，
    # 而這支檔案在那之前就會被 import，所以不能在模組載入時就建立。
    if key not in _sound_cache:
        _sound_cache[key] = _load_sound(key)
    return _sound_cache[key]


# 光劍/彈珠圖片，沿用 BilateralCoordinationTraining 原本 Game2 的素材（原圖是
# 2048px 高解析度，這裡只載入原始圖一次、快取起來，實際顯示大小由呼叫端用
# pygame.transform.smoothscale 縮小，不會每一幀都重新縮放）。
_IMAGE_PATHS = {
    "blue_sword": os.path.join("assets", "image", "lightsaber", "blue_light_sword.png"),
    "red_sword": os.path.join("assets", "image", "lightsaber", "red_light_sword.png"),
    "marble": os.path.join("assets", "image", "lightsaber", "blue_marble.png"),
    "marble_broke": os.path.join("assets", "image", "lightsaber", "blue_marble_broke.png"),
    "orange_marble": os.path.join("assets", "image", "lightsaber", "red_marble.png"),
    "orange_broke": os.path.join("assets", "image", "lightsaber", "red_marble_broke.png"),
}

_image_cache = {}


def _crop_to_opaque(image):
    """裁掉圖片四周的透明留白，只留下真正有內容的範圍。原始美術素材（尤其
    light_sword.png）四周留了不少透明空間，而且留白還不對稱（左右、上下留白
    都不一樣寬）——如果直接拿整張圖片去算『圖片中心』『劍柄在下緣正中央』，
    算出來的中心點會偏掉，貼出來的光劍方向也會跟著偏（實測偏了 15~25 度）。
    """
    mask = pygame.mask.from_surface(image)
    rects = mask.get_bounding_rects()
    if not rects:
        return image
    left = min(r.left for r in rects)
    top = min(r.top for r in rects)
    right = max(r.right for r in rects)
    bottom = max(r.bottom for r in rects)
    return image.subsurface(pygame.Rect(left, top, right - left, bottom - top)).copy()


def _get_image(key):
    # 延遲載入，理由跟 _get_sound 一樣：呼叫 convert_alpha() 需要 pygame 視窗
    # 已經建立，這支檔案在那之前就會被 import。缺檔時印警告、回傳 None，呼叫端
    # 要自己準備退回原生圖形畫的備案，不能讓遊戲直接掛掉。
    if key not in _image_cache:
        path = resource_path(_IMAGE_PATHS[key])
        if not os.path.exists(path):
            print(f"[game3_lightsaber_marble] 找不到圖片檔: {path}，這裡會退回原生圖形畫。")
            _image_cache[key] = None
        else:
            _image_cache[key] = _crop_to_opaque(pygame.image.load(path).convert_alpha())
    return _image_cache[key]


def _scaled_copy(image, size):
    """把原始圖片等比縮放，讓長邊等於 size，回傳新的 Surface（不會動到快取
    裡的原圖）。"""
    w, h = image.get_size()
    ratio = size / max(w, h)
    return pygame.transform.smoothscale(image, (max(1, int(w * ratio)), max(1, int(h * ratio))))


_DISTANCE_HINT_TEXT = {
    "too_close": "離攝影機太近了，請往後退一點",
    "too_far": "離攝影機太遠了，請往前靠近一點",
}

_MID_BASE, _MID_TIP = 9, 12
_PINKY_BASE, _PINKY_TIP = 17, 20

_COUNTDOWN_SECONDS = 3.0


def _mirrored_xy(landmark):
    """跟畫面顯示的鏡像視角一致的座標（x 取 1.0-x）。角度計算要用這個，不然轉動
    方向會跟畫面上看到的相反。"""
    return (1.0 - landmark.x, landmark.y)


def _hand_pointing_angle(landmarks, aspect=1.0):
    def point(index):
        x, y = _mirrored_xy(landmarks[index])
        return x * aspect, y
    return motion.hand_pointing_angle_deg(
        point(_MID_BASE), point(_MID_TIP),
        point(_PINKY_BASE), point(_PINKY_TIP),
    )


def _blit_hilt_anchored(surf, image, pivot, angle_deg):
    """把 image（假設原始圖片朝上畫、劍柄在圖片下緣正中央，跟這次用的
    light_sword.png 素材一致）繞著『劍柄』這個點旋轉到 angle_deg 方向，貼到
    surf 上，劍柄準確對齊 pivot。不能直接用 pygame.transform.rotate 預設
    繞『圖片幾何中心』旋轉，那樣劍柄位置會跟著角度亂跑、光劍看起來會在畫面上
    漂移，不會穩穩地插在 pivot 上。

    角度慣例（跟這支檔案其他地方一致）：0 度朝右、逆時針為正；圖片預設朝上
    畫，對應角度 90 度，所以旋轉量是 angle_deg - 90。
    """
    rotation = angle_deg - 90.0
    rotated = pygame.transform.rotozoom(image, rotation, 1.0)
    half_h = image.get_height() / 2.0
    theta = math.radians(rotation)
    hilt_offset = (half_h * math.sin(theta), half_h * math.cos(theta))
    center = (pivot[0] - hilt_offset[0], pivot[1] - hilt_offset[1])
    rect = rotated.get_rect(center=center)
    surf.blit(rotated, rect)


_MARBLE_FADE_SEC = 0.25  # 打中之後碎裂圖淡出要花幾秒，見 Marble.hit()/fade()


class Marble(pygame.sprite.Sprite):
    def __init__(self, pivot, angle_deg, outer_radius, inner_radius, speed, image, image_broke, color="orange"):
        super().__init__()
        self.pivot = pivot
        self.color = color
        self.angle_deg = angle_deg
        self.outer_radius = outer_radius
        self.inner_radius = inner_radius
        self.speed = speed
        self.distance = outer_radius
        self.broken = False
        self._alpha = 255.0
        self._image_broke = image_broke

        if image is not None:
            r = cfg.MARBLE_RADIUS
            self.image = pygame.transform.smoothscale(image, (r * 2, r * 2))
        else:
            r = cfg.MARBLE_RADIUS
            self.image = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(self.image, (250, 210, 90), (r, r), r)
            pygame.draw.circle(self.image, (140, 110, 30), (r, r), r, width=2)
        self.rect = self.image.get_rect()
        self._sync_rect()

    def _sync_rect(self):
        rad = math.radians(self.angle_deg)
        x = self.pivot[0] + self.distance * math.cos(rad)
        y = self.pivot[1] - self.distance * math.sin(rad)
        self.rect.center = (int(x), int(y))

    def step(self, dt) -> bool:
        """往圓心移動一步，回傳是否已經飛到中心範圍內（沒被打到＝漏接）。"""
        self.distance -= self.speed * dt * 60.0  # speed 是「每幀」單位常數，換算成跟影格率無關
        self._sync_rect()
        return self.distance <= self.inner_radius

    def hit(self):
        """打中的瞬間：換成碎裂圖，原地淡出，不是立刻消失——讓玩家看得到
        『真的打中了』的視覺回饋（沒有碎裂圖素材時就直接消失，不影響原本
        『打中即刪除』的行為）。"""
        if self._image_broke is None:
            self.kill()
            return
        center = self.rect.center
        self.broken = True
        self._alpha = 255.0
        r = cfg.MARBLE_RADIUS
        self.image = pygame.transform.smoothscale(self._image_broke, (r * 2, r * 2))
        self.rect = self.image.get_rect(center=center)

    def fade(self, dt) -> bool:
        """碎裂淡出動畫的每幀更新，回傳是否已經完全淡出、可以移除了。"""
        self._alpha -= 255.0 / _MARBLE_FADE_SEC * dt
        if self._alpha <= 0:
            return True
        self.image.set_alpha(int(self._alpha))
        return False


class LightSword(pygame.sprite.Sprite):
    def __init__(self, pivot, length, color, sword_image):
        super().__init__()
        self.pivot = pivot
        self.length = length
        self.color = color
        self.angle_deg = 90.0
        self.active = False
        self.target_angle_deg = None
        self._allow_scoring = False
        self._render_state = None
        # sword_image 是已經縮放成高度等於 length 的原圖（朝上畫、劍柄在下緣
        # 正中央），None 代表找不到圖片檔，退回原生圖形畫。
        self._sword_image = sword_image
        self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=pivot)

    def update_towards(self, target_angle_deg):
        self.set_target(target_angle_deg)
        self.advance(1 / 30)

    def set_target(self, target_angle_deg, allow_scoring=True):
        self.target_angle_deg = target_angle_deg
        self._allow_scoring = allow_scoring
        if target_angle_deg is None or not allow_scoring:
            self.active = False

    def advance(self, dt):
        target_angle_deg = self.target_angle_deg
        if target_angle_deg is None:
            self.active = False
            self._rebuild()
            return
        # atan2 wraps the left horizontal from +180 to -180. Keep that
        # boundary continuous before clamping each sword to its own side.
        target_angle_deg = (target_angle_deg + 90) % 360 - 90
        pointing_up = motion.is_within_active_arc(target_angle_deg, cfg.SABER_ARC_MIN_DEG, cfg.SABER_ARC_MAX_DEG)
        lo, hi = getattr(self, "allowed_arc", (cfg.SABER_ARC_MIN_DEG, cfg.SABER_ARC_MAX_DEG))
        target_angle_deg = max(lo, min(hi, target_angle_deg))
        alpha = 1 - (1 - cfg.ANGLE_SMOOTH_LERP) ** (max(0, dt) * 30)
        self.angle_deg = max(lo, min(hi, motion.smooth_angle_towards(self.angle_deg, target_angle_deg, alpha)))
        self.active = self._allow_scoring and pointing_up and motion.is_within_active_arc(self.angle_deg, cfg.SABER_ARC_MIN_DEG, cfg.SABER_ARC_MAX_DEG)
        self._rebuild()

    def _rebuild(self):
        """畫光劍圖片本身（或找不到圖片時退回畫一條線），不再疊半透明扇形——
        判定範圍已經收窄到只比劍身寬一點點（見 config.py::HIT_ANGLE_TOLERANCE_DEG
        的說明），劍身本身的寬度已經足以代表判定範圍，不需要額外畫框框標示。
        """
        state = (self.angle_deg, self.active)
        if state == self._render_state:
            return
        self._render_state = state
        size = int(self.length * 2 + 8)
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (size // 2, size // 2)
        color = self.color if self.active else (100, 100, 110)

        if self._sword_image is not None:
            sword_img = self._sword_image
            if not self.active:
                sword_img = sword_img.copy()
                sword_img.set_alpha(100)
            _blit_hilt_anchored(surf, sword_img, center, self.angle_deg)
        else:
            rad = math.radians(self.angle_deg)
            end = (center[0] + self.length * math.cos(rad), center[1] - self.length * math.sin(rad))
            pygame.draw.line(surf, color, center, end, cfg.SABER_WIDTH)
            pygame.draw.circle(surf, color, center, cfg.SABER_WIDTH + 2)

        self.image = surf
        self.rect = surf.get_rect(center=self.pivot)


class Game3Scene(Scene):
    def on_enter(self, ctx, **kwargs):
        if kwargs.get("resumed"):
            return

        self._username = ctx.current_user
        # 【2026-09-09 暫時解鎖全部關卡】正常規則是要先過關前一關才能選下一關
        # （見 user_store.get_cleared_levels()），但這幾輪一直在調關卡本身的
        # 速度/判定，逼玩家每次都要先啃完 Lv.1 才能碰到 Lv.2/3 太浪費測試時間
        # ——先全部解鎖方便測，要恢復正常的過關限制再跟我說一聲。
        self.level_options = [{**level, "unlocked": True} for level in cfg.LEVELS]
        self.selected_level = None

        w, h = ctx.screen.get_size()
        self._screen_size = (w, h)
        self.level_select_widget = LevelSelect(
            (w // 2 - 420, h // 2 - 40, 840, 100), self.level_options, self._on_level_selected)

        self.guide_panel = InstructionPanel(
            (w // 2 - 360, h // 2 - 230, 720, 420), DISPLAY_NAME,
            [
                "右手橘劍打左側橘球，左手藍劍打右側藍球；光劍不能跨過中線。",
                "四指保持伸直、同步彎動掌指關節；手指彎曲或漏偵測時不能得分。",
                "中央球須用同色劍擊中，錯色扣 1 分並播放錯誤音。",
            ],
            self._on_guide_dismissed,
        )
        played_before = len(user_store.get_history_for_game(ctx.current_user, GAME_ID, limit=1)) > 0
        self.state = "level_select" if played_before else "guide"
        self.state_start_time = time.time()

        # 幾何：樞紐放在畫面偏下方，攻擊弧只露出上半部分（跟原本
        # BilateralCoordinationTraining 的設計概念一樣，圓心在畫面下緣附近）。
        self.pivot = (w // 2, int(h * 0.92))
        self.outer_radius = min(w, h) * cfg.OUTER_RADIUS_RATIO
        self.inner_radius = self.outer_radius * cfg.INNER_RADIUS_RATIO
        saber_length = self.inner_radius * 2.4

        blue_sword_img = _get_image("blue_sword")
        red_sword_img = _get_image("red_sword")
        self._marble_image = _get_image("marble")
        self._marble_image_broke = _get_image("marble_broke")
        self._orange_marble = _get_image("orange_marble")
        self._orange_broke = _get_image("orange_broke")
        # 圖片原始尺寸很大（2048px），縮放成高度等於 saber_length（劍柄到劍尖
        # 剛好對應 length，跟 _blit_hilt_anchored()/命中判定的幾何假設一致），
        # 只在進場的時候做一次，不會每一幀都重新縮放。
        blue_sword_scaled = _scaled_copy(blue_sword_img, saber_length) if blue_sword_img else None
        red_sword_scaled = _scaled_copy(red_sword_img, saber_length) if red_sword_img else None

        self.left_sword = LightSword(self.pivot, saber_length, (255, 140, 90), red_sword_scaled)   # 右手控制
        self.right_sword = LightSword(self.pivot, saber_length, (90, 170, 255), blue_sword_scaled)   # 左手控制

        self.left_sword.allowed_arc = (90.0, cfg.SABER_ARC_MAX_DEG)
        self.right_sword.allowed_arc = (cfg.SABER_ARC_MIN_DEG, 90.0)
        self.hand_postures = {}
        self.last_hand_frame_at = 0.0
        self.last_frame_id = -1
        self.display_frame = None
        self.left_landmarks = None
        self.right_landmarks = None
        self.distance_hint = None

        self.marbles = pygame.sprite.Group()
        self.play_start_time = None
        self.next_spawn_at = None
        self.max_possible_score = 0
        self.score = 0
        self.hits = 0
        self.misses = 0
        self.session_result = None
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
        frame, self.last_frame_id, _cam_read_ms, result = get_hand_frame(ctx, self.last_frame_id)
        if frame is not None:
            self._process_frame(frame, ctx.landmarker, result)

        if self.state == "playing" and time.time() - self.last_hand_frame_at > 0.3:
            for sword in (self.left_sword, self.right_sword):
                sword.set_target(None, False)
        if self.state == "playing":
            for sword in (self.left_sword, self.right_sword):
                sword.advance(dt)
        self._advance_state(ctx, dt)

        if self._pending_transition is not None:
            t, self._pending_transition = self._pending_transition, None
            return t
        return None

    def _process_frame(self, frame, landmarker, result=None):
        if result is None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(mp_image)

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        left_landmarks = None
        right_landmarks = None
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

        if self.state == "playing":
            self.last_hand_frame_at = time.time()
            for side, landmarks, sword in (("right", right_landmarks, self.left_sword),
                                           ("left", left_landmarks, self.right_sword)):
                posture = hand_posture(landmarks, w / h)
                self.hand_postures[side] = posture
                if landmarks is not None and all(math.isfinite(p.x) and math.isfinite(p.y) for p in landmarks):
                    posture["pointing_angle"] = _hand_pointing_angle(landmarks, w / h)
                    sword.set_target(posture["pointing_angle"], allow_scoring=posture["valid"])
                else:
                    sword.set_target(None, False)

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
        self.hand_postures = {}
        self.last_hand_frame_at = 0.0
        for sword in (self.left_sword, self.right_sword):
            sword.set_target(None, False)
        self.marbles.empty()
        self.max_possible_score = 0
        self.score = 0
        self.hits = 0
        self.misses = 0
        self._schedule_next_spawn(0.0)
        self.arcade_recording = ArcadeRecording(GAME_ID, now, self._screen_size, self.selected_level)
        record_sabers(self, now)

    def _schedule_next_spawn(self, elapsed_sec):
        lo, hi = self.selected_level["spawn_interval_range_sec"]
        self.next_spawn_at = elapsed_sec + random.uniform(lo, hi)

    def _update_playing(self, ctx, dt, now):
        elapsed_sec = now - self.play_start_time
        level = self.selected_level

        if elapsed_sec >= level["play_time_sec"]:
            self._finish_playing(ctx)
            return
        travel = (self.outer_radius-self.inner_radius) / (motion.marble_speed_for(level, elapsed_sec)*60)
        if elapsed_sec >= self.next_spawn_at and elapsed_sec + travel < level["play_time_sec"]:
            angle = motion.marble_spawn_angle_deg(level, cfg.ACTIVE_ARC_MIN_DEG, cfg.ACTIVE_ARC_MAX_DEG)
            speed = motion.marble_speed_for(level, elapsed_sec)
            color = (random.choice(("orange", "blue")) if abs(angle - 90) < 1e-6
                     else "orange" if angle > 90 else "blue")
            marble = Marble(self.pivot, angle, self.outer_radius, self.inner_radius, speed,
                self._orange_marble if color == "orange" else self._marble_image,
                self._orange_broke if color == "orange" else self._marble_image_broke)
            marble.color = color
            self.marbles.add(marble)
            self.max_possible_score += 1
            self._schedule_next_spawn(elapsed_sec)

        for marble in list(self.marbles):
            if marble.broken:
                # 打中之後的碎裂淡出動畫，不參與飛行/命中判定，淡完就移除。
                if marble.fade(dt):
                    marble.kill()
                continue

            missed = marble.step(dt)
            if missed:
                self.arcade_recording.event(now, "漏接彈珠（不扣分）", marble,
                    self.arcade_recording.point(*marble.rect.center), self.score, self.score)
                self.misses += 1
                marble.kill()
                sound = _get_sound("miss")
                if sound is not None:
                    sound.play()
                continue

            for sword, color, hand in ((self.left_sword, "orange", "right"),
                                        (self.right_sword, "blue", "left")):
                central = abs(marble.angle_deg - 90) < 1e-6
                allowed_side = central or (marble.angle_deg > 90 if hand == "right" else marble.angle_deg < 90)
                if not (sword.active and allowed_side and motion.is_marble_hit(
                        marble.angle_deg, marble.distance, sword.angle_deg, sword.length,
                        cfg.HIT_ANGLE_TOLERANCE_DEG)):
                    continue
                correct = color == marble.color
                delta = cfg.HIT_SCORE if correct else -1
                self.arcade_recording.event(now, "同色光劍命中" if correct else "中央球錯色（扣 1 分）", marble,
                    self.arcade_recording.point(*marble.rect.center), self.score, self.score + delta,
                    side=hand, sword_angle=sword.angle_deg, color=marble.color)
                self.score += delta
                self.hits += int(correct)
                marble.hit()
                sound = _get_sound("hit" if correct else "miss")
                if sound is not None:
                    sound.play()
                break

        record_sabers(self, now)
        if elapsed_sec >= level["play_time_sec"]:
            self._finish_playing(ctx)

    def _finish_playing(self, ctx):
        threshold = max(1, math.ceil(self.max_possible_score * 0.8))
        self.session_result = scoring.compute_session_result(
            self.score, self.hits, self.misses, {**self.selected_level, "pass_score": threshold})
        details = self.session_result.to_details(self.selected_level["level_id"])
        details.update(rule_version="saber_colors_v2", max_possible_score=self.max_possible_score,
                       pass_score=threshold, pass_ratio=0.8)
        details["arcade_replay"] = self.arcade_recording.data
        begin_result_save(self, ctx, GAME_ID, self.score, details)
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
            self._draw_arena(surface)
            self._draw_countdown(surface, w, h)
        elif self.state == "playing":
            self._draw_arena(surface)
            self._draw_playing_hud(surface, w)
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

    def _draw_arena(self, surface):
        pygame.draw.circle(surface, (40, 46, 56), self.pivot, int(self.outer_radius), width=2)
        pygame.draw.circle(surface, (60, 68, 80), self.pivot, int(self.inner_radius), width=2)

        for marble in self.marbles:
            surface.blit(marble.image, marble.rect)
        surface.blit(self.left_sword.image, self.left_sword.rect)
        surface.blit(self.right_sword.image, self.right_sword.rect)

    def _draw_countdown(self, surface, w, h):
        remaining = _COUNTDOWN_SECONDS - (time.time() - self.state_start_time)
        number = max(1, math.ceil(remaining))
        font = get_font(120)
        text = font.render(str(number), True, COLOR_ACCENT)
        surface.blit(text, text.get_rect(center=(w // 2, h // 2)))

    def _draw_playing_hud(self, surface, w):
        font = get_font(28)
        elapsed = time.time() - self.play_start_time
        remaining = max(0.0, self.selected_level["play_time_sec"] - elapsed)
        msg = font.render(f"分數 {self.score}　剩餘時間 {remaining:.0f}s", True, COLOR_TEXT)
        surface.blit(msg, msg.get_rect(centerx=w // 2, top=90))
        for i, side in enumerate(("left", "right")):
            posture = self.hand_postures.get(side, {"reason": "等待入鏡"})
            sword = self.right_sword if side == "left" else self.left_sword
            name = "左手／藍劍" if side == "left" else "右手／橘劍"
            label = get_font(18).render(f"{name} {sword.angle_deg:.0f}°：{posture['reason']}", True, COLOR_TEXT)
            surface.blit(label, (PADDING, 165 + i * 26))

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
            f"命中 {self.session_result.hits}　漏接 {self.session_result.misses}　{pass_label}",
            True, pass_color)
        surface.blit(info, info.get_rect(centerx=w // 2, top=h // 2 - 10))

        threshold = max(1, math.ceil(self.max_possible_score * 0.8))
        rule = get_font(22).render(f"本局可得 {self.max_possible_score} 分　過關需 {threshold} 分（80%）", True, COLOR_TEXT)
        surface.blit(rule, rule.get_rect(centerx=w // 2, top=h // 2 + 50))
        self.back_button.draw(surface)
        self.retry_button.draw(surface)
