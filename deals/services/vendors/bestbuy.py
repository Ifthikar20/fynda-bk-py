"""
Best Buy Vendor

Searches Best Buy via their Products API.
Extends BaseVendorService — returns VendorProduct.
"""

import os
import logging
from typing import List, Optional
from datetime import datetime
import requests

from .base_vendor import BaseVendorService, VendorProduct

logger = logging.getLogger(__name__)


class BestBuyVendor(BaseVendorService):
    """Best Buy product search via Products API."""
    
    VENDOR_ID = "bestbuy"
    VENDOR_NAME = "Best Buy"
    PRIORITY = 70
    TIMEOUT = 15
    
    BASE_URL = "https://api.bestbuy.com/v1"
    
    def _load_credentials(self):
        self.api_key = os.getenv("BESTBUY_API_KEY")
        if self.api_key:
            logger.info("Best Buy vendor initialized")
    
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    # ── BaseVendorService._do_search implementation ─────────────
    
    def _do_search(self, query: str, limit: int) -> List[VendorProduct]:
        if not self.is_configured():
            return []
        
        # Build search filter
        search_parts = [f"(search={query})"]
        search_parts.append("(inStoreAvailability=true|onlineAvailability=true)")
        search_query = "&".join(search_parts)
        
        url = f"{self.BASE_URL}/products({search_query})"
        
        params = {
            "apiKey": self.api_key,
            "format": "json",
            "pageSize": str(limit),
            "show": "sku,name,shortDescription,salePrice,regularPrice,url,image,condition,freeShipping,customerReviewAverage,customerReviewCount,inStoreAvailability,onlineAvailability,categoryPath",
            "sort": "salePrice.asc",
        }
        
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for product in data.get("products", []):
            sale_price = product.get("salePrice", 0)
            regular_price = product.get("regularPrice", sale_price)
            
            discount = 0
            if regular_price > sale_price:
                discount = int((1 - sale_price / regular_price) * 100)
            
            shipping = "Free Shipping" if product.get("freeShipping") else "Shipping calculated"
            in_stock = product.get("onlineAvailability", False) or product.get("inStoreAvailability", False)
            
            category_path = product.get("categoryPath", [])
            category = category_path[-1].get("name", "") if category_path else ""
            
            results.append(VendorProduct(
                id=f"bestbuy-{product.get('sku', '')}",
                title=product.get("name", ""),
                description=product.get("shortDescription", "") or "",
                price=sale_price,
                original_price=regular_price if regular_price != sale_price else None,
                discount_percent=discount,
                currency="USD",
                url=product.get("url", ""),
                image_url=product.get("image", ""),
                source="Best Buy",
                merchant_name="Best Buy",
                seller="Best Buy",
                seller_rating=100.0,
                condition=product.get("condition", "New"),
                shipping=shipping,
                rating=product.get("customerReviewAverage", 0) or 0,
                reviews_count=product.get("customerReviewCount", 0) or 0,
                in_stock=in_stock,
                category=category,
                fetched_at=datetime.now().isoformat(),
            ))
        
        logger.info(f"Best Buy returned {len(results)} products for '{query}'")
        return results
