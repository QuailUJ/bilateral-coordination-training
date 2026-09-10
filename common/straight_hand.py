"""Shared four-finger posture checks for the saber and triangle games.

Initial camera heuristics, adjustable after player testing. MCP flexion is
allowed; bending either interphalangeal joint invalidates the whole hand.
"""
import math

STRAIGHT_MIN_DEG = 155.0
MCP_PRESS_MAX_DEG = 135.0
MCP_SYNC_SPREAD_DEG = 25.0
HAND_SYNC_SECONDS = 0.30


def angle(a, b, c):
    u = tuple(x-y for x, y in zip(a, b))
    v = tuple(x-y for x, y in zip(c, b))
    magnitude = math.sqrt(sum(x*x for x in u) * sum(x*x for x in v))
    if magnitude < 1e-8:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x*y for x, y in zip(u, v))/magnitude))))


def hand_posture(landmarks, aspect=1.0):
    if not landmarks or len(landmarks) != 21:
        return {"valid": False, "pressed": False, "reason": "未偵測到完整手部"}
    points = [(p.x*aspect, p.y, getattr(p, "z", 0.0)*aspect) for p in landmarks]
    if not all(math.isfinite(v) for p in points for v in p):
        return {"valid": False, "pressed": False, "reason": "手部座標無效"}
    pip = [angle(points[i], points[i+1], points[i+2]) for i in (5, 9, 13, 17)]
    dip = [angle(points[i+1], points[i+2], points[i+3]) for i in (5, 9, 13, 17)]
    mcp = [angle(points[0], points[i], points[i+1]) for i in (5, 9, 13, 17)]
    straight = min(pip + dip) >= STRAIGHT_MIN_DEG
    synchronous = max(mcp)-min(mcp) <= MCP_SYNC_SPREAD_DEG
    valid = straight and synchronous
    return {"valid": valid, "pressed": valid and max(mcp) <= MCP_PRESS_MAX_DEG,
            "reason": "正常" if valid else "四指需伸直且同步彎動掌指關節",
            "pip": pip, "dip": dip, "mcp": mcp}
