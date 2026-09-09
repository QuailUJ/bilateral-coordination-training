"""Shared volume for cached and newly loaded game sounds."""
import pygame

_volume = 1.0
_sounds = []


def set_volume(value):
    global _volume
    _volume = max(0.0, min(1.0, value))
    for sound in _sounds:
        sound.set_volume(_volume)
    if pygame.mixer.get_init():
        pygame.mixer.music.set_volume(_volume)


def load_sound(path):
    if not pygame.mixer.get_init():
        return None
    sound = pygame.mixer.Sound(path)
    sound.set_volume(_volume)
    _sounds.append(sound)
    return sound
