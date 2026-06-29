import os
from datetime import datetime, timezone

os.environ["ACCESS_TOKEN"] = "test_token"
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_KEY"] = "test_key"

import fuel_methods
from fastapi.testclient import TestClient
from fuel_api import app

client = TestClient(app)


def sample_row():
    return {
        "id": 1,
        "summary_month": "2026-05-01",
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "petrol_news": "Petrol prices rising.",
        "diesel_news": "Diesel prices stable.",
        "unleaded93_inland": 23.25,
        "unleaded93_coast": 22.25,
        "unleaded95_inland": 24.25,
        "unleaded95_coast": 23.25,
        "diesel500_inland": 21.50,
        "diesel500_coast": 20.50,
        "diesel50_inland": 21.75,
        "diesel50_coast": 20.75,
        "lrp93_inland": 23.00,
        "lrp93_coast": 22.00,
    }


def write_cache(path, row=None):
    path.write_text(fuel_methods.json.dumps(row or sample_row()), encoding="utf-8")


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Message": "Welcome to Openfuel API"}


def test_read_fuel_without_token_from_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "latest_fuel_data.json"
    write_cache(cache_path)
    monkeypatch.setattr(fuel_methods, "CACHE_PATH", cache_path)

    response = client.get("/fuel/unleaded93/inland")

    assert response.status_code == 200
    assert response.json()["price"] == 23.25


def test_invalid_token_does_not_block_public_read(tmp_path, monkeypatch):
    cache_path = tmp_path / "latest_fuel_data.json"
    write_cache(cache_path)
    monkeypatch.setattr(fuel_methods, "CACHE_PATH", cache_path)

    response = client.get("/fuel/unleaded93/inland", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 200
    assert response.json()["price"] == 23.25


def test_read_fuel_all_from_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "latest_fuel_data.json"
    write_cache(cache_path)
    monkeypatch.setattr(fuel_methods, "CACHE_PATH", cache_path)

    response = client.get("/fuel/all")

    assert response.status_code == 200
    assert len(response.json()) == len(fuel_methods.PRICE_COLUMNS)


def test_read_single_fuel_from_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "latest_fuel_data.json"
    write_cache(cache_path)
    monkeypatch.setattr(fuel_methods, "CACHE_PATH", cache_path)

    response = client.get("/fuel/unleaded93/inland")

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "fuel_type": "unleaded93",
        "location": "inland",
        "price": 23.25,
        "price_date": "2026-05-01",
    }


def test_missing_or_stale_cache_fetches_supabase_and_writes_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "latest_fuel_data.json"
    monkeypatch.setattr(fuel_methods, "CACHE_PATH", cache_path)
    monkeypatch.setattr(fuel_methods, "_fetch_latest_fuel_row_from_supabase", lambda: sample_row())

    response = client.get("/fuel/unleaded95/coast")

    assert response.status_code == 200
    assert response.json()["price"] == 23.25
    assert cache_path.exists()
    assert "cached_at" in fuel_methods.json.loads(cache_path.read_text(encoding="utf-8"))


def test_fresh_cache_is_used_without_supabase(tmp_path, monkeypatch):
    cache_path = tmp_path / "latest_fuel_data.json"
    write_cache(cache_path)
    monkeypatch.setattr(fuel_methods, "CACHE_PATH", cache_path)

    def fail_fetch():
        raise RuntimeError("Supabase unavailable")

    monkeypatch.setattr(fuel_methods, "_fetch_latest_fuel_row_from_supabase", fail_fetch)

    response = client.get("/fuel/diesel50/coast")

    assert response.status_code == 200
    assert response.json()["price"] == 20.75


def test_stale_cache_is_fallback_when_supabase_fails(tmp_path, monkeypatch):
    cache_path = tmp_path / "latest_fuel_data.json"
    stale_row = sample_row()
    stale_row["cached_at"] = "2020-01-01T00:00:00+00:00"
    write_cache(cache_path, stale_row)
    monkeypatch.setattr(fuel_methods, "CACHE_PATH", cache_path)

    def fail_fetch():
        raise RuntimeError("Supabase unavailable")

    monkeypatch.setattr(fuel_methods, "_fetch_latest_fuel_row_from_supabase", fail_fetch)

    response = client.get("/fuel/diesel50/coast")

    assert response.status_code == 200
    assert response.json()["price"] == 20.75


def test_missing_cache_and_supabase_failure_returns_503(tmp_path, monkeypatch):
    cache_path = tmp_path / "latest_fuel_data.json"
    monkeypatch.setattr(fuel_methods, "CACHE_PATH", cache_path)

    def fail_fetch():
        raise RuntimeError("Supabase unavailable")

    monkeypatch.setattr(fuel_methods, "_fetch_latest_fuel_row_from_supabase", fail_fetch)

    response = client.get("/fuel/diesel50/coast")

    assert response.status_code == 503


def test_invalid_fuel_or_location_returns_422():
    fuel_response = client.get("/fuel/petrol/inland")
    location_response = client.get("/fuel/unleaded93/north")

    assert fuel_response.status_code == 422
    assert location_response.status_code == 422


def test_read_news_all_from_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "latest_fuel_data.json"
    write_cache(cache_path)
    monkeypatch.setattr(fuel_methods, "CACHE_PATH", cache_path)

    response = client.get("/news")

    assert response.status_code == 200
    assert response.json() == {
        "month": "2026-05-01",
        "petrol": "Petrol prices rising.",
        "diesel": "Diesel prices stable.",
    }


def test_read_news_single_from_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "latest_fuel_data.json"
    write_cache(cache_path)
    monkeypatch.setattr(fuel_methods, "CACHE_PATH", cache_path)

    response = client.get("/news/petrol")

    assert response.status_code == 200
    assert response.json() == {
        "month": "2026-05-01",
        "fuel_type": "petrol",
        "summary": "Petrol prices rising.",
    }
