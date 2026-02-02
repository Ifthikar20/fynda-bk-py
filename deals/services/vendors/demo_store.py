"""
Demo Store Service

Uses Platzi Fake Store API for demo purposes.
Provides real clothing product data with images.
"""

import requests
import logging
from typing import List, Optional

from .base_vendor import BaseVendorService, VendorProduct

logger = logging.getLogger(__name__)


class DemoStoreService(BaseVendorService):
    """
    Demo product service using Platzi Fake Store API.
    
    Free API with real clothing images - perfect for demos.
    No authentication required.
    """
    
    VENDOR_ID = "demo_store"
    VENDOR_NAME = "Demo Store"
    API_BASE_URL = "https://api.escuelajs.co/api/v1"
    
    def search_products(self, query: str, limit: int = 20) -> List[VendorProduct]:
        """Search for products matching the query."""
        try:
            response = requests.get(
                f"{self.API_BASE_URL}/products",
                params={"offset": 0, "limit": 50},
                timeout=self.timeout
            )
            response.raise_for_status()
            
            all_products = response.json()
            
            # Filter by query
            query_lower = query.lower()
            filtered = [
                p for p in all_products
                if query_lower in p.get("title", "").lower()
                or query_lower in p.get("description", "").lower()
                or query_lower in p.get("category", {}).get("name", "").lower()
            ]
            
            # If no matches, return all products
            if not filtered:
                filtered = all_products
            
            # Convert to VendorProduct format
            products = []
            for p in filtered[:limit]:
                images = p.get("images", [])
                image_url = images[0] if images else ""
                if image_url.startswith('["') or image_url.startswith("['"):
                    image_url = image_url.strip('[]"\'')
                
                price = p.get("price", 0)
                products.append(VendorProduct(
                    id=f"demo-{p['id']}",
                    title=p.get("title", "")[:100],
                    description=p.get("description", "")[:300],
                    price=price,
                    original_price=round(price * 1.3, 2),
                    currency="USD",
                    image_url=image_url,
                    product_url=f"https://demo.fynda.shop/product/{p['id']}",
                    affiliate_url=f"https://demo.fynda.shop/product/{p['id']}",
                    merchant_name=self.VENDOR_NAME,
                    merchant_id=self.VENDOR_ID,
                    network=self.VENDOR_ID,
                    category=p.get("category", {}).get("name", "Fashion"),
                    brand="Demo Brand",
                    in_stock=True,
                    discount_percent=30,
                ))
            
            logger.info(f"Demo Store returned {len(products)} products for '{query}'")
            return products
            
        except requests.RequestException as e:
            logger.error(f"Demo Store API error: {e}")
            return []
