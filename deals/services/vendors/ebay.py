"""
eBay Vendor

Searches eBay via the Browse API.
Extends BaseVendorService — returns VendorProduct.
"""

import os
import logging
from typing import List, Optional
from datetime import datetime
import requests
import base64

from .base_vendor import BaseVendorService, VendorProduct, AuthenticationError

logger = logging.getLogger(__name__)


class EbayVendor(BaseVendorService):
    """eBay product search via Browse API."""
    
    VENDOR_ID = "ebay"
    VENDOR_NAME = "eBay"
    PRIORITY = 85
    TIMEOUT = 15
    
    AUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    
    def _load_credentials(self):
        self.client_id = os.getenv("EBAY_CLIENT_ID")
        self.client_secret = os.getenv("EBAY_CLIENT_SECRET")
        self._access_token = None
        
        if self.client_id and self.client_secret:
            logger.info("eBay vendor initialized")
        else:
            logger.info("eBay credentials not set — eBay vendor disabled")
    
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)
    
    def _get_access_token(self) -> Optional[str]:
        """Get OAuth2 access token for eBay API."""
        if self._access_token:
            return self._access_token
        if not self.is_configured():
            return None
            
        try:
            credentials = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            
            response = requests.post(
                self.AUTH_URL,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {credentials}",
                },
                data={
                    "grant_type": "client_credentials",
                    "scope": "https://api.ebay.com/oauth/api_scope",
                },
                timeout=10,
            )
            response.raise_for_status()
            self._access_token = response.json().get("access_token")
            return self._access_token
        except Exception as e:
            logger.error(f"eBay OAuth failed: {e}")
            return None
    
    # ── BaseVendorService._do_search implementation ─────────────
    
    def _do_search(self, query: str, limit: int) -> List[VendorProduct]:
        if not self.is_configured():
            return []
        
        token = self._get_access_token()
        if not token:
            raise AuthenticationError("Could not obtain eBay access token")
        
        params = {
            "q": query,
            "limit": str(min(limit, 50)),
            "sort": "price",
            "filter": "deliveryCountry:US,conditions:{NEW}",
        }
        
        response = requests.get(
            self.SEARCH_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                "X-EBAY-C-ENDUSERCTX": "contextualLocation=country=US",
            },
            params=params,
            timeout=self.timeout,
        )
        
        # Token expired — retry once
        if response.status_code == 401:
            self._access_token = None
            token = self._get_access_token()
            if not token:
                raise AuthenticationError("eBay token refresh failed")
            response = requests.get(
                self.SEARCH_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                    "X-EBAY-C-ENDUSERCTX": "contextualLocation=country=US",
                },
                params=params,
                timeout=self.timeout,
            )
        
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("itemSummaries", []):
            try:
                product = self._parse_item(item)
                if product:
                    results.append(product)
            except Exception as e:
                logger.debug(f"Failed to parse eBay item: {e}")
        
        logger.info(f"eBay returned {len(results)} products for '{query}'")
        return results
    
    def _parse_item(self, item: dict) -> Optional[VendorProduct]:
        """Parse an eBay item summary into VendorProduct."""
        price_data = item.get("price", {})
        price_str = price_data.get("value", "0")
        try:
            price = float(price_str)
        except ValueError:
            return None
        
        if price <= 0:
            return None
        
        currency = price_data.get("currency", "USD")
        
        # Image
        image = item.get("image", {})
        image_url = image.get("imageUrl", "")
        
        # Condition
        condition = item.get("condition", "New")
        
        # Shipping
        shipping_options = item.get("shippingOptions", [])
        shipping = "Standard"
        if shipping_options:
            cost = shipping_options[0].get("shippingCost", {})
            if cost.get("value") == "0.00":
                shipping = "Free Shipping"
        
        # Seller
        seller_info = item.get("seller", {})
        seller = seller_info.get("username", "eBay Seller")
        seller_rating = None
        feedback = seller_info.get("feedbackPercentage")
        if feedback:
            try:
                seller_rating = float(feedback)
            except ValueError:
                pass
        
        return VendorProduct(
            id=f"ebay-{item.get('itemId', '')}",
            title=item.get("title", ""),
            description=item.get("shortDescription", "") or item.get("title", ""),
            price=price,
            currency=currency,
            url=item.get("itemWebUrl", ""),
            image_url=image_url,
            source="eBay",
            merchant_name="eBay",
            brand=item.get("brand", ""),
            condition=condition,
            shipping=shipping,
            seller=seller,
            seller_rating=seller_rating,
            in_stock=True,
            category=item.get("categories", [{}])[0].get("categoryName", "") if item.get("categories") else "",
            fetched_at=datetime.now().isoformat(),
        )
