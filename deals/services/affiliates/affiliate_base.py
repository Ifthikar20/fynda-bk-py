"""
Base classes for affiliate network integrations.

Provides common interface and data models for all affiliate networks.
"""

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


@dataclass
class AffiliateProduct:
    """
    Standardized product data from any affiliate network.
    
    This unified model allows products from CJ, Rakuten, ShareASale, etc.
    to be displayed together in search results.
    """
    id: str
    title: str
    description: str
    price: float
    currency: str
    image_url: str
    product_url: str           # Direct product URL
    affiliate_url: str         # Affiliate tracking URL (earns commission)
    merchant_name: str
    merchant_id: str
    network: str               # "cj", "rakuten", "shareasale", "awin"
    category: str
    brand: str
    in_stock: bool
    original_price: Optional[float] = None
    discount_percent: Optional[float] = None
    sku: Optional[str] = None
    upc: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        discount = None
        if self.original_price and self.price and self.original_price > self.price:
            discount = round((1 - self.price / self.original_price) * 100)
        
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "price": self.price or 0,
            "original_price": self.original_price,
            "discount_percent": discount or self.discount_percent,
            "currency": self.currency,
            "image_url": self.image_url,
            "url": self.affiliate_url,  # Use affiliate URL for tracking
            "product_url": self.product_url,
            "source": f"Affiliate ({self.network.upper()})",
            "merchant_name": self.merchant_name,
            "merchant_id": self.merchant_id,
            "network": self.network,
            "category": self.category,
            "brand": self.brand,
            "in_stock": self.in_stock,
            "sku": self.sku,
            "upc": self.upc,
            "type": "affiliate",
        }


class AffiliateService(ABC):
    """
    Abstract base class for affiliate network integrations.
    
    Each network (CJ, Rakuten, ShareASale, etc.) implements this interface.
    """
    
    # Network identifier
    NETWORK_NAME: str = "unknown"
    
    # API configuration
    api_key: Optional[str] = None
    timeout: int = 10
    
    def __init__(self):
        """Initialize service and load credentials from environment."""
        self._load_credentials()
    
    @abstractmethod
    def _load_credentials(self) -> None:
        """Load API credentials from environment variables."""
        pass
    
    @abstractmethod
    def search_products(self, query: str, limit: int = 20) -> list[AffiliateProduct]:
        """
        Search for products across the network's merchants.
        
        Args:
            query: Product search query
            limit: Maximum number of products to return
            
        Returns:
            List of AffiliateProduct objects
        """
        pass
    
    @abstractmethod
    def _search_api(self, query: str, limit: int) -> list[AffiliateProduct]:
        """Make actual API call to the network."""
        pass
    
    @abstractmethod
    def _get_mock_products(self, query: str, limit: int) -> list[AffiliateProduct]:
        """Generate mock products for testing/demo when API is unavailable."""
        pass
    
    def is_configured(self) -> bool:
        """Check if the service has valid API credentials."""
        return self.api_key is not None and len(self.api_key) > 0
    
    def generate_affiliate_link(self, product_url: str) -> str:
        """
        Generate an affiliate tracking link for a product URL.
        
        Override in subclasses for network-specific link generation.
        """
        return product_url


class AffiliateServiceError(Exception):
    """Base exception for affiliate service errors."""
    pass


class RateLimitError(AffiliateServiceError):
    """Raised when API rate limit is exceeded."""
    pass


class AuthenticationError(AffiliateServiceError):
    """Raised when API authentication fails."""
    pass
