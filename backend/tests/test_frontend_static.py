"""En producción FastAPI sirve también el frontend compilado (un solo servicio)."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def client_with_dist(dist) -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, frontend_dist=dist)))


def test_serves_frontend_and_keeps_api_routes(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id='root'></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    client = client_with_dist(dist)

    index = client.get("/")
    assert index.status_code == 200
    assert "text/html" in index.headers["content-type"]
    assert "root" in index.text
    assert client.get("/assets/app.js").status_code == 200
    # La API sigue respondiendo JSON y tiene prioridad sobre los estáticos.
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/no-existe").status_code == 404


def test_without_dist_only_the_api_is_served(tmp_path):
    for dist in (None, tmp_path / "no-existe"):
        client = client_with_dist(dist)
        assert client.get("/").status_code == 404
        assert client.get("/api/health").status_code == 200


def test_index_is_revalidated_and_hashed_assets_are_cached_forever(tmp_path):
    """Regresión: tras un despliegue, el navegador seguía con el index.html viejo en caché y
    el visitante veía la versión anterior de la interfaz."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id='root'></div>", encoding="utf-8")
    (dist / "assets" / "index-3f2a.js").write_text("console.log('ok')", encoding="utf-8")
    client = client_with_dist(dist)

    assert client.get("/").headers["cache-control"] == "no-cache"
    assert client.get("/index.html").headers["cache-control"] == "no-cache"
    assert "immutable" in client.get("/assets/index-3f2a.js").headers["cache-control"]
