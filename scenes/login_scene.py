"""
scenes/login_scene.py - 登入畫面

只需要使用者名稱、免密碼：輸入名稱按 Enter 或按登入按鈕，如果是第一次看到
這個名稱就自動建立新的使用者資料檔（data/users/<name>.json）並立刻寫檔，
如果已經存在就直接讀回舊資料（成績歷史都在裡面）。下方也列出最近登入過的
使用者名稱，方便快速切換不用每次重打。
"""

import pygame
import os

from common.scene_manager import Scene, Transition
from data_store import user_store
from ui.theme import get_font, COLOR_BG, COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_DANGER, PADDING
from ui.widgets import TextInput, Button


class LoginScene(Scene):
    def on_enter(self, ctx, **kwargs):
        self._persistence = getattr(ctx, "persistence", None)
        self._login_future = None
        w, h = ctx.screen.get_size()
        input_w, input_h = 480, 64
        self.text_input = TextInput(
            (w // 2 - input_w // 2, h // 2 - input_h // 2, input_w, input_h),
            placeholder="輸入使用者名稱...", font_size=32,
        )
        self.login_button = Button(
            (w // 2 - input_w // 2, h // 2 - input_h // 2 + input_h + 20, input_w, 56),
            "登入 / 建立新使用者", on_click=self._submit,
        )
        self.trial_button = Button((w//2-input_w//2, self.login_button.rect.bottom+12, input_w, 48),
                                   "測試版右手畫圓", self._submit_trial, font_size=25)
        self._trial_requested = False
        # 這是整個場景堆疊最底層（登入畫面沒有再上一層可以 ESC 返回了），所以
        # 「退出程式」放在這裡當唯一的正式離開入口，右上角，跟其他按鈕的位置
        # 分開避免誤按。
        self.exit_button = Button((w - PADDING - 160, PADDING, 160, 48), "退出程式", on_click=self._exit_app)
        self.error_message = ""
        self.known_usernames = user_store.list_known_display_names()
        self._quick_buttons = self._build_quick_buttons(w, h, input_w)

    def _build_quick_buttons(self, w, h, input_w):
        buttons = []
        names = self.known_usernames[:6]
        start_y = self.trial_button.rect.bottom + 56
        for i, name in enumerate(names[:max(0, (h-start_y-12)//44)]):
            rect = (w // 2 - input_w // 2, start_y + i * 44, input_w, 36)
            buttons.append(Button(rect, name, on_click=lambda n=name: self._login_as(n), font_size=20))
        return buttons

    def _submit(self):
        self._trial_requested = False
        self._login_as(self.text_input.text)

    def _submit_trial(self):
        self._login_as(self.text_input.text)
        self._trial_requested = bool(self._login_future or getattr(self, "_pending_username", None))

    def _login_as(self, raw_username: str):
        try:
            user_store.sanitize_username(raw_username)
            self.error_message = ""
            if self._persistence is not None:
                self._login_future = self._persistence.login(raw_username)
                return
            user_data = user_store.create_or_load_user(raw_username)
            if not os.path.exists(user_store.user_file_path(raw_username)):
                user_store.save_user(user_data)
        except ValueError as e:
            self.error_message = str(e)
            return
        self._pending_username = raw_username.strip()

    @staticmethod
    def _exit_app():
        pygame.quit()
        raise SystemExit

    def handle_event(self, ctx, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit

        if self._login_future is not None:
            self.exit_button.handle_event(event)
            return None

        result = self.text_input.handle_event(event)
        if result == "submit":
            self._submit()
        self.login_button.handle_event(event)
        self.trial_button.handle_event(event)
        self.exit_button.handle_event(event)
        for btn in self._quick_buttons:
            btn.handle_event(event)
        return None

    def update(self, ctx, dt):
        self.text_input.update(dt)
        if self._login_future is not None and self._login_future.done():
            try:
                self._pending_username = self._login_future.result()
            except Exception as error:
                self.error_message = str(error)
            self._login_future = None
        if getattr(self, "_pending_username", None):
            ctx.current_user = self._pending_username
            self._pending_username = None
            if self._trial_requested:
                self._trial_requested = False
                from scenes.circle_trial_scene import CircleTrialScene
                return Transition("push", CircleTrialScene())
            from scenes.main_menu_scene import MainMenuScene
            return Transition("replace", MainMenuScene())
        return None

    def draw(self, ctx, surface):
        surface.fill(COLOR_BG)
        w, h = surface.get_size()

        title_font = get_font(48)
        title = title_font.render("復健訓練遊戲平台", True, COLOR_TEXT)
        surface.blit(title, title.get_rect(centerx=w // 2, top=h // 4))

        self.text_input.draw(surface)
        self.login_button.draw(surface)
        self.trial_button.draw(surface)
        self.exit_button.draw(surface)
        if self._login_future is not None:
            text = get_font(22).render("正在載入使用者資料…", True, COLOR_TEXT_MUTED)
            surface.blit(text, text.get_rect(centerx=w//2, bottom=self.text_input.rect.top-10))

        if self.error_message:
            err_font = get_font(22)
            err_surf = err_font.render(self.error_message, True, COLOR_DANGER)
            surface.blit(err_surf, err_surf.get_rect(centerx=w // 2, top=self.text_input.rect.top - 35))

        if self._quick_buttons:
            hint_font = get_font(18)
            hint = hint_font.render("最近使用過的名稱：", True, COLOR_TEXT_MUTED)
            surface.blit(hint, (self._quick_buttons[0].rect.x, self._quick_buttons[0].rect.y - 30))
            for btn in self._quick_buttons:
                btn.draw(surface)
