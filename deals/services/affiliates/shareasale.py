"""
ShareASale API Service

Provides access to 16,000+ merchant product catalogs.

API Documentation: ShareASale Dashboard → Tools → Merchant API
"""

import os
import logging
import hashlib
import random
import hmac
import time
import requests
from datetime import datetime
from typing import Optional

from .affiliate_base import AffiliateProduct, AffiliateService, AuthenticationError

logger = logging.getLogger(__name__)


class ShareASaleService(AffiliateService):
    """
    ShareASale integration using their Affiliate API.
    
    Provides access to 16,000+ merchants including:
    - Reebok, Fanatics
    - Wayfair, Overstock
    - Warby Parker, ModCloth
    - Many smaller/niche retailers
    
    Required environment variables:
    - SHAREASALE_AFFILIATE_ID: Your affiliate ID
    - SHAREASALE_API_TOKEN: API token
    - SHAREASALE_API_SECRET: API secret key
    """
    
    NETWORK_NAME = "shareasale"
    API_BASE_URL = "https://api.shareasale.com/w.cfm"
    
    def _load_credentials(self):
        """Load ShareASale API credentials from environment."""
        self.affiliate_id = os.getenv("SHAREASALE_AFFILIATE_ID")
        self.api_key = os.getenv("SHAREASALE_API_TOKEN")
        self.api_secret = os.getenv("SHAREASALE_API_SECRET")
        self.timeout = 15
    
    def is_configured(self) -> bool:
        """Check if ShareASale credentials are configured."""
        return all([self.affiliate_id, self.api_key, self.api_secret])
    
    def _generate_signature(self, timestamp: str, action: str) -> str:
        """
        Generate HMAC signature for API authentication.
        
        ShareASale requires: API Token + ':' + Timestamp + ':' + Action + ':' + API Secret
        """
        message = f"{self.api_key}:{timestamp}:{action}:{self.api_secret}"
        signature = hashlib.sha256(message.encode()).hexdigest()
        return signature
    
    def search_products(self, query: str, limit: int = 20) -> list[AffiliateProduct]:
        """
        Search ShareASale merchant catalogs.
        
        Note: ShareASale's API is more limited for product search.
        Primary method is via product data feeds (FTP).
        
        Args:
            query: Product search query
            limit: Maximum results
            
        Returns:
            List of products from ShareASale merchants
        """
        if self.is_configured():
            try:
                return self._search_api(query, limit)
            except AuthenticationError:
                logger.error("ShareASale API authentication failed")
            except Exception as e:
                logger.warning(f"ShareASale API error, using mock: {e}")
        
        return self._get_mock_products(query, limit)
    
    def _search_api(self, query: str, limit: int) -> list[AffiliateProduct]:
        """
        Search ShareASale products.
        
        Note: ShareASale's merchant search is limited.
        For full product data, use their product feeds via FTP.
        This implementation searches available merchants.
        """
        timestamp = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        action = "merchantSearch"
        
        signature = self._generate_signature(timestamp, action)
        
        headers = {
            "x-ShareASale-Date": timestamp,
            "x-ShareASale-Authentication": signature,
        }
        
        params = {
            "affiliateId": self.affiliate_id,
            "token": self.api_key,
            "version": "2.9",
            "action": action,
            "keywords": query,
            "format": "json",
        }
        
        response = requests.get(
            self.API_BASE_URL,
            headers=headers,
            params=params,
            timeout=self.timeout
        )
        
        if response.status_code == 401:
            raise AuthenticationError("Invalid ShareASale credentials")
        
        response.raise_for_status()
        data = response.json()
        
        # ShareASale returns merchants, not individual products
        # Convert merchant data to product-like format
        products = []
        for merchant in data.get("merchants", [])[:limit]:
            try:
                products.append(AffiliateProduct(
                    id=f"sas-m{merchant.get('merchantId', '')}",
                    title=f"{query.title()} at {merchant.get('merchantName', 'Store')}",
                    description=merchant.get("programDescription", "")[:500],
                    price=0.0,  # Merchant-level, no specific price
                    original_price=None,
                    currency="USD",
                    image_url=merchant.get("merchantLogoUrl", ""),
                    product_url=merchant.get("merchantUrl", ""),
                    affiliate_url=self.generate_affiliate_link(merchant.get("merchantUrl", "")),
                    merchant_name=merchant.get("merchantName", ""),
                    merchant_id=str(merchant.get("merchantId", "")),
                    network=self.NETWORK_NAME,
                    category=merchant.get("category", ""),
                    brand=merchant.get("merchantName", ""),
                    in_stock=True,
                    sku=None,
                    upc=None,
                ))
            except Exception as e:
                logger.debug(f"Error parsing ShareASale merchant: {e}")
                continue
        
        logger.info(f"ShareASale API returned {len(products)} merchants for '{query}'")
        return products
    
    def _get_mock_products(self, query: str, limit: int) -> list[AffiliateProduct]:
        """Generate mock ShareASale products for demo/testing."""
        
        merchants = [
            {"name": "Wayfair", "id": "47910", "category": "Home & Furniture"},
            {"name": "Reebok", "id": "28128", "category": "Sports & Fitness"},
            {"name": "Fanatics", "id": "26550", "category": "Sports Apparel"},
            {"name": "ModCloth", "id": "43976", "category": "Fashion"},
            {"name": "Warby Parker", "id": "39233", "category": "Eyewear"},
            {"name": "Sun Basket", "id": "70882", "category": "Food & Meal Kits"},
            {"name": "Cratejoy", "id": "47823", "category": "Subscription Boxes"},
            {"name": "Zazzle", "id": "26193", "category": "Custom Products"},
            {"name": "StackSocial", "id": "47050", "category": "Tech Deals"},
            {"name": "StockX", "id": "94621", "category": "Sneakers & Streetwear"},
        ]
        
        products = []
        for i in range(min(limit, len(merchants) * 2)):
            merchant = merchants[i % len(merchants)]
            pid = hashlib.md5(f"sas-{query}-{i}".encode()).hexdigest()[:12]
            
            base_price = 40 + random.randint(0, 350)
            has_discount = random.random() > 0.3
            sale_price = base_price * 0.75 if has_discount else base_price
            
            products.append(AffiliateProduct(
                id=f"sas-{pid}",
                title=f"{query.title()} - {merchant['name']} Collection" if i % 2 == 0 else f"Shop {query.title()} Now",
                description=f"Find the best {query} deals at {merchant['name']}. Exclusive selection.",
                price=round(sale_price, 2),
                original_price=round(base_price, 2) if has_discount else None,
                currency="USD",
                image_url=f"https://picsum.photos/seed/sas{query}{i}/400/400",
                product_url=f"https://{merchant['name'].lower().replace(' ', '')}.com/shop/{pid}",
                affiliate_url=f"https://www.shareasale.com/r.cfm?u={self.affiliate_id or '12345'}&m={merchant['id']}&d={pid}",
                merchant_name=merchant["name"],
                merchant_id=merchant["id"],
                network=self.NETWORK_NAME,
                category=merchant["category"],
                brand=query.title().split()[0] if query else "Brand",
                in_stock=random.random() > 0.1,
                sku=f"SAS-{pid[:8].upper()}",
                upc=None,
            ))
        
        return products
    
    def generate_affiliate_link(self, product_url: str) -> str:
        """Generate ShareASale affiliate tracking link."""
        if self.affiliate_id:
            return f"https://www.shareasale.com/r.cfm?u={self.affiliate_id}&urllink={product_url}"
        return product_url


# Singleton instance
shareasale_service = ShareASaleService()
