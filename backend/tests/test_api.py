from pathlib import Path

from fastapi.testclient import TestClient

from ai_singer.main import app

client = TestClient(app)


def test_health_works_without_model_storage(monkeypatch) -> None:
    monkeypatch.delenv("AI_SINGER_STORAGE_ROOT", raising=False)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_blocks_unconfigured_storage(monkeypatch) -> None:
    monkeypatch.delenv("AI_SINGER_STORAGE_ROOT", raising=False)
    response = client.get("/ready")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_ready_blocks_disconnected_drive(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_SINGER_STORAGE_ROOT", str(tmp_path / "missing"))
    response = client.get("/ready")
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


def test_ready_accepts_connected_storage(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_SINGER_STORAGE_ROOT", str(tmp_path))
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "storage": "available"}
