"""
Facebook Marketplace Service

Searches for products on Facebook Marketplace.
Note: Facebook Marketplace API requires Meta partner approval.
This service uses RapidAPI's unofficial Marketplace endpoint as a fallback.
"""

import os
import logging
import hashlib
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


@dataclass
class FacebookDeal:
    """Represents a Facebook Marketplace listing."""
    id: str
    title: str
    description: str
    price: float
    currency: str
    url: str
    image_url: str
    condition: str
    location: str
    seller: str
    posted_at: str
    
    def to_dict(self):
        return {
            "id": f"fb-{self.id}",
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "original_price": self.price,
            "discount_percent": 0,
            "currency": self.currency,
            "source": "Facebook Marketplace",
            "seller": self.seller,
            "seller_rating": None,
            "url": self.url,
            "image_url": self.image_url,
            "condition": self.condition,
            "shipping": "Local pickup",
            "rating": None,
            "reviews_count": None,
            "in_stock": True,
            "relevance_score": 0,
            "features": ["local", "marketplace"],
            "fetched_at": datetime.now().isoformat(),
        }


class FacebookMarketplaceService:
    """
    Service for searching products on Facebook Marketplace.
    
    Uses RapidAPI's Facebook Marketplace endpoint.
    Falls back to mock data if API is not configured.
    """
    
    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_KEY")
        self.api_host = "facebook-marketplace.p.rapidapi.com"
    
    def search(self, query: str, limit: int = 10, max_price: Optional[float] = None, 
               location: str = "new york") -> list[FacebookDeal]:
        """
        Search for products on Facebook Marketplace.
        
        Args:
            query: Search query
            limit: Maximum number of results
            max_price: Maximum price filter
            location: Location for local listings
            
        Returns:
            List of FacebookDeal objects
        """
        if self.api_key:
            try:
                return self._search_api(query, limit, max_price, location)
            except Exception as e:
                logger.warning(f"Facebook Marketplace API error, using mock: {e}")
        
        return self._get_mock_listings(query, limit, max_price)
    
    def _search_api(self, query: str, limit: int, max_price: Optional[float], 
                    location: str) -> list[FacebookDeal]:
        """Search Facebook Marketplace using RapidAPI."""
        url = f"https://{self.api_host}/search"
        
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host,
        }
        
        params = {
            "query": query,
            "location": location,
            "limit": str(limit),
        }
        
        if max_price:
            params["max_price"] = str(int(max_price))
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        deals = []
        
        for item in data.get("listings", []):
            price_str = item.get("price", "$0")
            # Parse price from string like "$500" or "$1,200"
            price = float(price_str.replace("$", "").replace(",", "")) if price_str else 0
            
            deals.append(FacebookDeal(
                id=item.get("id", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
                price=price,
                currency="USD",
                url=item.get("url", f"https://facebook.com/marketplace/item/{item.get('id', '')}"),
                image_url=item.get("image", ""),
                condition=item.get("condition", "Used"),
                location=item.get("location", location),
                seller=item.get("seller", {}).get("name", "Facebook User"),
                posted_at=item.get("posted_at", ""),
            ))
        
        return deals
    
    def _get_mock_listings(self, query: str, limit: int, max_price: Optional[float]) -> list[FacebookDeal]:
        """Generate mock Facebook Marketplace listings."""
        
        # Create realistic mock data based on query
        base_prices = {
            "camera": [350, 500, 750, 280, 620],
            "laptop": [450, 800, 650, 1100, 380],
            "phone": [250, 400, 550, 180, 700],
            "default": [150, 300, 450, 200, 550],
        }
        
        # Find matching category
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
        
        deals = []
        for i, (template, price) in enumerate(zip(templates[:limit], prices[:limit])):
            # Apply price filter
            if max_price and price > max_price:
                continue
            
            listing_id = hashlib.md5(f"{query}-fb-{i}".encode()).hexdigest()[:10]
            
            deals.append(FacebookDeal(
                id=listing_id,
                title=template["title"],
                description=f"Selling my {query}. In great condition. Serious buyers only.",
                price=float(price),
                currency="USD",
                url=f"https://facebook.com/marketplace/item/{listing_id}",
                image_url=f"https://picsum.photos/seed/{listing_id}/400/300",
                condition=template["condition"],
                location="New York, NY",
                seller=template["seller"],
                posted_at=datetime.now().isoformat(),
            ))
        
        return deals


# Singleton instance
facebook_service = FacebookMarketplaceService()
