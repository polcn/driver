from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db as db_module


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setattr(db_module, "DATABASE_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_module_fixture():
    return db_module
