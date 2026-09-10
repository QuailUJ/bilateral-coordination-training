"""
ui/widgets.py - 共用 pygame UI 元件：Button / ScrollList / TextInput / LevelSelect / InstructionPanel

這些元件故意設計成不依賴 SceneManager/AppContext，只吃 pygame 事件跟畫布，
方便各個 Scene 直接組合使用。
"""

import pygame

from ui.theme import (
    get_font, COLOR_PANEL, COLOR_TEXT, COLOR_TEXT_MUTED,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, PADDING,
)


class Button:
    def __init__(self, rect, label, on_click=None, font_size=28, subtitle=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.subtitle = subtitle
        self.on_click = on_click
        self.font_size = font_size
        self.hovered = False
        self.enabled = True
        # "選取中"跟"不能按"是兩種不同的視覺狀態，故意分開兩個旗標——之前
        # 用 enabled=False 表現「選取中」會讓被選到的按鈕看起來像壞掉/不能按
        # （文字變淡），而不是「這顆現在選到了」，兩者不能共用同一個旗標。
        self.selected = False

    def handle_event(self, event):
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.on_click is not None:
                    self.on_click()
                return True
        return False

    def draw(self, surface):
        if self.selected:
            color = COLOR_ACCENT
        elif self.hovered and self.enabled:
            color = COLOR_ACCENT_HOVER
        else:
            color = COLOR_PANEL
        pygame.draw.rect(surface, color, self.rect, border_radius=10)
        pygame.draw.rect(surface, COLOR_ACCENT, self.rect, width=2, border_radius=10)

        font = get_font(self.font_size)
        text_color = COLOR_TEXT if (self.enabled or self.selected) else COLOR_TEXT_MUTED
        label_surf = font.render(self.label, True, text_color)
        if self.subtitle:
            sub_font = get_font(max(14, self.font_size - 10))
            sub_surf = sub_font.render(self.subtitle, True, COLOR_TEXT_MUTED)
            total_h = label_surf.get_height() + sub_surf.get_height() + 4
            label_y = self.rect.centery - total_h // 2
            surface.blit(label_surf, label_surf.get_rect(centerx=self.rect.centerx, top=label_y))
            surface.blit(sub_surf, sub_surf.get_rect(
                centerx=self.rect.centerx, top=label_y + label_surf.get_height() + 4))
        else:
            surface.blit(label_surf, label_surf.get_rect(center=self.rect.center))


class TextInput:
    """單行文字輸入框，用於登入畫面輸入使用者名稱。"""

    def __init__(self, rect, placeholder="", font_size=32, max_len=50):
        self.rect = pygame.Rect(rect)
        self.placeholder = placeholder
        self.font_size = font_size
        self.max_len = max_len
        self.text = ""
        self.active = True
        self._cursor_visible = True
        self._cursor_timer = 0.0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                return "submit"
            elif event.unicode and event.unicode.isprintable() and len(self.text) < self.max_len:
                self.text += event.unicode
        return None

    def update(self, dt):
        self._cursor_timer += dt
        if self._cursor_timer >= 0.5:
            self._cursor_timer = 0.0
            self._cursor_visible = not self._cursor_visible

    def draw(self, surface):
        pygame.draw.rect(surface, COLOR_PANEL, self.rect, border_radius=8)
        border_color = COLOR_ACCENT if self.active else COLOR_TEXT_MUTED
        pygame.draw.rect(surface, border_color, self.rect, width=2, border_radius=8)

        font = get_font(self.font_size)
        if self.text:
            text_surf = font.render(self.text, True, COLOR_TEXT)
        else:
            text_surf = font.render(self.placeholder, True, COLOR_TEXT_MUTED)
        surface.blit(text_surf, (self.rect.x + PADDING, self.rect.centery - text_surf.get_height() // 2))

        if self.active and self._cursor_visible:
            cursor_x = self.rect.x + PADDING + font.size(self.text)[0] + 2
            cursor_y1 = self.rect.centery - font.get_height() // 2
            cursor_y2 = self.rect.centery + font.get_height() // 2
            pygame.draw.line(surface, COLOR_TEXT, (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)


class InstructionPanel:
    """遊戲開始前的操作說明畫面：標題 + 條列說明文字 + 一個「開始」按鈕。純顯示
    用途，不管遊戲本身的狀態機怎麼設計——呼叫端在自己的初始 state（例如
    `"guide"`）裡建立一個 InstructionPanel，收到 on_start 之後自行切換到下一個
    state（通常是關卡選擇或校準）即可，這裡不負責狀態轉換。

    lines: 條列說明文字（純文字 list），內容由每款遊戲自己決定，例如玩法規則、
           「請站在攝影機前方讓雙手都能入鏡」這類提醒。
    """

    def __init__(self, rect, title, lines, on_start, button_label="開始"):
        self.rect = pygame.Rect(rect)
        self.title = title
        self.lines = lines
        self.button = Button((self.rect.centerx - 100, self.rect.bottom - 76, 200, 56),
                              button_label, on_click=on_start, font_size=26)

    def handle_event(self, event):
        self.button.handle_event(event)

    def draw(self, surface):
        pygame.draw.rect(surface, COLOR_PANEL, self.rect, border_radius=14)
        pygame.draw.rect(surface, COLOR_ACCENT, self.rect, width=2, border_radius=14)

        title_font = get_font(30)
        title_surf = title_font.render(self.title, True, COLOR_TEXT)
        surface.blit(title_surf, title_surf.get_rect(centerx=self.rect.centerx, top=self.rect.top + 24))

        from ui.training_panels import _wrap
        y = self.rect.top + 24 + title_surf.get_height() + 24
        for size in range(22, 11, -1):
            line_font = get_font(size)
            wrapped = _wrap(["• " + line for line in self.lines], line_font, self.rect.width - 80)
            step = line_font.get_linesize() + 6
            if len(wrapped)*step <= self.button.rect.top-y-12:
                break
        for line in wrapped:
            line_surf = line_font.render(line, True, COLOR_TEXT_MUTED)
            surface.blit(line_surf, (self.rect.left + 40, y))
            y += step

        self.button.draw(surface)


class LevelSelect:
    """關卡選擇列表：吃一份關卡設定，畫成可點的 Button 網格，未解鎖的關卡顯示
    成灰階、點了沒反應。取代舊專案「自由調整時間長度」的設定畫面——時間、速度
    等參數改成由企劃內建在每個關卡的設定裡，玩家只選要玩哪一個。

    levels: list[dict]，每筆至少要有 "level_id"、"label"；可選 "description"
            （當 Button 的 subtitle）、"unlocked"（預設 True）。
    on_select(level_id): 點選已解鎖關卡時呼叫。
    columns: 排成幾欄；預設 None 表示全部排一整排（跟原本行為一樣，關卡數量
             少的遊戲適用）；選項很多時（例如 16 種動作組合）傳欄數排成網格，
             比單排塞好排版。
    """

    def __init__(self, rect, levels, on_select, font_size=28, columns=None):
        self.rect = pygame.Rect(rect)
        self.levels = levels
        self.on_select = on_select
        self.font_size = font_size
        self.columns = columns
        self.buttons = []
        self._build_buttons()

    def _build_buttons(self):
        n = len(self.levels)
        self.buttons = []
        if n == 0:
            return
        gap = PADDING
        cols = min(self.columns, n) if self.columns else n
        rows = (n + cols - 1) // cols
        btn_w = (self.rect.width - gap * (cols - 1)) // cols
        btn_h = (self.rect.height - gap * (rows - 1)) // rows
        for i, level in enumerate(self.levels):
            col, row = i % cols, i // cols
            x = self.rect.x + col * (btn_w + gap)
            y = self.rect.y + row * (btn_h + gap)
            unlocked = level.get("unlocked", True)
            level_id = level["level_id"]
            on_click = (lambda lid=level_id: self.on_select(lid)) if unlocked else None
            btn = Button((x, y, btn_w, btn_h), level["label"],
                         on_click=on_click, font_size=self.font_size,
                         subtitle=level.get("description"))
            btn.enabled = unlocked
            self.buttons.append(btn)

    def handle_event(self, event):
        for btn in self.buttons:
            btn.handle_event(event)

    def draw(self, surface):
        for level, btn in zip(self.levels, self.buttons):
            btn.draw(surface)
            if "color" in level:
                pygame.draw.rect(surface, level["color"], btn.rect, 3, border_radius=8)


class ScrollList:
    """簡單的可捲動列表，用於歷史成績畫面。items 是字串或 (line1, line2) tuple 的 list。

    on_select(record)：可選，設定了才會回應點擊。set_items() 可以額外傳一份
    跟 items 同長度、同順序的 records（原始資料，通常是不方便直接塞進顯示
    文字的物件），點到某一列時會拿該列對應的 record 呼叫 on_select；records
    裡對應到 None 的那幾列點了沒反應（用來標記「這幾列本來就不能點」）。
    """

    def __init__(self, rect, items=None, font_size=24, row_height=48, on_select=None):
        self.rect = pygame.Rect(rect)
        self.items = items or []
        self.records = []
        self.font_size = font_size
        self.row_height = row_height
        self.scroll_offset = 0
        self.on_select = on_select

    def set_items(self, items, records=None):
        self.items = items
        self.records = list(records) if records is not None else [None] * len(items)
        self.scroll_offset = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(pygame.mouse.get_pos()):
            self.scroll_offset -= event.y * self.row_height
            self._clamp_scroll()
        elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
              and self.on_select is not None and self.rect.collidepoint(event.pos)):
            index = self._row_index_at(event.pos[1])
            if index is not None and index < len(self.records) and self.records[index] is not None:
                self.on_select(self.records[index])

    def _row_index_at(self, screen_y):
        relative_y = screen_y - self.rect.y + self.scroll_offset - 8
        if relative_y < 0:
            return None
        index = int(relative_y // self.row_height)
        return index if 0 <= index < len(self.items) else None

    def _clamp_scroll(self):
        max_scroll = max(0, len(self.items) * self.row_height - self.rect.height)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

    def draw(self, surface):
        pygame.draw.rect(surface, COLOR_PANEL, self.rect, border_radius=8)
        clip = surface.get_clip()
        surface.set_clip(self.rect)

        font = get_font(self.font_size)
        y = self.rect.y - self.scroll_offset + 8
        for item in self.items:
            if y + self.row_height >= self.rect.y and y <= self.rect.bottom:
                if isinstance(item, tuple):
                    line1, line2 = item
                    surf1 = font.render(line1, True, COLOR_TEXT)
                    surface.blit(surf1, (self.rect.x + PADDING, y))
                    if line2:
                        font2 = get_font(max(14, self.font_size - 6))
                        surf2 = font2.render(line2, True, COLOR_TEXT_MUTED)
                        surface.blit(surf2, (self.rect.x + PADDING, y + surf1.get_height() + 2))
                else:
                    surf = font.render(str(item), True, COLOR_TEXT)
                    surface.blit(surf, (self.rect.x + PADDING, y))
            y += self.row_height

        surface.set_clip(clip)

        if not self.items:
            empty_font = get_font(self.font_size)
            empty_surf = empty_font.render("目前還沒有紀錄", True, COLOR_TEXT_MUTED)
            surface.blit(empty_surf, empty_surf.get_rect(center=self.rect.center))
