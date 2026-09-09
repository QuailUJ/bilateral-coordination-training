"""Device-wide settings, saved atomically beside the application."""
import json
import os
import sys

from common.paths import resource_path


def settings_path():
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "data", "settings.json")
    return resource_path("data/settings.json")


def load_settings(path=None):
    defaults = {"camera_index": 0, "volume": 1.0}
    try:
        with open(path or settings_path(), encoding="utf-8") as file:
            data = json.load(file)
        index, volume = data.get("camera_index"), data.get("volume")
        if type(index) is int and index >= 0:
            defaults["camera_index"] = index
        if type(volume) in (int, float) and 0 <= volume <= 1:
            defaults["volume"] = volume
    except (OSError, ValueError, AttributeError):
        pass
    return defaults


def save_settings(camera_index, volume, path=None):
    path = path or settings_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as file:
        json.dump({"camera_index": camera_index, "volume": volume}, file)
        file.flush()
        os.fsync(file.fileno())
    os.replace(path + ".tmp", path)
