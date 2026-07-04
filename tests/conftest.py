import os
import tempfile

# Point the app at a throwaway database before main.py is imported
# (Settings loads once at import time).
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from main import Booking, app, auth_sessions, engine


@pytest.fixture()
def client():
    # `with` runs the lifespan hook: create_all + seed data. Wipe
    # bookings (including seeded ones) so each test starts empty.
    with TestClient(app) as c:
        with Session(engine) as session:
            session.exec(delete(Booking))
            session.commit()
        yield c
    auth_sessions.clear()


def login(client: TestClient, username: str, password: str) -> dict:
    res = client.post(
        "/api/login", json={"username": username, "password": password}
    )
    assert res.status_code == 200, res.text
    token = res.json()["token"]
    return {"Authorization": f"Bearer {token}"}
