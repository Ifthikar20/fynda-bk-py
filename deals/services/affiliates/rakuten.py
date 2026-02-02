"""
Rakuten Advertising API Service

Provides access to 2,500+ retailer product catalogs.

API Documentation: https://developers.rakutenadvertising.com/
"""

import os
import logging
import hashlib
import random
import requests
from typing import Optional
from xml.etree import ElementTree

from .affiliate_base import AffiliateProduct, AffiliateService, AuthenticationError

logger = logging.getLogger(__name__)


class RakutenService(AffiliateService):
    """
    Rakuten Advertising integration using their Product Search API.
    
    Provides access to major retailers like:
    - Macy's, Nordstrom
    - Sephora, Ulta
    - GameStop, Microsoft Store
    - Office Depot, Staples
    - And 2,500+ more
    
    Required environment variables:
    - RAKUTEN_API_TOKEN: Bearer token from developer portal
    - RAKUTEN_SITE_ID: Your registered site ID
    """
    
    NETWORK_NAME = "rakuten"
    API_BASE_URL = "https://api.rakutenadvertising.com/productsearch/1.0"
    
    def _load_credentials(self):
        """Load Rakuten API credentials from environment."""
        self.api_key = os.getenv("RAKUTEN_API_TOKEN")
        self.site_id = os.getenv("RAKUTEN_SITE_ID")
        self.timeout = 15
    
    def search_products(self, query: str, limit: int = 20) -> list[AffiliateProduct]:
        """
        Search Rakuten product catalogs.
        
        Args:
            query: Product search query
            limit: Maximum results
            
        Returns:
            List of products from Rakuten merchants (empty if API unavailable)
        """
        if not self.is_configured():
            logger.debug("Rakuten API not configured - skipping")
            return []
        
        try:
            return self._search_api(query, limit)
        except AuthenticationError:
            logger.error("Rakuten API authentication failed")
            return []
        except Exception as e:
            logger.warning(f"Rakuten API error: {e}")
            return []
    
    def _search_api(self, query: str, limit: int) -> list[AffiliateProduct]:
        """
        Search Rakuten using their Product Search API.
        
        Rakuten returns XML by default.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        params = {
            "keyword": query,
            "max": min(limit, 100),
        }
        
        response = requests.get(
            self.API_BASE_URL,
            headers=headers,
            params=params,
            timeout=self.timeout
        )
        
        if response.status_code == 401:
            raise AuthenticationError("Invalid Rakuten API token")
        
        response.raise_for_status()
        
        # Parse XML response
        products = []
        try:
            root = ElementTree.fromstring(response.content)
            
            for item in root.findall(".//item")[:limit]:
                try:
                    price_text = item.findtext("price", "0")
                    price = float(price_text.replace(",", "").replace("$", ""))
                    
                    retail_text = item.findtext("retailprice", "0") or "0"
                    retail_price = float(retail_text.replace(",", "").replace("$", ""))
                    
                    products.append(AffiliateProduct(
                        id=f"rakuten-{item.findtext('linkid', '')}",
                        title=item.findtext("productname", "")[:200],
                        description=item.findtext("description", {}).get("short", "")[:500],
                        price=price,
                        original_price=retail_price if retail_price > price else None,
                        currency=item.findtext("currency", "USD"),
                        image_url=item.findtext("imageurl", ""),
                        product_url=item.findtext("linkurl", ""),
                        affiliate_url=item.findtext("linkurl", ""),
                        merchant_name=item.findtext("merchantname", ""),
                        merchant_id=item.findtext("mid", ""),
                        network=self.NETWORK_NAME,
                        category=item.findtext("categoryname", "") or item.findtext("category", {}).get("primary", ""),
                        brand=item.findtext("manufacturer", "") or item.findtext("brand", ""),
                        in_stock=item.findtext("instock", "yes").lower() == "yes",
                        sku=item.findtext("sku"),
                        upc=item.findtext("upc"),
                    ))
                except Exception as e:
                    logger.debug(f"Error parsing Rakuten product: {e}")
                    continue
                    
        except ElementTree.ParseError as e:
            logger.error(f"Error parsing Rakuten XML: {e}")
            raise
        
        logger.info(f"Rakuten API returned {len(products)} products for '{query}'")
        return products
    
    def _get_mock_products(self, query: str, limit: int) -> list[AffiliateProduct]:
        """Generate mock Rakuten products for demo/testing."""
        
        merchants = [
            {"name": "Macys", "id": "5432", "category": "Department Store"},
            {"name": "Nordstrom", "id": "6543", "category": "Fashion"},
            {"name": "Sephora", "id": "7654", "category": "Beauty"},
            {"name": "GameStop", "id": "8765", "category": "Gaming"},
            {"name": "Office Depot", "id": "9876", "category": "Office"},
            {"name": "Groupon", "id": "1098", "category": "Deals"},
            {"name": "Kohls", "id": "2109", "category": "Department Store"},
            {"name": "JCPenney", "id": "3210", "category": "Department Store"},
        ]
        
        products = []
        for i in range(min(limit, len(merchants) * 2)):
            merchant = merchants[i % len(merchants)]
            pid = hashlib.md5(f"rakuten-{query}-{i}".encode()).hexdigest()[:12]
            
            base_price = 30 + random.randint(0, 400)
            has_discount = random.random() > 0.4
            sale_price = base_price * 0.80 if has_discount else base_price
            
            # Build URL safely without special chars
            merchant_slug = merchant["name"].lower().replace(" ", "")
            
            products.append(AffiliateProduct(
                id=f"rakuten-{pid}",
                title=f"{query.title()} from {merchant['name']}" if i % 2 == 0 else f"Trending {query.title()} Deal",
                description=f"Discover {query} at {merchant['name']}. Great prices and selection.",
                price=round(sale_price, 2),
                original_price=round(base_price, 2) if has_discount else None,
                currency="USD",
                image_url=f"https://picsum.photos/seed/rak{query}{i}/400/400",
                product_url=f"https://{merchant_slug}.com/p/{pid}",
                affiliate_url=f"https://click.linksynergy.com/deeplink?id={pid}&murl=product",
                merchant_name=merchant["name"],
                merchant_id=merchant["id"],
                network=self.NETWORK_NAME,
                category=merchant["category"],
                brand=query.title().split()[0] if query else "Brand",
                in_stock=random.random() > 0.15,
                sku=f"R-{pid[:8].upper()}",
                upc=None,
            ))
        
        return products
    
    def generate_affiliate_link(self, product_url: str) -> str:
        """Generate Rakuten affiliate tracking link."""
        if self.site_id:
            return f"https://click.linksynergy.com/deeplink?id={self.site_id}&murl={product_url}"
        return product_url


# Singleton instance
rakuten_service = RakutenService()
