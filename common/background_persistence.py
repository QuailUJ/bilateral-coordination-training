"""Serialized background IO; pygame and camera updates remain on the UI thread."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from data_store import user_store


class BackgroundPersistence:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="game-storage")

    def login(self, username):
        base = user_store._default_base_dir()
        def load():
            data = user_store.create_or_load_user(username, base)
            if not os.path.exists(user_store.user_file_path(username, base)):
                user_store.save_user(data, base)
            return username.strip()
        return self.executor.submit(load)

    def save_result(self, username, game_id, score, details, record_id=None):
        base = user_store._default_base_dir()
        return self.executor.submit(user_store.append_history_record, username, game_id, score, details, base, record_id)

    def close(self):
        self.executor.shutdown(wait=True)


def begin_result_save(scene, ctx, game_id, score, details):
    service = getattr(ctx, "persistence", None)
    if service is None:
        user_store.append_history_record(ctx.current_user, game_id, score, details)
        scene.state = "result"
        return
    scene.state = "settling"
    scene.save_error = ""
    # Recording is now stopped. Details only reference the completed session;
    # live camera frames are separate and remain free to update.
    scene._save_payload = (ctx.current_user, game_id, score, details, str(uuid.uuid4()))
    scene._save_future = service.save_result(*scene._save_payload)


def poll_result_save(scene):
    future = getattr(scene, "_save_future", None)
    if future is None or not future.done():
        return
    scene._save_future = None
    try:
        future.result()
    except Exception as error:
        scene.save_error = str(error)
    else:
        scene.state = "result"
        scene._save_payload = None


def draw_save_status(scene, surface):
    import pygame
    from ui.theme import get_font, COLOR_PANEL, COLOR_TEXT
    error = getattr(scene, "save_error", "")
    text = "存檔失敗，按 R 重試：" + error if error else "正在整理與保存結果，攝影機持續更新…"
    rect = pygame.Rect(20, surface.get_height()-125, surface.get_width()-40, 48)
    pygame.draw.rect(surface, COLOR_PANEL, rect, border_radius=8)
    font = get_font(22)
    while font.size(text)[0] > rect.width-20 and len(text) > 20:
        text = text[:-2]
    rendered = font.render(text, True, COLOR_TEXT)
    surface.blit(rendered, rendered.get_rect(center=rect.center))
