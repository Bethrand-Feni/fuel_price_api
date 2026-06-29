import logging
from enum import Enum

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from fuel_methods import (
    FuelDataUnavailableError,
    get_all_latest_fuel_prices,
    get_latest_fuel_price,
    get_latest_news,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()


class FuelType(str, Enum):
    unleaded93 = "unleaded93"
    unleaded95 = "unleaded95"
    diesel500 = "diesel500"
    diesel50 = "diesel50"
    lrp93 = "lrp93"


class Location(str, Enum):
    inland = "inland"
    coast = "coast"


class NewsFuelType(str, Enum):
    petrol = "petrol"
    diesel = "diesel"


class Fuel(BaseModel):
    id: int
    fuel_type: str
    location: str
    price: float
    price_date: str


class AllNews(BaseModel):
    month: str
    petrol: str
    diesel: str


class FuelNews(BaseModel):
    month: str
    fuel_type: str
    summary: str


@app.get("/")
def read_root():
    return {"Message": "Welcome to Openfuel API"}


@app.get("/fuel/all", response_model=list[Fuel])
def read_fuel_all():
    try:
        data = get_all_latest_fuel_prices()
    except FuelDataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if data:
        return data
    raise HTTPException(status_code=404, detail="No fuel prices found")


@app.get("/fuel/{fuel_type}/{location}", response_model=Fuel)
def read_fuel(fuel_type: FuelType, location: Location):
    try:
        data = get_latest_fuel_price(fuel_type.value, location.value)
    except FuelDataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if data:
        return data
    raise HTTPException(status_code=404, detail=f"Fuel type {fuel_type.value} in {location.value} not found")


@app.get("/news", response_model=AllNews)
def read_all_news():
    try:
        data = get_latest_news()
    except FuelDataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if data:
        return data
    raise HTTPException(status_code=404, detail="No news summaries found")


@app.get("/news/{fuel_type}", response_model=FuelNews)
def read_fuel_news(fuel_type: NewsFuelType):
    try:
        data = get_latest_news(fuel_type.value)
    except FuelDataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if data:
        return data
    raise HTTPException(status_code=404, detail=f"News summary for {fuel_type.value} not found")
