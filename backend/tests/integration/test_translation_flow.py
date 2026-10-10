"""Translation failure/retry and language-change flows over the real API (mock engine)."""

from fastapi.testclient import TestClient

from tests.integration.conftest import recv_type, register, send_message, start_conversation


def test_translation_failure_keeps_message_and_retry_works(client: TestClient) -> None:
    a = register(client, "alice", "guj_Gujr")
    b = register(client, "bob", "hin_Deva")
    cid = start_conversation(a, b)
    engine = client.app.state.translator.engine  # type: ignore[attr-defined]
    with a.ws() as ws_a, b.ws() as ws_b:
        engine.fail_all = True
        send_message(ws_a, cid, "will fail")
        msg = recv_type(ws_b, "message.created")["payload"]["message"]
        tr = recv_type(ws_b, "message.translated")["payload"]
        assert tr["status"] == "failed"
        assert tr["translated_text"] is None
        assert tr["error_message"]

        # Original survives in history
        items = b.get(f"/api/v1/conversations/{cid}/messages").json()["items"]
        assert items[0]["original_text"] == "will fail"
        assert items[0]["translations"][0]["status"] == "failed"

        engine.fail_all = False
        resp = b.post(f"/api/v1/messages/{msg['id']}/translations/retry", json={})
        assert resp.status_code == 202
        assert resp.json()["status"] == "pending"
        assert recv_type(ws_b, "message.translated")["payload"]["status"] == "pending"
        done = recv_type(ws_b, "message.translated")["payload"]
        assert done["status"] == "completed" and done["translated_text"] == "[hin_Deva] will fail"

    # Retry did not create another message
    assert len(a.get(f"/api/v1/conversations/{cid}/messages").json()["items"]) == 1
    tr_id = done["id"]
    assert b.get(f"/api/v1/translations/{tr_id}").json()["status"] == "completed"
    eve = register(client, "eve")
    assert eve.get(f"/api/v1/translations/{tr_id}").status_code == 404
    assert eve.post(f"/api/v1/messages/{msg['id']}/translations/retry", json={}).status_code == 404


def test_retranslate_after_language_change(client: TestClient) -> None:
    a = register(client, "alice", "guj_Gujr")
    b = register(client, "bob", "hin_Deva")
    cid = start_conversation(a, b)
    with a.ws() as ws_a, b.ws() as ws_b:
        send_message(ws_a, cid, "પહેલાં")
        recv_type(ws_b, "message.translated")
        b.patch("/api/v1/users/me/language", json={"preferred_language": "eng_Latn"})
        send_message(ws_a, cid, "પછી")
        tr = recv_type(ws_b, "message.translated")["payload"]
        assert tr["target_language"] == "eng_Latn"
        assert tr["model_name"] == "ai4bharat/indictrans2-indic-en-dist-200M"
        # History is not rewritten; explicit request creates a new-language translation
        first = b.get(f"/api/v1/conversations/{cid}/messages").json()["items"][0]
        assert [t["target_language"] for t in first["translations"]] == ["hin_Deva"]
        resp = b.post(f"/api/v1/messages/{first['id']}/translations/retry", json={"target_language": "eng_Latn"})
        assert resp.status_code == 202
        recv_type(ws_b, "message.translated")
        done = recv_type(ws_b, "message.translated")["payload"]
        assert done["target_language"] == "eng_Latn" and done["status"] == "completed"


def test_rest_translate_endpoint(client: TestClient) -> None:
    a = register(client, "alice")
    ok = a.post("/api/v1/translations", json={"text": "hi", "source_language": "eng_Latn",
                                              "target_language": "hin_Deva"})
    assert ok.status_code == 200
    assert ok.json()["model_name"] == "ai4bharat/indictrans2-en-indic-dist-200M"
    same = a.post("/api/v1/translations", json={"text": "hi", "source_language": "eng_Latn",
                                                "target_language": "eng_Latn"})
    assert same.status_code == 400
    assert same.json()["error"]["code"] == "unsupported_language_pair"
    bad = a.post("/api/v1/translations", json={"text": "hi", "source_language": "eng_Latn",
                                               "target_language": "deu_Latn"})
    assert bad.status_code == 422


def test_health(client: TestClient) -> None:
    body = client.get("/api/v1/health").json()
    assert body["database"] == "ok"
    assert body["translation"]["backend"] == "mock"
