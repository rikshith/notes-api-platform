import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_health_and_ready():
    with TestClient(app) as c:
        assert c.get("/health").json() == {"status": "ok"}
        assert c.get("/ready").status_code == 200


def test_create_and_read_note():
    with TestClient(app) as c:
        r = c.post("/notes", json={"title": "hello", "body": "world"})
        assert r.status_code == 201
        nid = r.json()["id"]
        assert c.get(f"/notes/{nid}").json()["title"] == "hello"
        assert c.get("/notes/999999").status_code == 404


def test_error_drill():
    with TestClient(app) as c:
        assert c.get("/error?rate=1").status_code == 500
        assert c.get("/error?rate=0").status_code == 200


def test_metrics_exposed():
    with TestClient(app) as c:
        c.get("/health")
        assert "http_requests_total" in c.get("/metrics").text
