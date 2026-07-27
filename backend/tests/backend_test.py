"""Backend API tests for Right to Recall Movement."""
import os
import uuid
import pytest
import requests

# Point at a running API with TEST_BASE_URL, e.g.
#   TEST_BASE_URL=http://localhost:8000 pytest backend/tests
# Defaults to localhost so a stray run never hits a deployed environment.
BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ----- Content endpoints -----
@pytest.mark.parametrize("name", ["campaigns", "blogs", "faq", "news", "testimonials", "resources"])
def test_content_endpoints_non_empty(client, name):
    r = client.get(f"{API}/content/{name}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list) and len(data) > 0


def test_blog_by_id_and_404(client):
    blogs = client.get(f"{API}/content/blogs").json()
    bid = blogs[0]["id"]
    r = client.get(f"{API}/content/blogs/{bid}")
    assert r.status_code == 200
    assert r.json()["id"] == bid

    r404 = client.get(f"{API}/content/blogs/nonexistent-xyz")
    assert r404.status_code == 404


def test_stats(client):
    r = client.get(f"{API}/stats")
    assert r.status_code == 200
    data = r.json()
    for k in ["supporters", "volunteers", "campaigns"]:
        assert k in data
        assert isinstance(data[k], int)


# ----- Volunteer -----
def test_volunteer_create_and_persist(client):
    email = f"TEST_vol_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "name": "TEST Volunteer",
        "email": email,
        "phone": "9999999999",
        "state": "Maharashtra",
        "profession": "Engineer",
        "reason": "I want to help the movement",
    }
    r = client.post(f"{API}/volunteers", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["email"] == email
    assert "id" in data
    # Note: GET /api/volunteers is admin-only in new API (see admin submissions tests)


def test_volunteer_invalid_email_422(client):
    r = client.post(f"{API}/volunteers", json={
        "name": "TEST", "email": "not-an-email", "phone": "9999999999",
        "state": "MH", "profession": "Dev", "reason": "reasons"
    })
    assert r.status_code == 422


# ----- Contact -----
def test_contact_create(client):
    email = f"TEST_c_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(f"{API}/contact", json={
        "name": "TEST User", "email": email,
        "subject": "Hello", "message": "This is a test message"
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["email"] == email
    assert "id" in data


# ----- Newsletter -----
def test_newsletter_and_duplicate(client):
    email = f"TEST_nl_{uuid.uuid4().hex[:8]}@example.com"
    r1 = client.post(f"{API}/newsletter", json={"email": email})
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1.get("already") is False
    r2 = client.post(f"{API}/newsletter", json={"email": email})
    assert r2.status_code == 200
    assert r2.json().get("already") is True


# ----- Supporters / Join Movement -----
import re

def test_supporter_and_duplicate(client):
    email = f"TEST_sup_{uuid.uuid4().hex[:8]}@example.com"
    payload = {"name": "TEST Sup", "email": email, "state": "Karnataka", "city": "Bengaluru", "mobile": "9999999999", "pledge": True}
    r1 = client.post(f"{API}/supporters", json=payload)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1.get("already") is False
    assert d1.get("name") == "TEST Sup"
    assert "created_at" in d1
    mid = d1.get("movement_id")
    assert mid and re.match(r"^RTR-\d{4}-[A-F0-9]{6}$", mid), f"Bad movement_id: {mid}"

    # Duplicate returns same movement_id
    r2 = client.post(f"{API}/supporters", json=payload)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2.get("already") is True
    assert d2.get("movement_id") == mid

    # Auto-newsletter: subscribing same email should say already:true
    rn = client.post(f"{API}/newsletter", json={"email": email})
    assert rn.status_code == 200
    assert rn.json().get("already") is True, "Supporter email was not auto-subscribed to newsletter"


def test_supporter_validation_422(client):
    # Missing name
    r = client.post(f"{API}/supporters", json={"email": "a@b.com", "state": "Delhi"})
    assert r.status_code == 422
    # Invalid email
    r2 = client.post(f"{API}/supporters", json={"name": "TEST", "email": "not-an-email", "state": "Delhi"})
    assert r2.status_code == 422


# ----- Knowledge Hub content -----
def test_jurisdictions_content(client):
    r = client.get(f"{API}/content/jurisdictions")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) > 0
    for j in data:
        assert "place" in j and "region" in j and "summary" in j


def test_myths_content(client):
    r = client.get(f"{API}/content/myths")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) > 0
    for m in data:
        assert "myth" in m and "fact" in m
