"""
Facebook Marketplace Vendor

Searches Facebook Marketplace via RapidAPI.
Extends BaseVendorService — returns VendorProduct.

Only returns clothing/fashion items — non-clothing results are filtered out.
Supports user location for distance calculation.
"""

import os
import logging
import hashlib
import math
from typing import List, Optional, Tuple
from datetime import datetime
import requests

from .base_vendor import BaseVendorService, VendorProduct

logger = logging.getLogger(__name__)

# Clothing/fashion keywords — only items matching these pass the filter
CLOTHING_KEYWORDS = {
    # Tops
    "shirt", "blouse", "top", "tee", "t-shirt", "tank", "cami", "camisole",
    "sweater", "hoodie", "sweatshirt", "cardigan", "pullover", "polo", "henley",
    "tunic", "crop top", "bodysuit",
    # Bottoms
    "pants", "jeans", "trousers", "shorts", "skirt", "leggings", "joggers",
    "chinos", "culottes", "palazzo",
    # Dresses & jumpsuits
    "dress", "gown", "maxi", "midi", "mini", "romper", "jumpsuit", "overalls",
    # Outerwear
    "jacket", "coat", "blazer", "parka", "windbreaker", "vest", "puffer",
    "trench", "bomber", "denim jacket", "leather jacket", "raincoat",
    # Footwear
    "shoes", "sneakers", "boots", "sandals", "heels", "flats", "loafers",
    "mules", "slides", "pumps", "oxfords", "espadrilles", "wedges",
    # Accessories
    "bag", "purse", "handbag", "tote", "clutch", "backpack", "wallet",
    "belt", "scarf", "hat", "cap", "beanie", "gloves", "sunglasses",
    "watch", "jewelry", "necklace", "bracelet", "earring", "ring",
    # Activewear
    "activewear", "sportswear", "athleisure", "sports bra", "yoga pants",
    "workout", "gym wear", "running shoes", "athletic",
    # Swimwear & intimates
    "swimsuit", "bikini", "swimwear", "lingerie", "bra", "underwear",
    # General
    "clothing", "apparel", "outfit", "wear", "fashion", "garment",
    "suit", "tuxedo", "uniform",
}


def _is_clothing_item(title: str, description: str = "") -> bool:
    """Check if an item is clothing/fashion based on title and description."""
    text = f"{title} {description}".lower()
    return any(kw in text for kw in CLOTHING_KEYWORDS)


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in miles between two lat/lng points."""
    R = 3958.8  # Earth radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


class FacebookVendor(BaseVendorService):
    """Facebook Marketplace search via RapidAPI — clothing only."""

    VENDOR_ID = "facebook"
    VENDOR_NAME = "Facebook Marketplace"
    PRIORITY = 50
    TIMEOUT = 8

    API_HOST = "facebook-marketplace.p.rapidapi.com"

    # User location (set by orchestrator before search)
    _user_lat: Optional[float] = None
    _user_lng: Optional[float] = None
    _max_distance_miles: Optional[float] = None

    def _load_credentials(self):
        from django.conf import settings
        self.api_key = settings.RAPIDAPI_KEY
        if self.api_key:
            logger.info("Facebook Marketplace vendor initialized")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def set_user_location(self, lat: float, lng: float, max_distance: Optional[float] = None):
        """Set user's current location for distance calculation and filtering."""
        self._user_lat = lat
        self._user_lng = lng
        self._max_distance_miles = max_distance

    def _within_distance(self, features: list) -> bool:
        """Check if item's distance (from features list) is within max_distance."""
        if self._max_distance_miles is None:
            return True
        for feat in features:
            if isinstance(feat, str) and feat.startswith("distance:"):
                try:
                    dist = float(feat.split(":", 1)[1])
                    return dist <= self._max_distance_miles
                except (ValueError, IndexError):
                    pass
        # No distance info — include by default
        return True

    # ── BaseVendorService._do_search implementation ─────────────

    def _do_search(self, query: str, limit: int) -> List[VendorProduct]:
        if not self.is_configured():
            logger.debug("Facebook Marketplace vendor not configured, skipping")
            return []

        try:
            # Request more than needed since we'll filter non-clothing items
            raw_results = self._search_api(query, limit * 3)
            # Filter to clothing only
            filtered = [r for r in raw_results if _is_clothing_item(r.title, r.description)]
            logger.info(
                f"Facebook clothing filter: {len(raw_results)} raw → {len(filtered)} clothing items"
            )

            # Filter by max distance if set
            if self._max_distance_miles is not None:
                before = len(filtered)
                filtered = [
                    r for r in filtered
                    if self._within_distance(r.features)
                ]
                logger.info(
                    f"Facebook distance filter ({self._max_distance_miles}mi): "
                    f"{before} → {len(filtered)} items"
                )

            return filtered[:limit]
        except Exception as e:
            logger.warning(f"Facebook Marketplace API error: {e}")
            return []

    def _search_api(self, query: str, limit: int) -> List[VendorProduct]:
        """Search Facebook Marketplace via RapidAPI."""
        url = f"https://{self.API_HOST}/search"

        params = {
            "query": query,
            "limit": str(limit),
            "category": "apparel",  # Request clothing category from API
        }

        # Use user's location for local results if available
        if self._user_lat is not None and self._user_lng is not None:
            params["latitude"] = str(self._user_lat)
            params["longitude"] = str(self._user_lng)
        else:
            params["location"] = "new york"

        response = requests.get(
            url,
            headers={
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": self.API_HOST,
            },
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("listings", []):
            price_str = item.get("price", "$0")
            price = float(price_str.replace("$", "").replace(",", "")) if price_str else 0

            # Extract product location
            item_location = item.get("location", {})
            item_lat = item_location.get("latitude") if isinstance(item_location, dict) else None
            item_lng = item_location.get("longitude") if isinstance(item_location, dict) else None
            location_name = (
                item_location.get("name", "")
                if isinstance(item_location, dict)
                else str(item_location) if item_location else ""
            )

            # Calculate distance if both locations are available
            distance_miles = None
            if (
                self._user_lat is not None
                and self._user_lng is not None
                and item_lat is not None
                and item_lng is not None
            ):
                distance_miles = round(_haversine_miles(
                    self._user_lat, self._user_lng,
                    float(item_lat), float(item_lng),
                ), 1)

            # Build features list
            features = ["local", "marketplace", "used"]
            if distance_miles is not None:
                features.append(f"distance:{distance_miles}")
            if location_name:
                features.append(f"location:{location_name}")

            product = VendorProduct(
                id=f"fb-{item.get('id', '')}",
                title=item.get("title", ""),
                description=item.get("description", ""),
                price=price,
                currency="USD",
                url=item.get("url", f"https://facebook.com/marketplace/item/{item.get('id', '')}"),
                image_url=item.get("image", ""),
                source="Facebook Marketplace",
                seller=item.get("seller", {}).get("name", "Facebook User"),
                condition=item.get("condition", "Used"),
                shipping="Local pickup",
                features=features,
                distance_miles=distance_miles,
                location_name=location_name or "",
                fetched_at=datetime.now().isoformat(),
            )
            results.append(product)

        logger.info(f"Facebook returned {len(results)} products for '{query}'")
        return results
    
