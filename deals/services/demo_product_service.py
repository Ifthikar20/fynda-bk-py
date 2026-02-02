"""
Demo Product API Service

Uses Platzi Fake Store API for demo purposes.
This provides real clothing product data while waiting for affiliate approvals.

Replace this with affiliate network APIs (Rakuten, CJ, Sovrn) once approved.
"""

import requests
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class DemoProductService:
    """
    Demo product service using Platzi Fake Store API.
    
    Free API with real clothing images - perfect for demos.
    No authentication required.
    """
    
    API_BASE_URL = "https://api.escuelajs.co/api/v1"
    
    def __init__(self):
        self.timeout = 10
    
    def search_products(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for products matching the query.
        
        Args:
            query: Search term
            limit: Maximum results
            
        Returns:
            List of product dictionaries
        """
        try:
            # Get products and filter by query
            response = requests.get(
                f"{self.API_BASE_URL}/products",
                params={"offset": 0, "limit": 50},
                timeout=self.timeout
            )
            response.raise_for_status()
            
            all_products = response.json()
            
            # Filter by query (case-insensitive search in title)
            query_lower = query.lower()
            filtered = [
                p for p in all_products
                if query_lower in p.get("title", "").lower()
                or query_lower in p.get("description", "").lower()
                or query_lower in p.get("category", {}).get("name", "").lower()
            ]
            
            # If no matches, return all products as suggestions
            if not filtered:
                filtered = all_products
            
            # Convert to our standard format
            products = []
            for p in filtered[:limit]:
                images = p.get("images", [])
                # Clean up image URLs
                image_url = images[0] if images else ""
                if image_url.startswith('["') or image_url.startswith("['"):
                    # Sometimes the API returns stringified arrays
                    image_url = image_url.strip('[]"\'')
                
                products.append({
                    "id": f"demo-{p['id']}",
                    "title": p.get("title", "")[:100],
                    "description": p.get("description", "")[:300],
                    "price": p.get("price", 0),
                    "original_price": round(p.get("price", 0) * 1.3, 2),  # Simulate discount
                    "currency": "USD",
                    "image_url": image_url,
                    "product_url": f"https://demo.fynda.shop/product/{p['id']}",
                    "affiliate_url": f"https://demo.fynda.shop/product/{p['id']}",
                    "merchant_name": "Demo Store",
                    "merchant_id": "demo",
                    "network": "demo",
                    "category": p.get("category", {}).get("name", "Fashion"),
                    "brand": "Demo Brand",
                    "in_stock": True,
                    "discount_percent": 30,
                })
            
            logger.info(f"Demo API returned {len(products)} products for '{query}'")
            return products
            
        except requests.RequestException as e:
            logger.error(f"Demo API error: {e}")
            return []
    
    def get_product_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get a single product by ID."""
        try:
            response = requests.get(
                f"{self.API_BASE_URL}/products/{product_id}",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching product {product_id}: {e}")
            return None
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all product categories."""
        try:
            response = requests.get(
                f"{self.API_BASE_URL}/categories",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching categories: {e}")
            return []
    
    def get_products_by_category(self, category_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get products in a specific category."""
        try:
            response = requests.get(
                f"{self.API_BASE_URL}/categories/{category_id}/products",
                params={"limit": limit},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching category {category_id} products: {e}")
            return []


# Singleton instance
demo_product_service = DemoProductService()
