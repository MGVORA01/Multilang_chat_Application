"""End-to-end acceptance test against a running stack (spec section 14).

    cd backend
    .venv/bin/python -m scripts.e2e_acceptance --base http://localhost:5173 [--db postgresql://...]

--base: frontend dev server (exercises the Vite proxy) or backend (http://localhost:8000).
--db:   optional plain postgresql:// URL to verify persistence directly in PostgreSQL.
Works with TRANSLATION_BACKEND=indictrans2 (real model) or mock. Step 11 forces a failure only
with the mock backend; with the real model it verifies retry on an existing message instead.
"""

import argparse
import asyncio
import json
import re
import sys
import time
import uuid

import httpx
import websockets

GUJ = re.compile(r"[઀-૿]")
DEVA = re.compile(r"[ऀ-ॿ]")
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)


class Client:
    def __init__(self, base: str, name: str, lang: str, origin: str) -> None:
        self.base = base
        self.origin = origin
        self.http = httpx.AsyncClient(base_url=base, timeout=30)
        suffix = uuid.uuid4().hex[:6]
        self.username = f"{name}_{suffix}"
        self.lang = lang
        self.token = ""
        self.id = ""
        self.ws: websockets.ClientConnection | None = None
        self.events: asyncio.Queue[dict] = asyncio.Queue()

    @property
    def h(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def register_and_login(self) -> bool:
        r = await self.http.post("/api/v1/auth/register", json={
            "username": self.username, "email": f"{self.username}@example.com", "password": "password123",
            "display_name": self.username, "preferred_language": self.lang})
        if r.status_code != 201:
            return False
        r = await self.http.post("/api/v1/auth/login", json={"login": self.username, "password": "password123"})
        self.token = r.json()["access_token"]
        self.id = r.json()["user"]["id"]
        return r.status_code == 200

    async def connect(self) -> None:
        ticket = (await self.http.post("/api/v1/auth/ws-ticket", headers=self.h)).json()["ticket"]
        url = self.base.replace("http", "ws", 1) + f"/ws/chat?ticket={ticket}"
        self.ws = await websockets.connect(url, origin=self.origin)
        asyncio.create_task(self._reader())

    async def _reader(self) -> None:
        assert self.ws
        try:
            async for raw in self.ws:
                await self.events.put(json.loads(raw))
        except websockets.ConnectionClosed:
            pass

    async def wait_for(self, pred, timeout: float) -> dict | None:  # type: ignore[no-untyped-def]
        deadline = time.monotonic() + timeout
        while (left := deadline - time.monotonic()) > 0:
            try:
                ev = await asyncio.wait_for(self.events.get(), left)
            except TimeoutError:
                return None
            if pred(ev):
                return ev
        return None

    async def send(self, conversation_id: str, text: str) -> str:
        assert self.ws
        cmid = uuid.uuid4().hex
        await self.ws.send(json.dumps({"type": "message.send", "id": cmid, "payload": {
            "conversation_id": conversation_id, "text": text, "client_message_id": cmid}}))
        return cmid


async def main(base: str, db: str | None, timeout: float, origin: str) -> int:
    a = Client(base, "guj_user", "guj_Gujr", origin)
    b = Client(base, "hin_user", "hin_Deva", origin)
    eve = Client(base, "intruder", "eng_Latn", origin)

    check("1. both users can register and log in", await a.register_and_login() and await b.register_and_login())
    await eve.register_and_login()
    backend = (await a.http.get("/api/v1/health")).json()["translation"]["backend"]
    print(f"    translation backend: {backend}")

    r1 = await a.http.post("/api/v1/conversations", json={"participant_id": b.id}, headers=a.h)
    r2 = await b.http.post("/api/v1/conversations", json={"participant_id": a.id}, headers=b.h)
    cid = r1.json()["id"]
    check("2. both open the same conversation", r1.json()["id"] == r2.json()["id"], f"status {r1.status_code}/{r2.status_code}")

    await a.connect()
    await b.connect()
    guj_text = "તમે કેમ છો?"
    cmid = await a.send(cid, guj_text)
    ack = await a.wait_for(lambda e: e["type"] == "message.created" and e["correlation_id"] == cmid, 10)
    msg_id = ack["payload"]["message"]["id"] if ack else None
    check("3. user A sends a Gujarati message (acknowledged)", msg_id is not None)

    persisted = False
    if db:
        import asyncpg

        conn = await asyncpg.connect(db)
        row = await conn.fetchrow("SELECT original_text, source_language FROM messages WHERE id = $1", uuid.UUID(msg_id))
        await conn.close()
        persisted = bool(row) and row["original_text"] == guj_text and row["source_language"] == "guj_Gujr"
        check("4. original message persisted in PostgreSQL (direct SQL)", persisted)
    else:
        hist = (await a.http.get(f"/api/v1/conversations/{cid}/messages", headers=a.h)).json()["items"]
        persisted = any(m["id"] == msg_id and m["original_text"] == guj_text for m in hist)
        check("4. original message persisted (via history API; pass --db for direct SQL)", persisted)

    created_b = await b.wait_for(lambda e: e["type"] == "message.created" and e["payload"]["message"]["id"] == msg_id, 10)
    t0 = time.monotonic()
    tr = await b.wait_for(lambda e: e["type"] == "message.translated" and e["payload"]["message_id"] == msg_id
                          and e["payload"]["status"] != "pending", timeout)
    latency = time.monotonic() - t0
    ok5 = bool(tr) and tr["payload"]["status"] == "completed" and tr["payload"]["target_language"] == "hin_Deva"
    check("5. backend generated a Hindi translation", ok5,
          f"{tr['payload']['translated_text']!r} via {tr['payload']['model_name']} ({latency:.1f}s after delivery)" if tr else "timeout")
    if backend == "indictrans2" and tr:
        check("   translation is in Devanagari script", bool(DEVA.search(tr["payload"]["translated_text"] or "")))
    check("6. user B received the translated message over WebSocket", bool(created_b and tr))
    check("7. user B can view the original text", bool(created_b) and created_b["payload"]["message"]["original_text"] == guj_text)

    hin_text = "मैं ठीक हूँ, धन्यवाद।"
    reply_cmid = await b.send(cid, hin_text)
    ack_b = await b.wait_for(lambda e: e["type"] == "message.created" and e["correlation_id"] == reply_cmid, 10)
    reply_id = ack_b["payload"]["message"]["id"] if ack_b else None
    check("8. user B replies in Hindi", reply_id is not None)
    tr_a = await a.wait_for(lambda e: e["type"] == "message.translated" and e["payload"]["message_id"] == reply_id
                            and e["payload"]["status"] != "pending", timeout)
    ok9 = bool(tr_a) and tr_a["payload"]["status"] == "completed" and tr_a["payload"]["target_language"] == "guj_Gujr"
    check("9. user A receives the Gujarati translation", ok9, repr(tr_a["payload"]["translated_text"]) if tr_a else "timeout")
    if backend == "indictrans2" and tr_a:
        check("   translation is in Gujarati script", bool(GUJ.search(tr_a["payload"]["translated_text"] or "")))

    # 10. "reload": fresh HTTP clients, re-login, fetch history
    ok10 = True
    for c in (a, b):
        fresh = httpx.AsyncClient(base_url=base, timeout=30)
        tok = (await fresh.post("/api/v1/auth/login", json={"login": c.username, "password": "password123"})).json()["access_token"]
        items = (await fresh.get(f"/api/v1/conversations/{cid}/messages", headers={"Authorization": f"Bearer {tok}"})).json()["items"]
        ok10 &= [m["original_text"] for m in items] == [guj_text, hin_text]
        ok10 &= all(m["translations"] and m["translations"][0]["status"] == "completed" for m in items)
        await fresh.aclose()
    check("10. both users see full history (with translations) after reload", ok10)

    if backend == "mock":
        fail_cmid = await a.send(cid, "this will __fail__")
        ack_f = await a.wait_for(lambda e: e["type"] == "message.created" and e["correlation_id"] == fail_cmid, 10)
        fid = ack_f["payload"]["message"]["id"] if ack_f else ""
        got = await b.wait_for(lambda e: e["type"] == "message.translated" and e["payload"]["message_id"] == fid
                               and e["payload"]["status"] == "failed", 10)
        hist = (await b.http.get(f"/api/v1/conversations/{cid}/messages", headers=b.h)).json()["items"]
        kept = any(m["id"] == fid and m["original_text"] == "this will __fail__" for m in hist)
        check("11. translation failure does not lose the message", bool(got) and kept)
    else:
        r = await b.http.post(f"/api/v1/messages/{msg_id}/translations/retry", json={"target_language": "eng_Latn"}, headers=b.h)
        got = await b.wait_for(lambda e: e["type"] == "message.translated" and e["payload"]["message_id"] == msg_id
                               and e["payload"]["target_language"] == "eng_Latn" and e["payload"]["status"] != "pending", timeout)
        hist = (await b.http.get(f"/api/v1/conversations/{cid}/messages", headers=b.h)).json()["items"]
        check("11. retry/re-translate works without creating a message (failure path covered by pytest)",
              r.status_code == 202 and bool(got) and len(hist) == 2,
              repr(got["payload"]["translated_text"]) if got else "timeout")

    codes = [
        (await eve.http.get(f"/api/v1/conversations/{cid}", headers=eve.h)).status_code,
        (await eve.http.get(f"/api/v1/conversations/{cid}/messages", headers=eve.h)).status_code,
    ]
    await eve.connect()
    await eve.send(cid, "let me in")
    err = await eve.wait_for(lambda e: e["type"] == "error", 5)
    leaked = await eve.wait_for(lambda e: e["type"].startswith("message."), 1)
    check("12. a third user cannot access the conversation", codes == [404, 404] and bool(err)
          and err["payload"]["code"] == "conversation_not_found" and leaked is None, f"REST {codes}")

    for c in (a, b, eve):
        if c.ws:
            await c.ws.close()
        await c.http.aclose()
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:5173")
    p.add_argument("--db", default=None, help="postgresql://user:pw@host:port/db for direct persistence check")
    p.add_argument("--timeout", type=float, default=180, help="seconds to wait for each translation")
    p.add_argument("--origin", default=None, help="browser Origin header (default: --base); must be in FRONTEND_ORIGIN")
    args = p.parse_args()
    base = args.base.rstrip("/")
    sys.exit(asyncio.run(main(base, args.db, args.timeout, args.origin or base)))
