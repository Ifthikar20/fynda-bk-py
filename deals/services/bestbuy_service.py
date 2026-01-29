"""
Best Buy Products API Service

Searches for products on Best Buy using their API.
Documentation: https://developer.bestbuy.com/documentation/products-api
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


@dataclass
class BestBuyDeal:
    """Represents a Best Buy product."""
    sku: str
    name: str
    description: str
    price: float
    original_price: Optional[float]
    discount_percent: int
    url: str
    image_url: str
    condition: str
    shipping: str
    rating: float
    reviews_count: int
    in_stock: bool
    category: str
    
    def to_dict(self):
        return {
            "id": f"bestbuy-{self.sku}",
            "title": self.name,
            "description": self.description,
            "price": self.price,
            "original_price": self.original_price or self.price,
            "discount_percent": self.discount_percent,
            "currency": "USD",
            "source": "Best Buy",
            "seller": "Best Buy",
            "seller_rating": 100.0,
            "url": self.url,
            "image_url": self.image_url,
            "condition": self.condition,
            "shipping": self.shipping,
            "rating": self.rating,
            "reviews_count": self.reviews_count,
            "in_stock": self.in_stock,
            "relevance_score": 0,
            "features": [],
            "fetched_at": datetime.now().isoformat(),
        }


class BestBuyService:
    """
    Service for searching products on Best Buy.
    
    Uses the Best Buy Products API.
    Falls back to empty results if API key is not configured.
    """
    
    BASE_URL = "https://api.bestbuy.com/v1"
    
    def __init__(self):
        self.api_key = os.getenv("BESTBUY_API_KEY")
    
    def search(self, query: str, limit: int = 10, max_price: Optional[float] = None) -> list[BestBuyDeal]:
        """
        Search for products on Best Buy.
        
        Args:
            query: Search query
            limit: Maximum number of results
            max_price: Maximum price filter
            
        Returns:
            List of BestBuyDeal objects
        """
        if not self.api_key:
            logger.info("Best Buy API key not configured")
            return []
        
        try:
            return self._search_api(query, limit, max_price)
        except Exception as e:
            logger.warning(f"Best Buy API error: {e}")
            return []
    
    def _search_api(self, query: str, limit: int, max_price: Optional[float]) -> list[BestBuyDeal]:
        """Search Best Buy using their Products API."""
        
        # Build search query
        search_parts = [f"(search={query})"]
        
        if max_price:
            search_parts.append(f"(salePrice<={max_price})")
        
        # Only in-stock items
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
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        deals = []
        
        for product in data.get("products", []):
            sale_price = product.get("salePrice", 0)
            regular_price = product.get("regularPrice", sale_price)
            
            # Calculate discount
            discount = 0
            if regular_price > sale_price:
                discount = int((1 - sale_price / regular_price) * 100)
            
            # Determine shipping
            shipping = "Free Shipping" if product.get("freeShipping") else "Shipping calculated"
            
            # Check availability
            in_stock = product.get("onlineAvailability", False) or product.get("inStoreAvailability", False)
            
            # Get category
            category_path = product.get("categoryPath", [])
            category = category_path[-1].get("name", "") if category_path else ""
            
            deals.append(BestBuyDeal(
                sku=str(product.get("sku", "")),
                name=product.get("name", ""),
                description=product.get("shortDescription", "") or "",
                price=sale_price,
                original_price=regular_price if regular_price != sale_price else None,
                discount_percent=discount,
                url=product.get("url", ""),
                image_url=product.get("image", ""),
                condition=product.get("condition", "New"),
                shipping=shipping,
                rating=product.get("customerReviewAverage", 0) or 0,
                reviews_count=product.get("customerReviewCount", 0) or 0,
                in_stock=in_stock,
                category=category,
            ))
        
        return deals


# Singleton instance
bestbuy_service = BestBuyService()
