from __future__ import annotations

import asyncio
import math
from datetime import date
from statistics import mean
from typing import Any

import httpx

from app.models.schemas import PricePoint, SearchRequest, SearchResponse, TrendPoint
from app.services.geocoding import GeocodingService
from app.utils.config import settings


class LandPriceService:
    xpt002_url = "https://www.reinfolib.mlit.go.jp/ex-api/external/XPT002"

    async def search(self, payload: SearchRequest) -> SearchResponse:
        location = await self._resolve_location(payload)
        is_demo = False
        notice = None

        if settings.mlit_api_key:
            years = self._candidate_years()
            yearly_points = await self._fetch_points_for_years(
                location["latitude"], location["longitude"], years
            )
        elif settings.demo_mode:
            years = self._candidate_years()
            yearly_points = self._build_demo_points(
                location["latitude"], location["longitude"], years
            )
            is_demo = True
            notice = "デモモードです。MLIT_API_KEY を設定すると実データに切り替わります。"
        else:
            raise RuntimeError(
                "MLIT_API_KEY が未設定です。.env に API キーを設定してください。"
            )

        latest_year, latest_points = self._select_latest_points(yearly_points)
        nearest_points = self._nearest_points(
            latest_points,
            location["latitude"],
            location["longitude"],
            payload.sample_limit,
        )
        if not nearest_points:
            raise RuntimeError("周辺の地価データが見つかりませんでした。")

        samples = nearest_points[: payload.sample_limit]
        trend = self._build_trend(
            yearly_points,
            location["latitude"],
            location["longitude"],
            payload.sample_limit,
        )
        nearest = samples[0]
        average_price = round(mean(point["price"] for point in samples))

        return SearchResponse(
            address=location["address"],
            latitude=location["latitude"],
            longitude=location["longitude"],
            average_price=average_price,
            nearest_price=nearest["price"],
            nearest_point=nearest["point_name"],
            nearest_station=nearest.get("nearest_station"),
            nearest_distance_meters=round(nearest["distance_meters"], 1),
            year=latest_year,
            samples=[PricePoint(**point) for point in samples],
            trend=[TrendPoint(**point) for point in trend],
            source="Demo dataset" if is_demo else "MLIT 不動産情報ライブラリ XPT002",
            is_demo=is_demo,
            notice=notice,
        )

    async def _resolve_location(self, payload: SearchRequest) -> dict[str, Any]:
        if payload.mode == "coordinates":
            return {
                "address": payload.address or "指定座標",
                "latitude": payload.latitude,
                "longitude": payload.longitude,
            }
        return await GeocodingService().geocode(payload.address or "")

    def _candidate_years(self) -> list[int]:
        current_year = date.today().year
        return [current_year - offset for offset in range(0, 4)]

    async def _fetch_points_for_years(
        self, latitude: float, longitude: float, years: list[int]
    ) -> dict[int, list[dict[str, Any]]]:
        tasks = [self._fetch_year_points(latitude, longitude, year) for year in years]
        results = await asyncio.gather(*tasks)
        return {year: points for year, points in zip(years, results, strict=True)}

    async def _fetch_year_points(
        self, latitude: float, longitude: float, year: int
    ) -> list[dict[str, Any]]:
        headers = {"Ocp-Apim-Subscription-Key": settings.mlit_api_key}
        async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
            tasks = []
            for x, y in self._neighbor_tiles(latitude, longitude, 15):
                params = {
                    "response_format": "geojson",
                    "z": 15,
                    "x": x,
                    "y": y,
                    "year": year,
                }
                tasks.append(client.get(self.xpt002_url, params=params))
            responses = await asyncio.gather(*tasks, return_exceptions=True)

        points: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        for response in responses:
            if isinstance(response, Exception):
                continue
            if response.status_code >= 400:
                continue
            payload = response.json()
            for feature in payload.get("features", []):
                props = feature.get("properties", {})
                geometry = feature.get("geometry", {})
                coords = geometry.get("coordinates") or []
                if len(coords) < 2:
                    continue
                point_id = props.get("point_id")
                if point_id in seen_ids:
                    continue
                seen_ids.add(point_id)
                price = self._extract_price(props)
                if price is None:
                    continue
                points.append(
                    {
                        "point_name": props.get("standard_lot_number_ja")
                        or props.get("place_name_ja")
                        or f"地点 {point_id}",
                        "price": int(price),
                        "year": year,
                        "distance_meters": round(
                            self._haversine(latitude, longitude, coords[1], coords[0]), 1
                        ),
                        "nearest_station": props.get("nearest_station_name_ja"),
                        "use_category": props.get("use_category_name_ja"),
                        "address_label": self._compose_address(props),
                        "latitude": float(coords[1]),
                        "longitude": float(coords[0]),
                    }
                )
        return points

    def _select_latest_points(
        self, yearly_points: dict[int, list[dict[str, Any]]]
    ) -> tuple[int, list[dict[str, Any]]]:
        for year in sorted(yearly_points.keys(), reverse=True):
            if yearly_points[year]:
                return year, yearly_points[year]
        raise RuntimeError("対象年の地価データを取得できませんでした。")

    def _nearest_points(
        self,
        points: list[dict[str, Any]],
        latitude: float,
        longitude: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        ranked = [
            {
                **point,
                "distance_meters": round(
                    self._haversine(
                        latitude, longitude, point["latitude"], point["longitude"]
                    ),
                    1,
                ),
            }
            for point in points
        ]
        return sorted(ranked, key=lambda item: item["distance_meters"])[:limit]

    def _build_trend(
        self,
        yearly_points: dict[int, list[dict[str, Any]]],
        latitude: float,
        longitude: float,
        sample_limit: int,
    ) -> list[dict[str, Any]]:
        trend = []
        for year in sorted(yearly_points.keys()):
            nearest = self._nearest_points(
                yearly_points[year], latitude, longitude, sample_limit
            )
            if not nearest:
                continue
            trend.append(
                {
                    "year": year,
                    "average_price": round(mean(point["price"] for point in nearest)),
                    "count": len(nearest),
                }
            )
        return trend

    def _neighbor_tiles(self, latitude: float, longitude: float, zoom: int) -> list[tuple[int, int]]:
        x, y = self._latlon_to_tile(latitude, longitude, zoom)
        return [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]

    def _latlon_to_tile(self, latitude: float, longitude: float, zoom: int) -> tuple[int, int]:
        lat_rad = math.radians(latitude)
        n = 2**zoom
        x = int((longitude + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return x, y

    def _haversine(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        radius = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)
        a = (
            math.sin(d_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        )
        return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _compose_address(self, props: dict[str, Any]) -> str:
        parts = [
            props.get("prefecture_name_ja"),
            props.get("city_county_name_ja"),
            props.get("ward_town_village_name_ja"),
            props.get("place_name_ja"),
        ]
        return "".join(part for part in parts if part)

    def _extract_price(self, props: dict[str, Any]) -> int | None:
        current_price = props.get("u_current_years_price_ja")
        if isinstance(current_price, str):
            digits = "".join(char for char in current_price if char.isdigit())
            if digits:
                return int(digits)
        numeric_price = props.get("current_years_price") or props.get("price")
        if numeric_price is not None:
            return int(numeric_price)
        return None

    def _build_demo_points(
        self, latitude: float, longitude: float, years: list[int]
    ) -> dict[int, list[dict[str, Any]]]:
        base_points = [
            {
                "name": "サンプルA-1",
                "station": "渋谷",
                "use_category": "00,住宅地",
                "address": "東京都渋谷区サンプル1",
                "lat_offset": 0.0022,
                "lon_offset": 0.0014,
                "price": 1_180_000,
            },
            {
                "name": "サンプルA-2",
                "station": "表参道",
                "use_category": "05,商業地",
                "address": "東京都渋谷区サンプル2",
                "lat_offset": -0.0011,
                "lon_offset": 0.0032,
                "price": 1_420_000,
            },
            {
                "name": "サンプルA-3",
                "station": "渋谷",
                "use_category": "00,住宅地",
                "address": "東京都渋谷区サンプル3",
                "lat_offset": 0.0035,
                "lon_offset": -0.0022,
                "price": 1_090_000,
            },
            {
                "name": "サンプルA-4",
                "station": "恵比寿",
                "use_category": "05,商業地",
                "address": "東京都渋谷区サンプル4",
                "lat_offset": -0.0024,
                "lon_offset": -0.0018,
                "price": 1_360_000,
            },
            {
                "name": "サンプルA-5",
                "station": "代官山",
                "use_category": "07,準工業地",
                "address": "東京都渋谷区サンプル5",
                "lat_offset": 0.0015,
                "lon_offset": -0.0031,
                "price": 980_000,
            },
        ]
        yearly_points: dict[int, list[dict[str, Any]]] = {}
        latest_year = max(years)
        for year in years:
            adjustment = 1 - ((latest_year - year) * 0.035)
            points = []
            for point in base_points:
                point_lat = latitude + point["lat_offset"]
                point_lon = longitude + point["lon_offset"]
                points.append(
                    {
                        "point_name": point["name"],
                        "price": round(point["price"] * adjustment),
                        "year": year,
                        "distance_meters": round(
                            self._haversine(latitude, longitude, point_lat, point_lon), 1
                        ),
                        "nearest_station": point["station"],
                        "use_category": point["use_category"],
                        "address_label": point["address"],
                        "latitude": point_lat,
                        "longitude": point_lon,
                    }
                )
            yearly_points[year] = points
        return yearly_points
