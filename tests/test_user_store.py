import json
import os

import pytest

from data_store import user_store


def test_sanitize_username_strips_illegal_chars():
    assert user_store.sanitize_username('a/b\\c:d*e?f"g<h>i|j') == "a_b_c_d_e_f_g_h_i_j"


def test_sanitize_username_rejects_blank():
    with pytest.raises(ValueError):
        user_store.sanitize_username("   ")


def test_create_or_load_user_default_shape(tmp_path):
    base_dir = str(tmp_path)
    data = user_store.create_or_load_user("王小明", base_dir=base_dir)
    assert data["username"] == "王小明"
    assert data["history"] == []
    assert data["schema_version"] == 1
    # 還沒 save，檔案不應該存在
    assert not os.path.exists(user_store.user_file_path("王小明", base_dir))


def test_save_user_creates_file_and_no_leftover_tmp(tmp_path):
    base_dir = str(tmp_path)
    data = user_store.create_or_load_user("阿寶", base_dir=base_dir)
    user_store.save_user(data, base_dir=base_dir)

    path = user_store.user_file_path("阿寶", base_dir)
    assert os.path.exists(path)
    assert not os.path.exists(path + ".tmp")

    with open(path, encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["username"] == "阿寶"


def test_append_history_record_persists_across_reload(tmp_path):
    base_dir = str(tmp_path)
    user_store.append_history_record(
        "小華", "game1_bilateral_vertical", 87.5, {"foo": "bar"}, base_dir=base_dir,
    )

    reloaded = user_store.create_or_load_user("小華", base_dir=base_dir)
    assert len(reloaded["history"]) == 1
    record = reloaded["history"][0]
    assert record["game_id"] == "game1_bilateral_vertical"
    assert record["score"] == 87.5
    assert record["details"] == {"foo": "bar"}
    assert "record_id" in record and "timestamp" in record


def test_get_history_for_game_filters_and_sorts_and_limits(tmp_path):
    base_dir = str(tmp_path)
    for score in [10, 20, 30]:
        user_store.append_history_record("小美", "game1_bilateral_vertical", score, {}, base_dir=base_dir)
    user_store.append_history_record("小美", "game2_other", 999, {}, base_dir=base_dir)

    records = user_store.get_history_for_game("小美", "game1_bilateral_vertical", base_dir=base_dir)
    assert len(records) == 3
    assert all(r["game_id"] == "game1_bilateral_vertical" for r in records)

    limited = user_store.get_history_for_game("小美", "game1_bilateral_vertical", limit=2, base_dir=base_dir)
    assert len(limited) == 2


def test_corrupt_json_recovers_without_crashing(tmp_path):
    base_dir = str(tmp_path)
    path = user_store.user_file_path("壞掉的人", base_dir)
    os.makedirs(base_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("{this is not valid json")

    data = user_store.create_or_load_user("壞掉的人", base_dir=base_dir)
    assert data["history"] == []
    assert os.path.exists(path + ".corrupt.bak")
    assert not os.path.exists(path)


def test_list_known_usernames(tmp_path):
    base_dir = str(tmp_path)
    user_store.append_history_record("使用者A", "game1_bilateral_vertical", 1, {}, base_dir=base_dir)
    user_store.append_history_record("使用者B", "game1_bilateral_vertical", 1, {}, base_dir=base_dir)

    names = user_store.list_known_usernames(base_dir=base_dir)
    assert set(names) == {"使用者A", "使用者B"}


def test_list_known_display_names_uses_original_username_not_filename(tmp_path):
    # 原始輸入含有頭尾空白，sanitize 後的檔名會跟原始字串不一樣（檔名會被
    # strip）；但 JSON 裡的 "username" 欄位保留使用者「完整原始輸入」，
    # 顯示名稱應該要用這個，不是清理過的檔名。
    base_dir = str(tmp_path)
    user_store.append_history_record("  小美  ", "game1_bilateral_vertical", 1, {}, base_dir=base_dir)

    display_names = user_store.list_known_display_names(base_dir=base_dir)
    assert display_names == ["  小美  "]

    filenames = user_store.list_known_usernames(base_dir=base_dir)
    assert filenames == ["小美"]  # 檔名清單不受這個修正影響，維持原行為


def test_get_cleared_levels_only_counts_passed_records_with_level_id(tmp_path):
    base_dir = str(tmp_path)
    user_store.append_history_record(
        "關卡玩家", "game3_lightsaber_marble", 300,
        {"level_id": "lv1", "passed": True}, base_dir=base_dir,
    )
    user_store.append_history_record(
        "關卡玩家", "game3_lightsaber_marble", 50,
        {"level_id": "lv2", "passed": False}, base_dir=base_dir,
    )
    user_store.append_history_record(
        "關卡玩家", "game3_lightsaber_marble", 999,
        {}, base_dir=base_dir,  # 沒有 level_id 的舊資料/其他情況
    )

    cleared = user_store.get_cleared_levels("關卡玩家", "game3_lightsaber_marble", base_dir=base_dir)
    assert cleared == {"lv1"}


def test_list_known_display_names_skips_corrupt_file(tmp_path):
    base_dir = str(tmp_path)
    user_store.append_history_record("正常使用者", "game1_bilateral_vertical", 1, {}, base_dir=base_dir)
    with open(os.path.join(base_dir, "壞掉.json"), "w", encoding="utf-8") as f:
        f.write("{not valid json")

    display_names = user_store.list_known_display_names(base_dir=base_dir)
    assert display_names == ["正常使用者"]
