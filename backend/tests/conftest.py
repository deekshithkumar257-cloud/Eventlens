"""Shared fixtures. Every test uses its own temporary SQLite database."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test_eventlens.db"
    monkeypatch.setenv("EVENTLENS_DB_PATH", str(path))
    monkeypatch.delenv("EVENTLENS_MAX_UPLOAD_MB", raising=False)
    monkeypatch.delenv("EVENTLENS_SAMPLE_PATH", raising=False)
    return path


@pytest.fixture()
def client(db_path):
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
