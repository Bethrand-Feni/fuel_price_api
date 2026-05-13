import os
# Set dummy environment variables for testing BEFORE importing app
os.environ["ACCESS_TOKEN"] = "test_token"
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_KEY"] = "test_key"

import pytest
from fastapi.testclient import TestClient
import auth
# Ensure the module-level variable is set correctly
auth.ACCESS_TOKEN = "test_token"

from fuel_api import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Message": "Welcome to Openfuel API"}

def test_read_fuel_unauthorized():
    response = client.get("/fuel/Petrol/Inland")
    assert response.status_code == 401

def test_read_fuel_success(mocker):
    mock_data = {
        "id": 1,
        "fuel_type": "unleaded93",
        "location": "inland",
        "price": 23.25,
        "price_date": "2026-05-01"
    }
    mocker.patch("fuel_api.get_latest_fuel_price", return_value=mock_data)
    
    response = client.get(
        "/fuel/unleaded93/inland",
        headers={"Authorization": "Bearer test_token"}
    )
    assert response.status_code == 200
    assert response.json() == mock_data

def test_read_news_all(mocker):
    mock_news = {
        "month": "2026-05-01",
        "petrol": "Petrol prices rising.",
        "diesel": "Diesel prices stable."
    }
    mocker.patch("fuel_api.get_latest_news", return_value=mock_news)
    
    response = client.get(
        "/news",
        headers={"Authorization": "Bearer test_token"}
    )
    assert response.status_code == 200
    assert response.json() == mock_news

def test_read_news_single(mocker):
    mock_news = {
        "month": "2026-05-01",
        "fuel_type": "petrol",
        "summary": "Petrol prices rising."
    }
    mocker.patch("fuel_api.get_latest_news", return_value=mock_news)
    
    response = client.get(
        "/news/petrol",
        headers={"Authorization": "Bearer test_token"}
    )
    assert response.status_code == 200
    assert response.json() == mock_news

def test_read_news_not_found(mocker):
    mocker.patch("fuel_api.get_latest_news", return_value=None)
    
    response = client.get(
        "/news/petrol",
        headers={"Authorization": "Bearer test_token"}
    )
    assert response.status_code == 404
