"""
data_store/user_store.py - 使用者 JSON 檔案讀寫 API

每個函式都收一個可選的 base_dir 參數：正式執行時預設用
common.paths.resource_path("data/users")，單元測試時可以傳 tmp_path，完全不
會碰到真正的使用者資料，也不需要攝影機/pygame 就能測。

寫檔一律走「先寫 .tmp、fsync、再 os.replace() 換名」的原子寫入模式，確保
程式中途當機或斷電不會留下寫一半、讀不回來的損毀 JSON；讀檔如果真的遇到壞掉
的 JSON，會把壞檔另存成 .corrupt.bak 並回傳一份全新的預設資料，不會讓整支
程式崩潰。
"""

import json
import os
import re
import time
import threading
from collections import OrderedDict
from typing import Optional

from common.paths import resource_path, ensure_dir
from data_store.schema import new_user_data, new_history_record

_ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_MAX_USERNAME_LEN = 50
_cache = OrderedDict()
_cache_lock = threading.Lock()


def _signature(path):
    info = os.stat(path)
    return (info.st_mtime_ns, info.st_size)


def _remember(path, data):
    with _cache_lock:
        _cache[os.path.abspath(path)] = (_signature(path), data)
        _cache.move_to_end(os.path.abspath(path))
        while len(_cache) > 3:
            _cache.popitem(last=False)


def _cached(path):
    with _cache_lock:
        entry = _cache.get(os.path.abspath(path))
    if entry and os.path.exists(path) and entry[0] == _signature(path):
        return dict(entry[1], history=list(entry[1]["history"]))


def _load_json(stream):
    # The C decoder normally holds the GIL for a whole large replay file.
    # Yield periodically from object_hook so background loading cannot freeze
    # the camera/UI thread while decoding thousands of frame dictionaries.
    count = 0
    def yield_object(value):
        nonlocal count
        count += 1
        if count % 128 == 0:
            time.sleep(0)
        return value
    chunks = []
    while True:
        chunk = stream.read(262144)
        if not chunk:
            break
        chunks.append(chunk)
        time.sleep(0)
    return json.loads("".join(chunks), object_hook=yield_object)


def _default_base_dir() -> str:
    return resource_path(os.path.join("data", "users"))


def sanitize_username(raw: str) -> str:
    """把使用者輸入的名稱轉成安全的檔名。原始字串仍完整保留在 JSON 的
    "username" 欄位裡，這裡只影響「檔名」。"""
    name = raw.strip()
    if not name:
        raise ValueError("使用者名稱不可為空白。")
    name = _ILLEGAL_FILENAME_CHARS.sub("_", name)
    name = name[:_MAX_USERNAME_LEN].strip()
    if not name:
        raise ValueError("使用者名稱淨化後為空字串，請換一個名稱。")
    return name


def user_file_path(username: str, base_dir: Optional[str] = None) -> str:
    base = base_dir or _default_base_dir()
    return os.path.join(base, f"{sanitize_username(username)}.json")


def delete_user(username: str, base_dir: Optional[str] = None) -> bool:
    """Remove this account and its history/replays, including known backup files."""
    from pathlib import Path
    base = Path(base_dir or _default_base_dir()).resolve()
    path = Path(user_file_path(username, str(base)))
    targets = [Path(str(path) + suffix) for suffix in (".tmp", ".corrupt.bak", "")]
    if any(target.resolve().parent != base for target in targets):
        raise ValueError("使用者資料路徑不合法。")
    found = False
    for target in targets:
        if target.exists():
            target.unlink()
            found = True
    return found


def list_known_usernames(base_dir: Optional[str] = None) -> list:
    """回傳「檔名」清單（已經過 sanitize_username 處理過，可能跟使用者當初
    輸入的原始字串不完全一樣，例如去除頭尾空白或特殊符號）。這個函式適合拿來
    當作「這個 base_dir 底下有哪些帳號檔案」的內部用途；畫面上要顯示給使用者
    看的名稱，請用 list_known_display_names()。"""
    base = base_dir or _default_base_dir()
    if not os.path.isdir(base):
        return []
    names = []
    for fname in sorted(os.listdir(base)):
        if fname.endswith(".json"):
            names.append(fname[: -len(".json")])
    return names


def list_known_display_names(base_dir: Optional[str] = None) -> list:
    """回傳每個使用者檔案裡實際存的原始 "username" 欄位，用於登入畫面的
    「最近使用過的名稱」快速按鈕——直接用檔名 (list_known_usernames) 當顯示
    文字可能跟使用者當初打的不完全一樣（sanitize_username 會去除頭尾空白、
    把不合法的檔名字元換成底線），這裡改成讀回真正存的原始字串，顯示才會跟
    使用者的輸入一致。個別檔案讀取失敗就跳過，不影響其他人（正常情況下不該
    發生，因為 create_or_load_user 已經有損毀復原機制，這裡只是多一層防呆）。
    """
    base = base_dir or _default_base_dir()
    if not os.path.isdir(base):
        return []
    display_names = []
    for fname in sorted(os.listdir(base)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(base, fname)
        try:
            cached = _cached(path)
            if cached is not None:
                display_names.append(cached.get("username", fname[:-5]))
                continue
            with open(path, "r", encoding="utf-8") as f:
                # Username is in the small schema header, before history.
                header = f.read(65536)
                match = re.search(r'"username"\s*:\s*("(?:[^"\\]|\\.)*")', header)
                if match:
                    display_names.append(json.loads(match.group(1)))
                    continue
                f.seek(0)
                data = _load_json(f)
            display_names.append(data.get("username", fname[: -len(".json")]))
        except (json.JSONDecodeError, OSError):
            continue
    return display_names


def create_or_load_user(username: str, base_dir: Optional[str] = None) -> dict:
    """讀取使用者資料；檔案不存在就回傳一份預設結構（尚未寫檔——呼叫端登入成功
    後應該立刻呼叫 save_user 讓檔案馬上出現）。JSON 損毀時自動改名成
    .corrupt.bak 並回傳全新預設資料，不拋例外。"""
    path = user_file_path(username, base_dir)
    if not os.path.exists(path):
        return new_user_data(username)

    cached = _cached(path)
    if cached is not None:
        return cached

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = _load_json(f)
        if not isinstance(data, dict) or "history" not in data:
            raise ValueError("資料格式不符合預期 schema。")
        _remember(path, data)
        return dict(data, history=list(data["history"]))
    except (json.JSONDecodeError, ValueError, OSError) as e:
        backup_path = path + ".corrupt.bak"
        try:
            os.replace(path, backup_path)
            print(f"[user_store] 使用者資料損毀，已備份到 {backup_path}，原因: {e}")
        except OSError:
            pass
        return new_user_data(username)


def save_user(user_data: dict, base_dir: Optional[str] = None) -> None:
    """原子寫入使用者資料：寫到同目錄的 .tmp 檔、flush+fsync，再 os.replace()
    換名（Windows/POSIX 皆為原子操作），避免半寫入造成的損毀檔案。"""
    username = user_data["username"]
    path = user_file_path(username, base_dir)
    ensure_dir(os.path.dirname(path))

    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        # iterencode keeps encoding interruptible; compact whitespace also
        # greatly reduces replay-file write volume without dropping any data.
        encoder = json.JSONEncoder(ensure_ascii=False, separators=(",", ":"))
        for index, chunk in enumerate(encoder.iterencode(user_data)):
            f.write(chunk)
            if index % 4096 == 0:
                time.sleep(0)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)
    _remember(path, dict(user_data, history=list(user_data["history"])))


def append_history_record(username: str, game_id: str, score: float,
                           details: dict, base_dir: Optional[str] = None, record_id=None) -> dict:
    """建立一筆新的成績紀錄、附加進使用者資料、存檔，回傳寫入的完整使用者資料。"""
    user_data = create_or_load_user(username, base_dir)
    if record_id and any(r.get("record_id") == record_id for r in user_data["history"]):
        return user_data
    record = new_history_record(game_id, score, details)
    if record_id:
        record["record_id"] = record_id
    user_data["history"].append(record)
    save_user(user_data, base_dir)
    return user_data


def get_cleared_levels(username: str, game_id: str, base_dir: Optional[str] = None) -> set:
    """掃描某使用者、某遊戲的歷史紀錄，回傳 details 裡標記 "passed": True 的
    level_id 集合。給「關卡解鎖」畫面用：呼叫端自行決定解鎖規則（通常是「上一關
    的 level_id 有沒有出現在這個集合裡」），這支只負責讀歷史、不管解鎖規則本身，
    因為不同遊戲的關卡排序/過關條件不一樣，硬塞進共用邏輯反而會綁死彈性。
    每一款有關卡制的遊戲，寫入 history 時 details 裡都要記得放 "level_id" 跟
    "passed" 這兩個欄位（其餘欄位仍然自由）。
    """
    records = get_history_for_game(username, game_id, base_dir=base_dir)
    cleared = set()
    for record in records:
        details = record.get("details") or {}
        if details.get("passed") and "level_id" in details:
            cleared.add(details["level_id"])
    return cleared


def delete_history_record(username: str, record_id: str,
                          base_dir: Optional[str] = None) -> bool:
    """Delete exactly one identified record from this user's history."""
    if not record_id:
        return False
    data = create_or_load_user(username, base_dir)
    for index, record in enumerate(data["history"]):
        if record.get("record_id") == record_id:
            del data["history"][index]
            save_user(data, base_dir)
            return True
    return False


def get_history_for_game(username: str, game_id: str,
                          limit: Optional[int] = None,
                          base_dir: Optional[str] = None) -> list:
    """回傳某使用者、某遊戲的歷史紀錄，依時間新到舊排序。limit 不為 None 時只取
    最新的 N 筆（例如遊戲一開場拿最近 5 筆算 suggest_margin 用）。"""
    user_data = create_or_load_user(username, base_dir)
    records = [r for r in user_data.get("history", []) if r.get("game_id") == game_id]
    records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    if limit is not None:
        records = records[:limit]
    return records
