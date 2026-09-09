"""
common/scene_manager.py - 場景（畫面）管理

整個新專案只開一個 pygame 視窗，畫面切換（登入 -> 主選單 -> 遊戲/歷史成績 ->
回主選單）都是靠切換「場景 (Scene)」物件來實現，不是開多個視窗。用一個簡單的
stack 來管理場景，支援 push（切到新畫面，可以再返回上一頁）、pop（返回上一
頁）、replace（直接取代目前畫面，不留返回路徑，例如登入成功後不該讓玩家「返回」
到登入畫面）。
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


class Scene:
    """所有畫面（LoginScene / MainMenuScene / HistoryScene / GameXScene...）的基底類別。"""

    def on_enter(self, ctx, **kwargs):
        """切換進這個場景時呼叫一次，kwargs 是上一個場景傳過來的參數。"""

    def on_exit(self, ctx):
        """離開這個場景時呼叫一次（不論是 pop 掉還是被 replace 蓋掉）。"""

    def handle_event(self, ctx, event) -> Optional["Transition"]:
        """處理單一 pygame 事件，需要切場景就回傳 Transition，否則回傳 None。"""
        return None

    def update(self, ctx, dt: float) -> Optional["Transition"]:
        """每幀呼叫一次（dt 為秒），需要切場景就回傳 Transition，否則回傳 None。"""
        return None

    def draw(self, ctx, surface):
        """把這個場景畫到 surface 上。"""


@dataclass
class Transition:
    kind: str  # "push" | "pop" | "replace"
    scene: Optional[Scene] = None
    kwargs: dict = field(default_factory=dict)


class SceneManager:
    def __init__(self, ctx):
        self.ctx = ctx
        self._stack: list[Scene] = []
        self._settings = None
        from ui.widgets import Button
        self.settings_button = Button((16, 16, 180, 44), "設定（F1）", self._open_settings, font_size=24)

    def _open_settings(self):
        if self._settings is None:
            from scenes.settings_scene import SettingsScene
            self._settings = SettingsScene()
            self._settings.on_enter(self.ctx, manage_users=(self.current.__class__.__name__ in ("MainMenuScene", "LoginScene")
                and getattr(self.current, "_login_future", None) is None))

    def _layout_settings_button(self):
        w, h = self.ctx.screen.get_size()
        name = self.current.__class__.__name__
        if name == "LoginScene":
            self.settings_button.rect.topleft = (w - 376, 16)
        elif name == "MainMenuScene":
            self.settings_button.rect.topleft = (w - 196, 16)
        else:
            self.settings_button.rect.topleft = (w - 196, h - 60)

    @property
    def current(self) -> Optional[Scene]:
        return self._stack[-1] if self._stack else None

    def push(self, scene: Scene, **kwargs):
        self._stack.append(scene)
        scene.on_enter(self.ctx, **kwargs)

    def pop(self):
        if not self._stack:
            return
        top = self._stack.pop()
        top.on_exit(self.ctx)
        if self._stack:
            self._stack[-1].on_enter(self.ctx, resumed=True)

    def replace(self, scene: Scene, **kwargs):
        if self._stack:
            top = self._stack.pop()
            top.on_exit(self.ctx)
        self._stack.append(scene)
        scene.on_enter(self.ctx, **kwargs)

    def apply(self, transition: Optional[Transition]):
        if transition is None:
            return
        if transition.kind == "push":
            self.push(transition.scene, **transition.kwargs)
        elif transition.kind == "pop":
            self.pop()
        elif transition.kind == "replace":
            self.replace(transition.scene, **transition.kwargs)
        else:
            raise ValueError(f"未知的 Transition.kind: {transition.kind}")

    def handle_event(self, event):
        if self.current is None:
            return
        import pygame
        if self._settings is not None:
            transition = self._settings.handle_event(self.ctx, event)
            if transition is not None:
                users_changed = self._settings.users_changed
                self._settings.on_exit(self.ctx)
                self._settings = None
                if users_changed:
                    if self.ctx.current_user is None:
                        from scenes.login_scene import LoginScene
                        self.replace(LoginScene())
                    else:
                        self.current.on_enter(self.ctx, resumed=True)
            return
        if event.type == pygame.KEYDOWN and (event.key == pygame.K_F1 or
                (event.key == pygame.K_ESCAPE and self.current.__class__.__name__ == "LoginScene")):
            self._open_settings()
            return
        self._layout_settings_button()
        if self.settings_button.handle_event(event):
            return
        if getattr(self.current, "state", None) == "settling":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r and getattr(self.current, "save_error", ""):
                self.current.save_error = ""
                self.current._save_future = self.ctx.persistence.save_result(*self.current._save_payload)
            return
        self.apply(self.current.handle_event(self.ctx, event))

    def update(self, dt: float):
        if self._settings is not None:
            self._settings.update(self.ctx, dt)
            return
        if self.current is None:
            return
        self.apply(self.current.update(self.ctx, dt))
        if self.current is not None:
            from common.background_persistence import poll_result_save
            poll_result_save(self.current)

    def draw(self, surface):
        if self._settings is not None:
            self._settings.draw(self.ctx, surface)
            return
        if self.current is None:
            return
        self.current.draw(self.ctx, surface)
        if getattr(self.current, "state", None) == "settling":
            from common.background_persistence import draw_save_status
            draw_save_status(self.current, surface)
        self._layout_settings_button()
        self.settings_button.draw(surface)

    @property
    def is_empty(self) -> bool:
        return not self._stack
