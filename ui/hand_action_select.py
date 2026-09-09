"""Independent, mutually exclusive choices for each hand."""
import pygame
from ui.widgets import Button
from ui.theme import get_font, COLOR_TEXT, COLOR_TEXT_MUTED

OPTIONS = [("N", "不使用"), ("V", "垂直"), ("H", "水平（平行）"), ("CW", "順時針"), ("CCW", "逆時針")]
LABELS = dict(OPTIONS)


class HandActionSelect:
    def __init__(self, size, on_start):
        w, h = size
        self.choices = {"left": "V", "right": "V"}
        self.buttons = {}
        width = min(340, (w - 100) // 2)
        height = min(60, max(30, (h - 330) // 5))
        self.headings = []
        for side, title, x in (("left", "左手", w//2-width-20), ("right", "右手", w//2+20)):
            self.headings.append((title, (x+width//2, 145)))
            for i, (action, label) in enumerate(OPTIONS):
                self.buttons[side, action] = Button((x, 175+i*(height+10), width, height), label,
                    lambda s=side, a=action: self.choose(s, a), font_size=24)
        bottom = 175 + 5*(height+10)
        self.start = Button((w//2-150, bottom+35, 300, 52), "開始測試", lambda: on_start(dict(self.choices)))
        self.note_position = (w//2, bottom+12)
        self.choose("left", "V")

    def choose(self, side, action):
        self.choices[side] = action
        for (s, a), button in self.buttons.items():
            button.selected = self.choices[s] == a
            button.label = LABELS[a]
        self.start.enabled = any(a != "N" for a in self.choices.values())

    def handle_event(self, event):
        for button in self.buttons.values():
            button.handle_event(event)
        self.start.handle_event(event)

    def draw(self, surface):
        for title, center in self.headings:
            text = get_font(28).render(title, True, COLOR_TEXT)
            surface.blit(text, text.get_rect(center=center))
        for button in self.buttons.values():
            button.draw(surface)
            box = pygame.Rect(button.rect.left+18, button.rect.centery-9, 18, 18)
            pygame.draw.rect(surface, COLOR_TEXT, box, 2)
            if button.selected:
                pygame.draw.lines(surface, COLOR_TEXT, False,
                    [(box.left+3, box.centery), (box.left+7, box.bottom-4), (box.right-3, box.top+4)], 2)
        note = "每手選一項；不使用的手不用出現在鏡頭中" if self.start.enabled else "請至少啟用一隻手"
        text = get_font(18).render(note, True, COLOR_TEXT_MUTED)
        surface.blit(text, text.get_rect(center=self.note_position))
        self.start.draw(surface)
