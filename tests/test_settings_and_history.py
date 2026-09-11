import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from common import game_time, audio
from common.app_context import AppContext
from common.camera_hand_tracker import CameraStream
from common.scene_manager import SceneManager
from data_store import settings_store, user_store
from scenes.history_scene import HistoryScene
from scenes.login_scene import LoginScene


def test_finger_circle_keeps_more_than_thirty_points_and_breaks_short_gap(ctx, monkeypatch):
    import numpy as np
    from test_hand_identity import hand, result
    from games.game2_finger_vertical.scene import Game2Scene
    scene = Game2Scene()
    scene.on_enter(ctx)
    scene._on_level_selected("CWCW")
    scene._start_playing(0)
    left, right = hand(.25), hand(.75)
    left[8].y = right[8].y = .35
    frame = np.zeros((480, 640, 3), np.uint8)
    for i in range(90):
        monkeypatch.setattr(game_time, "time", lambda i=i: i / 30)
        observations = result(("Right", right)) if i == 70 else result(("Left", left), ("Right", right))
        scene._process_frame(frame, None, observations)
    assert len(scene.left_trail) > 60
    assert None in scene.left_trail
    assert scene.left_recognizer.completed == 0
    assert scene.tracking_interruptions["left"] == 0
    assert scene.debug_snapshot["left"]["trail_start_t"] == 0
    scene.draw(ctx, ctx.screen)


def test_fist_partial_turn_does_not_erase_the_visible_arc(ctx, monkeypatch):
    import numpy as np
    from test_hand_identity import hand, result
    from games.game1_bilateral_vertical.scene import Game1Scene
    scene = Game1Scene()
    scene.on_enter(ctx)
    scene._on_actions_selected({"left": "CW", "right": "N"})
    scene._start_playing(0)
    points = [(.3, .28)] * 5 + [(.36, .33), (.4, .4), (.38, .38), (.38, .395)]
    for i, (x, y) in enumerate(points):
        monkeypatch.setattr(game_time, "time", lambda i=i: i / 30)
        scene._process_frame(np.zeros((480, 640, 3), np.uint8), None,
                             result(("Left", hand(1-x, y))))
    assert scene.left_recognizer.completed == 0
    assert scene.left_recognizer.just_started_lap  # Rejected partial reversal.
    assert len(scene.left_trail) >= 6


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    pygame.init()
    monkeypatch.setattr(user_store, "_default_base_dir", lambda: str(tmp_path / "users"))
    monkeypatch.setattr(settings_store, "settings_path", lambda: str(tmp_path / "settings.json"))
    context = AppContext(pygame.display.set_mode((1440, 900)), pygame.time.Clock(),
                         CameraStream(None), None, current_user="test")
    yield context
    game_time.resume()
    audio._sounds.clear()
    from ui.theme import _font_cache
    _font_cache.clear()
    pygame.quit()


def test_settings_roundtrip_and_invalid_values(tmp_path):
    path = str(tmp_path / "settings.json")
    settings_store.save_settings(2, 0.3, path)
    assert settings_store.load_settings(path) == {"camera_index": 2, "volume": 0.3}
    (tmp_path / "settings.json").write_text('{"camera_index": -2, "volume": 9}')
    assert settings_store.load_settings(path) == {"camera_index": 0, "volume": 1.0}


def test_login_escape_settings_preserves_input_and_saves(ctx):
    manager = SceneManager(ctx)
    manager.push(LoginScene())
    manager.current.text_input.text = "unfinished"
    escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    manager.handle_event(escape)
    assert manager._settings is not None
    manager._settings._volume(ctx, -0.4)
    manager.update(0.1)
    manager.draw(ctx.screen)
    manager.handle_event(escape)
    assert manager._settings is None
    assert manager.current.text_input.text == "unfinished"
    assert settings_store.load_settings()["volume"] == 0.6


def test_pause_excludes_settings_time(monkeypatch):
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(game_time._clock, "time", lambda: clock.now)
    monkeypatch.setattr(game_time, "_offset", 0.0)
    monkeypatch.setattr(game_time, "_paused_at", None)
    game_time.pause()
    clock.now += 50
    assert game_time.time() == 100
    game_time.resume()
    clock.now += 3
    assert game_time.time() == 103


def test_delete_confirmation_refreshes_chart_and_best(ctx):
    for score in (10, 90):
        user_store.append_history_record("test", "game1_bilateral_vertical", score, {})
    user_store.append_history_record("other", "game1_bilateral_vertical", 99, {})
    scene = HistoryScene()
    scene.on_enter(ctx)
    scene._on_filter_selected("game1_bilateral_vertical")
    scene._on_mode_selected("best_scores")
    scene.update(ctx, 0)
    scene._on_record_selected(scene.list_view.records[0])
    assert scene.selected_record["score"] == 90
    scene._delete(ctx)
    scene.draw(ctx, ctx.screen)
    assert len(user_store.create_or_load_user("test")["history"]) == 2
    scene._cancel_selection()
    assert len(user_store.create_or_load_user("test")["history"]) == 2
    scene._on_record_selected(scene.list_view.records[0])
    scene._delete(ctx)
    scene._delete(ctx)
    assert scene.chart_values == [10]
    assert scene.list_view.records[0]["score"] == 10
    assert len(user_store.create_or_load_user("other")["history"]) == 1
    record = scene.list_view.records[0]
    assert user_store.delete_history_record("test", record["record_id"])
    assert not user_store.delete_history_record("test", record["record_id"])
    scene._reload(ctx)
    assert scene.list_view.items == []


def test_failed_camera_switch_preserves_original(ctx, monkeypatch):
    from common import camera_hand_tracker
    original = ctx.camera
    def fail(**kwargs):
        raise RuntimeError("camera unavailable")
    monkeypatch.setattr(camera_hand_tracker, "open_camera", fail)
    with pytest.raises(RuntimeError):
        ctx.switch_camera(3)
    assert ctx.camera is original
    assert ctx.camera_index == 0


def test_successful_camera_switch_releases_old_camera(ctx, monkeypatch):
    from common import app_context, camera_hand_tracker
    old_cap = SimpleNamespace(released=False)
    old_cap.release = lambda: setattr(old_cap, "released", True)
    ctx.camera = CameraStream(old_cap)
    new_cap = object()
    monkeypatch.setattr(camera_hand_tracker, "open_camera", lambda **kw: (new_cap, "fake"))
    stream = SimpleNamespace(cap=new_cap, start=lambda: stream,
                             get_next=lambda *a, **kw: (object(), 1, 0))
    monkeypatch.setattr(app_context, "CameraStream", lambda cap: stream)
    ctx.switch_camera(2)
    assert ctx.camera is stream
    assert ctx.camera_index == 2
    assert old_cap.released


def test_volume_applies_to_cached_and_new_sounds(ctx):
    from common.paths import resource_path
    audio.set_volume(0.4)
    first = audio.load_sound(resource_path("assets/sound/correct.wav"))
    assert first.get_volume() == pytest.approx(0.4, abs=0.01)
    audio.set_volume(0)
    second = audio.load_sound(resource_path("assets/sound/correct.wav"))
    assert first.get_volume() == second.get_volume() == 0


def test_finger_scene_counts_ten_but_waits_for_sixty_seconds(ctx, monkeypatch):
    import copy
    import numpy as np
    from test_game2_finger_motion import landmarks
    from games.game2_finger_vertical.scene import Game2Scene

    scene = Game2Scene()
    scene.on_enter(ctx)
    scene.selected_action = {"combo_id": "VV", "left": "V", "right": "V", "label": "雙手垂直"}
    scene._start_playing(0)
    timer = SimpleNamespace(now=0.0)
    monkeypatch.setattr(game_time, "time", lambda: timer.now)
    frame = np.zeros((640, 640, 3), dtype=np.uint8)
    closed, opened = landmarks(), landmarks(True)

    def process(amount, frames=1):
        for _ in range(frames):
            left = copy.deepcopy(closed)
            for i in range(21):
                left[i].x += (opened[i].x - closed[i].x) * amount - 0.22
                left[i].y += (opened[i].y - closed[i].y) * amount
            right = copy.deepcopy(left)
            for p in right:
                p.x += 0.44
            result = SimpleNamespace(hand_landmarks=[left, right], handedness=[
                [SimpleNamespace(category_name="Left", score=0.99)],
                [SimpleNamespace(category_name="Right", score=0.99)]])
            detector = SimpleNamespace(detect=lambda image: result)
            timer.now += 0.05
            scene._process_frame(frame.copy(), detector)
            scene._advance_state(ctx)

    process(0, 10)
    for rep in range(10):
        for step in range(1, 11):
            process(step / 10)
        process(1, 5)
        for step in range(9, -1, -1):
            process(step / 10)
        process(0, 10)
        assert scene.sync_tracker.completed_pairs == rep + 1
        assert scene.state == "playing"
    timer.now = 60.0
    scene._advance_state(ctx)
    assert scene.state == "result"
    history = user_store.create_or_load_user("test")["history"]
    assert len(history) == 1
    assert history[0]["score"] == 10
    assert history[0]["details"]["pass_score"] == 8
    analysis = history[0]["details"]["analysis"]
    assert analysis["version"] == 1
    assert analysis["tip_landmark"] == 8
    frames = analysis["frames"]
    assert frames[-1]["paired"] == 10
    assert frames[-1]["left"]["completed"] == 10
    assert all(a["t"] <= b["t"] for a, b in zip(frames, frames[1:]))
    assert any("pip_angle" in frame["left"]["metrics"] for frame in frames)
    assert frames[-1]["score_kind"] == "synchronous_points"
    from scenes.replay_scene import ReplayScene
    replay = ReplayScene()
    replay.on_enter(ctx, history[0])
    replay._seek(frames[len(frames)//2]["t"])
    replay.draw(ctx, ctx.screen)
    assert replay.frames[replay._current_frame_index()]["t"] <= replay.playback_t
    assert replay.duration > 2.5


@pytest.mark.parametrize("game", [0, 1])
def test_all_combinations_wait_for_deadline(ctx, monkeypatch, game):
    from games.game1_bilateral_vertical.config import ACTION_SETS
    from games.game1_bilateral_vertical.scene import Game1Scene
    from games.game2_finger_vertical.scene import Game2Scene
    timer = SimpleNamespace(now=0)
    monkeypatch.setattr(game_time, "time", lambda: timer.now)
    for action in ACTION_SETS:
        scene = (Game1Scene if game == 0 else Game2Scene)()
        scene.on_enter(ctx)
        scene.selected_action = action
        scene._start_playing(0)
        for rep in range(1, 13):
            scene.sync_tracker.update(rep, rep, rep)
        timer.now = 59.99
        scene._advance_state(ctx)
        assert scene.state == "playing"
        timer.now = 60
        scene._advance_state(ctx)
        assert scene.state == "result"
        assert scene.session_result.score == 12
        assert scene.session_result.passed


def test_game_zero_mislabeled_right_discards_only_unfinished_left(ctx, monkeypatch):
    import numpy as np
    from test_hand_identity import acquire, result
    from games.game1_bilateral_vertical.scene import Game1Scene
    scene = Game1Scene()
    scene.timed_session = False  # Legacy recognizer/trial regression.
    scene.on_enter(ctx)
    scene.selected_action = {"combo_id": "VV", "left": "V", "right": "V", "label": "雙手垂直"}
    scene._start_playing(0)
    left, right = acquire(scene.hand_identity)
    scene.left_recognizer.completed = 2
    scene.left_recognizer.half_swings = 1
    scene.left_trail.append((0.75, 0.5))
    scene.trail_recorder.record_left_point((0.75, 0.5))
    scene.trail_recorder.finish_left_rep()
    scene.trail_recorder.record_left_point((0.74, 0.5))
    monkeypatch.setattr(game_time, "time", lambda: 0.1)
    detector = SimpleNamespace(detect=lambda image: result(("Left", right)))
    scene._process_frame(np.zeros((480, 640, 3), dtype=np.uint8), detector)
    assert scene.left_landmarks is None
    assert not scene.left_trail
    assert scene.left_recognizer.completed == 2
    assert scene.left_recognizer.half_swings == 0
    assert scene.trail_recorder._current_left == []
    assert scene.trail_recorder._pending_left == [[[0.75, 0.5]]]
    logged = scene.diagnostics["frames"][-1]
    assert logged["left"]["tracking"]["accepted"] is False
    assert logged["left"]["tracking"]["reason"] in ("wrist_jump", "identity_conflict")
    assert logged["left"]["tracking"]["raw_tip"] == [0.25, 0.5]
    assert logged["left"]["tip"] is None
    assert logged["left"]["interruptions"] == 1


def test_camera_gap_records_reason_without_recounting_one_interruption(ctx, monkeypatch):
    import json
    from games.game1_bilateral_vertical.scene import Game1Scene
    from common.training_diagnostics import export_diagnostics
    scene = Game1Scene()
    scene.on_enter(ctx)
    scene.selected_action = {"combo_id": "VV", "left": "V", "right": "V", "label": "雙手垂直"}
    scene._start_playing(0)
    scene.last_sample_time = 0
    monkeypatch.setattr(game_time, "time", lambda: 1.0)
    scene.update(ctx, 0.1)
    monkeypatch.setattr(game_time, "time", lambda: 1.2)
    scene.update(ctx, 0.1)
    analysis = json.loads(json.dumps(export_diagnostics(scene, ctx), allow_nan=False))
    assert len(analysis["frames"]) == 2
    assert analysis["frames"][-1]["source"] == "camera_gap"
    assert analysis["frames"][-1]["left"]["tracking"]["reason"] == "camera_gap"
    assert analysis["frames"][-1]["left"]["interruptions"] == 1


def test_fist_short_loss_preserves_progress_long_loss_resets_and_replay_draws(ctx, monkeypatch):
    import json
    import numpy as np
    from test_hand_identity import acquire, result
    from games.game1_bilateral_vertical.scene import Game1Scene
    from common.training_diagnostics import export_diagnostics
    from scenes.replay_scene import ReplayScene
    scene = Game1Scene()
    scene.on_enter(ctx)
    scene.selected_action = {"combo_id": "VV", "left": "V", "right": "V", "label": "雙手垂直"}
    scene._start_playing(0)
    left, right = acquire(scene.hand_identity)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    def feed(t, detections):
        monkeypatch.setattr(game_time, "time", lambda: t)
        scene._process_frame(frame.copy(), SimpleNamespace(detect=lambda image: result(*detections)))
    feed(0.1, [("Left", left), ("Right", right)])
    # Rendering also works before the fixed reference has been calibrated.
    replay = ReplayScene()
    replay.on_enter(ctx, {"details": {"analysis": export_diagnostics(scene, ctx)}})
    replay.draw(ctx, ctx.screen)
    feed(0.41, [("Left", left), ("Right", right)])
    recognizer = scene.left_recognizer
    recognizer.half_swings = 1
    recognizer.completed = 2
    feed(0.44, [("Right", right)])
    assert scene.left_recognizer is recognizer
    assert recognizer.half_swings == 1
    assert scene.debug_snapshot["left"]["tip"] is None
    for t in (0.47, 0.50, 0.53):
        feed(t, [("Left", left), ("Right", right)])
    assert scene.left_recognizer is recognizer
    assert recognizer.half_swings == 1
    assert scene.debug_snapshot["left"]["reference"] is None
    assert scene.debug_snapshot["left"]["metrics"]["recognition"] == "reversal"
    scene.draw(ctx, ctx.screen)
    feed(0.56, [("Right", right)])
    feed(0.95, [("Right", right)])
    assert scene.left_recognizer is not recognizer
    assert scene.left_recognizer.completed == 2
    assert scene.left_recognizer.half_swings == 0
    analysis = json.loads(json.dumps(export_diagnostics(scene, ctx), allow_nan=False))
    assert analysis["tracking_point_kind"] == "palm_center"
    replay.on_enter(ctx, {"details": {"analysis": analysis}})
    replay.playback_t = 0.53
    replay.draw(ctx, ctx.screen)


def test_legacy_replay_remains_available_and_buttons_do_not_overlap(ctx):
    from scenes.replay_scene import ReplayScene
    record = {"details": {"level_id": "VV", "reps": [
        {"round": 1, "hand": "left", "score": 23, "trail": [[0.3, 0.2], [0.3, 0.7]]},
        {"round": 1, "hand": "right", "score": 23, "trail": [[0.7, 0.2], [0.7, 0.7]]}]}}
    replay = ReplayScene()
    replay.on_enter(ctx, record)
    replay.draw(ctx, ctx.screen)
    assert not replay.frames
    assert replay.duration == 2.5
    buttons = [replay.prev_button, replay.next_button, replay.pause_button, replay.replay_button, replay.speed_button]
    assert all(not a.rect.colliderect(b.rect) for i, a in enumerate(buttons) for b in buttons[i+1:])


def test_analysis_only_record_is_replayable_and_scrubbing_is_synchronized(ctx, monkeypatch):
    from common.training_diagnostics import record_diagnostics, export_diagnostics
    from games.game1_bilateral_vertical.scene import Game1Scene
    from scenes.history_scene import _replay_payload
    from scenes.replay_scene import ReplayScene
    scene = Game1Scene()
    scene.on_enter(ctx)
    scene.selected_action = {"combo_id": "VH", "left": "V", "right": "H", "label": "左垂直右水平"}
    scene._start_playing(0)
    for t, left_count, right_count in [(0, 0, 0), (1, 3, 0), (4, 3, 1)]:
        scene.left_recognizer.completed = left_count
        scene.right_recognizer.completed = right_count
        record_diagnostics(scene, t)
    record = {"details": {"level_id": "VH", "analysis": export_diagnostics(scene, ctx)}}
    assert _replay_payload(record) is record
    replay = ReplayScene()
    replay.on_enter(ctx, record)
    replay._seek(2)
    frame = replay.frames[replay._current_frame_index()]
    assert frame["left"]["completed"] == 3
    assert frame["right"]["completed"] == 0
    replay._next_round()
    assert replay.playback_t == 4
    assert not replay.playing
    replay._prev_round()
    assert replay.playback_t == 1
    replay.speed = 0.5
    replay.playing = True
    replay.update(ctx, 1)
    assert replay.playback_t == 1.5
    replay.handle_event(ctx, pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=replay.timeline_rect.center))
    assert replay.playback_t == pytest.approx(2, abs=0.01)
    assert not replay.playing
    replay.draw(ctx, ctx.screen)


def test_live_camera_stays_between_side_panels(ctx):
    import numpy as np
    from ui.training_panels import training_layout
    from games.game1_bilateral_vertical.scene import Game1Scene
    scene = Game1Scene()
    scene.display_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    video = scene._draw_camera_feed(ctx.screen, *ctx.screen.get_size())
    left, center, right = training_layout(ctx.screen.get_size())
    assert center.contains(video)
    assert not left.colliderect(video)
    assert not right.colliderect(video)


def test_formal_games_share_sixteen_color_coded_options(ctx):
    from games.game1_bilateral_vertical.scene import Game1Scene
    from games.game2_finger_vertical.scene import Game2Scene
    scenes = [Game1Scene(), Game2Scene()]
    for scene in scenes:
        scene.on_enter(ctx)
        scene._on_guide_dismissed()
        assert scene.state == "level_select"
    assert scenes[0].level_options == scenes[1].level_options
    assert len(scenes[1].level_options) == 16
    assert scenes[1].level_select_widget.columns == 2
    assert len(scenes[0].level_select_widget.buttons) == 16
    assert [sum(o["difficulty"] == i for o in scenes[0].level_options) for i in range(1,6)] == [2,2,2,2,8]
    for scene in scenes:
        scene.draw(ctx, ctx.screen)
        for option in scene.level_options:
            scene._on_level_selected(option["level_id"])
            assert scene.selected_action["combo_id"] == option["level_id"]


@pytest.mark.parametrize("side", ["left", "right"])
@pytest.mark.parametrize("action", ["H", "V"])
def test_single_hand_only_in_camera_finishes_ten_and_replays(ctx, monkeypatch, side, action):
    import numpy as np
    from test_hand_identity import hand, result
    from games.game1_bilateral_vertical.scene import Game1Scene, GAME_ID
    from scenes.replay_scene import ReplayScene
    scene = Game1Scene()
    scene.timed_session = False  # Legacy recognizer/trial regression.
    scene.on_enter(ctx)
    other = "right" if side == "left" else "left"
    scene._on_actions_selected({side: action, other: "N"})
    scene._start_playing(0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    def feed(t, offset):
        monkeypatch.setattr(game_time, "time", lambda: t)
        lm = hand(.3 + (offset if action == "H" else 0), .4 + (offset if action == "V" else 0))
        scene._process_frame(frame.copy(), SimpleNamespace(detect=lambda image: result((side.title(), lm))))
        scene._advance_state(ctx)
    for i in range(3):
        feed(i * .03, 0)
    assert getattr(scene, side + "_landmarks") is not None
    t = .4
    for _ in range(10):
        feed(t, .12)
        feed(t+.3, 0)
        t += .6
    feed(t, .12)
    assert scene.state == "result"
    assert scene.session_result.score == 10
    assert scene.tracking_interruptions[other] == 0
    record = user_store.get_history_for_game(ctx.current_user, GAME_ID, limit=1)[0]
    assert record["details"]["training_mode"] == "single"
    assert record["details"]["enabled_hands"] == [side]
    assert record["details"]["analysis"]["frames"][-1][other]["tip"] is None
    scene.draw(ctx, ctx.screen)
    replay = ReplayScene()
    replay.on_enter(ctx, record)
    replay.draw(ctx, ctx.screen)


@pytest.mark.parametrize("side", ["left", "right"])
@pytest.mark.parametrize("action", ["CW", "CCW"])
def test_single_circle_only_in_camera_finishes_ten(ctx, monkeypatch, side, action):
    import math
    import numpy as np
    from test_hand_identity import hand, result
    from games.game1_bilateral_vertical.scene import Game1Scene
    scene = Game1Scene()
    scene.timed_session = False  # Legacy recognizer/trial regression.
    scene.on_enter(ctx)
    other = "right" if side == "left" else "left"
    scene._on_actions_selected({side: action, other: "N"})
    scene._start_playing(0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    def feed(t, x, y):
        monkeypatch.setattr(game_time, "time", lambda: t)
        scene._process_frame(frame.copy(), SimpleNamespace(detect=lambda image: result((side.title(), hand(1-x, y)))))
        scene._advance_state(ctx)
    for i in range(15):
        feed(i*.03, .3, .28)
    sign = 1 if action == "CW" else -1
    for i in range(1, 12*120):
        angle = -math.pi/2 + sign*i/120*math.tau
        feed(.45+i*.03, .3+.12*math.cos(angle), .4+.12*math.sin(angle))
        if i == 110:  # 330 degrees: no early credit or disappearing tail.
            assert getattr(scene, side + "_recognizer").completed == 0
            assert len(getattr(scene, side + "_trail")) > 100
            scene.draw(ctx, ctx.screen)
        if i == 120:
            assert getattr(scene, side + "_recognizer").completed == 0
            assert len(getattr(scene, side + "_trail")) > 120
        if i == 135:
            assert getattr(scene, side + "_recognizer").completed == 1
            assert len(getattr(scene, side + "_trail")) < 30
        if scene.state == "result":
            break
    assert scene.state == "result"
    assert scene.sync_tracker.score == 10
    assert scene.session_result.score > 99
    assert scene.tracking_interruptions[other] == 0


def test_login_circle_trial_five_loops_save_quality_and_replay(ctx, monkeypatch):
    import math
    import numpy as np
    from test_hand_identity import hand, result
    from scenes.circle_trial_scene import CircleTrialScene
    from games.game1_bilateral_vertical.scene import GAME_ID
    login = LoginScene()
    login.on_enter(ctx)
    login._submit_trial()
    assert login.error_message
    assert login.update(ctx, .01) is None
    login.text_input.text = "trial_user"
    login._submit_trial()
    transition = login.update(ctx, .01)
    assert transition.kind == "push"
    assert isinstance(transition.scene, CircleTrialScene)
    assert ctx.current_user == "trial_user"
    scene = transition.scene
    scene.on_enter(ctx)
    scene.draw(ctx, ctx.screen)
    scene._start_playing(0)
    frame = np.zeros((480,640,3),dtype=np.uint8)
    for i in range(700):
        t=i/30
        angle=-math.pi/2+max(0,i-5)*math.tau/120
        x=.35+.06*math.cos(angle)+.02*max(0,i-5)/120
        y=.4+.06*math.sin(angle)
        monkeypatch.setattr(game_time,"time",lambda:t)
        scene._process_frame(frame.copy(), SimpleNamespace(detect=lambda image:result(("Right",hand(1-x,y)))))
        scene._advance_state(ctx)
        if scene.state == "result":
            break
    assert scene.state == "result"
    assert len(scene.circle_records) == 5
    record=user_store.get_history_for_game(ctx.current_user,GAME_ID,limit=1)[0]
    assert record["details"]["analysis"]["target_pairs"] == 5
    assert record["details"]["completed_circles"] == 5
    assert len(record["details"]["reps"]) == 5
    assert record["score"] > 70
    scene.draw(ctx,ctx.screen)
    scene._replay()
    replay = scene._pending_transition.scene
    replay.on_enter(ctx,record=record)
    replay.playback_t = replay.duration
    replay.draw(ctx,ctx.screen)


def test_trial_loss_recreates_trial_algorithm_preserving_completed_count(ctx):
    from scenes.circle_trial_scene import CircleTrialScene
    from games.game1_bilateral_vertical.circle_trial_motion import UpperReversalCircle
    from common.training_tracking import interrupt_hand
    scene=CircleTrialScene()
    scene.on_enter(ctx)
    scene._start_playing(0)
    scene.right_recognizer.completed=2
    interrupt_hand(scene,"right",scene.make_recognizer)
    assert isinstance(scene.right_recognizer,UpperReversalCircle)
    assert scene.right_recognizer.completed==2


@pytest.mark.parametrize("left_action,right_action", [("CW","CW"),("CW","CCW"),("CCW","CW"),("CCW","CCW")])
def test_formal_bilateral_circles_timed_session_saves_each_hand(ctx,monkeypatch,left_action,right_action):
    import math
    import numpy as np
    from test_hand_identity import hand,result
    from games.game1_bilateral_vertical.scene import Game1Scene,GAME_ID
    scene=Game1Scene();scene.on_enter(ctx)
    scene._on_actions_selected({"left":left_action,"right":right_action});scene._start_playing(0)
    frame=np.zeros((80,100,3),dtype=np.uint8)
    for i in range(1350):
        t=i/30
        monkeypatch.setattr(game_time,"time",lambda:t)
        detections=[]
        for side,action,cx,radius in [("Left",left_action,.25,.04),("Right",right_action,.75,.06)]:
            angle=-math.pi/2+(1 if action=="CW" else -1)*max(0,i-5)*math.tau/120
            x=cx+radius*math.cos(angle);y=.4+radius*math.sin(angle)
            detections.append((side,hand(1-x,y)))
        scene._process_frame(frame.copy(),SimpleNamespace(detect=lambda image:result(*detections)))
        scene._advance_state(ctx)
        if scene.state=="result":break
    assert scene.state=="playing"
    monkeypatch.setattr(game_time,"time",lambda:60.0)
    scene._advance_state(ctx)
    assert scene.state=="result"
    assert scene.sync_tracker.completed_pairs>=10
    record=user_store.get_history_for_game(ctx.current_user,GAME_ID,limit=1)[0]
    details=record["details"]
    assert details["analysis"]["reference_kind"]=="observed_top_reversal"
    assert details["rule_version"] == "timed_bilateral_v2"
    for side in ("left","right"):
        laps=details["circle_records"][side]
        assert len(laps)>=10
        assert all(r["hand"]==side and r["quality"]>99 for r in laps)
        assert laps[1]["start_t"]==pytest.approx(laps[0]["end_t"])
    from scenes.replay_scene import ReplayScene
    replay=ReplayScene();replay.on_enter(ctx,record);replay.draw(ctx,ctx.screen)


@pytest.mark.parametrize("circle_side",["left","right"])
@pytest.mark.parametrize("direction",["CW","CCW"])
@pytest.mark.parametrize("axis",["H","V"])
def test_mixed_modes_use_same_circle_algorithm(ctx,circle_side,direction,axis):
    from games.game1_bilateral_vertical.scene import Game1Scene
    from games.game1_bilateral_vertical.circle_trial_motion import UpperReversalCircle
    scene=Game1Scene();scene.on_enter(ctx)
    other="right" if circle_side=="left" else "left"
    scene._on_actions_selected({circle_side:direction,other:axis});scene._start_playing(0)
    recognizer=getattr(scene,circle_side+"_recognizer")
    assert isinstance(recognizer,UpperReversalCircle)
    assert recognizer.direction==direction
    from common.training_tracking import interrupt_hand
    interrupt_hand(scene,circle_side,scene.make_recognizer)
    assert getattr(scene,circle_side+"_recognizer").direction==direction


def test_user_deletion_requires_confirmation_and_clears_only_selected_data(ctx):
    from pathlib import Path
    from scenes.user_management_scene import UserManagementScene
    for name in ("test", "other"):
        user_store.append_history_record(name, "game1_bilateral_vertical", 10, {"reps": [1]})
    path = user_store.user_file_path("test")
    for suffix in (".tmp", ".corrupt.bak"):
        Path(path+suffix).write_text("backup")
    scene = UserManagementScene()
    scene.on_enter(ctx)
    scene._select("test")
    scene.handle_event(ctx, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert Path(path).exists()
    scene._select("test")
    scene._delete(ctx)
    assert ctx.current_user is None
    assert all(not Path(path+suffix).exists() for suffix in ("", ".tmp", ".corrupt.bak"))
    assert len(user_store.create_or_load_user("other")["history"]) == 1
    assert "test" not in user_store.list_known_display_names()


def test_settings_delete_current_user_returns_to_login(ctx):
    from scenes.main_menu_scene import MainMenuScene
    user_store.append_history_record("test", "game1_bilateral_vertical", 1, {})
    manager = SceneManager(ctx)
    manager.push(MainMenuScene())
    manager._open_settings()
    settings = manager._settings
    settings._manage_users(ctx)
    settings.user_management._select("test")
    settings.user_management._delete(ctx)
    escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    manager.handle_event(escape)  # Return from user manager.
    manager.handle_event(escape)  # Save and close settings.
    assert isinstance(manager.current, LoginScene)
    assert "test" not in manager.current.known_usernames


def test_saber_replay_records_hit_miss_and_actual_score(ctx, monkeypatch):
    from games.game3_lightsaber_marble import scene as module
    from scenes.replay_scene import ReplayScene
    from scenes.history_scene import _replay_payload
    monkeypatch.setattr(module, "_get_sound", lambda key: None)
    scene = module.Game3Scene()
    scene.on_enter(ctx)
    scene.selected_level = dict(scene.level_options[0])
    scene._start_playing(0)
    scene.next_spawn_at = 999
    scene.left_sword.active = True
    scene.left_sword.angle_deg = 90
    hit = module.Marble(scene.pivot, 90, scene.inner_radius*1.2, scene.inner_radius, 0, None, None)
    miss = module.Marble(scene.pivot, 30, scene.inner_radius*0.9, scene.inner_radius, 0, None, None)
    scene.marbles.add(hit, miss)
    scene._update_playing(ctx, 0, 1)
    scene._finish_playing(ctx)
    record = user_store.create_or_load_user("test")["history"][-1]
    data = record["details"]["arcade_replay"]
    assert [event["delta"] for event in data["events"]] == [module.cfg.HIT_SCORE, 0]
    assert sum(event["delta"] for event in data["events"]) == record["score"]
    assert data["events"][0]["side"] == "right"
    assert data["events"][0]["object_id"] != data["events"][1]["object_id"]
    assert _replay_payload(record) is record
    replay = ReplayScene()
    replay.on_enter(ctx, record)
    replay._select_score_event(data["events"][0])
    assert replay.playback_t == 1
    assert not replay.playing
    replay.draw(ctx, ctx.screen)


def test_triangle_replay_lists_all_score_and_combo_outcomes(ctx, monkeypatch):
    from games.game4_bilateral_press import scene as module
    from common.arcade_recording import record_triangles
    from scenes.replay_scene import ReplayScene
    monkeypatch.setattr(module, "_get_sound", lambda key: None)
    scene = module.Game4Scene()
    scene.on_enter(ctx)
    scene.selected_level = dict(scene.level_options[0])
    scene._start_playing(0)
    width = ctx.screen.get_width()
    for i, (color, pressed) in enumerate((("blue", True), ("red", True), ("blue", False), ("red", False))):
        tri = module.Triangle("left", color, 0)
        tri.distance_px = width * (module.cfg.PADDLE_OFFSET_RATIO if pressed else module.cfg.PADDLE_OFFSET_RATIO + module.cfg.HIT_WINDOW_RATIO + 0.01)
        scene.triangles = [tri]
        scene._resolve_triangles("left", pressed, width, now=i+1)
        record_triangles(scene, i+1)
    scene._finish_playing(ctx)
    record = user_store.create_or_load_user("test")["history"][-1]
    data = record["details"]["arcade_replay"]
    assert [event["delta"] for event in data["events"]] == [1, -1, 0, 0]
    assert data["events"][1]["combo_before"] == 1
    assert data["events"][1]["combo_after"] == 0
    assert sum(event["delta"] for event in data["events"]) == record["score"]
    replay = ReplayScene()
    replay.on_enter(ctx, record)
    assert len(replay.event_list.records) == 4
    replay._select_score_event(data["events"][1])
    assert replay.frames[replay._current_frame_index()]["score"] == 0
    replay.draw(ctx, ctx.screen)


@pytest.mark.parametrize("game", [0,1,2,3,4])
def test_every_camera_scene_keeps_updating_while_result_save_is_pending(ctx,monkeypatch,game):
    import json
    import numpy as np
    from concurrent.futures import Future
    from games.game1_bilateral_vertical.scene import Game1Scene
    from games.game2_finger_vertical.scene import Game2Scene
    from games.game3_lightsaber_marble.scene import Game3Scene
    from games.game4_bilateral_press.scene import Game4Scene
    from scenes.circle_trial_scene import CircleTrialScene
    future=Future();calls=[]
    def save(*args):
        calls.append(args)
        return future
    ctx.persistence=SimpleNamespace(save_result=save)
    scene=[Game1Scene,Game2Scene,Game3Scene,Game4Scene,CircleTrialScene][game]()
    scene.on_enter(ctx)
    if game in (0,1):
        scene.selected_action={"combo_id":"VV","left":"V","right":"V","label":"雙手垂直"}
    elif game in (2,3):
        scene.selected_level=dict(scene.level_options[0])
    scene._start_playing(0)
    scene._finish_playing(ctx)
    assert scene.state=="settling"
    before=json.dumps(calls[0][3],sort_keys=True)
    camera_count=[0]
    def next_frame(last_id,timeout=0):
        camera_count[0]+=1
        return np.full((80,100,3),camera_count[0],dtype=np.uint8),camera_count[0],0
    ctx.camera=SimpleNamespace(get_next=next_frame)
    ctx.landmarker=SimpleNamespace(detect=lambda image:SimpleNamespace(hand_landmarks=[],handedness=[]))
    manager=SceneManager(ctx);manager._stack.append(scene)
    for _ in range(3):
        manager.update(.03)
        manager.draw(ctx.screen)
    assert camera_count[0]==3
    assert scene.state=="settling"
    assert len(calls)==1
    assert json.dumps(calls[0][3],sort_keys=True)==before
    assert scene.display_frame[0,0,0]==3
    future.set_result({})
    manager.update(.03)
    assert scene.state=="result"
    assert camera_count[0]==4


def test_login_background_load_does_not_rewrite_existing_user(ctx,monkeypatch):
    import threading
    from pathlib import Path
    from common.background_persistence import BackgroundPersistence
    user_store.save_user(user_store.create_or_load_user("test"))
    path=Path(user_store.user_file_path("test"))
    before=(path.stat().st_mtime_ns,path.read_bytes())
    started=threading.Event();release=threading.Event()
    original=user_store.create_or_load_user
    def delayed(*args,**kwargs):
        started.set()
        assert release.wait(3)
        return original(*args,**kwargs)
    monkeypatch.setattr(user_store,"create_or_load_user",delayed)
    service=BackgroundPersistence();ctx.persistence=service
    try:
        scene=LoginScene();scene.on_enter(ctx)
        scene._login_as("test")
        assert started.wait(1)
        assert scene.update(ctx,.03) is None
        scene.draw(ctx,ctx.screen)
        release.set();scene._login_future.result(timeout=3)
        assert scene.update(ctx,.03).kind=="replace"
        assert (path.stat().st_mtime_ns,path.read_bytes())==before
    finally:
        release.set();service.close()


@pytest.mark.parametrize("hand,angle,color,expected", [
    ("right", 120, "orange", 1), ("left", 60, "blue", 1),
    ("right", 60, "blue", 0), ("left", 120, "orange", 0),
    ("right", 90, "blue", -1), ("left", 90, "orange", -1),
])
def test_saber_side_and_central_color_rules(ctx, monkeypatch, hand, angle, color, expected):
    from games.game3_lightsaber_marble import scene as module
    monkeypatch.setattr(module, "_get_sound", lambda key: None)
    scene = module.Game3Scene()
    scene.on_enter(ctx)
    scene.selected_level = dict(scene.level_options[0])
    scene._start_playing(0)
    scene.next_spawn_at = 999
    sword = scene.left_sword if hand == "right" else scene.right_sword
    sword.active = True
    sword.angle_deg = angle
    marble = module.Marble(scene.pivot, angle, scene.inner_radius*1.2,
                           scene.inner_radius, 0, None, None, color=color)
    scene.marbles.add(marble)
    scene._update_playing(ctx, 0, 1)
    assert scene.score == expected
    assert sum(e["delta"] for e in scene.arcade_recording.data["events"]) == expected


def test_saber_cannot_rotate_across_center(ctx):
    from games.game3_lightsaber_marble.scene import Game3Scene
    scene = Game3Scene()
    scene.on_enter(ctx)
    for _ in range(20):
        scene.left_sword.update_towards(0)
        scene.right_sword.update_towards(180)
    assert scene.left_sword.angle_deg >= 90
    assert scene.right_sword.angle_deg <= 90


@pytest.mark.parametrize("delay,expected", [(0.0,2),(.3,2),(.301,0),(None,0)])
def test_triangle_pairs_require_two_presses(ctx, monkeypatch, delay, expected):
    from games.game4_bilateral_press import scene as module
    monkeypatch.setattr(module,"_get_sound",lambda key:None)
    scene=module.Game4Scene(); scene.on_enter(ctx)
    scene.selected_level=dict(scene.level_options[0]); scene._start_playing(0)
    w=ctx.screen.get_width()
    for side in ("left","right"):
        tri=module.Triangle(side,"blue",0);tri.pair_id=1;tri.pressed_at=None
        tri.distance_px=w*module.cfg.PADDLE_OFFSET_RATIO
        scene.triangles.append(tri)
    scene._resolve_triangles("left",True,w,1)
    assert scene.combo_state.score==0
    if delay is not None:
        scene._resolve_triangles("right",True,w,1+delay)
    scene._resolve_triangles("left",False,w,2)
    assert scene.combo_state.score==expected
    assert all(tri.resolved for tri in scene.triangles)
    assert sum(e["delta"] for e in scene.arcade_recording.data["events"])==expected
    scene._resolve_triangles("right",True,w,2)
    assert scene.combo_state.score==expected


@pytest.mark.parametrize("color,expected",[("blue",2),("red",0)])
def test_triangle_spawn_colors_match_and_denominator_counts_blue(ctx, monkeypatch,color,expected):
    from games.game4_bilateral_press import scene as module
    scene=module.Game4Scene();scene.on_enter(ctx)
    scene.selected_level=dict(scene.level_options[0]);scene._start_playing(0)
    scene.left_press_confirmed=scene.right_press_confirmed=False
    monkeypatch.setattr(scene,"_random_color",lambda:color)
    scene._update_playing(ctx,0,2)
    assert len(scene.triangles)==2
    assert {tri.color for tri in scene.triangles}=={color}
    assert len({tri.pair_id for tri in scene.triangles})==1
    assert scene.max_possible_score==expected


@pytest.mark.parametrize("game",[0,1])
@pytest.mark.parametrize("score,passed",[(7,False),(8,True)])
def test_timed_training_pass_threshold(ctx,monkeypatch,game,score,passed):
    from games.game1_bilateral_vertical.scene import Game1Scene
    from games.game2_finger_vertical.scene import Game2Scene
    scene=(Game1Scene if game==0 else Game2Scene)();scene.on_enter(ctx)
    scene._on_level_selected("VV");scene._start_playing(0)
    scene.sync_tracker.score=score
    monkeypatch.setattr(game_time,"time",lambda:60.0)
    scene._advance_state(ctx)
    assert scene.session_result.passed==passed
    scene.retry_button.on_click()
    assert scene.state=="countdown"
    scene._start_playing(63)
    assert scene.sync_tracker.score==0


@pytest.mark.parametrize("game",[2,3])
def test_arcade_pass_ratio_uses_actual_available_targets(ctx,game):
    from games.game3_lightsaber_marble.scene import Game3Scene
    from games.game4_bilateral_press.scene import Game4Scene
    from games.game4_bilateral_press.scoring import ComboState
    scene=(Game3Scene if game==2 else Game4Scene)();scene.on_enter(ctx)
    scene.selected_level=dict(scene.level_options[0]);scene._start_playing(0)
    scene.max_possible_score=11
    if game==2: scene.score=8
    else: scene.combo_state=ComboState(score=8)
    scene._finish_playing(ctx)
    assert not scene.session_result.passed
    if game==2: scene.score=9
    else: scene.combo_state=ComboState(score=9)
    scene._finish_playing(ctx)
    assert scene.session_result.passed


def test_history_best_and_latest_separate_levels_and_rule_versions():
    scene=HistoryScene()
    records=[{"score":score,"timestamp":str(i),"details":{"level_id":level,"rule_version":version,"passed":True}}
             for i,(level,version,score) in enumerate([("lv1","old",90),("lv1","new",8),("lv1","new",7),("lv2","new",5)])]
    rows,payload=scene._best_single_game_rows(records)
    assert len(rows)==3
    row=next(row for row,rec in zip(rows,payload) if rec["score"]==8)
    assert "最高 8" in row[0] and "最近 7" in row[1]


def test_saber_pointing_down_is_not_activated_by_boundary_clamp(ctx):
    from games.game3_lightsaber_marble.scene import Game3Scene
    scene=Game3Scene();scene.on_enter(ctx)
    scene.left_sword.update_towards(-90)
    scene.right_sword.update_towards(-90)
    assert not scene.left_sword.active and not scene.right_sword.active


@pytest.mark.parametrize('press_kind,expected', [('both', 2), ('left_only', 0), ('curled', 0)])
@pytest.mark.parametrize('flex', [50, 60])
def test_triangle_realistic_straight_finger_press_moves_paddles_and_scores(ctx, monkeypatch, press_kind, expected, flex):
    import numpy as np
    from test_straight_hand import anatomical_pose
    from games.game4_bilateral_press import scene as module
    played = []
    monkeypatch.setattr(module, '_play_sound', played.append)
    scene = module.Game4Scene(); scene.on_enter(ctx)
    scene.selected_level = dict(scene.level_options[0]); scene._start_playing(0)
    scene.next_spawn_at = 999
    frame = np.zeros((480, 640, 3), np.uint8)
    timer = SimpleNamespace(now=1.0)
    monkeypatch.setattr(game_time, 'time', lambda: timer.now)
    def feed(flex):
        hands = [anatomical_pose(flex), anatomical_pose(flex)]
        if press_kind == 'left_only':
            hands[1] = anatomical_pose(0)
        if press_kind == 'curled' and flex:
            for hand in hands:
                hand[7].x += .15
        result = SimpleNamespace(hand_landmarks=hands, handedness=[
            [SimpleNamespace(category_name=side, score=.99)] for side in ('Left', 'Right')])
        scene._process_frame(frame, None, result)
        scene._update_playing(ctx, 0, timer.now)
    feed(0)
    assert not scene.left_press_confirmed and not scene.right_press_confirmed
    neutral_snapshot = scene.arcade_recording.data['frames'][-1]['postures']
    for side in ('left', 'right'):
        tri = module.Triangle(side, 'blue', 0)
        tri.pair_id=1; tri.pressed_at=None
        tri.distance_px=ctx.screen.get_width()*module.cfg.PADDLE_OFFSET_RATIO
        scene.triangles.append(tri)
    timer.now = 1.1
    feed(flex)
    if press_kind == 'both':
        assert scene.left_flash_until > timer.now and scene.right_flash_until > timer.now
    assert scene.combo_state.score == expected
    assert played == (['hit'] if expected else [])
    assert sum(e['delta'] for e in scene.arcade_recording.data['events']) == expected
    assert not neutral_snapshot['left']['pressed']
    timer.now = 1.2
    feed(flex)
    assert scene.left_press_confirmed == (press_kind != 'curled')
    assert scene.right_press_confirmed == (press_kind == 'both')
    assert scene.combo_state.score == expected


@pytest.mark.parametrize('gap', [.1, .5])
def test_triangle_press_is_immediate_on_entry_and_after_tracking_gap(ctx, monkeypatch, gap):
    import numpy as np
    from test_straight_hand import anatomical_pose
    from games.game4_bilateral_press import scene as module
    scene = module.Game4Scene(); scene.on_enter(ctx)
    scene.selected_level = dict(scene.level_options[0]); scene._start_playing(0)
    timer = SimpleNamespace(now=1.0)
    monkeypatch.setattr(game_time, 'time', lambda: timer.now)
    def feed(flex):
        hands = [] if flex is None else [anatomical_pose(flex)]
        result = SimpleNamespace(hand_landmarks=hands, handedness=[
            [SimpleNamespace(category_name='Left', score=.99)]] if hands else [])
        scene._process_frame(np.zeros((480, 640, 3), np.uint8), None, result)
    feed(60)
    assert scene.left_press_confirmed
    timer.now += .03
    feed(None)
    assert not scene.left_press_confirmed
    timer.now = 1.0 + gap
    feed(60)
    assert scene.left_press_confirmed
    for flex in (60, 60, 0, 60):
        timer.now += .03
        feed(flex)
        assert scene.left_press_confirmed == (flex == 60)


def test_triangle_paddles_use_fixed_swing_for_different_pressed_angles(ctx, monkeypatch):
    import numpy as np
    from test_straight_hand import anatomical_pose
    from games.game4_bilateral_press import scene as module
    from common.arcade_recording import record_triangles
    scene = module.Game4Scene(); scene.on_enter(ctx)
    scene.selected_level = dict(scene.level_options[0]); scene._start_playing(0)
    timer = SimpleNamespace(now=1.0)
    monkeypatch.setattr(game_time, 'time', lambda: timer.now)
    def feed(flex):
        result = SimpleNamespace(hand_landmarks=[anatomical_pose(flex)]*2,
            handedness=[[SimpleNamespace(category_name=side)] for side in ('Left', 'Right')])
        scene._process_frame(np.zeros((480, 640, 3), np.uint8), None, result)
        surface = pygame.Surface(ctx.screen.get_size())
        scene._draw_hand_paddles(surface, surface.get_width(), 350)
        return pygame.surfarray.array3d(surface)
    upright = feed(0)
    partial = feed(25)
    assert not scene.left_press_confirmed and not scene.right_press_confirmed
    assert all(p['paddle_angle'] == 0 for p in scene.hand_postures.values())
    assert np.array_equal(upright, partial)
    shallow = feed(50)
    down = feed(60)
    assert np.array_equal(shallow, down)
    assert not np.array_equal(upright, down)
    assert scene.left_press_confirmed and scene.right_press_confirmed
    timer.now = 2.0  # The previous 0.15 second animation timeout has expired.
    surface = pygame.Surface(ctx.screen.get_size())
    scene._draw_hand_paddles(surface, surface.get_width(), 350)
    assert np.array_equal(pygame.surfarray.array3d(surface), down)
    record_triangles(scene, timer.now)
    snapshot = scene.arcade_recording.data['frames'][-1]['postures']
    feed(0)
    assert snapshot['left']['paddle_angle'] == module.cfg.PADDLE_SWING_DEG


def test_triangle_sound_retries_failed_load(monkeypatch):
    from games.game4_bilateral_press import scene as module
    monkeypatch.setattr(module, '_sound_cache', {'hit': None})
    monkeypatch.setattr(pygame.mixer, 'get_init', lambda: (44100, -16, 2))
    sound = object()
    monkeypatch.setattr(module, '_load_sound', lambda key: sound)
    assert module._get_sound('hit') is sound


def test_triangle_sound_recovers_audio_initialization(monkeypatch):
    from games.game4_bilateral_press import scene as module
    monkeypatch.setattr(module, '_sound_cache', {})
    initialized = []
    monkeypatch.setattr(pygame.mixer, 'get_init', lambda: None)
    monkeypatch.setattr(pygame.mixer, 'init', lambda: initialized.append(True))
    sound = object()
    monkeypatch.setattr(module, '_load_sound', lambda key: sound)
    assert module._get_sound('hit') is sound
    assert initialized == [True]


def test_triangle_sound_uses_channel_when_all_busy(monkeypatch):
    from games.game4_bilateral_press import scene as module
    sound = SimpleNamespace(play=lambda: None)
    played = []
    monkeypatch.setattr(module, '_get_sound', lambda key: sound)
    monkeypatch.setattr(pygame.mixer, 'find_channel', lambda force: SimpleNamespace(play=played.append))
    module._play_sound('error')
    assert played == [sound]
