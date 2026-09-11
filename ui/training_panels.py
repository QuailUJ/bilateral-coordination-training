"""One renderer for side diagnostics in live training and recorded playback."""
import pygame
from functools import lru_cache

from common.cv_pygame import bgr_frame_to_surface
from ui.theme import COLOR_PANEL, COLOR_TEXT, COLOR_TEXT_MUTED, get_font

REASONS = {
    "tracked_by_position": "依拳頭位置延續追蹤",
    "tracked": "追蹤正常", "no_detection": "未偵測到手", "low_confidence": "左右手信心不足",
    "invalid_coordinates": "座標無效", "duplicate_label": "左右手標籤重複",
    "hands_overlap": "雙手太靠近／重疊", "need_both_hands": "請雙手分開入鏡",
    "wrist_jump": "手腕突然跳位", "identity_conflict": "位置接近另一隻手",
    "tip_jump": "指尖突然跳位", "stabilizing": "等待連續穩定影格", "camera_gap": "攝影機暫無新影像",
}


def training_layout(size):
    w, h = size
    side = min(320, max(190, int(w * 0.22)))
    left = pygame.Rect(16, 70, side - 24, h - 155)
    right = pygame.Rect(w - side + 8, 70, side - 24, h - 155)
    center = pygame.Rect(side + 8, 70, w - 2 * side - 16, h - 190)
    return left, center, right


def draw_training_view(surface, frame):
    """Keep the camera preview separate from the aspect-correct trajectory area."""
    _, area, _ = training_layout(surface.get_size())
    preview_height = max(1, min(110, area.height // 4))
    trajectory = pygame.Rect(area.left, area.top + preview_height + 12,
                             area.width, max(1, area.height - preview_height - 12))
    image_h, image_w = frame.shape[:2] if frame is not None else (480, 640)
    trajectory = pygame.Rect(0, 0, image_w, image_h).fit(trajectory)
    pygame.draw.rect(surface, COLOR_PANEL, trajectory)
    if frame is not None:
        preview = pygame.Rect(0, 0, image_w, image_h).fit(
            pygame.Rect(area.left, area.top, area.width, preview_height))
        preview.right = area.right
        surface.blit(pygame.transform.smoothscale(bgr_frame_to_surface(frame), preview.size), preview)
    return trajectory


def _number(value, digits=2):
    return "—" if value is None else f"{value:.{digits}f}"


def diagnostic_lines(frame, side):
    if not frame or side not in frame:
        return ["等待攝影機資料"]
    item = frame[side]
    if item.get("action") == "N":
        return ["此手：不使用", "不參與判定與計次", "不需要出現在鏡頭中"]
    tracking = item["tracking"]
    lines = [f"目標動作：{item['action']}",
             f"已配對：{frame['paired']} / {frame.get('target_pairs', 10)} 組",
             f"此手完成：{item['completed']} 次",
             f"等待另一手配對：{item['waiting']} 次",
             f"平均分數：{_number(frame['average_score'], 1)}",
             REASONS.get(tracking["reason"], tracking["reason"])]
    if frame.get("training_mode") == "single":
        lines[1] = f"已完成：{frame['paired']} / {frame.get('target_pairs', 10)} 組"
        lines[3] = "單手測試：無需另一手配對"
        lines[4] = "以完成組數記錄成績"
    if frame.get("score_kind") == "circle_quality":
        lines[1] = f"已完成：{frame['paired']} / {frame.get('target_pairs', 5)} 圈"
        lines[4] = f"平均圓度：{_number(frame['average_score'], 1)} 分"
    if frame.get("score_kind") == "synchronous_points":
        lines[1] = f"同步成功：{frame['paired']} 組（每組 +1 分）"
        lines[4] = f"目前分數：{frame['average_score']}／8 分過關"
        lines.append(f"剩餘：{frame['remaining_seconds']:.1f} 秒；同步容許差 0.3 秒")
    if frame.get("raw_hand_count") is not None:
        lines.append(f"模型找到：{frame['raw_hand_count']} 隻手")
    if tracking.get("confidence") is not None:
        lines.append(f"左右手分類信心：{tracking['confidence']:.2f}")
    lines.extend([f"追蹤中斷：{item['interruptions']} 次", f"判定狀態：{item['state']}"])
    if not tracking.get("accepted"):
        lines.append("未完成動作中斷，請重新準備")
    if item.get("feedback"):
        lines.append(item["feedback"])
    if item.get("half_swings") is not None:
        lines.append(f"半擺動：{item['half_swings']} / 2")
    metrics = item.get("metrics", {})
    if metrics.get("recognition") == "upper_reversal_circle":
        lines.extend(["上方反轉結算，不需回固定點",
                      f"反向確認：{_number(metrics.get('reversal'), 3)} / {metrics['reversal_on']:.3f}",
                      f"上圈接合誤差／半徑：{_number(metrics.get('closure_ratio'), 2)}"])
    if metrics.get("recognition") == "reversal":
        lines.extend([f"本段幅度：{_number(metrics.get('travel'), 3)} / {metrics['amp_on']:.3f}",
                      f"反向確認：{_number(metrics.get('reversal'), 3)} / {metrics['reversal_on']:.3f}",
                      "兩段反向算一組，不需回固定點"])
    elif "axis" in metrics:
        offset = item.get("offset_" + metrics["axis"])
        point_label = "拳心-固定基準" if item.get("tracking_point_kind") == "palm_center" else "指尖-手腕"
        lines.extend([f"{point_label}：{_number(offset, 3)}",
                      f"觸發 / 回中：{metrics['amp_on']:.3f} / {metrics['amp_off']:.3f}"])
    if "turn_threshold_deg" in metrics:
        lines.append(f"轉角：{item['turn_degrees']:.0f} / {metrics['turn_threshold_deg']:.0f}°")
    if "pip_angle" in metrics:
        lines.extend([f"中間指節：{metrics['pip_angle']:.0f}°（需 {metrics['pip_min']:.0f}°）",
                      f"末端指節：{metrics['dip_angle']:.0f}°（需 {metrics['dip_min']:.0f}°）",
                      f"指尖位移：{_number(metrics.get('primary'))} / {metrics['travel_on']:.2f}",
                      f"收回距離：{_number(metrics.get('distance'))} / {metrics['return_off']:.2f}"])
    lines.extend([f"上次耗時：{_number(item.get('last_duration'))} 秒",
                  f"上次幅度：{_number(item.get('last_peak'), 3)}",
                  f"上圈品質：{_number(item.get('last_quality'), 1)}"])
    pair = frame.get("pair_detail")
    if pair:
        lines.extend([f"上組開始差：{pair['start_diff_s']:.2f} 秒",
                      f"上組耗時差：{pair['duration_diff_s']:.2f} 秒",
                      f"上組第三項：{pair['third_score']:.1f} 分",
                      f"上組得分：{pair['score']:.1f} 分"])
    if frame.get("window_remaining") is not None:
        lines.append(f"同步視窗剩餘：{frame['window_remaining']:.1f} 秒")
    hint = {"too_close": "離攝影機太近，請後退", "too_far": "離攝影機太遠，請靠近"}.get(item.get("distance_hint", frame.get("distance_hint")))
    if hint:
        lines.append(hint)
    return lines


def _wrap(lines, font, width):
    return [part for line in lines for part in _wrap_line(line, font, width)]


@lru_cache(maxsize=2048)
def _wrap_line(line, font, width):
    if font.size(line)[0] <= width:
        return (line,)
    wrapped = []
    while line:
        low, high = 1, len(line)
        while low < high:
            mid = (low + high + 1) // 2
            if font.size(line[:mid])[0] <= width:
                low = mid
            else:
                high = mid - 1
        wrapped.append(line[:low])
        line = line[low:]
    return tuple(wrapped)


@lru_cache(maxsize=512)
def _render_text(font, text, color):
    return font.render(text, True, color)


def draw_panel(surface, rect, title, lines, color):
    pygame.draw.rect(surface, COLOR_PANEL, rect, border_radius=10)
    label = _render_text(get_font(24), title, color)
    surface.blit(label, (rect.x + 12, rect.y + 12))
    for size in range(20, 10, -1):
        font = get_font(size)
        wrapped = _wrap(lines, font, rect.width - 24)
        step = font.get_linesize() + 3
        if len(wrapped) * step <= rect.height - 58:
            break
    for i, text in enumerate(wrapped):
        label = _render_text(font, text, COLOR_TEXT if i < 6 else COLOR_TEXT_MUTED)
        surface.blit(label, (rect.x + 12, rect.y + 48 + i * step))


def draw_training_panels(surface, frame):
    left, _, right = training_layout(surface.get_size())
    draw_panel(surface, left, "左手判定", diagnostic_lines(frame, "left"), (90, 200, 230))
    draw_panel(surface, right, "右手判定", diagnostic_lines(frame, "right"), (240, 150, 60))
