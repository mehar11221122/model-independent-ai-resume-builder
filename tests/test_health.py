from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root() -> None:
    """Root now serves the demo UI (static HTML) instead of raw JSON."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_api_info() -> None:
    response = client.get("/api")
    assert response.status_code == 200
    assert "docs" in response.json()
