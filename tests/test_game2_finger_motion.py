import copy
import math
from types import SimpleNamespace as NS

import pytest

from games.game2_finger_vertical.motion import FingerExtensionRecognition


def landmarks(extended=False, horizontal=False):
    points = [NS(x=0.5, y=0.7, z=0.0) for _ in range(21)]
    for base, x in ((5, 0.46), (9, 0.5), (13, 0.54), (17, 0.58)):
        coords = [(x, 0.55), (x, 0.48), (x + 0.04, 0.52), (x + 0.03, 0.56)]
        if base == 5 and extended:
            coords = [(x, 0.55), (x, 0.48), (x, 0.42), (x, 0.36)]
        for i, (px, py) in enumerate(coords):
            points[base+i] = NS(x=px, y=py, z=0.0)
    if horizontal:
        for point in points:
            dx, dy = point.x - 0.5, point.y - 0.7
            point.x, point.y = 0.5 - dy, 0.7 + dx
    return points


def feed(recognizer, pose, now, frames=4):
    for _ in range(frames):
        recognizer.update_landmarks(now, pose)
        now += 0.1
    return now


@pytest.mark.parametrize("action", ["H", "V"])
def test_fist_extend_return_counts_one_and_ten_reps(action):
    recognizer = FingerExtensionRecognition(action)
    closed = landmarks(horizontal=action == "H")
    opened = landmarks(True, horizontal=action == "H")
    now = 0.0
    for rep in range(10):
        now = feed(recognizer, closed, now)
        now = feed(recognizer, opened, now)
        assert recognizer.completed == rep  # Must return to the fist.
        now = feed(recognizer, closed, now)
        assert recognizer.completed == rep + 1
        assert recognizer.last_rep_duration > 0
        assert recognizer.last_rep_peak >= 0.65


def test_extended_finger_without_initial_fist_cannot_count():
    recognizer = FingerExtensionRecognition("V")
    feed(recognizer, landmarks(True), 0, frames=30)
    assert recognizer.completed == 0
    assert recognizer.state == "await_fist"


def test_wrong_direction_does_not_count():
    recognizer = FingerExtensionRecognition("V")
    closed = landmarks(horizontal=True)
    now = feed(recognizer, closed, 0)
    now = feed(recognizer, landmarks(True, horizontal=True), now)
    feed(recognizer, closed, now)
    assert recognizer.completed == 0


def test_whole_hand_translation_does_not_count():
    recognizer = FingerExtensionRecognition("V")
    closed = landmarks()
    moved = copy.deepcopy(closed)
    for p in moved:
        p.y -= 0.25
    now = feed(recognizer, closed, 0)
    now = feed(recognizer, moved, now)
    feed(recognizer, closed, now)
    assert recognizer.completed == 0


def test_mcp_only_rotation_does_not_count():
    recognizer = FingerExtensionRecognition("V")
    closed = landmarks()
    moved = copy.deepcopy(closed)
    pivot = moved[5]
    angle = math.radians(90)
    for p in moved[6:9]:
        x, y = p.x - pivot.x, p.y - pivot.y
        p.x = pivot.x + x * math.cos(angle) - y * math.sin(angle)
        p.y = pivot.y + x * math.sin(angle) + y * math.cos(angle)
    now = feed(recognizer, closed, 0)
    now = feed(recognizer, moved, now)
    feed(recognizer, closed, now)
    assert recognizer.completed == 0


def test_tip_displacement_with_still_bent_joints_does_not_count():
    recognizer = FingerExtensionRecognition("V")
    closed = landmarks()
    moved = copy.deepcopy(closed)
    for p in moved[5:9]:
        p.y -= 0.25
    now = feed(recognizer, closed, 0)
    now = feed(recognizer, moved, now)
    feed(recognizer, closed, now)
    assert recognizer.completed == 0


def test_open_other_fingers_invalidates_extension():
    recognizer = FingerExtensionRecognition("V")
    opened = landmarks(True)
    for i, y in zip((10, 11, 12), (0.48, 0.42, 0.36)):
        opened[i] = NS(x=0.5, y=y, z=0.0)
    now = feed(recognizer, landmarks(), 0)
    now = feed(recognizer, opened, now)
    feed(recognizer, landmarks(), now)
    assert recognizer.completed == 0


def test_single_frame_extension_noise_does_not_count():
    recognizer = FingerExtensionRecognition("V")
    now = feed(recognizer, landmarks(), 0)
    now = feed(recognizer, landmarks(True), now, frames=1)
    feed(recognizer, landmarks(), now)
    assert recognizer.completed == 0


def test_hand_size_scaling_preserves_count():
    recognizer = FingerExtensionRecognition("V")
    poses = [landmarks(), landmarks(True), landmarks()]
    now = 0
    for pose in poses:
        for p in pose:
            p.x = 0.5 + (p.x - 0.5) * 0.6
            p.y = 0.7 + (p.y - 0.7) * 0.6
        now = feed(recognizer, pose, now)
    assert recognizer.completed == 1


def test_dip_must_extend_even_when_pip_and_tip_move():
    recognizer = FingerExtensionRecognition("V")
    opened = landmarks(True)
    opened[8] = NS(x=0.50, y=0.40, z=0.0)
    now = feed(recognizer, landmarks(), 0)
    now = feed(recognizer, opened, now)
    feed(recognizer, landmarks(), now)
    assert recognizer.completed == 0


def test_tiny_tip_displacement_with_straight_joints_does_not_count():
    recognizer = FingerExtensionRecognition("V")
    opened = landmarks(True)
    for i, y in zip((6, 7, 8), (0.54, 0.53, 0.52)):
        opened[i] = NS(x=0.46, y=y, z=0.0)
    now = feed(recognizer, landmarks(), 0)
    now = feed(recognizer, opened, now)
    feed(recognizer, landmarks(), now)
    assert recognizer.completed == 0
