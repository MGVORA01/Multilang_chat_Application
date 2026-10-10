"""Security regression tests: each one attacks a trust boundary through the real API/WebSocket."""

import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from tests.integration.conftest import (
    assert_silent,
    recv,
    recv_type,
    register,
    send,
    send_message,
    start_conversation,
)

FOREIGN_ORIGIN = {"origin": "https://evil.example"}


# ---------------------------------------------------------------- authentication / sessions
def test_refresh_token_reuse_revokes_every_session(client: TestClient) -> None:
    """M1: replaying a rotated refresh token (theft) kills all of the user's refresh tokens."""
    register(client, "alice")
    stolen = client.cookies.get("mlchat_refresh")
    assert client.post("/api/v1/auth/refresh").status_code == 200  # owner rotates
    legit = client.cookies.get("mlchat_refresh")

    client.cookies.set("mlchat_refresh", stolen, path="/api/v1/auth")  # attacker replays the old one
    reuse = client.post("/api/v1/auth/refresh")
    assert reuse.status_code == 401 and reuse.json()["error"]["code"] == "refresh_reused"

    client.cookies.set("mlchat_refresh", legit, path="/api/v1/auth")  # the newer token is dead too
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_login_is_limited_per_account_across_ips(client: TestClient) -> None:
    """M2: guessing one account's password from many IPs still hits a per-account budget."""
    register(client, "alice")
    client.app.state.login_limiter.limit = 3  # type: ignore[attr-defined]
    codes = []
    for i in range(5):
        client.app.state.auth_limiter.reset()  # simulate a fresh IP each time  # type: ignore[attr-defined]
        codes.append(client.post("/api/v1/auth/login", json={"login": "ALICE", "password": f"guess-{i}"}).status_code)
    assert codes == [401, 401, 401, 429, 429]


def test_registration_does_not_reveal_which_field_exists(client: TestClient) -> None:
    """L2: the conflict response must not confirm that a given email is registered."""
    register(client, "alice")
    resp = client.post("/api/v1/auth/register", json={
        "username": "someoneelse", "email": "alice@example.com", "password": "password123",
        "display_name": "X", "preferred_language": "eng_Latn"})
    assert resp.status_code == 409
    assert "details" not in resp.json()["error"]


def test_cookie_endpoints_reject_foreign_origins(client: TestClient) -> None:
    """L4: CSRF defence in depth on refresh/logout (the cookie is also SameSite=Strict)."""
    register(client, "alice")
    for path in ("/api/v1/auth/refresh", "/api/v1/auth/logout"):
        resp = client.post(path, headers=FOREIGN_ORIGIN)
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "origin_not_allowed"
    assert client.post("/api/v1/auth/refresh", headers={"origin": "http://localhost:5173"}).status_code == 200


def test_cannot_escalate_through_profile_payload(client: TestClient) -> None:
    """Mass assignment: unknown/privileged fields in the body are ignored, never applied."""
    a = register(client, "alice")
    resp = a.patch("/api/v1/users/me", json={"display_name": "A", "is_active": False, "email": "x@evil.example",
                                               "id": str(uuid.uuid4()), "password_hash": "x"})
    assert resp.status_code == 200
    me = a.get("/api/v1/auth/me").json()
    assert me["is_active"] is True and me["email"] == "alice@example.com" and me["id"] == a.id


def test_profile_image_must_be_https(client: TestClient) -> None:
    """L3: images load in other users' browsers; javascript:/http: are refused."""
    a = register(client, "alice")
    for url in ("http://tracker.example/p.png", "javascript:alert(1)", "data:image/png;base64,AAAA"):
        assert a.patch("/api/v1/users/me", json={"profile_image_url": url}).status_code == 422
    assert a.patch("/api/v1/users/me", json={"profile_image_url": "https://cdn.example/a.png"}).status_code == 200


# ---------------------------------------------------------------- privacy / access control
def test_presence_is_private_to_contacts(client: TestClient) -> None:
    """M3: strangers can find a user but not see whether they're online or when they were last seen."""
    alice = register(client, "alice")
    bob = register(client, "bob")
    stranger = register(client, "stranger")
    start_conversation(alice, bob)
    with alice.ws() as ws:
        recv_type(ws, "session.ready")
        seen_by_stranger = stranger.get("/api/v1/users", params={"q": "alice"}).json()["items"][0]
        assert seen_by_stranger["is_online"] is False and seen_by_stranger["last_seen_at"] is None
        assert stranger.get(f"/api/v1/users/{alice.id}").json()["is_online"] is False
        assert bob.get(f"/api/v1/users/{alice.id}").json()["is_online"] is True  # contacts still see it


def test_injection_style_input_is_inert(client: TestClient) -> None:
    """Search/path inputs are parameters, never SQL; malformed IDs are rejected by validation."""
    a = register(client, "alice")
    for q in ("' OR '1'='1", "%' --", "\\x00; DROP TABLE users;--"):
        resp = a.get("/api/v1/users", params={"q": q})
        assert resp.status_code == 200 and resp.json()["total"] == 0
    assert a.get("/api/v1/conversations/1 OR 1=1/messages").status_code == 422
    assert a.get("/api/v1/users").status_code == 200  # users table intact


def test_read_receipts_cannot_target_other_conversations(client: TestClient) -> None:
    """A member of conversation X can't mark messages of conversation Y as read via X."""
    a = register(client, "alice")
    b = register(client, "bob")
    eve = register(client, "eve")
    cid_ab = start_conversation(a, b)
    cid_ae = start_conversation(a, eve)
    with a.ws() as ws_a, eve.ws() as ws_e:
        send_message(ws_a, cid_ab, "private")
        private_id = recv_type(ws_a, "message.created")["payload"]["message"]["id"]
        send(ws_e, "message.read", {"conversation_id": cid_ae, "message_id": private_id})
        assert recv_type(ws_e, "error")["payload"]["code"] == "message_not_found"
        send(ws_e, "message.read", {"conversation_id": cid_ab, "message_id": private_id})
        assert recv_type(ws_e, "error")["payload"]["code"] == "conversation_not_found"
        assert_silent(ws_a, ignore=("presence.updated", "message.translated"))


# ---------------------------------------------------------------- WebSocket abuse
def test_send_limit_is_shared_across_connections(client: TestClient) -> None:
    """M4: opening more sockets must not multiply the per-user message budget."""
    a = register(client, "alice")
    b = register(client, "bob")
    cid = start_conversation(a, b)
    client.app.state.ws_send_limiter.limit = 2  # type: ignore[attr-defined]
    with a.ws() as ws1, a.ws() as ws2:
        send_message(ws1, cid, "one")
        recv_type(ws1, "message.created")
        send_message(ws2, cid, "two")
        recv_type(ws2, "message.created")
        send_message(ws2, cid, "three")  # third message from a *different* socket
        assert recv_type(ws2, "error")["payload"]["code"] == "rate_limited"


def test_connections_per_user_are_capped(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    a = register(client, "alice")
    monkeypatch.setattr(get_settings(), "WS_MAX_CONNECTIONS_PER_USER", 2)
    with a.ws() as one, a.ws() as two:
        recv_type(one, "session.ready")
        recv_type(two, "session.ready")
        with a.ws() as three:
            assert recv(three)["payload"]["code"] == "too_many_connections"
            with pytest.raises(WebSocketDisconnect) as exc:
                recv(three)
            assert exc.value.code == 4429


def test_event_flood_is_limited_per_connection(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    a = register(client, "alice")
    monkeypatch.setattr(get_settings(), "WS_EVENTS_PER_10S", 3)
    with a.ws() as ws:
        recv_type(ws, "session.ready")
        for _ in range(4):
            send(ws, "ping", {})
        events = [recv(ws) for _ in range(4)]
        assert [e["type"] for e in events][:3] == ["pong", "pong", "pong"]
        assert events[3]["payload"]["code"] == "rate_limited"


def test_ws_tickets_are_rate_limited(client: TestClient) -> None:
    a = register(client, "alice")
    client.app.state.ticket_limiter.limit = 2  # type: ignore[attr-defined]
    codes = [a.post("/api/v1/auth/ws-ticket").status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_translation_retry_is_rate_limited(client: TestClient) -> None:
    """M5: retries trigger model inference, so they share the per-user inference budget."""
    a = register(client, "alice", "guj_Gujr")
    b = register(client, "bob", "hin_Deva")
    cid = start_conversation(a, b)
    with a.ws() as ws:
        send_message(ws, cid, "નમસ્તે")
        mid = recv_type(ws, "message.created")["payload"]["message"]["id"]
    client.app.state.translate_limiter.limit = 2  # type: ignore[attr-defined]
    codes = [b.post(f"/api/v1/messages/{mid}/translations/retry", json={"target_language": lang}).status_code
             for lang in ("eng_Latn", "tam_Taml", "ben_Beng")]
    assert codes == [202, 202, 429]


def test_failed_translation_does_not_leak_internal_error_text(client: TestClient) -> None:
    """M8: chat members see a generic reason; engine/exception details stay in server logs."""
    a = register(client, "alice", "guj_Gujr")
    b = register(client, "bob", "hin_Deva")
    cid = start_conversation(a, b)
    client.app.state.translator.engine.fail_all = True  # type: ignore[attr-defined]
    with a.ws() as ws_a, b.ws() as ws_b:
        send_message(ws_a, cid, "will fail")
        tr = recv_type(ws_b, "message.translated")["payload"]
        assert tr["status"] == "failed"
        assert tr["error_message"] == "Translation failed"


# ---------------------------------------------------------------- HTTP hardening
def test_security_headers_on_api_responses(client: TestClient) -> None:
    """M6: nosniff, no framing, no referrer, locked-down CSP; tokens never cached."""
    resp = client.get("/api/v1/languages")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in resp.headers["content-security-policy"]
    login = client.post("/api/v1/auth/register", json={
        "username": "alice", "email": "alice@example.com", "password": "password123",
        "display_name": "A", "preferred_language": "eng_Latn"})
    assert login.headers["cache-control"] == "no-store"
    error = client.get("/api/v1/auth/me")  # error responses get the headers too
    assert error.status_code == 401 and error.headers["x-content-type-options"] == "nosniff"


def test_oversized_request_bodies_are_rejected(client: TestClient) -> None:
    """M6: bodies are capped before the app parses them (declared or streamed)."""
    big = "x" * (get_settings().MAX_REQUEST_BODY_BYTES + 1)
    declared = client.post("/api/v1/auth/login", content=big, headers={"content-type": "application/json"})
    assert declared.status_code == 413 and declared.json()["error"]["code"] == "payload_too_large"

    def chunks():  # type: ignore[no-untyped-def]
        for _ in range(100):
            yield b"x" * 1024  # no Content-Length: streamed

    streamed = client.post("/api/v1/auth/login", content=chunks(), headers={"content-type": "application/json"})
    assert streamed.status_code == 413


def test_metrics_can_be_disabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    a = register(client, "alice")
    assert a.get("/api/v1/metrics").status_code == 200
    monkeypatch.setattr(get_settings(), "METRICS_ENABLED", False)
    assert a.get("/api/v1/metrics").status_code == 404


def test_health_hides_error_details_in_production(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = client.app.state.translator.engine  # type: ignore[attr-defined]
    monkeypatch.setattr(engine, "status", lambda: {"indic-indic": {"state": "error", "error": "secret /home/x path"}})
    assert "secret" in client.get("/api/v1/health").text
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    assert "secret" not in client.get("/api/v1/health").text
