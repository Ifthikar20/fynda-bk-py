"""
Shopify Stores Scraper Service

Scrapes products from Shopify stores using their public /products.json API.
All Shopify stores expose this endpoint without authentication.
"""

import os
import logging
import hashlib
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


# Popular Shopify stores to search (add more as needed)
DEFAULT_SHOPIFY_STORES = [
    # Fashion
    {"name": "Fashion Nova", "domain": "fashionnova.com", "category": "fashion"},
    {"name": "Gymshark", "domain": "gymshark.com", "category": "fitness"},
    {"name": "Allbirds", "domain": "allbirds.com", "category": "shoes"},
    {"name": "MVMT", "domain": "mvmt.com", "category": "watches"},
    {"name": "Chubbies", "domain": "chubbiesshorts.com", "category": "fashion"},
    # Tech & Gadgets
    {"name": "Anker", "domain": "anker.com", "category": "tech"},
    {"name": "Peak Design", "domain": "peakdesign.com", "category": "camera"},
    {"name": "Moment", "domain": "shopmoment.com", "category": "camera"},
    # Home & Lifestyle
    {"name": "Brooklinen", "domain": "brooklinen.com", "category": "home"},
    {"name": "Ruggable", "domain": "ruggable.com", "category": "home"},
    # Beauty
    {"name": "ColourPop", "domain": "colourpop.com", "category": "beauty"},
    {"name": "Kylie Cosmetics", "domain": "kyliecosmetics.com", "category": "beauty"},
]


@dataclass
class ShopifyProduct:
    """Represents a product from a Shopify store."""
    id: str
    title: str
    description: str
    price: float
    compare_at_price: Optional[float]
    discount_percent: int
    currency: str
    url: str
    image_url: str
    vendor: str
    store_name: str
    store_domain: str
    product_type: str
    tags: list
    in_stock: bool
    
    def to_dict(self):
        return {
            "id": f"shopify-{self.id}",
            "title": self.title,
            "description": self.description[:200] if self.description else "",
            "price": self.price,
            "original_price": self.compare_at_price or self.price,
            "discount_percent": self.discount_percent,
            "currency": self.currency,
            "source": f"Shopify ({self.store_name})",
            "seller": self.vendor or self.store_name,
            "seller_rating": None,
            "url": self.url,
            "image_url": self.image_url,
            "condition": "New",
            "shipping": "Varies",
            "rating": None,
            "reviews_count": None,
            "in_stock": self.in_stock,
            "relevance_score": 0,
            "features": self.tags[:5],
            "fetched_at": datetime.now().isoformat(),
        }


class ShopifyScraperService:
    """
    Service for scraping products from Shopify stores.
    
    Uses the public /products.json endpoint available on all Shopify stores.
    No authentication required.
    """
    
    def __init__(self, stores: list = None):
        self.stores = stores or DEFAULT_SHOPIFY_STORES
        self.timeout = 10
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        }
    
    def search(self, query: str, limit: int = 10, max_price: Optional[float] = None,
               category: Optional[str] = None) -> list[ShopifyProduct]:
        """
        Search for products across multiple Shopify stores.
        
        Args:
            query: Product search query
            limit: Maximum total results
            max_price: Maximum price filter
            category: Filter by store category (fashion, tech, etc.)
            
        Returns:
            List of ShopifyProduct objects
        """
        # Filter stores by category if specified
        stores_to_search = self.stores
        if category:
            stores_to_search = [s for s in self.stores if s.get("category") == category]
        
        # Search stores in parallel
        all_products = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._search_store, store, query, max_price): store
                for store in stores_to_search[:8]  # Limit to 8 stores
            }
            
            for future in as_completed(futures, timeout=15):
                store = futures[future]
                try:
                    products = future.result()
                    all_products.extend(products)
                    logger.info(f"Found {len(products)} products from {store['name']}")
                except Exception as e:
                    logger.warning(f"Error scraping {store['name']}: {e}")
        
        # Sort by relevance (title match) and return top results
        query_lower = query.lower()
        all_products.sort(
            key=lambda p: sum(1 for word in query_lower.split() if word in p.title.lower()),
            reverse=True
        )
        
        return all_products[:limit]
    
    def _search_store(self, store: dict, query: str, max_price: Optional[float]) -> list[ShopifyProduct]:
        """Search a single Shopify store."""
        domain = store["domain"]
        store_name = store["name"]
        
        # Try HTTPS first, then HTTP
        for protocol in ["https", "http"]:
            try:
                url = f"{protocol}://{domain}/products.json"
                params = {
                    "limit": 50,  # Shopify allows up to 250
                }
                
                response = requests.get(
                    url, 
                    params=params, 
                    headers=self.headers, 
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_products(data, query, max_price, store_name, domain)
                    
            except requests.exceptions.SSLError:
                continue
            except Exception as e:
                logger.debug(f"Failed to fetch {domain}: {e}")
                continue
        
        return []
    
    def _parse_products(self, data: dict, query: str, max_price: Optional[float],
                        store_name: str, domain: str) -> list[ShopifyProduct]:
        """Parse products from Shopify JSON response."""
        products = []
        query_words = set(query.lower().split())
        
        for product in data.get("products", []):
            title = product.get("title", "")
            title_lower = title.lower()
            
            # Filter by query - at least one word must match
            if not any(word in title_lower for word in query_words):
                # Also check tags and product type
                tags = [t.lower() for t in product.get("tags", [])]
                product_type = product.get("product_type", "").lower()
                if not any(word in tag for word in query_words for tag in tags):
                    if not any(word in product_type for word in query_words):
                        continue
            
            # Get first available variant with price
            variants = product.get("variants", [])
            if not variants:
                continue
            
            # Find best variant (in stock, with price)
            variant = None
            for v in variants:
                if v.get("available", True):
                    variant = v
                    break
            
            if not variant:
                variant = variants[0]  # Use first variant
            
            # Parse price
            try:
                price = float(variant.get("price", 0))
            except (TypeError, ValueError):
                continue
            
            if price == 0:
                continue
            
            # Apply price filter
            if max_price and price > max_price:
                continue
            
            # Parse compare_at_price (original price)
            compare_at = None
            discount = 0
            try:
                compare_at_str = variant.get("compare_at_price")
                if compare_at_str:
                    compare_at = float(compare_at_str)
                    if compare_at > price:
                        discount = int((1 - price / compare_at) * 100)
            except (TypeError, ValueError):
                pass
            
            # Get image
            images = product.get("images", [])
            image_url = images[0].get("src", "") if images else ""
            
            # Clean up description (remove HTML)
            description = product.get("body_html", "") or ""
            import re
            description = re.sub(r'<[^>]+>', '', description)
            description = description.strip()[:300]
            
            products.append(ShopifyProduct(
                id=f"{domain}-{product.get('id', '')}",
                title=title,
                description=description,
                price=price,
                compare_at_price=compare_at,
                discount_percent=discount,
                currency="USD",  # Most Shopify stores use USD
                url=f"https://{domain}/products/{product.get('handle', '')}",
                image_url=image_url,
                vendor=product.get("vendor", ""),
                store_name=store_name,
                store_domain=domain,
                product_type=product.get("product_type", ""),
                tags=product.get("tags", []),
                in_stock=variant.get("available", True),
            ))
        
        return products
    
    def add_store(self, name: str, domain: str, category: str = "other"):
        """Add a new Shopify store to the search list."""
        self.stores.append({
            "name": name,
            "domain": domain,
            "category": category,
        })
    
    def get_store_products(self, domain: str, limit: int = 50) -> list[ShopifyProduct]:
        """Get all products from a specific Shopify store."""
        store = {"name": domain, "domain": domain}
        
        for protocol in ["https", "http"]:
            try:
                url = f"{protocol}://{domain}/products.json"
                response = requests.get(
                    url,
                    params={"limit": limit},
                    headers=self.headers,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_products(data, "", None, domain, domain)
                    
            except Exception as e:
                continue
        
        return []


# Singleton instance
shopify_service = ShopifyScraperService()
