"""
ui/chart.py - 簡單的折線圖繪製（純 pygame 原生繪圖，不依賴外部繪圖套件）

給「帳號歷史」畫面顯示某款遊戲的分數趨勢用，之後其他畫面需要畫簡單的數值
走勢圖也可以直接重用，不用另外找繪圖套件。故意設計成跟 ui/widgets.py 一樣
不依賴 SceneManager/AppContext，只吃資料點跟畫布。
"""

import pygame

from ui.theme import get_font, COLOR_TEXT_MUTED, COLOR_ACCENT, COLOR_SUCCESS

_CHART_PAD = 28


def draw_line_chart(surface, rect, values, line_color=COLOR_ACCENT,
                     highlight_color=COLOR_SUCCESS, label_font_size=16):
    """在 rect 範圍內畫一條折線圖。values 是依時間排序（舊到新）的數字列表。

    只負責畫圖，不管資料怎麼來——呼叫端自己決定要畫哪個遊戲、哪個時間範圍的
    分數序列。資料點數 < 2 時畫不出線，只顯示文字提示，不會噴例外。
    """
    rect = pygame.Rect(rect)
    font = get_font(label_font_size)

    if len(values) < 2:
        msg = "至少要有 2 筆紀錄才能畫趨勢圖" if values else "目前還沒有紀錄"
        text = font.render(msg, True, COLOR_TEXT_MUTED)
        surface.blit(text, text.get_rect(center=rect.center))
        return

    lo, hi = min(values), max(values)
    if hi - lo < 1e-6:
        # 全部同分：畫一條置中水平線，避免除以零讓整張圖崩掉。
        lo, hi = lo - 1, hi + 1

    plot = rect.inflate(-_CHART_PAD * 2, -_CHART_PAD * 2)
    n = len(values)

    def to_px(i, v):
        x = plot.left + plot.width * i / (n - 1)
        y = plot.bottom - plot.height * (v - lo) / (hi - lo)
        return (int(x), int(y))

    points = [to_px(i, v) for i, v in enumerate(values)]

    # 軸線：只畫底線當參考，避免畫面太雜。
    pygame.draw.line(surface, COLOR_TEXT_MUTED, (plot.left, plot.bottom), (plot.right, plot.bottom), 1)

    pygame.draw.lines(surface, line_color, False, points, 3)
    for p in points:
        pygame.draw.circle(surface, line_color, p, 4)

    pygame.draw.circle(surface, highlight_color, points[values.index(max(values))], 8, width=2)

    hi_label = font.render(f"{max(values):.1f}", True, COLOR_TEXT_MUTED)
    surface.blit(hi_label, (rect.left + 4, plot.top - hi_label.get_height() // 2))
    lo_label = font.render(f"{min(values):.1f}", True, COLOR_TEXT_MUTED)
    surface.blit(lo_label, (rect.left + 4, plot.bottom - lo_label.get_height() // 2))
