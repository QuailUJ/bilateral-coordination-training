import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from common import camera_hand_tracker as tracking


class Camera:
    cap = True

    def __init__(self, value):
        self.frame = np.full((8, 8, 3), value, np.uint8)

    def get_next(self, previous, timeout):
        if previous == 1:
            threading.Event().wait(min(timeout, .01))
            return None, previous, 0
        return self.frame, 1, 2


def wait_packet(tracker, camera, previous=-1):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        packet = tracker.get_next(camera, previous)
        if packet[0] is not None:
            return packet
        threading.Event().wait(.005)
    pytest.fail('No inference result')


def test_background_inference_keeps_ui_free_and_pairs_frame_with_result(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    timestamps = []

    def detect(image, timestamp):
        timestamps.append(timestamp)
        entered.set()
        assert release.wait(2)
        return int(image.numpy_view()[0, 0, 0])

    detector = SimpleNamespace(detect_for_video=detect, close=lambda: None)
    monkeypatch.setattr(tracking, 'create_hand_landmarker', lambda **kw: detector)
    with tracking.GameHandLandmarker('unused') as tracker:
        camera = Camera(25)
        assert tracker.get_next(camera, -1)[0] is None
        assert entered.wait(2)
        try:
            # Inference is deliberately blocked: polling must still return.
            for _ in range(10):
                assert tracker.get_next(camera, -1)[0] is None
        finally:
            release.set()
        frame, ident, _, result = wait_packet(tracker, camera)
        assert result == int(frame[0, 0, 0]) == 25
        assert tracker.get_next(camera, ident)[0] is None
        frame, _, _, result = wait_packet(tracker, Camera(90))
        assert result == int(frame[0, 0, 0]) == 90
    assert timestamps == sorted(set(timestamps))
    assert not tracker._thread.is_alive()


def test_camera_switch_discards_inflight_old_camera_result(monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def detect(image, timestamp):
        value = int(image.numpy_view()[0, 0, 0])
        if value == 10:
            entered.set()
            assert release.wait(2)
        return value

    monkeypatch.setattr(tracking, 'create_hand_landmarker', lambda **kw:
        SimpleNamespace(detect_for_video=detect, close=lambda: None))
    with tracking.GameHandLandmarker('unused') as tracker:
        tracker.get_next(Camera(10), -1)
        assert entered.wait(2)
        camera = Camera(20)
        try:
            assert tracker.get_next(camera, 1)[0] is None
        finally:
            release.set()
        assert wait_packet(tracker, camera)[3] == 20


def test_worker_error_is_reported_instead_of_silently_freezing(monkeypatch):
    def detect(*args):
        raise ValueError('bad inference')
    monkeypatch.setattr(tracking, 'create_hand_landmarker', lambda **kw:
        SimpleNamespace(detect_for_video=detect, close=lambda: None))
    with tracking.GameHandLandmarker('unused') as tracker:
        with pytest.raises(RuntimeError, match='背景辨識'):
            wait_packet(tracker, Camera(0))
