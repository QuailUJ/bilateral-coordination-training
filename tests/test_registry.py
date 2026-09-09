"""games/registry.py 的一致性檢查：確保每一款遊戲都有必要的中繼資料，之後加
遊戲五的時候如果漏設定什麼，這裡會直接紅字提醒，不用等到主選單畫出來才發現。
"""

from games.registry import GAMES, GameSpec, get_game


def test_games_list_is_not_empty():
    assert len(GAMES) > 0


def test_every_game_has_required_metadata():
    for game in GAMES:
        assert isinstance(game, GameSpec)
        assert game.game_id and isinstance(game.game_id, str)
        assert game.display_name and isinstance(game.display_name, str)
        assert game.description and isinstance(game.description, str)
        assert callable(game.scene_factory)


def test_game_ids_are_unique():
    ids = [g.game_id for g in GAMES]
    assert len(ids) == len(set(ids)), f"game_id 重複: {ids}"


def test_scene_factory_produces_a_fresh_scene_instance_each_call():
    game = GAMES[0]
    a = game.scene_factory()
    b = game.scene_factory()
    assert a is not b  # 每次都要是新的實例，不能共用同一個 scene 物件跨場次


def test_get_game_returns_matching_spec():
    for game in GAMES:
        assert get_game(game.game_id) is game


def test_get_game_raises_key_error_for_unknown_id():
    try:
        get_game("__no_such_game__")
    except KeyError:
        pass
    else:
        raise AssertionError("找不到的 game_id 應該要拋 KeyError")
