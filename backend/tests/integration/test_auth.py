from fastapi.testclient import TestClient

from tests.integration.conftest import register


def test_register_login_me(client: TestClient) -> None:
    a = register(client, "alice", "guj_Gujr")
    assert a.user["preferred_language"] == "guj_Gujr"
    assert "password_hash" not in a.user

    resp = client.post("/api/v1/auth/login", json={"login": "ALICE", "password": "password123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"

    # login by email works too
    assert client.post("/api/v1/auth/login", json={"login": "alice@example.com",
                                                   "password": "password123"}).status_code == 200


def test_register_validation_and_duplicates(client: TestClient) -> None:
    register(client, "alice")
    dup = client.post("/api/v1/auth/register", json={
        "username": "Alice", "email": "other@example.com", "password": "password123",
        "display_name": "A", "preferred_language": "hin_Deva"})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "user_exists"

    bad = client.post("/api/v1/auth/register", json={
        "username": "x y", "email": "nope", "password": "short", "display_name": "",
        "preferred_language": "xxx_Yyyy"})
    assert bad.status_code == 422
    body = bad.json()["error"]
    assert body["code"] == "validation_error"
    fields = {d["loc"][-1] for d in body["details"]}
    assert {"username", "email", "password", "preferred_language"} <= fields


def test_invalid_credentials(client: TestClient) -> None:
    register(client, "alice")
    resp = client.post("/api/v1/auth/login", json={"login": "alice", "password": "wrong-password"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"
    resp = client.post("/api/v1/auth/login", json={"login": "ghost", "password": "wrong-password"})
    assert resp.status_code == 401


def test_protected_endpoints_require_token(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/conversations").status_code == 401
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_token"


def test_expired_token(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core import security
    from app.core.config import get_settings

    a = register(client, "alice")
    monkeypatch.setattr(get_settings(), "ACCESS_TOKEN_EXPIRE_MINUTES", -1)
    token, _ = security.create_access_token(a.user["id"])
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "token_expired"


def test_refresh_rotation_and_logout(client: TestClient) -> None:
    register(client, "alice")
    # TestClient keeps the httpOnly refresh cookie
    r1 = client.post("/api/v1/auth/refresh")
    assert r1.status_code == 200, r1.text
    old_cookie = r1.request.headers.get("cookie")
    assert client.post("/api/v1/auth/refresh").status_code == 200
    # Reusing a rotated token fails
    reuse = client.post("/api/v1/auth/refresh", headers={"cookie": old_cookie})
    assert reuse.status_code == 401
    # The reuse attempt cleared the cookie; log in again then log out
    client.post("/api/v1/auth/login", json={"login": "alice", "password": "password123"})
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_language_update(client: TestClient) -> None:
    a = register(client, "alice", "guj_Gujr")
    resp = a.patch("/api/v1/users/me/language", json={"preferred_language": "tam_Taml"})
    assert resp.status_code == 200
    assert resp.json()["preferred_language"] == "tam_Taml"
    bad = a.patch("/api/v1/users/me/language", json={"preferred_language": "fra_Latn"})
    assert bad.status_code == 422


def test_languages_endpoint(client: TestClient) -> None:
    codes = [lang["code"] for lang in client.get("/api/v1/languages").json()]
    assert len(codes) == 12
    assert {"eng_Latn", "guj_Gujr", "hin_Deva", "asm_Beng"} <= set(codes)


def test_auth_rate_limit(client: TestClient) -> None:
    client.app.state.auth_limiter.limit = 3  # type: ignore[attr-defined]
    codes = [client.post("/api/v1/auth/login", json={"login": "x", "password": "y"}).status_code
             for _ in range(5)]
    assert codes[:3] == [401, 401, 401]
    assert codes[3:] == [429, 429]


def test_invalid_refresh_clears_the_cookie(client: TestClient) -> None:
    register(client, "alice")
    client.cookies.set("mlchat_refresh", "not-a-real-token", path="/api/v1/auth")
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "refresh_invalid"
    set_cookie = resp.headers.get("set-cookie", "")
    assert "mlchat_refresh=" in set_cookie and "Max-Age=0" in set_cookie
