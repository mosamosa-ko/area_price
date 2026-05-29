from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SearchRequest(BaseModel):
    mode: Literal["address", "coordinates"] = "address"
    address: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    sample_limit: int = Field(default=5, ge=3, le=12)

    @model_validator(mode="after")
    def validate_input(self) -> "SearchRequest":
        if self.mode == "address" and not self.address:
            raise ValueError("住所を入力してください。")
        if self.mode == "coordinates" and (
            self.latitude is None or self.longitude is None
        ):
            raise ValueError("緯度経度を入力してください。")
        return self


class PricePoint(BaseModel):
    point_name: str
    price: int
    year: int
    distance_meters: float
    nearest_station: str | None = None
    use_category: str | None = None
    address_label: str | None = None
    latitude: float
    longitude: float


class TrendPoint(BaseModel):
    year: int
    average_price: int
    count: int


class SearchResponse(BaseModel):
    address: str
    latitude: float
    longitude: float
    average_price: int
    nearest_price: int
    nearest_point: str
    nearest_station: str | None = None
    nearest_distance_meters: float
    year: int
    samples: list[PricePoint]
    trend: list[TrendPoint]
    source: str
    is_demo: bool = False
    notice: str | None = None
