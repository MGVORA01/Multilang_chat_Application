import uuid

from fastapi.testclient import TestClient

from tests.integration.conftest import recv_type, register, send_message, start_conversation


def test_user_search(client: TestClient) -> None:
    a = register(client, "alice")
    register(client, "bob")
    register(client, "bobby")
    resp = a.get("/api/v1/users", params={"q": "bob"})
    assert resp.status_code == 200
    names = [u["username"] for u in resp.json()["items"]]
    assert names == ["bob", "bobby"]
    # Never returns yourself
    assert all(u["username"] != "alice" for u in a.get("/api/v1/users").json()["items"])
    # LIKE wildcards are escaped
    assert a.get("/api/v1/users", params={"q": "%"}).json()["total"] == 0


def test_create_conversation_is_idempotent(client: TestClient) -> None:
    a = register(client, "alice", "guj_Gujr")
    b = register(client, "bob", "hin_Deva")
    r1 = a.post("/api/v1/conversations", json={"participant_id": b.id})
    assert r1.status_code == 201
    r2 = b.post("/api/v1/conversations", json={"participant_id": a.id})
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    members = {m["username"] for m in r1.json()["members"]}
    assert members == {"alice", "bob"}

    assert a.post("/api/v1/conversations", json={"participant_id": a.id}).status_code == 400
    assert a.post("/api/v1/conversations", json={"participant_id": str(uuid.uuid4())}).status_code == 404
    assert len(a.get("/api/v1/conversations").json()["items"]) == 1


def test_non_member_cannot_access_conversation(client: TestClient) -> None:
    a = register(client, "alice")
    b = register(client, "bob")
    eve = register(client, "eve")
    cid = start_conversation(a, b)
    for url in (f"/api/v1/conversations/{cid}", f"/api/v1/conversations/{cid}/messages"):
        resp = eve.get(url)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "conversation_not_found"
    assert eve.get("/api/v1/conversations").json()["items"] == []


def test_history_pagination_and_persistence(client: TestClient) -> None:
    a = register(client, "alice", "eng_Latn")
    b = register(client, "bob", "eng_Latn")  # same language: no translation needed
    cid = start_conversation(a, b)
    with a.ws() as ws:
        for i in range(7):
            send_message(ws, cid, f"message {i}")
            recv_type(ws, "message.created")

    page1 = b.get(f"/api/v1/conversations/{cid}/messages", params={"limit": 3}).json()
    assert [m["original_text"] for m in page1["items"]] == ["message 4", "message 5", "message 6"]
    assert page1["has_more"] is True
    page2 = b.get(f"/api/v1/conversations/{cid}/messages",
                  params={"limit": 3, "before": page1["next_cursor"]}).json()
    assert [m["original_text"] for m in page2["items"]] == ["message 1", "message 2", "message 3"]
    page3 = b.get(f"/api/v1/conversations/{cid}/messages",
                  params={"limit": 3, "before": page2["next_cursor"]}).json()
    assert [m["original_text"] for m in page3["items"]] == ["message 0"]
    assert page3["has_more"] is False and page3["next_cursor"] is None

    conv = b.get("/api/v1/conversations").json()["items"][0]
    assert conv["last_message"]["original_text"] == "message 6"
    assert conv["unread_count"] == 7


def test_offline_recipient_gets_history_and_delivery_receipt(client: TestClient) -> None:
    a = register(client, "alice", "guj_Gujr")
    b = register(client, "bob", "hin_Deva")
    cid = start_conversation(a, b)
    with a.ws() as ws_a:
        send_message(ws_a, cid, "તમે કેમ છો?")
        created = recv_type(ws_a, "message.created")["payload"]["message"]
        assert created["status"] == "sent"  # bob offline
        recv_type(ws_a, "message.translated")

        # bob comes back later and loads history
        items = b.get(f"/api/v1/conversations/{cid}/messages").json()["items"]
        assert items[0]["original_text"] == "તમે કેમ છો?"
        tr = items[0]["translations"][0]
        assert tr["target_language"] == "hin_Deva" and tr["status"] == "completed"

        delivered = recv_type(ws_a, "message.delivered")["payload"]
        assert delivered["message_ids"] == [created["id"]]
        assert delivered["user_id"] == b.id
