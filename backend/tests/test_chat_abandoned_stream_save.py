"""An abandoned chat stream keeps the question (16 Oct 2026).

/api/chat/stream saved the question and the answer only after the stream finished, so
a closed tab or a cut stream left an empty chat: 37 since 11 Sep, and the question was
lost to /audit-queries. Verified end to end on 16 Oct: a stream cut after 1,500 bytes
kept the question, the 280-character partial answer and an `abandoned_streams` entry.
"""
import uuid
from types import SimpleNamespace

import api.chat as chat_api


class _Q:
    def __init__(self, obj):
        self.obj = obj

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self.obj


class _DB:
    def __init__(self, chat):
        self.chat, self.added, self.commits = chat, [], 0

    def query(self, *_a):
        return _Q(self.chat)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


def _run(monkeypatch, content, abandoned):
    chat = SimpleNamespace(id=uuid.uuid4(), title=None, message_count=0, total_tokens_used=0,
                           last_message_at=None, last_message_preview=None, chat_metadata={"is_probe": True})
    db = _DB(chat)
    monkeypatch.setattr(chat_api, "SessionLocal", lambda: db)
    chat_api._save_messages(str(chat.id), "Question?", content, assistant_message_id=str(uuid.uuid4()),
                            abandoned=abandoned)
    return chat, db


def test_abandoned_with_partial_answer_keeps_both_and_records_it(monkeypatch):
    chat, db = _run(monkeypatch, "Partial answer", abandoned=True)
    roles = [m.role for m in db.added]
    assert roles == ["user", "assistant"]
    assert chat.message_count == 2
    entry = chat.chat_metadata["abandoned_streams"][0]
    assert entry["partial_chars"] == len("Partial answer") and entry["assistant_message_id"]
    assert chat.chat_metadata["is_probe"] is True


def test_abandoned_before_any_text_keeps_the_question_only(monkeypatch):
    chat, db = _run(monkeypatch, "", abandoned=True)
    assert [m.role for m in db.added] == ["user"]
    assert chat.message_count == 1
    assert chat.chat_metadata["abandoned_streams"][0]["assistant_message_id"] is None


def test_a_finished_stream_is_saved_as_before(monkeypatch):
    chat, db = _run(monkeypatch, "Full answer", abandoned=False)
    assert [m.role for m in db.added] == ["user", "assistant"]
    assert chat.message_count == 2
    assert "abandoned_streams" not in chat.chat_metadata


def test_the_stream_saves_in_a_finally_guarded_by_a_flag():
    import inspect
    src = inspect.getsource(chat_api)
    assert "save_started = True" in src and "abandoned=True" in src and "if not save_started:" in src
