"""
DummyJSON Service

Uses DummyJSON API - free mock data API.
Provides 100+ products across many categories.
"""

import requests
import logging
from typing import List

from .base_vendor import BaseVendorService, VendorProduct

logger = logging.getLogger(__name__)


class DummyJSONService(BaseVendorService):
    """
    DummyJSON API integration.
    
    Free API with 100+ products across categories:
    - smartphones, laptops
    - fragrances, skincare
    - groceries, home-decoration
    - furniture, tops, womens-dresses
    - womens-shoes, mens-shirts, mens-shoes, etc.
    
    API: https://dummyjson.com/
    """
    
    VENDOR_ID = "dummyjson"
    VENDOR_NAME = "DummyJSON"
    API_BASE_URL = "https://dummyjson.com"
    
    def search_products(self, query: str, limit: int = 20) -> List[VendorProduct]:
        """Search for products matching the query."""
        try:
            # DummyJSON has a search endpoint
            response = requests.get(
                f"{self.API_BASE_URL}/products/search",
                params={"q": query, "limit": min(limit, 100)},
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            all_products = data.get("products", [])
            
            # If no search results, get all products
            if not all_products:
                response = requests.get(
                    f"{self.API_BASE_URL}/products",
                    params={"limit": limit},
                    timeout=self.timeout
                )
                response.raise_for_status()
                data = response.json()
                all_products = data.get("products", [])
            
            # Convert to VendorProduct format
            products = []
            for p in all_products[:limit]:
                price = p.get("price", 0)
                discount_pct = p.get("discountPercentage", 0)
                original_price = round(price / (1 - discount_pct / 100), 2) if discount_pct else price
                
                # Get first image from thumbnail or images array
                image_url = p.get("thumbnail", "")
                if not image_url:
                    images = p.get("images", [])
                    image_url = images[0] if images else ""
                
                products.append(VendorProduct(
                    id=f"dummyjson-{p['id']}",
                    title=p.get("title", "")[:100],
                    description=p.get("description", "")[:300],
                    price=price,
                    original_price=original_price if original_price > price else None,
                    currency="USD",
                    image_url=image_url,
                    product_url=f"https://dummyjson.example/product/{p['id']}",
                    affiliate_url=f"https://dummyjson.example/product/{p['id']}",
                    merchant_name=self.VENDOR_NAME,
                    merchant_id=self.VENDOR_ID,
                    network=self.VENDOR_ID,
                    category=p.get("category", ""),
                    brand=p.get("brand", ""),
                    in_stock=p.get("stock", 0) > 0,
                    discount_percent=int(discount_pct) if discount_pct else None,
                    sku=p.get("sku", f"DJ-{p['id']}"),
                ))
            
            logger.info(f"DummyJSON returned {len(products)} products for '{query}'")
            return products
            
        except requests.RequestException as e:
            logger.error(f"DummyJSON API error: {e}")
            return []
