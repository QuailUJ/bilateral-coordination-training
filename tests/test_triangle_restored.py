from types import SimpleNamespace
import itertools
import numpy as np
import pygame
import pytest

from test_settings_and_history import ctx
from games.game4_bilateral_press import scene as module


def hand(bent):
    points = [SimpleNamespace(x=.5, y=.8, z=0) for _ in range(21)]
    for base, x, down in zip((5, 9, 13, 17), (.35, .45, .55, .65), bent):
        points[base] = SimpleNamespace(x=x, y=.6, z=0)
        points[base+1] = SimpleNamespace(x=x, y=.4, z=0)
        points[base+2] = SimpleNamespace(x=x+.05 if down else x, y=.35, z=0)
        points[base+3] = SimpleNamespace(x=x+.1 if down else x, y=.4 if down else .2, z=0)
    return points


@pytest.mark.parametrize('bent', list(itertools.product((False, True), repeat=4)))
def test_only_all_four_fingers_trigger_press(bent):
    assert module._is_hand_pressed(hand(bent)) == all(bent)


def test_missing_and_invalid_hand_do_not_press():
    assert not module._is_hand_pressed(None)
    assert not module._is_hand_pressed([])
    points = hand((True,)*4)
    points[20].x = float('nan')
    assert not module._is_hand_pressed(points)


def test_restored_triangle_animates_and_scores_each_side_independently(ctx, monkeypatch):
    scene = module.Game4Scene(); scene.on_enter(ctx)
    scene.selected_level = dict(scene.level_options[0]); scene._start_playing(0)
    scene.next_spawn_at = 999
    monkeypatch.setattr(module.time, 'time', lambda: 1.0)
    played = []
    monkeypatch.setattr(module, '_get_sound', lambda key: SimpleNamespace(play=lambda: played.append(key)))
    result = SimpleNamespace(hand_landmarks=[hand((True,)*4), hand((True, False, False, False))],
        handedness=[[SimpleNamespace(category_name=side)] for side in ('Left', 'Right')])
    scene._process_frame(np.zeros((480, 640, 3), np.uint8), None, result)
    assert scene.left_press_confirmed and not scene.right_press_confirmed
    assert scene.left_flash_until == pytest.approx(1.15)
    assert scene.right_flash_until == 0
    for side in ('left', 'right'):
        tri = module.Triangle(side, 'blue', 0)
        tri.distance_px = ctx.screen.get_width()*module.cfg.PADDLE_OFFSET_RATIO
        scene.triangles.append(tri)
    scene._update_playing(ctx, 0, 1)
    assert scene.combo_state.score == 1
    assert played == ['hit']
    assert [tri.side for tri in scene.triangles] == ['right']
    angles = []
    rotate = pygame.transform.rotate
    monkeypatch.setattr(pygame.transform, 'rotate', lambda surface, angle: (angles.append(angle), rotate(surface, angle))[1])
    scene._draw_hand_paddles(ctx.screen, ctx.screen.get_width(), 350)
    assert angles == [-50, 0]
    assert scene.arcade_recording.data['frames'][-1]['presses'] == {'left': True, 'right': False}


def test_restored_triangle_has_original_levels_and_independent_colors(ctx, monkeypatch):
    assert [level['duration_sec'] for level in module.cfg.LEVELS] == [45]*3
    assert [level['pass_score'] for level in module.cfg.LEVELS] == [15, 25, 35]
    scene = module.Game4Scene(); scene.on_enter(ctx)
    scene.selected_level = dict(scene.level_options[0]); scene._start_playing(0)
    colors = iter(('blue', 'red'))
    monkeypatch.setattr(scene, '_random_color', lambda: next(colors))
    scene.left_press_confirmed = scene.right_press_confirmed = False
    scene._update_playing(ctx, 0, 2)
    assert [tri.color for tri in scene.triangles] == ['blue', 'red']
