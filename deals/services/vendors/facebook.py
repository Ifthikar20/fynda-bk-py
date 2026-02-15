"""
Facebook Marketplace Vendor

Searches Facebook Marketplace via RapidAPI.
Extends BaseVendorService — returns VendorProduct.
"""

import os
import logging
import hashlib
from typing import List, Optional
from datetime import datetime
import requests

from .base_vendor import BaseVendorService, VendorProduct

logger = logging.getLogger(__name__)


class FacebookVendor(BaseVendorService):
    """Facebook Marketplace search via RapidAPI."""
    
    VENDOR_ID = "facebook"
    VENDOR_NAME = "Facebook Marketplace"
    PRIORITY = 50
    TIMEOUT = 15
    
    API_HOST = "facebook-marketplace.p.rapidapi.com"
    
    def _load_credentials(self):
        self.api_key = os.getenv("RAPIDAPI_KEY")
        if self.api_key:
            logger.info("Facebook Marketplace vendor initialized")
    
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    # ── BaseVendorService._do_search implementation ─────────────
    
    def _do_search(self, query: str, limit: int) -> List[VendorProduct]:
        if not self.is_configured():
            # No API key — return nothing instead of fake mock listings
            logger.debug("Facebook Marketplace vendor not configured, skipping")
            return []
        
        try:
            return self._search_api(query, limit)
        except Exception as e:
            logger.warning(f"Facebook Marketplace API error: {e}")
            return []
    
    def _search_api(self, query: str, limit: int) -> List[VendorProduct]:
        """Search Facebook Marketplace via RapidAPI."""
        url = f"https://{self.API_HOST}/search"
        
        response = requests.get(
            url,
            headers={
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": self.API_HOST,
            },
            params={
                "query": query,
                "location": "new york",
                "limit": str(limit),
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("listings", []):
            price_str = item.get("price", "$0")
            price = float(price_str.replace("$", "").replace(",", "")) if price_str else 0
            
            results.append(VendorProduct(
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
                features=["local", "marketplace"],
                fetched_at=datetime.now().isoformat(),
            ))
        
        logger.info(f"Facebook returned {len(results)} products for '{query}'")
        return results
    
    def _get_mock_listings(self, query: str, limit: int) -> List[VendorProduct]:
        """Generate mock Facebook Marketplace listings."""
        base_prices = {
            "camera": [350, 500, 750, 280, 620],
            "laptop": [450, 800, 650, 1100, 380],
            "phone": [250, 400, 550, 180, 700],
            "default": [150, 300, 450, 200, 550],
        }
        
        category = "default"
        for cat in base_prices:
            if cat in query.lower():
                category = cat
                break
        
        prices = base_prices[category]
        
        templates = [
            {"title": f"{query} - Like New Condition", "condition": "Like new", "seller": "Local Seller"},
            {"title": f"{query} - Great Deal!", "condition": "Good", "seller": "Tech Enthusiast"},
            {"title": f"Used {query} - Works Perfectly", "condition": "Good", "seller": "Moving Sale"},
            {"title": f"{query} with Accessories", "condition": "Like new", "seller": "Photography Buff"},
            {"title": f"Barely Used {query}", "condition": "Like new", "seller": "Upgrade Sale"},
        ]
        
        results = []
        for i, (template, price) in enumerate(zip(templates[:limit], prices[:limit])):
            listing_id = hashlib.md5(f"{query}-fb-{i}".encode()).hexdigest()[:10]
            
            results.append(VendorProduct(
                id=f"fb-{listing_id}",
                title=template["title"],
                description=f"Selling my {query}. In great condition. Serious buyers only.",
                price=float(price),
                currency="USD",
                url=f"https://facebook.com/marketplace/item/{listing_id}",
                image_url=f"https://picsum.photos/seed/{listing_id}/400/300",
                source="Facebook Marketplace",
                seller=template["seller"],
                condition=template["condition"],
                shipping="Local pickup",
                features=["local", "marketplace"],
                fetched_at=datetime.now().isoformat(),
            ))
        
        return results
