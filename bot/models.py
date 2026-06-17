"""Shared data model for a single apartment listing."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Listing:
    source: str               # "olx" or "otodom"
    listing_id: str           # stable per-site id, used for dedup
    title: str
    url: str
    price: Optional[int] = None        # PLN / month (rent)
    area: Optional[float] = None       # m²
    rooms: Optional[int] = None
    district: Optional[str] = None
    image: Optional[str] = None

    # ----- enriched fields (filled from the detail page) -----
    images: list = field(default_factory=list)   # up to 10 photo URLs
    floor: Optional[str] = None                  # e.g. "6", "parter"
    deposit: Optional[int] = None                # Kaucja, PLN
    admin_rent: Optional[int] = None             # Czynsz administracyjny, PLN
    available_from: Optional[str] = None
    is_private: Optional[bool] = None            # True=owner, False=agency
    pets: Optional[bool] = None
    parking: Optional[bool] = None
    storage: Optional[bool] = None               # komórka / piwnica
    furnished: Optional[bool] = None
    balcony: Optional[bool] = None
    elevator: Optional[bool] = None
    description: Optional[str] = None

    raw: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Globally-unique dedup key across both sites."""
        return f"{self.source}:{self.listing_id}"

    def price_per_m2(self) -> Optional[float]:
        if self.price and self.area:
            return round(self.price / self.area, 1)
        return None
