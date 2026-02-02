"""
FakeStore Service

Uses FakeStoreAPI - a free fake e-commerce API.
Provides 20 products across clothing, jewelry, electronics.
"""

import requests
import logging
from typing import List

from .base_vendor import BaseVendorService, VendorProduct

logger = logging.getLogger(__name__)


class FakeStoreService(BaseVendorService):
    """
    FakeStore API integration.
    
    Free API with 20 products:
    - men's clothing
    - women's clothing
    - jewelery
    - electronics
    
    API: https://fakestoreapi.com/
    """
    
    VENDOR_ID = "fakestore"
    VENDOR_NAME = "FakeStore"
    API_BASE_URL = "https://fakestoreapi.com"
    
    def search_products(self, query: str, limit: int = 20) -> List[VendorProduct]:
        """Search for products matching the query."""
        try:
            # FakeStore doesn't have search, get all and filter
            response = requests.get(
                f"{self.API_BASE_URL}/products",
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
                or query_lower in p.get("category", "").lower()
            ]
            
            # If no matches, return all
            if not filtered:
                filtered = all_products
            
            # Convert to VendorProduct format
            products = []
            for p in filtered[:limit]:
                price = p.get("price", 0)
                original_price = round(price * 1.25, 2)
                discount = int((1 - price / original_price) * 100) if original_price > price else 0
                
                products.append(VendorProduct(
                    id=f"fakestore-{p['id']}",
                    title=p.get("title", "")[:100],
                    description=p.get("description", "")[:300],
                    price=price,
                    original_price=original_price,
                    currency="USD",
                    image_url=p.get("image", ""),
                    product_url=f"https://fakestore.example/product/{p['id']}",
                    affiliate_url=f"https://fakestore.example/product/{p['id']}",
                    merchant_name=self.VENDOR_NAME,
                    merchant_id=self.VENDOR_ID,
                    network=self.VENDOR_ID,
                    category=p.get("category", ""),
                    brand="FakeStore Brand",
                    in_stock=True,
                    discount_percent=discount if discount > 0 else None,
                    sku=f"FS-{p['id']}",
                ))
            
            logger.info(f"FakeStore returned {len(products)} products for '{query}'")
            return products
            
        except requests.RequestException as e:
            logger.error(f"FakeStore API error: {e}")
            return []
