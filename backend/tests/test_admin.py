"""Admin auth, content CRUD, uploads and submissions API tests."""
import os
import io
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "socialservant@gmail.com"
ADMIN_PASSWORD = "RightToRecall@2026"

CONTENT_TYPES = ["campaigns", "blogs", "news", "faq", "testimonials", "resources",
                 "leaders", "jurisdictions", "myths"]


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "admin"
    assert data["user"]["email"] == ADMIN_EMAIL.lower()
    assert isinstance(data["access_token"], str) and len(data["access_token"]) > 10
    return data["access_token"]


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ----- Auth -----
def test_login_wrong_password_401():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrongpass!!"})
    assert r.status_code == 401


def test_auth_me_returns_admin(auth_headers):
    r = requests.get(f"{API}/auth/me", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == ADMIN_EMAIL.lower()
    assert data["role"] == "admin"


def test_auth_me_no_token_401():
    r = requests.get(f"{API}/auth/me")
    assert r.status_code == 401


def test_auth_me_invalid_token_401():
    r = requests.get(f"{API}/auth/me", headers={"Authorization": "Bearer garbage.token.here"})
    assert r.status_code == 401


# ----- Public content DB-backed (all 9 types non-empty) -----
@pytest.mark.parametrize("ctype", CONTENT_TYPES)
def test_public_content_all_types_non_empty(ctype):
    r = requests.get(f"{API}/content/{ctype}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0, f"{ctype} is empty"


def test_public_content_blog_by_id():
    blogs = requests.get(f"{API}/content/blogs").json()
    bid = blogs[0]["id"]
    r = requests.get(f"{API}/content/blogs/{bid}")
    assert r.status_code == 200
    assert r.json()["id"] == bid


# ----- Admin auth guards -----
def test_admin_endpoints_require_auth():
    for path in ["/admin/content/faq", "/admin/submissions/supporters"]:
        r = requests.get(f"{API}{path}")
        assert r.status_code == 401, f"{path} should be 401 without token, got {r.status_code}"


def test_admin_create_requires_auth():
    r = requests.post(f"{API}/admin/content/faq", json={"question": "Q", "answer": "A"})
    assert r.status_code == 401


# ----- Admin CRUD (FAQ) -----
def test_admin_faq_crud_full_cycle(auth_headers):
    # CREATE
    q = f"TEST_faq_q_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/admin/content/faq",
                      json={"question": q, "answer": "TEST answer", "category": "Test"},
                      headers=auth_headers)
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["question"] == q
    assert created["answer"] == "TEST answer"
    fid = created["id"]
    assert fid

    # Verify appears in public list
    pub = requests.get(f"{API}/content/faq").json()
    assert any(x["id"] == fid for x in pub)

    # UPDATE
    r2 = requests.put(f"{API}/admin/content/faq/{fid}",
                     json={"question": q, "answer": "UPDATED answer", "category": "Test"},
                     headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["answer"] == "UPDATED answer"

    # Verify persisted
    pub2 = requests.get(f"{API}/content/faq").json()
    got = [x for x in pub2 if x["id"] == fid][0]
    assert got["answer"] == "UPDATED answer"

    # DELETE
    r3 = requests.delete(f"{API}/admin/content/faq/{fid}", headers=auth_headers)
    assert r3.status_code == 200
    assert r3.json().get("ok") is True

    # verify removed
    pub3 = requests.get(f"{API}/content/faq").json()
    assert not any(x["id"] == fid for x in pub3)


def test_admin_blog_create_autosets_date_and_dup_slug(auth_headers):
    title = f"TEST_blog_{uuid.uuid4().hex[:6]}"
    payload = {"title": title, "excerpt": "e", "category": "News", "content": "c"}
    r1 = requests.post(f"{API}/admin/content/blogs", json=payload, headers=auth_headers)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1.get("date"), "date should be auto-set"
    id1 = d1["id"]

    # Same title -> id should be suffixed (not collision)
    r2 = requests.post(f"{API}/admin/content/blogs", json=payload, headers=auth_headers)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["id"] != id1
    assert d2["id"].startswith(id1)

    # cleanup
    requests.delete(f"{API}/admin/content/blogs/{id1}", headers=auth_headers)
    requests.delete(f"{API}/admin/content/blogs/{d2['id']}", headers=auth_headers)


def test_admin_update_delete_nonexistent_404(auth_headers):
    r = requests.put(f"{API}/admin/content/faq/nonexistent-xyz",
                     json={"answer": "x"}, headers=auth_headers)
    assert r.status_code == 404
    r2 = requests.delete(f"{API}/admin/content/faq/nonexistent-xyz", headers=auth_headers)
    assert r2.status_code == 404


# ----- Uploads -----
# 1x1 transparent PNG
_PNG = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
    "0000000A49444154789C6300010000000500010D0A2DB40000000049454E44AE426082"
)


def test_upload_requires_auth():
    r = requests.post(f"{API}/admin/uploads", files={"file": ("x.png", _PNG, "image/png")})
    assert r.status_code == 401


def test_upload_and_fetch(auth_headers):
    r = requests.post(
        f"{API}/admin/uploads",
        files={"file": ("t.png", _PNG, "image/png")},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "id" in data
    assert data["url"].startswith("/api/uploads/")

    # Fetch back binary
    r2 = requests.get(f"{BASE_URL}{data['url']}")
    assert r2.status_code == 200
    assert r2.headers["content-type"].startswith("image/")
    assert r2.content == _PNG


# ----- Submissions (auth-required) -----
@pytest.mark.parametrize("kind", ["supporters", "volunteers", "contacts", "newsletter"])
def test_admin_submissions_auth_and_list(kind, auth_headers):
    r_unauth = requests.get(f"{API}/admin/submissions/{kind}")
    assert r_unauth.status_code == 401

    r = requests.get(f"{API}/admin/submissions/{kind}", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_admin_submissions_unknown_kind_404(auth_headers):
    r = requests.get(f"{API}/admin/submissions/aliens", headers=auth_headers)
    assert r.status_code == 404
