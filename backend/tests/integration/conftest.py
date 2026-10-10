"""Integration fixtures: real PostgreSQL (migrated with Alembic) and the full app via TestClient."""

import asyncio
import json
import os
import uuid
from collections.abc import Iterator
from typing import Any

import anyio
import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB:
    pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database to run integration tests",
                allow_module_level=True)

from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from app.main import app

TABLES = "message_receipts, message_translations, conversation_members, messages, conversations, refresh_tokens, users"


def _run_sql(*statements: str) -> None:
    async def go() -> None:
        engine = create_async_engine(TEST_DB, poolclass=NullPool)
        async with engine.begin() as conn:
            for sql in statements:
                await conn.execute(text(sql))
        await engine.dispose()

    asyncio.run(go())


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    _run_sql("DROP SCHEMA public CASCADE", "CREATE SCHEMA public")
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "..", "alembic"))
    command.upgrade(cfg, "head")  # exercises the real migration
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    _run_sql(f"TRUNCATE {TABLES} CASCADE")
    with TestClient(app) as c:
        yield c


class Session:
    """A registered user with an access token."""

    def __init__(self, client: TestClient, data: dict[str, Any]) -> None:
        self.client = client
        self.token = data["access_token"]
        self.user = data["user"]
        self.id = self.user["id"]

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, url: str, **kw: Any) -> Any:
        return self.client.get(url, headers=self.headers, **kw)

    def post(self, url: str, **kw: Any) -> Any:
        return self.client.post(url, headers=self.headers, **kw)

    def patch(self, url: str, **kw: Any) -> Any:
        return self.client.patch(url, headers=self.headers, **kw)

    def ws(self) -> Any:
        ticket = self.post("/api/v1/auth/ws-ticket").json()["ticket"]
        return self.client.websocket_connect(f"/ws/chat?ticket={ticket}")


def register(client: TestClient, username: str, lang: str = "eng_Latn", password: str = "password123") -> Session:
    resp = client.post("/api/v1/auth/register", json={
        "username": username, "email": f"{username}@example.com", "password": password,
        "display_name": username.title(), "preferred_language": lang,
    })
    assert resp.status_code == 201, resp.text
    return Session(client, resp.json())


def start_conversation(a: Session, b: Session) -> str:
    resp = a.post("/api/v1/conversations", json={"participant_id": b.id})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def recv(ws: Any, timeout: float = 5.0) -> dict[str, Any]:
    async def _r() -> Any:
        with anyio.fail_after(timeout):
            return await ws._send_rx.receive()

    message = ws.portal.call(_r)
    ws._raise_on_close(message)
    return json.loads(message["text"])


def recv_type(ws: Any, type_: str, timeout: float = 5.0) -> dict[str, Any]:
    """Receive events until one of `type_` arrives (skipping presence/ready noise)."""
    while True:
        event = recv(ws, timeout)
        if event["type"] == type_:
            return event
        if event["type"] == "error" and type_ != "error":
            raise AssertionError(f"unexpected error event: {event}")


def assert_silent(ws: Any, timeout: float = 0.5, ignore: tuple[str, ...] = ("presence.updated",)) -> None:
    try:
        while True:
            event = recv(ws, timeout)
            if event["type"] not in ignore:
                raise AssertionError(f"expected no events, got {event}")
    except TimeoutError:
        return


def send(ws: Any, type_: str, payload: dict[str, Any], cid: str | None = None) -> str:
    cid = cid or uuid.uuid4().hex
    ws.send_json({"type": type_, "id": cid, "payload": payload})
    return cid


def send_message(ws: Any, conversation_id: str, text: str, client_message_id: str | None = None,
                 **extra: Any) -> str:
    return send(ws, "message.send", {"conversation_id": conversation_id, "text": text,
                                     "client_message_id": client_message_id or uuid.uuid4().hex, **extra})

