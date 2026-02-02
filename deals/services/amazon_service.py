"""
Amazon Product Search via RapidAPI

Searches for products on Amazon using the Real-Time Amazon Data API.
Documentation: https://rapidapi.com/letscrape-6bRBa3QguO5/api/real-time-amazon-data
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


@dataclass
class AmazonDeal:
    """Represents an Amazon product listing."""
    id: str
    title: str
    description: str
    price: float
    original_price: Optional[float]
    discount_percent: int
    currency: str
    url: str
    image_url: str
    rating: Optional[float]
    reviews_count: Optional[int]
    is_prime: bool
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "original_price": self.original_price or self.price,
            "discount_percent": self.discount_percent,
            "currency": self.currency,
            "source": "Amazon",
            "seller": "Amazon",
            "seller_rating": 5.0,  # Amazon default
            "url": self.url,
            "image_url": self.image_url,
            "condition": "New",
            "shipping": "Prime" if self.is_prime else "Standard",
            "rating": self.rating,
            "reviews_count": self.reviews_count,
            "in_stock": True,
            "relevance_score": 0,
            "features": [],
            "fetched_at": datetime.now().isoformat(),
        }


class AmazonService:
    """
    Service for searching products on Amazon via RapidAPI.
    
    Uses the Real-Time Amazon Data API for product searches.
    Falls back gracefully if API key is not configured.
    """
    
    BASE_URL = "https://real-time-amazon-data.p.rapidapi.com"
    
    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_KEY")
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            logger.info("Amazon RapidAPI service initialized")
        else:
            logger.warning("RAPIDAPI_KEY not set - Amazon search disabled")
    
    def _get_headers(self) -> dict:
        """Get API headers."""
        return {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "real-time-amazon-data.p.rapidapi.com"
        }
    
    def search(
        self, 
        query: str, 
        limit: int = 10, 
        max_price: Optional[float] = None,
        country: str = "US"
    ) -> List[AmazonDeal]:
        """
        Search for products on Amazon.
        
        Args:
            query: Search query
            limit: Maximum number of results
            max_price: Maximum price filter
            country: Amazon marketplace (US, UK, DE, etc.)
            
        Returns:
            List of AmazonDeal objects
        """
        if not self.enabled:
            logger.debug("Amazon search skipped - API key not configured")
            return []
        
        try:
            return self._search_api(query, limit, max_price, country)
        except Exception as e:
            logger.error(f"Amazon RapidAPI error: {e}")
            return []
    
    def _search_api(
        self, 
        query: str, 
        limit: int, 
        max_price: Optional[float],
        country: str
    ) -> List[AmazonDeal]:
        """Execute Amazon search via RapidAPI."""
        url = f"{self.BASE_URL}/search"
        
        params = {
            "query": query,
            "page": "1",
            "country": country,
            "sort_by": "RELEVANCE",
            "product_condition": "ALL"
        }
        
        # Add price filter if specified
        if max_price:
            params["max_price"] = str(int(max_price))
        
        response = requests.get(
            url, 
            headers=self._get_headers(), 
            params=params,
            timeout=15
        )
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") != "OK":
            logger.warning(f"Amazon API returned status: {data.get('status')}")
            return []
        
        deals = []
        products = data.get("data", {}).get("products", [])
        
        for item in products[:limit]:
            try:
                deal = self._parse_product(item)
                if deal:
                    deals.append(deal)
            except Exception as e:
                logger.debug(f"Failed to parse Amazon product: {e}")
                continue
        
        logger.info(f"Amazon search returned {len(deals)} products for '{query}'")
        return deals
    
    def _parse_product(self, item: dict) -> Optional[AmazonDeal]:
        """Parse a product from API response."""
        # Extract price
        price_str = item.get("product_price", "")
        if not price_str:
            return None
        
        # Parse price (remove currency symbol)
        try:
            price = float(price_str.replace("$", "").replace(",", "").strip())
        except ValueError:
            return None
        
        # Parse original price
        original_price = None
        original_str = item.get("product_original_price", "")
        if original_str:
            try:
                original_price = float(original_str.replace("$", "").replace(",", "").strip())
            except ValueError:
                pass
        
        # Calculate discount
        discount = 0
        if original_price and original_price > price:
            discount = int((1 - price / original_price) * 100)
        
        # Parse rating
        rating = None
        rating_str = item.get("product_star_rating")
        if rating_str:
            try:
                rating = float(rating_str)
            except ValueError:
                pass
        
        # Parse reviews count
        reviews = None
        reviews_str = item.get("product_num_ratings")
        if reviews_str:
            try:
                reviews = int(str(reviews_str).replace(",", ""))
            except ValueError:
                pass
        
        return AmazonDeal(
            id=f"amazon-{item.get('asin', '')}",
            title=item.get("product_title", ""),
            description=item.get("product_title", ""),  # API doesn't provide separate description
            price=price,
            original_price=original_price,
            discount_percent=discount,
            currency="USD",
            url=item.get("product_url", ""),
            image_url=item.get("product_photo", ""),
            rating=rating,
            reviews_count=reviews,
            is_prime=item.get("is_prime", False),
        )
    
    def get_product_details(self, asin: str, country: str = "US") -> Optional[AmazonDeal]:
        """
        Get detailed product information by ASIN.
        
        Args:
            asin: Amazon Standard Identification Number
            country: Amazon marketplace
            
        Returns:
            AmazonDeal or None if not found
        """
        if not self.enabled:
            return None
        
        try:
            url = f"{self.BASE_URL}/product-details"
            params = {"asin": asin, "country": country}
            
            response = requests.get(
                url, 
                headers=self._get_headers(), 
                params=params,
                timeout=15
            )
            response.raise_for_status()
            
            data = response.json()
            if data.get("status") == "OK":
                product = data.get("data", {})
                return self._parse_product(product)
            
            return None
        except Exception as e:
            logger.error(f"Failed to get Amazon product details: {e}")
            return None


# Singleton instance
amazon_service = AmazonService()
