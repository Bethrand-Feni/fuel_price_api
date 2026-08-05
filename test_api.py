from collections.abc import Iterable
from inspect import iscoroutinefunction
from typing import Any

import pytest
from fastapi.testclient import TestClient

from fuel_api import app, get_repository
from fuel_methods import (
    DIESEL_PRICE_COLUMNS,
    FUEL_TYPES,
    LOCATIONS,
    PETROL_PRICE_COLUMNS,
    PRICE_COLUMNS,
    FuelDataUnavailableError,
)


def sample_row(month: str = "2026-05-01", row_id: int = 1) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": row_id,
        "summary_month": month,
        "petrol_news": "Petrol prices rising.",
        "diesel_news": "Diesel prices stable.",
        "source_name": "test-source",
        "source_url": "https://example.invalid/source",
        "source_updated_on": "2026-05-01",
        "source_row_id": str(row_id),
        "source_hash": "a" * 64,
        "ingested_at": "2026-08-02T00:00:00+00:00",
    }
    row.update({column: 20.0 + index for index, column in enumerate(PRICE_COLUMNS)})
    return row


class FakeRepository:
    def __init__(self, rows: Iterable[dict[str, Any]] = ()):
        self.rows = list(rows)
        self.fail = False

    async def latest_row(self):
        if self.fail:
            raise FuelDataUnavailableError("Fuel data is unavailable")
        return max(self.rows, key=lambda row: row["summary_month"], default=None)

    async def history_rows(self, limit: int):
        if self.fail:
            raise FuelDataUnavailableError("Fuel history is unavailable")
        return sorted(self.rows, key=lambda row: row["summary_month"], reverse=True)[:limit]


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def repository_override():
    repository = FakeRepository([sample_row()])
    app.dependency_overrides[get_repository] = lambda: repository
    yield repository
    app.dependency_overrides.clear()


def test_read_root(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"Message": "Welcome to Openfuel API"}


def test_repository_dependency_is_async_for_threadless_worker_runtime():
    assert iscoroutinefunction(get_repository)


def test_public_reads_do_not_require_or_enforce_auth(client, repository_override):
    response = client.get(
        "/fuel/unleaded93/inland",
        headers={"Authorization": "Bearer definitely-wrong"},
    )

    assert response.status_code == 200
    assert response.json()["fuel_type"] == "unleaded93"


def test_cors_preflight_allows_any_origin_for_get(client):
    response = client.options(
        "/fuel/all",
        headers={
            "Origin": "https://example-frontend.netlify.app",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_read_all_returns_all_ten_prices_in_contract_order(client, repository_override):
    response = client.get("/fuel/all")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 10
    assert set(payload[0]) == {"fuel_type", "location", "price"}
    assert [(item["fuel_type"], item["location"]) for item in payload] == [
        (fuel_type, location) for fuel_type in FUEL_TYPES for location in LOCATIONS
    ]


def test_read_single_price_preserves_response_model(client, repository_override):
    response = client.get("/fuel/unleaded93/inland")

    assert response.status_code == 200
    assert response.json() == {
        "fuel_type": "unleaded93",
        "location": "inland",
        "price": 20.0,
    }


def test_history_is_oldest_to_newest(client):
    rows = [sample_row(f"2026-{month:02d}-01", month) for month in range(1, 13)]
    app.dependency_overrides[get_repository] = lambda: FakeRepository(reversed(rows))

    try:
        response = client.get("/fuel/history")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    months = response.json()["months"]
    assert [month["month"] for month in months] == [
        f"2026-{month:02d}-01" for month in range(1, 13)
    ]
    assert set(months[-1]["petrol"]) == set(PETROL_PRICE_COLUMNS)
    assert set(months[-1]["diesel"]) == set(DIESEL_PRICE_COLUMNS)


@pytest.mark.parametrize(
    ("path", "detail"),
    [
        ("/fuel/all", "No fuel prices found"),
        ("/fuel/unleaded93/inland", "Fuel type unleaded93 in inland not found"),
        ("/fuel/history", "No fuel history found"),
        ("/news", "No news summaries found"),
        ("/news/petrol", "News summary for petrol not found"),
    ],
)
def test_no_data_returns_404(client, path, detail):
    app.dependency_overrides[get_repository] = lambda: FakeRepository()

    try:
        response = client.get(path)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == detail


def test_d1_failure_returns_503(client):
    repository = FakeRepository([sample_row()])
    repository.fail = True
    app.dependency_overrides[get_repository] = lambda: repository

    try:
        response = client.get("/fuel/all")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "Fuel data is unavailable"}


def test_missing_d1_binding_returns_503(client):
    response = client.get("/fuel/all")

    assert response.status_code == 503
    assert response.json() == {"detail": "Fuel data is unavailable"}


@pytest.mark.parametrize(
    "path",
    [
        "/fuel/petrol/inland",
        "/fuel/unleaded93/north",
        "/news/gas",
    ],
)
def test_invalid_enum_values_return_422(client, path):
    response = client.get(path)

    assert response.status_code == 422
