import os
import tempfile
from pathlib import Path

import pytest

_TEST_DB = Path(tempfile.mkdtemp(prefix="bh_test_")) / "hospital.db"
os.environ["DATABASE_PATH"] = str(_TEST_DB)
os.environ["LOG_LEVEL"] = "WARNING"

from fastapi.testclient import TestClient

from app.db.seed import seed_doctors
from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session", autouse=True)
def seeded() -> None:
    seed_doctors()
