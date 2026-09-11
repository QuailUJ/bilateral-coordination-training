"""Render saved arcade states and mark exact scoring locations."""
import math
import pygame
from ui.theme import COLOR_PANEL, COLOR_TEXT, COLOR_TEXT_MUTED, get_font
from ui.training_panels import training_layout, draw_panel


def draw_arcade_replay(replay, surface):
    frame = replay.frames[replay._current_frame_index()]
    left, _, right = training_layout(surface.get_size())
    lines = [f"時間：{replay.playback_t:.2f} 秒", f"分數：{frame['score']}"]
    for key, label in (("hits", "命中"), ("misses", "漏接"), ("combo", "連擊"), ("max_combo", "最高連擊")):
        if key in frame:
            lines.append(f"{label}：{frame[key]}")
    for side, label in (("left", "左手"), ("right", "右手")):
        lines.append(label + ("：偵測到" if frame['hands'][side] else "：未偵測到"))
        if "presses" in frame:
            lines.append(label + ("：按壓" if frame['presses'][side] else "：未按壓"))
    for side, posture in frame.get("postures", {}).items():
        lines.append(("左手：" if side == "left" else "右手：") + posture["reason"])
    for sword in frame.get("swords", []):
        label = "左手" if sword["hand"] == "left" else "右手"
        lines.append(f"{label}光劍：{sword['angle']:.1f}° / {'有效' if sword['active'] else '無效'}")
    lines.extend(["右欄列出全部加扣分事件", "點事件可跳至發生時刻", "圓圈標示事件位置", "畫面重建，不含攝影機影片"])
    draw_panel(surface, left, "遊戲狀態", lines, (90, 200, 230))
    pygame.draw.rect(surface, COLOR_PANEL, right, border_radius=10)
    label = get_font(22).render("加扣分與判定事件", True, COLOR_TEXT)
    surface.blit(label, (right.x+10, right.y+10))
    replay.event_list.draw(surface)
    label = get_font(18).render(f"{replay.playback_t:.2f} 秒　分數 {frame['score']}　右欄可捲動、點選", True, COLOR_TEXT)
    surface.blit(label, label.get_rect(centerx=replay.canvas_rect.centerx, top=85))
    pygame.draw.rect(surface, COLOR_PANEL, replay.canvas_rect, border_radius=10)
    clip = surface.get_clip()
    surface.set_clip(replay.canvas_rect)
    for sword in frame.get("swords", []):
        color = sword.get("color", (90, 170, 255) if sword["hand"] == "right" else (255, 140, 90))
        if not sword["active"]:
            color = (100, 100, 110)
        pygame.draw.line(surface, color, replay._to_canvas_px(sword["start"]), replay._to_canvas_px(sword["end"]), 8)
    for side, point in frame.get("paddles", {}).items():
        x, y = replay._to_canvas_px(point)
        color = (90, 200, 230) if side == "left" else (240, 150, 60)
        posture = frame.get("postures", {}).get(side, {})
        if "paddle_angle" in posture:
            angle = math.radians(posture["paddle_angle"])
            direction = 1 if side == "left" else -1
            pygame.draw.rect(surface, (180, 180, 180), (x-7, y, 14, 28))
            if not posture.get("valid", False):
                color = (100, 100, 110)
            pygame.draw.line(surface, color, (x, y),
                (x + direction*math.sin(angle)*28, y-math.cos(angle)*28), 14)
        else:
            pygame.draw.rect(surface, color, (x-7, y-28, 14, 56))
        if frame["presses"][side]:
            pygame.draw.circle(surface, COLOR_TEXT, (x, y), 23, width=2)
    for obj in frame["objects"]:
        x, y = replay._to_canvas_px(obj["position"])
        if obj.get("shape") == "circle":
            color = (90, 170, 255) if obj["color"] == "blue" else (255, 140, 90)
            pygame.draw.circle(surface, (150,150,150) if obj['broken'] else color, (x,y), 10)
        elif "color" in obj:
            color = (80, 150, 240) if obj['color'] == 'blue' else (220, 90, 90)
            pygame.draw.polygon(surface, color, [(x,y-12), (x-12,y+12), (x+12,y+12)])
        else:
            pygame.draw.circle(surface, (150,150,150) if obj['broken'] else (250,210,90), (x,y), 10)
    for event in replay.analysis["events"]:
        if 0 <= replay.playback_t-event["t"] <= 0.8:
            x, y = replay._to_canvas_px(event["position"])
            color = (90, 220, 120) if event['delta'] > 0 else (250,90,90) if event['delta'] < 0 else (240,190,70)
            pygame.draw.circle(surface, color, (x,y), 24, width=3)
            text = get_font(18).render(f"{event['delta']:+g} {event['reason']}", True, color)
            rect = text.get_rect(centerx=x, bottom=y-28)
            rect.clamp_ip(replay.canvas_rect)
            surface.blit(text, rect)
    surface.set_clip(clip)
