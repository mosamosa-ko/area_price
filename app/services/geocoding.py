from __future__ import annotations

import re
from typing import Any

import httpx

from app.utils.config import settings


class GeocodingService:
    base_url = "https://nominatim.openstreetmap.org/search"

    async def geocode(self, address: str) -> dict[str, Any]:
        headers = {"User-Agent": settings.nominatim_user_agent}
        normalized = self._normalize_address(address)
        queries = self._build_queries(normalized)

        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            for query in queries:
                response = await client.get(self.base_url, params=query)
                response.raise_for_status()
                data = response.json()
                if data:
                    top = data[0]
                    return {
                        "address": top.get("display_name", normalized),
                        "latitude": float(top["lat"]),
                        "longitude": float(top["lon"]),
                    }

        raise ValueError("住所から位置を特定できませんでした。住所を少し短くして再検索してください。")

    def _normalize_address(self, address: str) -> str:
        address = address.strip().replace("\u3000", " ")
        address = re.sub(r"\s+", " ", address)
        address = address.replace("ヶ", "ケ")
        address = address.replace("之", "の")
        return address

    def _build_queries(self, address: str) -> list[dict[str, Any]]:
        shortened = re.sub(r"\d{3}-\d{4}", "", address).strip()
        municipality_only = re.split(r"\d", shortened, maxsplit=1)[0].strip()
        queries = [
            {
                "q": address,
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": "jp",
            },
            {
                "q": shortened or address,
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": "jp",
            },
            {
                "q": municipality_only or shortened or address,
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": "jp",
            },
            {
                "q": address,
                "format": "jsonv2",
                "limit": 1,
            },
        ]

        deduped: list[dict[str, Any]] = []
        seen: set[tuple[tuple[str, Any], ...]] = set()
        for query in queries:
            key = tuple(sorted(query.items()))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(query)
        return deduped
