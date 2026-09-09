"""Sound and camera settings shared by login, menu and training screens."""
import cv2
import pygame

from common import audio, game_time
from common.cv_pygame import bgr_frame_to_surface
from common.scene_manager import Scene, Transition
from data_store.settings_store import save_settings
from ui.theme import COLOR_BG, COLOR_TEXT, COLOR_TEXT_MUTED, get_font
from ui.widgets import Button


class SettingsScene(Scene):
    def on_enter(self, ctx, **kwargs):
        self.user_management = None
        self.users_changed = False
        game_time.pause()
        if pygame.mixer.get_init():
            pygame.mixer.pause()
        self.index = ctx.camera_index
        self.message = ctx.camera_error or "使用 + / - 選擇攝影機編號，再按「套用攝影機」。"
        self.frame_id = -1
        self.preview = None
        self.closing = False
        w, h = ctx.screen.get_size()
        x = w // 2
        self.buttons = [
            Button((x - 240, 140, 80, 48), "-", lambda: self._volume(ctx, -0.1)),
            Button((x + 160, 140, 80, 48), "+", lambda: self._volume(ctx, 0.1)),
            Button((x - 240, 220, 80, 48), "-", lambda: self._camera(-1)),
            Button((x + 160, 220, 80, 48), "+", lambda: self._camera(1)),
            Button((x - 140, 285, 280, 48), "套用攝影機", lambda: self._apply_camera(ctx)),
            Button((x - 160, h - 70, 320, 48), "儲存並返回（Esc）", lambda: self._close(ctx)),
        ]
        if kwargs.get("manage_users", False):
            self.buttons.append(Button((20, 20, 220, 48), "管理使用者", lambda: self._manage_users(ctx), font_size=24))

    def _manage_users(self, ctx):
        from scenes.user_management_scene import UserManagementScene
        self.user_management = UserManagementScene()
        self.user_management.on_enter(ctx)

    def _volume(self, ctx, delta):
        ctx.volume = round(max(0.0, min(1.0, ctx.volume + delta)), 2)
        audio.set_volume(ctx.volume)

    def _camera(self, delta):
        self.index = max(0, self.index + delta)

    def _apply_camera(self, ctx):
        try:
            ctx.switch_camera(self.index)
            self.frame_id = -1
            self.preview = None
            self.message = f"已切換至攝影機 {ctx.camera_index}"
        except (RuntimeError, cv2.error) as error:
            self.message = str(error)

    def _close(self, ctx):
        try:
            save_settings(ctx.camera_index, ctx.volume)
            self.closing = True
        except OSError:
            self.message = "設定儲存失敗，請確認 data 資料夾可寫入後再試。"

    def on_exit(self, ctx):
        game_time.resume()
        if pygame.mixer.get_init():
            pygame.mixer.unpause()

    def handle_event(self, ctx, event):
        if self.user_management is not None:
            transition = self.user_management.handle_event(ctx, event)
            if transition:
                self.users_changed |= self.user_management.changed
                self.user_management = None
            return None
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_F1):
            self._close(ctx)
        for button in self.buttons:
            button.handle_event(event)
        if self.closing:
            return Transition("pop")

    def update(self, ctx, dt):
        frame, self.frame_id, _ = ctx.camera.get_next(self.frame_id, timeout=0.0)
        if frame is not None:
            self.preview = bgr_frame_to_surface(cv2.flip(frame, 1))

    def draw(self, ctx, surface):
        if self.user_management is not None:
            self.user_management.draw(ctx, surface)
            return
        surface.fill(COLOR_BG)
        w, h = surface.get_size()
        for text, y, size in [
            ("聲音與攝影機設定", 50, 36),
            (f"音量：{round(ctx.volume * 100)}%", 145, 28),
            (f"攝影機：{self.index}", 225, 28),
            (f"目前使用：攝影機 {ctx.camera_index}　｜　切換後請確認預覽", 345, 20),
        ]:
            label = get_font(size).render(text, True, COLOR_TEXT)
            surface.blit(label, label.get_rect(centerx=w // 2, top=y))
        if self.preview is not None:
            height = max(40, min(300, h - 490))
            size = (height * self.preview.get_width() // self.preview.get_height(), height)
            preview = pygame.transform.smoothscale(self.preview, size)
            surface.blit(preview, preview.get_rect(centerx=w // 2, top=380))
        else:
            label = get_font(24).render("尚未取得攝影機影像", True, COLOR_TEXT_MUTED)
            surface.blit(label, label.get_rect(center=(w // 2, 420)))
        label = get_font(18).render(self.message, True, COLOR_TEXT_MUTED)
        surface.blit(label, label.get_rect(centerx=w // 2, bottom=h - 85))
        for button in self.buttons:
            button.draw(surface)
