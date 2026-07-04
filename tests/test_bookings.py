from conftest import login


# ---------- Login ----------

def test_login_success_returns_token_and_role(client):
    res = client.post(
        "/api/login", json={"username": "admin", "password": "admin123"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["username"] == "admin"
    assert body["is_admin"] is True
    assert body["token"]

    res = client.post(
        "/api/login", json={"username": "alice", "password": "alice123"}
    )
    assert res.json()["is_admin"] is False


def test_login_wrong_password_rejected(client):
    res = client.post(
        "/api/login", json={"username": "alice", "password": "wrong"}
    )
    assert res.status_code == 401


def test_login_unknown_user_rejected(client):
    res = client.post(
        "/api/login", json={"username": "nobody", "password": "x"}
    )
    assert res.status_code == 401


# ---------- Authentication required ----------

def test_bookings_require_login(client):
    assert client.get("/api/bookings").status_code == 401
    assert (
        client.post("/api/bookings", json={"time_slot": "10.00-11.00"}).status_code
        == 401
    )
    assert client.delete("/api/bookings/1").status_code == 401


# ---------- Booking visibility ----------

def test_user_sees_only_own_bookings(client):
    alice = login(client, "alice", "alice123")
    bob = login(client, "bob", "bob123")

    client.post("/api/bookings", json={"time_slot": "10.00-11.00"}, headers=alice)
    client.post("/api/bookings", json={"time_slot": "13.00-14.00"}, headers=bob)

    res = client.get("/api/bookings", headers=alice)
    assert res.status_code == 200
    bookings = res.json()
    assert len(bookings) == 1
    assert bookings[0]["username"] == "alice"
    assert bookings[0]["time_slot"] == "10.00-11.00"


def test_admin_sees_all_bookings(client):
    alice = login(client, "alice", "alice123")
    bob = login(client, "bob", "bob123")
    admin = login(client, "admin", "admin123")

    client.post("/api/bookings", json={"time_slot": "10.00-11.00"}, headers=alice)
    client.post("/api/bookings", json={"time_slot": "13.00-14.00"}, headers=bob)

    res = client.get("/api/bookings", headers=admin)
    assert res.status_code == 200
    assert {b["username"] for b in res.json()} == {"alice", "bob"}


# ---------- Booking management permissions ----------

def test_user_can_delete_own_booking(client):
    alice = login(client, "alice", "alice123")
    booking = client.post(
        "/api/bookings", json={"time_slot": "10.00-11.00"}, headers=alice
    ).json()

    res = client.delete(f"/api/bookings/{booking['id']}", headers=alice)
    assert res.status_code == 200
    assert client.get("/api/bookings", headers=alice).json() == []


def test_user_cannot_delete_others_booking(client):
    alice = login(client, "alice", "alice123")
    bob = login(client, "bob", "bob123")
    booking = client.post(
        "/api/bookings", json={"time_slot": "10.00-11.00"}, headers=alice
    ).json()

    res = client.delete(f"/api/bookings/{booking['id']}", headers=bob)
    assert res.status_code == 403
    assert len(client.get("/api/bookings", headers=alice).json()) == 1


def test_admin_can_delete_any_booking(client):
    alice = login(client, "alice", "alice123")
    admin = login(client, "admin", "admin123")
    booking = client.post(
        "/api/bookings", json={"time_slot": "10.00-11.00"}, headers=alice
    ).json()

    res = client.delete(f"/api/bookings/{booking['id']}", headers=admin)
    assert res.status_code == 200
    assert client.get("/api/bookings", headers=admin).json() == []


def test_empty_time_slot_rejected(client):
    alice = login(client, "alice", "alice123")
    res = client.post("/api/bookings", json={"time_slot": "   "}, headers=alice)
    assert res.status_code == 422
