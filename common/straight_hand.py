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


def hand_posture(landmarks, aspect=1.0, *, straight_min=STRAIGHT_MIN_DEG,
                 press_max=MCP_PRESS_MAX_DEG, sync_spread=MCP_SYNC_SPREAD_DEG):
    if not landmarks or len(landmarks) != 21:
        return {"valid": False, "pressed": False, "reason": "未偵測到完整手部"}
    points = [(p.x*aspect, p.y, getattr(p, "z", 0.0)*aspect) for p in landmarks]
    if not all(math.isfinite(v) for p in points for v in p):
        return {"valid": False, "pressed": False, "reason": "手部座標無效"}
    palm_back = tuple(a-b for a, b in zip(points[0], points[9]))
    if sum(v*v for v in palm_back) < 1e-8:
        return {"valid": False, "pressed": False, "reason": "請讓完整手掌入鏡"}
    pip = [angle(points[i], points[i+1], points[i+2]) for i in (5, 9, 13, 17)]
    dip = [angle(points[i+1], points[i+2], points[i+3]) for i in (5, 9, 13, 17)]
    # Use one palm direction: wrist-to-knuckle diagonals differ naturally
    # between fingers and must not be mistaken for asynchronous flexion.
    mcp = [angle(palm_back, (0, 0, 0), tuple(b-a for a, b in zip(points[i], points[i+1])))
           for i in (5, 9, 13, 17)]
    straight = min(pip + dip) >= straight_min
    synchronous = max(mcp)-min(mcp) <= sync_spread
    valid = straight and synchronous
    return {"valid": valid, "pressed": valid and max(mcp) <= press_max,
            "reason": ("正常" if valid else "手指中段與指尖需保持伸直" if not straight
                       else "四指請從手掌相接處一起彎動"),
            "pip": pip, "dip": dip, "mcp": mcp, "angle_reference": "common_palm_direction"}
