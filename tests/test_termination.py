from src.app.main import _is_termination, _speaker_selection_with_hard_stop


class _DummyGroupChat:
    def __init__(self, messages):
        self.messages = messages


def test_is_termination_accepts_terminate_at_end():
    assert _is_termination("交付完成\nTERMINATE") is True


def test_is_termination_accepts_message_dict():
    message = {"content": "最终验收通过\nTERMINATE"}

    assert _is_termination(message) is True


def test_is_termination_rejects_non_terminate_message():
    assert _is_termination("交付完成") is False


def test_is_termination_rejects_terminate_not_at_end():
    assert _is_termination("TERMINATE 交付完成") is False


def test_speaker_selection_hard_stop_when_terminated():
    groupchat = _DummyGroupChat([{"content": "验收通过\nTERMINATE"}])

    assert _speaker_selection_with_hard_stop(None, groupchat) is None


def test_speaker_selection_auto_when_not_terminated():
    groupchat = _DummyGroupChat([{"content": "继续执行下一步"}])

    assert _speaker_selection_with_hard_stop(None, groupchat) == "auto"
