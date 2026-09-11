"""Discard only an interrupted hand's unfinished motion and replay segment."""
from common import game_time


def interrupt_hand(scene, side, recognizer_factory):
    recognizer = getattr(scene, side + "_recognizer")
    if not hasattr(scene, "tracking_interruptions"):
        scene.tracking_interruptions = {"left": 0, "right": 0}
        scene.tracking_lost = {"left": False, "right": False}
    if not scene.tracking_lost[side]:
        scene.tracking_interruptions[side] += 1
    scene.tracking_lost[side] = True
    if recognizer is not None:
        replacement = recognizer_factory(scene.selected_action[side])
        replacement.completed = recognizer.completed
        setattr(scene, side + "_recognizer", replacement)
    getattr(scene, side + "_trail").clear()
    if hasattr(scene, "trail_start_times"):
        scene.trail_start_times[side] = game_time.time()
    if scene.trail_recorder is not None:
        scene.trail_recorder.discard_current(side)
