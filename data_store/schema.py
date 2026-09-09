"""
data_store/schema.py - 使用者資料的 JSON schema 定義與 record 建構

每人一個 JSON 檔（data/users/<sanitized_username>.json），格式：

{
  "schema_version": 1,
  "username": "王小明",              # 使用者輸入的原始字串（未經檔名淨化）
  "created_at": "2026-08-18T10:00:00+08:00",
  "history": [
    {
      "record_id": "uuid4",
      "game_id": "game1_bilateral_vertical",
      "timestamp": "2026-08-18T10:05:23+08:00",
      "score": 87.5,
      "details": { ... 各遊戲自訂 ... }
    },
    ...
  ]
}

game_id / timestamp / score / details 是所有未來遊戲（game2/3/4）都要遵守的
固定契約，details 裡面放什麼完全由各遊戲自己決定。
"""

import uuid
from datetime import datetime, timezone

SCHEMA_VERSION = 1


def new_user_data(username: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "username": username,
        "created_at": _now_iso(),
        "history": [],
    }


def new_history_record(game_id: str, score: float, details: dict) -> dict:
    return {
        "record_id": str(uuid.uuid4()),
        "game_id": game_id,
        "timestamp": _now_iso(),
        "score": score,
        "details": details,
    }


def _now_iso() -> str:
    # astimezone() 補上本機時區資訊，比純 utcnow() 更好讀（跟遊戲一設計裡的
    # 範例時間格式一致）。
    return datetime.now().astimezone().isoformat(timespec="seconds")
