from collections.abc import Mapping
from enum import Enum
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from fuel_methods import (
    D1Database,
    D1FuelRepository,
    FuelDataUnavailableError,
    FuelRepository,
    get_all_latest_fuel_prices,
    get_fuel_history,
    get_latest_fuel_price,
    get_latest_news,
)

app = FastAPI(title="Open Fuel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


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
    fuel_type: str
    location: str
    price: float


class AllNews(BaseModel):
    month: str
    petrol: str
    diesel: str


class FuelNews(BaseModel):
    month: str
    fuel_type: str
    summary: str


class FuelHistoryMonth(BaseModel):
    month: str
    petrol: dict[str, float]
    diesel: dict[str, float]
    news: dict[str, str]


class FuelHistory(BaseModel):
    months: list[FuelHistoryMonth]


@app.exception_handler(FuelDataUnavailableError)
async def handle_fuel_data_unavailable(
    request: Request,
    exc: FuelDataUnavailableError,
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


def _database_from_environment(environment: object) -> D1Database | None:
    if isinstance(environment, Mapping):
        database = environment.get("DB")
    else:
        database = getattr(environment, "DB", None)

    return database


class _UnavailableD1Database:
    def prepare(self, sql: str):
        raise RuntimeError("D1 binding DB is not configured")


async def get_repository(request: Request) -> FuelRepository:
    """Build a repository from this request's Worker environment binding."""
    environment = request.scope.get("env")
    database = _database_from_environment(environment) if environment is not None else None

    return D1FuelRepository(database if database is not None else _UnavailableD1Database())


RepositoryDependency = Annotated[FuelRepository, Depends(get_repository)]


@app.get("/")
async def read_root():
    return {"Message": "Welcome to Openfuel API"}


@app.get("/fuel/all", response_model=list[Fuel])
async def read_fuel_all(repository: RepositoryDependency):
    data = await get_all_latest_fuel_prices(repository)
    if data:
        return data
    raise HTTPException(status_code=404, detail="No fuel prices found")


@app.get("/fuel/{fuel_type}/{location}", response_model=Fuel)
async def read_fuel(
    fuel_type: FuelType,
    location: Location,
    repository: RepositoryDependency,
):
    data = await get_latest_fuel_price(repository, fuel_type.value, location.value)
    if data:
        return data
    raise HTTPException(
        status_code=404,
        detail=f"Fuel type {fuel_type.value} in {location.value} not found",
    )


@app.get("/fuel/history", response_model=FuelHistory)
async def read_fuel_history(repository: RepositoryDependency):
    data = await get_fuel_history(repository)
    if data:
        return {"months": data}
    raise HTTPException(status_code=404, detail="No fuel history found")


@app.get("/news", response_model=AllNews)
async def read_all_news(repository: RepositoryDependency):
    data = await get_latest_news(repository)
    if data:
        return data
    raise HTTPException(status_code=404, detail="No news summaries found")


@app.get("/news/{fuel_type}", response_model=FuelNews)
async def read_fuel_news(
    fuel_type: NewsFuelType,
    repository: RepositoryDependency,
):
    data = await get_latest_news(repository, fuel_type.value)
    if data:
        return data
    raise HTTPException(
        status_code=404,
        detail=f"News summary for {fuel_type.value} not found",
    )
