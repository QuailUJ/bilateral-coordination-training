"""
games/registry.py - 遊戲選單的擴充點

MainMenuScene 只依賴這支檔案的 GAMES 列表來畫出遊戲 tile，之後企劃確認遊戲
二/三/四之後，各自寫一個 games/gameN_xxx/ 模組（比照 game1_bilateral_vertical
的結構：scene.py 提供一個 Scene 子類別）、在下面 GAMES 加一個 GameSpec，選單
程式碼完全不用改。
"""

from dataclasses import dataclass
from typing import Callable

from common.scene_manager import Scene
from games.game1_bilateral_vertical.scene import Game1Scene, GAME_ID as GAME1_ID, \
    DISPLAY_NAME as GAME1_NAME, DESCRIPTION as GAME1_DESC
from games.game2_finger_vertical.scene import Game2Scene, GAME_ID as GAME2_ID, \
    DISPLAY_NAME as GAME2_NAME, DESCRIPTION as GAME2_DESC
from games.game3_lightsaber_marble.scene import Game3Scene, GAME_ID as GAME3_ID, \
    DISPLAY_NAME as GAME3_NAME, DESCRIPTION as GAME3_DESC
from games.game4_bilateral_press.scene import Game4Scene, GAME_ID as GAME4_ID, \
    DISPLAY_NAME as GAME4_NAME, DESCRIPTION as GAME4_DESC


@dataclass
class GameSpec:
    game_id: str
    display_name: str
    description: str
    scene_factory: Callable[[], Scene]
    enabled: bool = True


GAMES = [
    GameSpec(
        game_id=GAME1_ID,
        display_name=GAME1_NAME,
        description=GAME1_DESC,
        scene_factory=lambda: Game1Scene(),
    ),
    GameSpec(
        game_id=GAME2_ID,
        display_name=GAME2_NAME,
        description=GAME2_DESC,
        scene_factory=lambda: Game2Scene(),
    ),
    GameSpec(
        game_id=GAME3_ID,
        display_name=GAME3_NAME,
        description=GAME3_DESC,
        scene_factory=lambda: Game3Scene(),
    ),
    GameSpec(
        game_id=GAME4_ID,
        display_name=GAME4_NAME,
        description=GAME4_DESC,
        scene_factory=lambda: Game4Scene(),
    ),
]

_GAMES_BY_ID = {g.game_id: g for g in GAMES}


def get_game(game_id: str) -> GameSpec:
    return _GAMES_BY_ID[game_id]
