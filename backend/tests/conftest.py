import os
from datetime import date

import pytest

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["MARKET_DATA_PROVIDER"] = "demo"
os.environ["JWT_SECRET"] = "test-secret-with-enough-length-for-hs256"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.providers.demo import DemoProvider  # noqa: E402
from app.services.market import MarketService, get_market  # noqa: E402


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    market = MarketService(DemoProvider(), ttl_seconds=3600)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_market] = lambda: market
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth(client):
    r = client.post("/api/auth/register", json={"name": "Ana", "email": "ana@example.com", "password": "senha-forte-123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def today():
    return date.today()
