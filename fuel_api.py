import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from fuel_methods import get_latest_fuel_price, get_all_latest_fuel_prices, get_latest_news
from auth import verify_token

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()

class Fuel(BaseModel):
    id: int
    fuel_type: str
    location: str
    price: float
    price_date: str

@app.get("/")
def read_root():
    return {"Message": "Welcome to Openfuel API"}

@app.get("/fuel/all", response_model=list[Fuel], dependencies=[Depends(verify_token)])
def read_fuel_all():
    data = get_all_latest_fuel_prices()
    if data:
        return data
    raise HTTPException(status_code=404, detail="No fuel prices found")

@app.get("/fuel/{fuel_type}/{location}", response_model=Fuel, dependencies=[Depends(verify_token)])
def read_fuel(fuel_type: str, location: str):
    data = get_latest_fuel_price(fuel_type, location)
    if data:
        return data
    raise HTTPException(status_code=404, detail=f"Fuel type {fuel_type} in {location} not found")

@app.get("/news", dependencies=[Depends(verify_token)])
def read_all_news():
    """Returns both petrol and diesel news summaries for the latest month."""
    data = get_latest_news()
    if data:
        return data
    raise HTTPException(status_code=404, detail="No news summaries found")

@app.get("/news/{fuel_type}", dependencies=[Depends(verify_token)])
def read_fuel_news(fuel_type: str):
    """Returns the latest news summary for a specific fuel type (petrol or diesel)."""
    data = get_latest_news(fuel_type)
    if data:
        return data
    raise HTTPException(status_code=404, detail=f"News summary for {fuel_type} not found")
