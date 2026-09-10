"""
scenes/history_scene.py - 歷史成績畫面

可以用遊戲篩選（全部 / 單一遊戲），並且在「歷史新高」跟「全部成績」兩種檢視
模式之間切換：
    - 全部成績：依時間新到舊列出紀錄（篩選單一遊戲時只列該遊戲）。
    - 歷史新高：篩選單一遊戲時顯示該遊戲目前最高分；選「全部」時列出每款
      遊戲各自的最高分（自己跟自己比的排行榜）。
篩選到單一遊戲時，上方會多畫一張分數走勢折線圖（ui/chart.py），只有選到單一
遊戲時折線圖才有意義——不同遊戲的分數尺度/難度不一樣，混在一起畫不出有用的
趨勢。遊戲名稱一樣透過 games.registry 對照 game_id 顯示成中文，對照不到的
game_id（例如遊戲已下架）就 fallback 顯示原始 id，維持既有的容錯設計。

【2026-09-09 加上軌跡回放】只有 details 裡有 "reps" 欄位的紀錄（目前只有
遊戲零/遊戲一的「雙手都是水平垂直」或「雙手都是畫圓」組合，見兩邊
scoring.py::RepTrailRecorder）才有回放資料，這種紀錄前面會加一個「▶」，
點選紀錄後可選擇回放或刪除，沒有回放資料的紀錄仍可刪除。
"""

import pygame

from common.scene_manager import Scene, Transition
from data_store import user_store
from games.registry import GAMES, get_game
from scenes.replay_scene import ReplayScene
from ui.chart import draw_line_chart
from ui.theme import get_font, COLOR_BG, COLOR_TEXT, COLOR_TEXT_MUTED, PADDING
from ui.widgets import Button, ScrollList

ALL_GAMES_FILTER = "__all__"


def _display_name(game_id: str) -> str:
    try:
        return get_game(game_id).display_name
    except KeyError:
        return game_id


def _replay_payload(record):
    """回傳這筆紀錄能不能回放：有 details.reps 就回傳這筆紀錄本身(給
    ReplayScene 用)，沒有就回傳 None（停用回放按鈕）。"""
    details = record.get("details") or {}
    if details.get("reps") or (details.get("analysis") or {}).get("frames") or (details.get("arcade_replay") or {}).get("frames"):
        return record
    return None


class HistoryScene(Scene):
    CONTENT_TOP = 220
    CHART_HEIGHT = 200

    def on_enter(self, ctx, **kwargs):
        if kwargs.get("resumed"):
            self._reload(ctx)
            return
        w, h = ctx.screen.get_size()

        self.filter_game_id = ALL_GAMES_FILTER
        self.view_mode = "all_scores"  # "all_scores" | "best_scores"
        self._transition = None
        self.selected_record = None
        self.confirm_delete = False
        self.message = ""
        self.action_buttons = [
            Button((w // 2 - 300, h // 2 + 60, 180, 48), "回放軌跡", self._replay, font_size=22),
            Button((w // 2 - 90, h // 2 + 60, 180, 48), "刪除此筆", lambda: self._delete(ctx), font_size=22),
            Button((w // 2 + 120, h // 2 + 60, 180, 48), "取消", self._cancel_selection, font_size=22),
        ]

        self.back_button = Button((PADDING, h - PADDING - 56, 200, 56), "返回主選單", on_click=self._go_back)

        filter_ids = [ALL_GAMES_FILTER] + [g.game_id for g in GAMES]
        filter_labels = ["全部"] + [g.display_name for g in GAMES]
        self.filter_buttons = self._build_button_row(
            60, 100, filter_ids, filter_labels, self._on_filter_selected, font_size=18, btn_width=(w - 140) // len(filter_ids))

        self.mode_buttons = self._build_button_row(
            60, 156, ["best_scores", "all_scores"], ["最高／最近", "全部成績"],
            self._on_mode_selected, font_size=22, btn_width=180)

        self.list_view = ScrollList((PADDING, self.CONTENT_TOP, w - PADDING * 2, 1),
                                     on_select=self._on_record_selected)
        self._reload(ctx)

    def _on_record_selected(self, record):
        self.selected_record = record
        self.confirm_delete = False
        self.message = ""
        self.action_buttons[0].enabled = _replay_payload(record) is not None
        self.action_buttons[1].enabled = bool(record.get("record_id"))
        self.action_buttons[1].label = "刪除此筆"

    def _cancel_selection(self):
        self.selected_record = None
        self.confirm_delete = False

    def _replay(self):
        record = self.selected_record
        self._cancel_selection()
        self._transition = Transition("push", scene=ReplayScene(), kwargs={"record": record})

    def _delete(self, ctx):
        if not self.confirm_delete:
            self.confirm_delete = True
            self.action_buttons[0].enabled = False
            self.action_buttons[1].label = "確認刪除"
            return
        try:
            deleted = user_store.delete_history_record(ctx.current_user, self.selected_record["record_id"])
        except OSError:
            self.message = "刪除失敗，請確認資料夾可寫入後再試。"
            return
        self._cancel_selection()
        self.message = "已刪除紀錄" if deleted else "此筆紀錄已不存在"
        self._reload(ctx)

    @staticmethod
    def _build_button_row(x, y, ids, labels, on_select, font_size=20, btn_width=200, height=40, gap=10):
        buttons = []
        for i, (item_id, label) in enumerate(zip(ids, labels)):
            rect = (x + i * (btn_width + gap), y, btn_width, height)
            buttons.append((item_id, Button(rect, label, on_click=lambda iid=item_id: on_select(iid),
                                             font_size=font_size)))
        return buttons

    def _on_filter_selected(self, game_id):
        self.filter_game_id = game_id
        self._reload_pending = True

    def _on_mode_selected(self, mode):
        self.view_mode = mode
        self._reload_pending = True

    def _reload(self, ctx):
        self._reload_pending = False
        user_data = user_store.create_or_load_user(ctx.current_user)
        history = user_data.get("history", [])

        self._layout_list(ctx)

        if self.filter_game_id == ALL_GAMES_FILTER:
            self.chart_values = None
            if self.view_mode == "best_scores":
                rows, payload = self._best_per_game_rows(history)
            else:
                newest_first = sorted(history, key=lambda r: r.get("timestamp", ""), reverse=True)
                rows, payload = self._all_records_rows(newest_first)
        else:
            records = [r for r in history if r.get("game_id") == self.filter_game_id]
            records.sort(key=lambda r: r.get("timestamp", ""))
            self.chart_values = [r["score"] for r in records]

            if self.view_mode == "best_scores":
                rows, payload = self._best_single_game_rows(records)
            else:
                rows, payload = self._all_records_rows(list(reversed(records)))
        self.list_view.set_items(rows, records=payload)

    def _layout_list(self, ctx):
        w, h = ctx.screen.get_size()
        content_top = self.CONTENT_TOP
        if self.filter_game_id != ALL_GAMES_FILTER:
            content_top += self.CHART_HEIGHT + PADDING  # 幫折線圖留位置
        self.list_view.rect.update(PADDING, content_top, w - PADDING * 2,
                                    h - content_top - 56 - PADDING * 2)

    def _best_per_game_rows(self, history):
        by_game = {}
        for record in history:
            by_game.setdefault(record.get("game_id"), []).append(record)
        rows, payload = [], []
        for gid, records in sorted(by_game.items(), key=lambda item: _display_name(item[0])):
            game_rows, game_payload = self._best_single_game_rows(records)
            rows.extend((f"{_display_name(gid)}　{first}", second) for first, second in game_rows)
            payload.extend(game_payload)
        return rows, payload

    def _best_single_game_rows(self, records):
        groups = {}
        for record in records:
            details = record.get("details") or {}
            key = (details.get("level_id", "未分類"), details.get("rule_version", "舊版"))
            groups.setdefault(key, []).append(record)
        rows, payload = [], []
        for (level, version), group in sorted(groups.items()):
            best = max(group, key=lambda r: r["score"])
            latest = max(group, key=lambda r: r.get("timestamp", ""))
            label = (latest.get("details") or {}).get("action_label", level)
            def result(record):
                return f"{record['score']}（{'過關' if (record.get('details') or {}).get('passed') else '未過關'}）"
            rows.append((self._row_line1(best, f"{label}　最高 {result(best)}"),
                         f"最近 {result(latest)}　規則：{version}"))
            payload.append(best)
        return rows, payload

    def _all_records_rows(self, records):
        rows, payload = [], []
        for r in records:
            details = r.get("details") or {}
            result = f"完成：{r['score']} 組" if details.get("training_mode") == "single" else f"分數：{r['score']}"
            line1 = self._row_line1(r, f"{_display_name(r['game_id'])}　{result}")
            rows.append((line1, r.get("timestamp", "") + "　" + details.get("action_label", "")))
            payload.append(r)
        return rows, payload

    @staticmethod
    def _row_line1(record, text):
        return f"▶ {text}" if _replay_payload(record) is not None else text

    def _go_back(self):
        self._transition = Transition("pop")

    def handle_event(self, ctx, event):
        if self.selected_record is not None:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._cancel_selection()
                return None
            for button in self.action_buttons:
                if button.handle_event(event):
                    break
            return None
        if event.type == pygame.QUIT:
            pygame.quit()
            raise SystemExit
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._go_back()
        self.back_button.handle_event(event)
        for _, btn in self.filter_buttons:
            btn.handle_event(event)
        for _, btn in self.mode_buttons:
            btn.handle_event(event)
        self.list_view.handle_event(event)
        return None

    def update(self, ctx, dt):
        if self._reload_pending:
            self._reload(ctx)
        if self._transition is not None:
            t, self._transition = self._transition, None
            return t
        return None

    def draw(self, ctx, surface):
        surface.fill(COLOR_BG)
        w, _ = surface.get_size()
        title_font = get_font(36)
        title = title_font.render(f"{ctx.current_user} 的歷史成績", True, COLOR_TEXT)
        surface.blit(title, title.get_rect(centerx=w // 2, top=40))

        for item_id, btn in self.filter_buttons:
            btn.selected = (item_id == self.filter_game_id)
            btn.draw(surface)
        for item_id, btn in self.mode_buttons:
            btn.selected = (item_id == self.view_mode)
            btn.draw(surface)

        if self.chart_values is not None:
            chart_rect = (PADDING, self.CONTENT_TOP, w - PADDING * 2, self.CHART_HEIGHT)
            draw_line_chart(surface, chart_rect, self.chart_values)
            hint_font = get_font(16)
            hint = hint_font.render(
                f"{_display_name(self.filter_game_id)}　共 {len(self.chart_values)} 筆紀錄的分數走勢",
                True, COLOR_TEXT_MUTED)
            surface.blit(hint, (PADDING, self.CONTENT_TOP - 22))

        self.list_view.draw(surface)
        self.back_button.draw(surface)
        hint = get_font(18).render(self.message or "點選任一紀錄，可回放或刪除", True, COLOR_TEXT_MUTED)
        surface.blit(hint, (240, surface.get_height() - 50))
        if self.selected_record is not None:
            self._draw_record_actions(surface)

    def _draw_record_actions(self, surface):
        w, h = surface.get_size()
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 190))
        surface.blit(shade, (0, 0))
        pygame.draw.rect(surface, COLOR_BG, (w // 2 - 340, h // 2 - 140, 680, 280), border_radius=16)
        record = self.selected_record
        lines = [
            "確定刪除此筆紀錄？" if self.confirm_delete else "紀錄操作",
            f"{_display_name(record['game_id'])}　分數：{record['score']}",
            record.get("timestamp", ""),
            self.message or ("刪除後無法復原，成績走勢與歷史新高會重新計算。" if self.confirm_delete else "請選擇回放或刪除這筆紀錄。"),
        ]
        for i, text in enumerate(lines):
            label = get_font(26 if i == 0 else 20).render(text, True, COLOR_TEXT)
            surface.blit(label, label.get_rect(centerx=w // 2, top=h // 2 - 115 + i * 38))
        for button in self.action_buttons:
            button.draw(surface)
