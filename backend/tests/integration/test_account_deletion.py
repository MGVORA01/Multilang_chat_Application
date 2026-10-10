import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from starlette.websockets import WebSocketDisconnect

from tests.integration.conftest import recv, recv_type, register, send_message, start_conversation


def _delete(session, password: str = "password123"):  # type: ignore[no-untyped-def]
    return session.client.request("DELETE", "/api/v1/users/me", headers=session.headers,
                                  json={"password": password})


def _counts(user_id: str) -> dict[str, int]:
    """Rows still referencing the user, read straight from PostgreSQL."""
    queries = {
        "users": "SELECT count(*) FROM users WHERE id = :u",
        "refresh_tokens": "SELECT count(*) FROM refresh_tokens WHERE user_id = :u",
        "memberships": "SELECT count(*) FROM conversation_members WHERE user_id = :u",
        "messages_sent": "SELECT count(*) FROM messages WHERE sender_id = :u",
        "receipts": "SELECT count(*) FROM message_receipts WHERE user_id = :u",
    }

    async def go() -> dict[str, int]:
        engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
        async with engine.connect() as conn:
            out = {k: (await conn.execute(text(q), {"u": user_id})).scalar_one() for k, q in queries.items()}
            out["conversations"] = (await conn.execute(text("SELECT count(*) FROM conversations"))).scalar_one()
            out["all_messages"] = (await conn.execute(text("SELECT count(*) FROM messages"))).scalar_one()
            out["translations"] = (await conn.execute(text("SELECT count(*) FROM message_translations"))).scalar_one()
        await engine.dispose()
        return out

    return asyncio.run(go())


def test_wrong_password_does_not_delete(client: TestClient) -> None:
    a = register(client, "alice")
    resp = _delete(a, "wrong-password")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "invalid_password"
    assert a.get("/api/v1/auth/me").status_code == 200


def test_delete_account_removes_everything(client: TestClient) -> None:
    a = register(client, "alice", "guj_Gujr")
    b = register(client, "bob", "hin_Deva")
    cid = start_conversation(a, b)
    with a.ws() as ws_a, b.ws() as ws_b:
        send_message(ws_a, cid, "તમે કેમ છો?")
        recv_type(ws_b, "message.translated")
        send_message(ws_b, cid, "मैं ठीक हूँ")
        recv_type(ws_a, "message.translated")
        before = _counts(a.id)
        assert before["users"] == 1 and before["messages_sent"] == 1 and before["all_messages"] == 2

        assert _delete(a).status_code == 204

        # bob's copy of the chat disappears live
        removed = recv_type(ws_b, "conversation.removed")["payload"]
        assert removed == {"conversation_id": cid, "reason": "account_deleted"}

        # alice's open socket is closed with 4410
        with pytest.raises(WebSocketDisconnect) as exc:
            while True:
                recv(ws_a)
        assert exc.value.code == 4410

    # Nothing left in the database: user, tokens, memberships, both sides' messages, translations
    after = _counts(a.id)
    assert after == {"users": 0, "refresh_tokens": 0, "memberships": 0, "messages_sent": 0, "receipts": 0,
                     "conversations": 0, "all_messages": 0, "translations": 0}

    # old access token, refresh cookie and password no longer work
    assert a.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/refresh").status_code == 401
    assert client.post("/api/v1/auth/login", json={"login": "alice", "password": "password123"}).status_code == 401
    assert b.get("/api/v1/conversations").json()["items"] == []
    assert b.get(f"/api/v1/conversations/{cid}/messages").status_code == 404

    # bob is untouched; username/email can be registered again
    assert b.get("/api/v1/auth/me").status_code == 200
    assert register(client, "alice", "eng_Latn").id != a.id
