"""Record actual arena states and score transitions, never re-simulate randomness."""
import math


class ArcadeRecording:
    def __init__(self, game_id, start, size, level):
        self.start = start
        self.width, self.height = size
        self.next_id = 1
        self.data = {"version": 1, "game_id": game_id, "frame_size": list(size),
                     "level": dict(level), "frames": [], "events": []}

    def point(self, x, y):
        return [round(x/self.width, 5), round(y/self.height, 5)]

    def object_id(self, obj):
        if not hasattr(obj, "replay_id"):
            obj.replay_id = self.next_id
            self.next_id += 1
        return obj.replay_id

    def event(self, now, reason, obj, position, before, after, side=None, **extra):
        self.data["events"].append({"t": round(max(0, now-self.start), 5), "reason": reason,
            "object_id": self.object_id(obj), "position": position, "side": side,
            "score_before": before, "score_after": after, "delta": after-before, **extra})

    def frame(self, now, **state):
        self.data["frames"].append({"t": round(max(0, now-self.start), 5), **state})


def record_sabers(scene, now):
    recorder = scene.arcade_recording
    swords = []
    for hand, sword in (("right", scene.left_sword), ("left", scene.right_sword)):
        angle = math.radians(sword.angle_deg)
        swords.append({"hand": hand, "angle": sword.angle_deg, "active": sword.active,
            "color": list(sword.color), "start": recorder.point(*sword.pivot),
            "end": recorder.point(sword.pivot[0]+sword.length*math.cos(angle), sword.pivot[1]-sword.length*math.sin(angle))})
    recorder.frame(now, score=scene.score, hits=scene.hits, misses=scene.misses,
        hands={"left": scene.left_landmarks is not None, "right": scene.right_landmarks is not None},
        postures=getattr(scene, "hand_postures", {}), swords=swords, objects=[{"id": recorder.object_id(obj), "position": recorder.point(*obj.rect.center),
            "broken": obj.broken, "shape": "circle", "color": getattr(obj, "color", "blue")} for obj in scene.marbles])


def record_triangles(scene, now):
    from games.game4_bilateral_press import config as cfg
    recorder = scene.arcade_recording
    recorder.frame(now, score=scene.combo_state.score, combo=scene.combo_state.combo,
        max_combo=scene.combo_state.max_combo, postures=getattr(scene, "hand_postures", {}),
        hands={"left": scene.left_landmarks is not None, "right": scene.right_landmarks is not None},
        presses={"left": getattr(scene, "left_press_confirmed", False), "right": getattr(scene, "right_press_confirmed", False)},
        paddles={"left": [0.5-cfg.PADDLE_OFFSET_RATIO, cfg.SPAWN_Y_RATIO], "right": [0.5+cfg.PADDLE_OFFSET_RATIO, cfg.SPAWN_Y_RATIO]},
        objects=[{"id": recorder.object_id(obj), "position": recorder.point(scene._triangle_x(obj, recorder.width), recorder.height*cfg.SPAWN_Y_RATIO),
                  "color": obj.color, "side": obj.side, "pair_id": getattr(obj, "pair_id", None)} for obj in scene.triangles if not obj.resolved])
