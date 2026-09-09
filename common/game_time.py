"""Gameplay clock: time spent in settings does not consume training time."""
import time as _clock

_offset = 0.0
_paused_at = None


def time():
    return (_paused_at if _paused_at is not None else _clock.time()) - _offset


def pause():
    global _paused_at
    if _paused_at is None:
        _paused_at = _clock.time()


def resume():
    global _paused_at, _offset
    if _paused_at is not None:
        _offset += _clock.time() - _paused_at
        _paused_at = None
