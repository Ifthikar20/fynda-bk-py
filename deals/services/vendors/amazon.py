"""
Amazon Vendor

Searches Amazon via RapidAPI Real-Time Amazon Data API.
Extends BaseVendorService — returns VendorProduct.
"""

import os
import logging
from typing import List, Optional
from datetime import datetime
import requests

from .base_vendor import BaseVendorService, VendorProduct, QuotaExceededError

logger = logging.getLogger(__name__)


class AmazonVendor(BaseVendorService):
    """Amazon product search via RapidAPI."""
    
    VENDOR_ID = "amazon"
    VENDOR_NAME = "Amazon"
    PRIORITY = 95
    TIMEOUT = 15
    
    BASE_URL = "https://real-time-amazon-data.p.rapidapi.com"
    
    def _load_credentials(self):
        self.api_key = os.getenv("RAPIDAPI_KEY")
        if self.api_key:
            logger.info("Amazon RapidAPI vendor initialized")
        else:
            logger.warning("RAPIDAPI_KEY not set — Amazon vendor disabled")
    
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    # ── BaseVendorService._do_search implementation ─────────────
    
    def _do_search(self, query: str, limit: int) -> List[VendorProduct]:
        if not self.is_configured():
            return []
        
        url = f"{self.BASE_URL}/search"
        params = {
            "query": query,
            "page": "1",
            "country": "US",
            "sort_by": "RELEVANCE",
            "product_condition": "ALL",
        }
        
        response = requests.get(
            url,
            headers={
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": "real-time-amazon-data.p.rapidapi.com",
            },
            params=params,
            timeout=self.timeout,
        )
        
        if response.status_code == 429:
            raise QuotaExceededError("Amazon monthly API quota exceeded")
        
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") != "OK":
            logger.warning(f"Amazon API returned status: {data.get('status')}")
            return []
        
        products = data.get("data", {}).get("products", [])
        results = []
        
        for item in products[:limit]:
            try:
                product = self._parse_product(item)
                if product:
                    results.append(product)
            except Exception as e:
                logger.debug(f"Failed to parse Amazon product: {e}")
        
        logger.info(f"Amazon returned {len(results)} products for '{query}'")
        return results
    
    # ── Standalone method for product details (used by views) ───
    
    def get_product_details(self, asin: str, country: str = "US") -> Optional[VendorProduct]:
        """Get detailed product information by ASIN."""
        if not self.is_configured():
            return None
        try:
            url = f"{self.BASE_URL}/product-details"
            response = requests.get(
                url,
                headers={
                    "X-RapidAPI-Key": self.api_key,
                    "X-RapidAPI-Host": "real-time-amazon-data.p.rapidapi.com",
                },
                params={"asin": asin, "country": country},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "OK":
                return self._parse_product(data.get("data", {}))
            return None
        except Exception as e:
            logger.error(f"Failed to get Amazon product details: {e}")
            return None
    
    # ── Parsing ─────────────────────────────────────────────────
    
    def _parse_product(self, item: dict) -> Optional[VendorProduct]:
        """Parse a product from the RapidAPI response into VendorProduct."""
        price_str = item.get("product_price", "")
        if not price_str:
            return None
        try:
            price = float(price_str.replace("$", "").replace(",", "").strip())
        except ValueError:
            return None
        
        # Original price
        original_price = None
        original_str = item.get("product_original_price", "")
        if original_str:
            try:
                original_price = float(original_str.replace("$", "").replace(",", "").strip())
            except ValueError:
                pass
        
        # Discount
        discount = 0
        if original_price and original_price > price:
            discount = int((1 - price / original_price) * 100)
        
        # Rating
        rating = None
        rating_str = item.get("product_star_rating")
        if rating_str:
            try:
                rating = float(rating_str)
            except ValueError:
                pass
        
        # Reviews
        reviews = None
        reviews_str = item.get("product_num_ratings")
        if reviews_str:
            try:
                reviews = int(str(reviews_str).replace(",", ""))
            except ValueError:
                pass
        
        # Brand extraction
        brand = self._extract_brand(item)
        
        # Badge
        badge = item.get("product_badge") or None
        if not badge and item.get("is_best_seller"):
            badge = "Best Seller"
        elif not badge and item.get("is_amazon_choice"):
            badge = "Amazon Choice"
        
        return VendorProduct(
            id=f"amazon-{item.get('asin', '')}",
            title=item.get("product_title", ""),
            description=item.get("product_title", ""),
            price=price,
            original_price=original_price,
            discount_percent=discount,
            currency="USD",
            url=item.get("product_url", ""),
            image_url=item.get("product_photo", "") or item.get("product_image", "") or "",
            source="Amazon",
            merchant_name=brand or "Amazon",
            brand=brand or "Amazon",
            rating=rating,
            reviews_count=reviews,
            is_prime=item.get("is_prime", False),
            condition="New",
            shipping="Prime" if item.get("is_prime", False) else "Standard",
            seller=brand or "Amazon",
            seller_rating=5.0,
            badge=badge,
            fetched_at=datetime.now().isoformat(),
        )
    
    def _extract_brand(self, item: dict) -> str:
        """Extract brand name from product data or title."""
        brand = item.get("product_brand") or ""
        if brand.strip().lower() in ("n/a", "unknown", "none", ""):
            brand = ""
        
        if not brand:
            title = item.get("product_title", "")
            if title:
                skip_words = {
                    "women", "womens", "women's", "men", "mens", "men's",
                    "kids", "boys", "girls", "unisex", "adult", "baby",
                    "dress", "shirt", "shoe", "shoes", "pants", "jacket",
                    "new", "pack", "set", "pair", "with", "for", "the",
                }
                parts = title.split(" ")
                brand_parts = []
                for p in parts[:2]:
                    clean = p.strip("',\"").rstrip("'s")
                    if (clean and clean[0:1].isupper() and clean.isalpha()
                            and clean.lower() not in skip_words and len(clean) > 1):
                        if brand_parts and clean.lower() == brand_parts[-1].lower():
                            continue
                        brand_parts.append(clean)
                    else:
                        break
                brand = " ".join(brand_parts) if brand_parts else ""
        
        return brand.strip()
