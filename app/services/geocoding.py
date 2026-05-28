from __future__ import annotations

from typing import Any

import httpx

from app.utils.config import settings


class GeocodingService:
    base_url = "https://nominatim.openstreetmap.org/search"

    async def geocode(self, address: str) -> dict[str, Any]:
        params = {
            "q": address,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "jp",
        }
        headers = {"User-Agent": settings.nominatim_user_agent}
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

        if not data:
            raise ValueError("住所から位置を特定できませんでした。")

        top = data[0]
        return {
            "address": top.get("display_name", address),
            "latitude": float(top["lat"]),
            "longitude": float(top["lon"]),
        }
