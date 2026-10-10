import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.integration.conftest import assert_silent, recv, recv_type, register, send, send_message, start_conversation


def test_ws_rejects_missing_or_reused_ticket(client: TestClient) -> None:
    a = register(client, "alice")
    with client.websocket_connect("/ws/chat?ticket=bogus") as ws:
        assert recv(ws)["payload"]["code"] == "unauthorized"
        with pytest.raises(WebSocketDisconnect) as exc:
            recv(ws)
        assert exc.value.code == 4401

    ticket = a.post("/api/v1/auth/ws-ticket").json()["ticket"]
    with client.websocket_connect(f"/ws/chat?ticket={ticket}") as ws:
        assert recv(ws)["type"] == "session.ready"
    with client.websocket_connect(f"/ws/chat?ticket={ticket}") as ws:  # single use
        assert recv(ws)["payload"]["code"] == "unauthorized"


def test_ws_rejects_foreign_origin(client: TestClient) -> None:
    a = register(client, "alice")
    ticket = a.post("/api/v1/auth/ws-ticket").json()["ticket"]
    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect(f"/ws/chat?ticket={ticket}", headers={"origin": "https://evil.example"}),
    ):
        pass
    assert exc.value.code == 4403


def test_ping_and_invalid_events(client: TestClient) -> None:
    a = register(client, "alice")
    with a.ws() as ws:
        recv_type(ws, "session.ready")
        cid = send(ws, "ping", {})
        pong = recv_type(ws, "pong")
        assert pong["correlation_id"] == cid

        ws.send_text("not json")
        assert recv(ws)["payload"]["code"] == "invalid_event"
        send(ws, "nope.unknown", {})
        assert recv(ws)["payload"]["code"] == "unknown_event"
        send(ws, "message.send", {"conversation_id": "not-a-uuid", "text": "", "client_message_id": "x"})
        err = recv(ws)["payload"]
        assert err["code"] == "validation_error"
        # client cannot smuggle a sender id
        send(ws, "message.send", {"conversation_id": "00000000-0000-0000-0000-000000000000", "text": "hi",
                                  "client_message_id": "x", "sender_id": "someone"})
        assert recv(ws)["payload"]["code"] == "validation_error"
        ws.send_text("x" * 20000)
        assert recv(ws)["payload"]["code"] == "payload_too_large"
        # socket still usable after errors
        send(ws, "ping", {})
        assert recv_type(ws, "pong")


def test_two_users_translated_delivery(client: TestClient) -> None:
    """Gujarati user -> Hindi user, and the reply back, over WebSockets (mock translator)."""
    a = register(client, "alice", "guj_Gujr")
    b = register(client, "bob", "hin_Deva")
    cid = start_conversation(a, b)
    with a.ws() as ws_a, b.ws() as ws_b:
        recv_type(ws_a, "session.ready")
        recv_type(ws_b, "session.ready")

        corr = send_message(ws_a, cid, "તમે કેમ છો?")
        ack = recv_type(ws_a, "message.created")
        assert ack["correlation_id"] == corr
        msg = ack["payload"]["message"]
        assert msg["sender_id"] == a.id
        assert msg["source_language"] == "guj_Gujr"
        assert msg["status"] == "delivered"  # bob is online
        assert msg["translations"][0]["status"] == "pending"
        assert msg["translations"][0]["model_name"] == "ai4bharat/indictrans2-indic-indic-dist-320M"

        incoming = recv_type(ws_b, "message.created")["payload"]["message"]
        assert incoming["id"] == msg["id"]
        assert incoming["original_text"] == "તમે કેમ છો?"

        tr = recv_type(ws_b, "message.translated")["payload"]
        assert tr["message_id"] == msg["id"]
        assert tr["status"] == "completed"
        assert tr["target_language"] == "hin_Deva"
        assert tr["translated_text"] == "[hin_Deva] તમે કેમ છો?"

        # Bob replies in Hindi; Alice gets Gujarati
        send_message(ws_b, cid, "मैं ठीक हूँ")
        recv_type(ws_b, "message.created")
        # Alice also receives the hin_Deva translation event for her own message; skip to hers.
        reply_tr = recv_type(ws_a, "message.translated")["payload"]
        while reply_tr["target_language"] != "guj_Gujr":
            reply_tr = recv_type(ws_a, "message.translated")["payload"]
        assert reply_tr["status"] == "completed"
        assert reply_tr["translated_text"] == "[guj_Gujr] मैं ठीक हूँ"

        # read receipts
        send(ws_b, "message.read", {"conversation_id": cid, "message_id": msg["id"]})
        read = recv_type(ws_a, "message.read")["payload"]
        assert read["user_id"] == b.id and msg["id"] in read["message_ids"]


def test_english_routes_to_dedicated_checkpoints(client: TestClient) -> None:
    a = register(client, "alice", "eng_Latn")
    b = register(client, "bob", "hin_Deva")
    cid = start_conversation(a, b)
    with a.ws() as ws_a, b.ws() as ws_b:
        send_message(ws_a, cid, "Hello")
        m = recv_type(ws_a, "message.created")["payload"]["message"]
        assert m["translations"][0]["model_name"] == "ai4bharat/indictrans2-en-indic-dist-200M"
        recv_type(ws_b, "message.translated")
        send_message(ws_b, cid, "नमस्ते")
        m = recv_type(ws_b, "message.created")["payload"]["message"]
        assert m["translations"][0]["model_name"] == "ai4bharat/indictrans2-indic-en-dist-200M"


def test_no_cross_user_leakage(client: TestClient) -> None:
    a = register(client, "alice", "guj_Gujr")
    b = register(client, "bob", "hin_Deva")
    eve = register(client, "eve", "hin_Deva")
    cid = start_conversation(a, b)
    with a.ws() as ws_a, b.ws() as ws_b, eve.ws() as ws_e:
        recv_type(ws_e, "session.ready")
        send(ws_a, "typing.start", {"conversation_id": cid})
        assert recv_type(ws_b, "typing.started")["payload"]["user_id"] == a.id
        send_message(ws_a, cid, "secret")
        recv_type(ws_b, "message.translated")
        assert_silent(ws_e)

        # eve cannot send into or read the conversation
        send_message(ws_e, cid, "let me in")
        assert recv_type(ws_e, "error")["payload"]["code"] == "conversation_not_found"
        send(ws_e, "typing.start", {"conversation_id": cid})
        assert recv_type(ws_e, "error")["payload"]["code"] == "conversation_not_found"
        assert_silent(ws_b, ignore=("presence.updated", "typing.started"))


def test_multiple_connections_per_user(client: TestClient) -> None:
    a = register(client, "alice", "guj_Gujr")
    b = register(client, "bob", "guj_Gujr")
    cid = start_conversation(a, b)
    with a.ws() as phone, a.ws() as desktop, b.ws() as ws_b:
        send_message(ws_b, cid, "hello both")
        assert recv_type(phone, "message.created")["payload"]["message"]["original_text"] == "hello both"
        assert recv_type(desktop, "message.created")["payload"]["message"]["original_text"] == "hello both"


def test_duplicate_client_message_id(client: TestClient) -> None:
    a = register(client, "alice", "guj_Gujr")
    b = register(client, "bob", "hin_Deva")
    cid = start_conversation(a, b)
    with a.ws() as ws_a:
        send_message(ws_a, cid, "once", client_message_id="client-1")
        first = recv_type(ws_a, "message.created")["payload"]
        send_message(ws_a, cid, "once", client_message_id="client-1")  # retry after network blip
        second = recv_type(ws_a, "message.created")["payload"]
        assert second["duplicate"] is True
        assert second["message"]["id"] == first["message"]["id"]
    items = a.get(f"/api/v1/conversations/{cid}/messages").json()["items"]
    assert len(items) == 1


def test_presence(client: TestClient) -> None:
    a = register(client, "alice")
    b = register(client, "bob")
    start_conversation(a, b)
    with a.ws() as ws_a:
        recv_type(ws_a, "session.ready")
        with b.ws():
            ev = recv_type(ws_a, "presence.updated")["payload"]
            assert ev == {**ev, "user_id": b.id, "online": True}
            conv = a.get("/api/v1/conversations").json()["items"][0]
            assert any(m["id"] == b.id and m["is_online"] for m in conv["members"])
        ev = recv_type(ws_a, "presence.updated")["payload"]
        assert ev["user_id"] == b.id and ev["online"] is False
    assert a.get(f"/api/v1/users/{b.id}").json()["last_seen_at"] is not None


def test_message_length_limit(client: TestClient) -> None:
    a = register(client, "alice")
    b = register(client, "bob")
    cid = start_conversation(a, b)
    with a.ws() as ws:
        send_message(ws, cid, "a" * 2001)
        assert recv_type(ws, "error")["payload"]["code"] == "message_too_long"
        send_message(ws, cid, "   ")
        assert recv_type(ws, "error")["payload"]["code"] == "empty_message"


def test_session_ready_only_lists_contacts(client: TestClient) -> None:
    a = register(client, "alice")
    b = register(client, "bob")
    stranger = register(client, "stranger")
    start_conversation(a, b)
    with b.ws(), stranger.ws(), a.ws() as ws_a:
        ready = recv_type(ws_a, "session.ready")["payload"]
        assert ready["online_user_ids"] == [b.id]
