"""
CJ Affiliate (Commission Junction) API Service

Provides access to 3,000+ brand product catalogs via GraphQL API.

API Documentation: https://developers.cj.com/
"""

import os
import logging
import hashlib
import random
import requests
from typing import Optional

from .affiliate_base import AffiliateProduct, AffiliateService, AuthenticationError

logger = logging.getLogger(__name__)


class CJAffiliateService(AffiliateService):
    """
    CJ Affiliate integration using their GraphQL Product Feed API.
    
    Provides access to major brands like:
    - Home Depot, Lowe's
    - Nike, Adidas
    - Best Buy, Newegg
    - Target, Walmart (select products)
    - And 3,000+ more
    
    Required environment variables:
    - CJ_AFFILIATE_API_TOKEN: Personal Access Token from developer portal
    - CJ_WEBSITE_ID: Your registered website ID
    """
    
    NETWORK_NAME = "cj"
    API_BASE_URL = "https://ads.api.cj.com/v3/product-search"
    
    def _load_credentials(self):
        """Load CJ API credentials from environment."""
        self.api_key = os.getenv("CJ_AFFILIATE_API_TOKEN")
        self.website_id = os.getenv("CJ_WEBSITE_ID")
        self.timeout = 15
    
    def search_products(self, query: str, limit: int = 20) -> list[AffiliateProduct]:
        """
        Search CJ product catalogs.
        
        Args:
            query: Product search query
            limit: Maximum results (max 100)
            
        Returns:
            List of products from CJ merchants
        """
        if self.is_configured():
            try:
                return self._search_api(query, limit)
            except AuthenticationError:
                logger.error("CJ API authentication failed - check API token")
            except Exception as e:
                logger.warning(f"CJ API error, using mock: {e}")
        
        return self._get_mock_products(query, limit)
    
    def _search_api(self, query: str, limit: int) -> list[AffiliateProduct]:
        """
        Search CJ using their Product Search API.
        
        CJ uses REST API with bearer token authentication.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        params = {
            "website-id": self.website_id,
            "keywords": query,
            "records-per-page": min(limit, 100),
        }
        
        response = requests.get(
            self.API_BASE_URL,
            headers=headers,
            params=params,
            timeout=self.timeout
        )
        
        if response.status_code == 401:
            raise AuthenticationError("Invalid CJ API token")
        
        response.raise_for_status()
        data = response.json()
        
        products = []
        for item in data.get("products", [])[:limit]:
            try:
                price = float(item.get("price", 0))
                sale_price = float(item.get("sale-price", price))
                
                products.append(AffiliateProduct(
                    id=f"cj-{item.get('catalog-id', '')}-{item.get('sku', '')}",
                    title=item.get("name", "")[:200],
                    description=item.get("description", "")[:500],
                    price=sale_price if sale_price > 0 else price,
                    original_price=price if sale_price < price else None,
                    currency=item.get("currency", "USD"),
                    image_url=item.get("image-url", ""),
                    product_url=item.get("buy-url", ""),
                    affiliate_url=item.get("link-url", item.get("buy-url", "")),
                    merchant_name=item.get("advertiser-name", ""),
                    merchant_id=str(item.get("advertiser-id", "")),
                    network=self.NETWORK_NAME,
                    category=item.get("advertiser-category", ""),
                    brand=item.get("manufacturer-name", ""),
                    in_stock=item.get("in-stock", "yes").lower() == "yes",
                    sku=item.get("sku"),
                    upc=item.get("upc"),
                ))
            except Exception as e:
                logger.debug(f"Error parsing CJ product: {e}")
                continue
        
        logger.info(f"CJ API returned {len(products)} products for '{query}'")
        return products
    
    def _get_mock_products(self, query: str, limit: int) -> list[AffiliateProduct]:
        """Generate mock CJ products for demo/testing."""
        
        # Simulate real CJ merchant data
        merchants = [
            {"name": "Best Buy", "id": "2987", "category": "Electronics"},
            {"name": "Home Depot", "id": "1234", "category": "Home & Garden"},
            {"name": "Newegg", "id": "4567", "category": "Electronics"},
            {"name": "Nike", "id": "7890", "category": "Apparel"},
            {"name": "Target", "id": "3456", "category": "Department Store"},
            {"name": "Adorama", "id": "5678", "category": "Electronics"},
            {"name": "B&H Photo", "id": "6789", "category": "Electronics"},
            {"name": "REI", "id": "8901", "category": "Outdoor"},
        ]
        
        products = []
        for i in range(min(limit, len(merchants) * 2)):
            merchant = merchants[i % len(merchants)]
            pid = hashlib.md5(f"cj-{query}-{i}".encode()).hexdigest()[:12]
            
            base_price = 50 + random.randint(0, 500)
            has_discount = random.random() > 0.5
            sale_price = base_price * 0.85 if has_discount else base_price
            
            products.append(AffiliateProduct(
                id=f"cj-{pid}",
                title=f"{query.title()} - {merchant['name']} Exclusive" if i % 3 == 0 else f"Premium {query.title()} #{i+1}",
                description=f"Shop {query} at {merchant['name']}. High-quality product with fast shipping.",
                price=round(sale_price, 2),
                original_price=round(base_price, 2) if has_discount else None,
                currency="USD",
                image_url=f"https://picsum.photos/seed/cj{query}{i}/400/400",
                product_url=f"https://{merchant['name'].lower().replace(' ', '')}.com/product/{pid}",
                affiliate_url=f"https://www.anrdoezrs.net/click-{pid}?url=product",
                merchant_name=merchant["name"],
                merchant_id=merchant["id"],
                network=self.NETWORK_NAME,
                category=merchant["category"],
                brand=query.title().split()[0] if query else "Generic",
                in_stock=random.random() > 0.1,
                sku=f"SKU-{pid[:8].upper()}",
                upc=None,
            ))
        
        return products
    
    def generate_affiliate_link(self, product_url: str) -> str:
        """Generate CJ affiliate tracking link."""
        if self.website_id:
            # CJ deep linking format
            return f"https://www.anrdoezrs.net/click-{self.website_id}?url={product_url}"
        return product_url


# Singleton instance
cj_service = CJAffiliateService()
