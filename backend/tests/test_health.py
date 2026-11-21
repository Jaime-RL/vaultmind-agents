from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_returns_ok():
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_vite_dev_server():
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
