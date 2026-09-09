"""Account deletion UI; confirmation names the account and all affected data."""
import pygame
from common.scene_manager import Scene, Transition
from data_store import user_store
from ui.widgets import Button, ScrollList
from ui.theme import COLOR_BG, COLOR_TEXT, COLOR_DANGER, get_font


class UserManagementScene(Scene):
    def on_enter(self, ctx, **kwargs):
        w, h = ctx.screen.get_size()
        self.selected = None
        self.message = ""
        self.changed = False
        self.closing = False
        self.list_view = ScrollList((w//2-320, 120, 640, h-240), on_select=self._select)
        self.back = Button((16, h-72, 200, 48), "返回", lambda: setattr(self, "closing", True))
        self.confirm = Button((w//2-260, h//2+40, 250, 48), "刪除使用者及資料", lambda: self._delete(ctx), font_size=22)
        self.cancel = Button((w//2+20, h//2+40, 200, 48), "取消", lambda: setattr(self, "selected", None))
        self._reload()

    def _reload(self):
        names = user_store.list_known_display_names()
        self.list_view.set_items(names, records=names)

    def _select(self, name):
        self.selected = name
        self.message = ""

    def _delete(self, ctx):
        try:
            user_store.delete_user(self.selected)
        except (OSError, ValueError) as error:
            self.message = f"刪除失敗：{error}"
            return
        if ctx.current_user is not None and user_store.sanitize_username(ctx.current_user) == user_store.sanitize_username(self.selected):
            ctx.current_user = None
        self.selected = None
        self.changed = True
        self.message = "使用者與成績、回放資料已刪除。"
        self._reload()

    def handle_event(self, ctx, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.selected is not None:
                self.selected = None
            else:
                self.closing = True
        elif self.selected is not None:
            self.confirm.handle_event(event)
            self.cancel.handle_event(event)
        else:
            self.list_view.handle_event(event)
            self.back.handle_event(event)
        if self.closing:
            return Transition("pop")

    def draw(self, ctx, surface):
        surface.fill(COLOR_BG)
        w, h = surface.get_size()
        label = get_font(32).render("管理使用者：點選要刪除的帳號", True, COLOR_TEXT)
        surface.blit(label, label.get_rect(centerx=w//2, top=40))
        self.list_view.draw(surface)
        self.back.draw(surface)
        if self.selected is not None:
            pygame.draw.rect(surface, COLOR_BG, (w//2-355, h//2-130, 710, 240), border_radius=12)
            lines = [f"確定刪除「{self.selected}」？", "全部歷史成績與回放資料會一起刪除，無法復原。"]
            for i, line in enumerate(lines):
                text = get_font(22).render(line, True, COLOR_TEXT)
                surface.blit(text, text.get_rect(centerx=w//2, top=h//2-95+i*44))
            self.confirm.draw(surface)
            self.cancel.draw(surface)
        text = get_font(20).render(self.message, True, COLOR_DANGER)
        surface.blit(text, text.get_rect(centerx=w//2, bottom=h-85))
