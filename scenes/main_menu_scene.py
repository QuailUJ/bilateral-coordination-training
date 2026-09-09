"""
scenes/main_menu_scene.py - 登入後的主選單

從 games.registry.GAMES 動態產生遊戲 tile，之後新增遊戲二/三/四只要在
registry.py 加一筆 GameSpec，這支檔案完全不用改。另外提供「歷史成績」跟
「切換使用者」兩個入口。
"""

import pygame

from common.scene_manager import Scene, Transition
from games.registry import GAMES
from ui.theme import get_font, COLOR_BG, COLOR_TEXT, COLOR_TEXT_MUTED, PADDING
from ui.widgets import Button


class MainMenuScene(Scene):
    def on_enter(self, ctx, **kwargs):
        w, h = ctx.screen.get_size()
        self.buttons = []

        tile_w, tile_h = 320, 180
        gap = 40
        enabled_games = [g for g in GAMES if g.enabled]
        cols = max(1, min(4, len(enabled_games)) or 1)
        total_w = cols * tile_w + (cols - 1) * gap
        start_x = w // 2 - total_w // 2
        start_y = h // 2 - tile_h // 2 - 40

        for i, game in enumerate(enabled_games):
            col = i % cols
            row = i // cols
            rect = (start_x + col * (tile_w + gap), start_y + row * (tile_h + gap), tile_w, tile_h)
            btn = Button(rect, game.display_name, subtitle=game.description, font_size=26,
                         on_click=lambda g=game: self._launch_game(g.game_id))
            self.buttons.append(btn)

        bottom_y = h - 90
        self.history_button = Button((PADDING, bottom_y, 220, 56), "歷史成績", on_click=self._open_history)
        self.switch_user_button = Button((w - PADDING - 220, bottom_y, 220, 56),
                                          "切換使用者", on_click=self._switch_user)
        self._transition = None

    def _launch_game(self, game_id):
        from games.registry import get_game
        scene = get_game(game_id).scene_factory()
        self._transition = Transition("push", scene)

    def _open_history(self):
        from scenes.history_scene import HistoryScene
        self._transition = Transition("push", HistoryScene())

    def _switch_user(self):
        from scenes.login_scene import LoginScene
        self._transition = Transition("replace", LoginScene())

    def handle_event(self, ctx, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            # 遊戲畫面裡按 ESC 是「返回主選單」(Transition("pop"))；在主選單這裡
            # 再按一次 ESC 應該再往上一層，回到最外層的「選擇使用者」畫面
            # ——就跟按「切換使用者」按鈕的效果一樣。之前這裡寫成按 ESC 直接
            # 關掉整個程式，玩家連續按 ESC 想一路退回去時很容易多按一下就把整個
            # App 關掉，不是預期行為。正式的離開程式入口改放在登入畫面右上角的
            # 「退出程式」按鈕（登入畫面是堆疊最底層，沒有再上一層可以 ESC 了）。
            self._switch_user()

        for btn in self.buttons:
            btn.handle_event(event)
        self.history_button.handle_event(event)
        self.switch_user_button.handle_event(event)
        return None

    def update(self, ctx, dt):
        if self._transition is not None:
            t, self._transition = self._transition, None
            return t
        return None

    def draw(self, ctx, surface):
        surface.fill(COLOR_BG)
        w, h = surface.get_size()

        title_font = get_font(36)
        user_font = get_font(22)
        title = title_font.render("選擇遊戲", True, COLOR_TEXT)
        surface.blit(title, title.get_rect(centerx=w // 2, top=40))
        user_label = user_font.render(f"使用者：{ctx.current_user}", True, COLOR_TEXT_MUTED)
        surface.blit(user_label, (PADDING, 40))

        for btn in self.buttons:
            btn.draw(surface)
        self.history_button.draw(surface)
        self.switch_user_button.draw(surface)
