"""Source-language detection and translation targeting in the message flow."""

from fastapi.testclient import TestClient

from tests.integration.conftest import recv_type, register, send_message, start_conversation


def test_english_between_english_readers_is_not_translated(client: TestClient) -> None:
    a = register(client, "alice", "hin_Deva")  # reads Hindi but types English
    b = register(client, "bob", "eng_Latn")
    cid = start_conversation(a, b)
    with a.ws() as ws_a:
        send_message(ws_a, cid, "Hello this is meet.")  # no source_language -> auto-detect
        msg = recv_type(ws_a, "message.created")["payload"]["message"]
        assert msg["source_language"] == "eng_Latn"
        assert msg["translations"] == []  # recipient reads English: nothing to translate


def test_explicit_source_language_is_respected(client: TestClient) -> None:
    a = register(client, "alice", "eng_Latn")
    b = register(client, "bob", "guj_Gujr")
    cid = start_conversation(a, b)
    with a.ws() as ws_a:
        send_message(ws_a, cid, "namaste", source_language="hin_Deva")
        msg = recv_type(ws_a, "message.created")["payload"]["message"]
        assert msg["source_language"] == "hin_Deva"


def test_emoji_only_message_is_not_translated(client: TestClient) -> None:
    a = register(client, "alice", "guj_Gujr")
    b = register(client, "bob", "hin_Deva")
    cid = start_conversation(a, b)
    with a.ws() as ws_a:
        send_message(ws_a, cid, "👍🏽🎉 100")
        msg = recv_type(ws_a, "message.created")["payload"]["message"]
        assert msg["translations"] == []
        send_message(ws_a, cid, "અભિનંદન 🎉")  # emoji mixed with words is still translated
        msg = recv_type(ws_a, "message.created")["payload"]["message"]
        assert [t["target_language"] for t in msg["translations"]] == ["hin_Deva"]
