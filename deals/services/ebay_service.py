"""
eBay Browse API Service

Searches for products on eBay using the Browse API.
Documentation: https://developer.ebay.com/api-docs/buy/browse/overview.html
"""

import os
import logging
import base64
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


@dataclass
class EbayDeal:
    """Represents an eBay listing."""
    id: str
    title: str
    description: str
    price: float
    original_price: Optional[float]
    discount_percent: int
    currency: str
    url: str
    image_url: str
    condition: str
    shipping: str
    seller: str
    seller_rating: float
    location: str
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "original_price": self.original_price or self.price,
            "discount_percent": self.discount_percent,
            "currency": self.currency,
            "source": "eBay",
            "seller": self.seller,
            "seller_rating": self.seller_rating,
            "url": self.url,
            "image_url": self.image_url,
            "condition": self.condition,
            "shipping": self.shipping,
            "rating": None,
            "reviews_count": None,
            "in_stock": True,
            "relevance_score": 0,
            "features": [],
            "fetched_at": datetime.now().isoformat(),
        }


class EbayService:
    """
    Service for searching products on eBay.
    
    Uses the eBay Browse API for production.
    Falls back to mock data if credentials are not configured.
    """
    
    BASE_URL = "https://api.ebay.com"
    SANDBOX_URL = "https://api.sandbox.ebay.com"
    
    def __init__(self):
        self.app_id = os.getenv("EBAY_APP_ID")
        self.cert_id = os.getenv("EBAY_CERT_ID")
        self.use_sandbox = os.getenv("EBAY_SANDBOX", "false").lower() == "true"
        self._access_token = None
        self._token_expires = None
    
    @property
    def api_url(self):
        return self.SANDBOX_URL if self.use_sandbox else self.BASE_URL
    
    def _get_access_token(self) -> Optional[str]:
        """Get OAuth access token for eBay API."""
        if not self.app_id or not self.cert_id:
            return None
        
        # Check if token is still valid
        if self._access_token and self._token_expires:
            if datetime.now() < self._token_expires:
                return self._access_token
        
        try:
            auth_string = f"{self.app_id}:{self.cert_id}"
            auth_bytes = base64.b64encode(auth_string.encode()).decode()
            
            response = requests.post(
                f"{self.api_url}/identity/v1/oauth2/token",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {auth_bytes}",
                },
                data={
                    "grant_type": "client_credentials",
                    "scope": "https://api.ebay.com/oauth/api_scope",
                },
                timeout=10,
            )
            response.raise_for_status()
            
            data = response.json()
            self._access_token = data["access_token"]
            # Token expires in 2 hours, refresh at 1.5 hours
            from datetime import timedelta
            self._token_expires = datetime.now() + timedelta(hours=1, minutes=30)
            
            return self._access_token
            
        except Exception as e:
            logger.error(f"Failed to get eBay access token: {e}")
            return None
    
    def search(self, query: str, limit: int = 10, max_price: Optional[float] = None) -> list[EbayDeal]:
        """
        Search for products on eBay.
        
        Args:
            query: Search query
            limit: Maximum number of results
            max_price: Maximum price filter
            
        Returns:
            List of EbayDeal objects
        """
        token = self._get_access_token()
        if token:
            try:
                return self._search_api(query, limit, max_price, token)
            except Exception as e:
                logger.warning(f"eBay API error, using mock data: {e}")
        
        return []  # Return empty - orchestrator has mock data
    
    def _search_api(self, query: str, limit: int, max_price: Optional[float], token: str) -> list[EbayDeal]:
        """Search eBay using the Browse API."""
        url = f"{self.api_url}/buy/browse/v1/item_summary/search"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            "Content-Type": "application/json",
        }
        
        params = {
            "q": query,
            "limit": str(limit),
            "sort": "price",
        }
        
        # Add price filter
        if max_price:
            params["filter"] = f"price:[..{max_price}],priceCurrency:USD"
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        deals = []
        
        for item in data.get("itemSummaries", []):
            price_info = item.get("price", {})
            current_price = float(price_info.get("value", 0))
            
            # Get original price from marketing price
            marketing_price = item.get("marketingPrice", {})
            original_price = float(marketing_price.get("originalPrice", {}).get("value", current_price))
            
            # Calculate discount
            discount = 0
            if original_price > current_price:
                discount = int((1 - current_price / original_price) * 100)
            
            # Get shipping info
            shipping_options = item.get("shippingOptions", [])
            shipping = "Shipping calculated"
            if shipping_options:
                shipping_cost = shipping_options[0].get("shippingCost", {}).get("value", "0")
                if float(shipping_cost) == 0:
                    shipping = "Free Shipping"
                else:
                    shipping = f"${shipping_cost} shipping"
            
            # Get seller info
            seller = item.get("seller", {})
            
            deals.append(EbayDeal(
                id=f"ebay-{item.get('itemId', '')}",
                title=item.get("title", ""),
                description=item.get("shortDescription", ""),
                price=current_price,
                original_price=original_price if original_price != current_price else None,
                discount_percent=discount,
                currency=price_info.get("currency", "USD"),
                url=item.get("itemWebUrl", ""),
                image_url=item.get("image", {}).get("imageUrl", ""),
                condition=item.get("condition", "New"),
                shipping=shipping,
                seller=seller.get("username", ""),
                seller_rating=float(seller.get("feedbackPercentage", 0)),
                location=item.get("itemLocation", {}).get("city", ""),
            ))
        
        return deals


# Singleton instance
ebay_service = EbayService()
