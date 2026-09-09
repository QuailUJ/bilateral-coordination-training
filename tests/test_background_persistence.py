from concurrent.futures import Future
from types import SimpleNamespace
from common.background_persistence import begin_result_save,poll_result_save
from data_store import user_store


def test_failed_save_retains_payload_and_retry_id():
    f=Future();calls=[]
    service=SimpleNamespace(save_result=lambda *args:(calls.append(args),f)[1])
    ctx=SimpleNamespace(current_user="test",persistence=service)
    scene=SimpleNamespace(state="playing")
    begin_result_save(scene,ctx,"game",4,{"analysis":{"frames":[1,2]}})
    payload=scene._save_payload
    f.set_exception(OSError("disk unavailable"))
    poll_result_save(scene)
    assert scene.state=="settling"
    assert scene.save_error=="disk unavailable"
    assert scene._save_payload==payload
    f2=Future();scene._save_future=f2;f2.set_result({})
    poll_result_save(scene)
    assert scene.state=="result"


def test_retry_does_not_duplicate_a_record_already_written(tmp_path):
    for _ in range(2):
        user_store.append_history_record("test","game",5,{"passed":True},str(tmp_path),record_id="same-job")
    data=user_store.create_or_load_user("test",str(tmp_path))
    assert len(data["history"])==1


def test_cached_user_is_invalidated_by_external_change(tmp_path):
    import json
    from pathlib import Path
    user_store.append_history_record("test","game",1,{},str(tmp_path))
    path=Path(user_store.user_file_path("test",str(tmp_path)))
    data=json.loads(path.read_text(encoding="utf-8"))
    data["history"][0]["score"]=98765
    path.write_text(json.dumps(data),encoding="utf-8")
    assert user_store.get_history_for_game("test","game",base_dir=str(tmp_path))[0]["score"]==98765
