from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(db_module, "DATABASE_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_module_fixture():
    return db_module
