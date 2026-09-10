import pytest
from common.timed_training import CompletionSync


@pytest.mark.parametrize("delay,score", [(0.0,1),(.3,1),(.301,0),(.8,0)])
def test_completion_window(delay,score):
    tracker=CompletionSync()
    tracker.update(1,1,0)
    tracker.update(1+delay,1,1)
    assert tracker.score==score
    tracker.update(2,1,1)
    assert tracker.score==score


def test_unmatched_completions_expire_instead_of_pairing_later():
    tracker=CompletionSync()
    tracker.update(1,1,0)
    tracker.update(2,2,0)
    tracker.update(3,2,1)
    assert tracker.score==0
    tracker.update(4,3,2)
    assert tracker.score==1
