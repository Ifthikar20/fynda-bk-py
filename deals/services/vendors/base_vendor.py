"""
Base Vendor Service

Abstract base class for all vendor integrations.
All vendors must implement this interface and return VendorProduct instances.

Includes circuit breaker protection to prevent cascading failures
when a vendor API is down or rate-limited.
"""

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class VendorCategory(Enum):
    """Categories of vendors."""
    MARKETPLACE = "marketplace"  # Amazon, eBay, etc.
    AFFILIATE = "affiliate"      # CJ, Rakuten, ShareASale
    SOCIAL = "social"            # Facebook Marketplace
    DIRECT = "direct"            # Direct brand/Shopify stores
    DEMO = "demo"                # Free demo APIs


@dataclass
class VendorProduct:
    """
    Standardized product format across ALL vendors.
    
    Every vendor (Amazon, eBay, affiliates, Shopify, etc.) must return
    this format. The orchestrator only deals with VendorProduct.
    """
    id: str
    title: str
    description: str = ""
    price: float = 0.0
    original_price: Optional[float] = None
    discount_percent: Optional[int] = None
    currency: str = "USD"
    image_url: str = ""
    url: str = ""                   # Where user navigates to buy
    product_url: str = ""           # Direct product URL (for affiliates, may differ from url)
    source: str = ""                # Display name: "Amazon", "eBay", etc.
    merchant_name: str = ""
    merchant_id: str = ""
    network: str = ""               # Affiliate network if applicable
    category: str = ""
    brand: str = ""
    in_stock: bool = True
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    is_prime: bool = False
    condition: str = "New"
    shipping: str = ""
    seller: str = ""
    seller_rating: Optional[float] = None
    badge: Optional[str] = None     # "Best Seller", "Amazon Choice", etc.
    features: List[str] = field(default_factory=list)
    relevance_score: int = 0
    sku: Optional[str] = None
    upc: Optional[str] = None
    fetched_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "price": self.price or 0,
            "original_price": self.original_price or self.price,
            "discount_percent": self.discount_percent or 0,
            "currency": self.currency,
            "image_url": self.image_url,
            "url": self.url or self.product_url,
            "source": self.source,
            "merchant_name": self.merchant_name,
            "category": self.category,
            "brand": self.brand,
            "in_stock": self.in_stock,
            "rating": self.rating,
            "reviews_count": self.reviews_count,
            "is_prime": self.is_prime,
            "condition": self.condition,
            "shipping": self.shipping,
            "seller": self.seller,
            "seller_rating": self.seller_rating,
            "badge": self.badge,
            "features": self.features,
            "relevance_score": self.relevance_score,
            "fetched_at": self.fetched_at or datetime.now().isoformat(),
        }
        # Include affiliate-specific fields if present
        if self.network:
            d["network"] = self.network
            d["type"] = "affiliate"
        if self.product_url and self.product_url != self.url:
            d["product_url"] = self.product_url
        return d


@dataclass
class VendorConfig:
    """Configuration for a vendor."""
    id: str
    name: str
    service_class: str
    enabled: bool = True
    requires_auth: bool = False
    priority: int = 50          # Higher = preferred in ranking
    category: VendorCategory = VendorCategory.DEMO
    env_toggle_key: Optional[str] = None
    description: str = ""
    
    @property
    def env_key(self) -> str:
        """Get the environment variable key for this vendor."""
        return self.env_toggle_key or f"VENDOR_{self.id.upper()}"


class VendorError(Exception):
    """Base exception for vendor service errors."""
    pass


class QuotaExceededError(VendorError):
    """Raised when API rate limit / quota is exceeded."""
    pass


class AuthenticationError(VendorError):
    """Raised when API authentication fails."""
    pass


class BaseVendorService(ABC):
    """
    Abstract base class for all vendor services.
    
    All vendor implementations must inherit from this class
    and implement the _do_search method.
    
    Includes circuit breaker: after 3 consecutive failures,
    the vendor is bypassed for 60 seconds to prevent cascade.
    """
    
    VENDOR_ID: str = ""
    VENDOR_NAME: str = ""
    PRIORITY: int = 50              # Higher = preferred in ranking
    MAX_CONSECUTIVE_FAILURES: int = 3
    CIRCUIT_COOLDOWN_SECONDS: int = 60
    TIMEOUT: int = 10
    
    def __init__(self):
        self._consecutive_failures = 0
        self._circuit_open_until: Optional[float] = None
        self.timeout = self.TIMEOUT
        self._load_credentials()
    
    # ── Public API ──────────────────────────────────────────────
    
    def search_products(self, query: str, limit: int = 20) -> List[VendorProduct]:
        """
        Search for products matching the query.
        
        Protected by circuit breaker — returns empty if vendor is
        currently in failure cooldown.
        
        Args:
            query: Search term
            limit: Maximum number of results
            
        Returns:
            List of VendorProduct objects
        """
        if self._is_circuit_open():
            logger.debug(f"[{self.VENDOR_NAME}] Circuit open, skipping")
            return []
        
        try:
            results = self._do_search(query, limit)
            self._on_success()
            return results
        except QuotaExceededError:
            logger.warning(f"[{self.VENDOR_NAME}] Quota exceeded")
            self._open_circuit(cooldown=300)  # 5 min cooldown for quota
            raise
        except Exception as e:
            self._on_failure(e)
            return []
    
    # ── Abstract method — subclasses implement this ─────────────
    
    @abstractmethod
    def _do_search(self, query: str, limit: int) -> List[VendorProduct]:
        """
        Execute the actual search against the vendor API.
        
        Subclasses implement this method with their specific API logic.
        Must return List[VendorProduct].
        """
        pass
    
    # ── Optional hooks ──────────────────────────────────────────
    
    def _load_credentials(self):
        """Load any required credentials. Override in subclasses."""
        pass
    
    def is_configured(self) -> bool:
        """Check if vendor is properly configured (has required credentials)."""
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get vendor status information."""
        return {
            "vendor_id": self.VENDOR_ID,
            "vendor_name": self.VENDOR_NAME,
            "configured": self.is_configured(),
            "priority": self.PRIORITY,
            "timeout": self.timeout,
            "circuit_open": self._is_circuit_open(),
            "consecutive_failures": self._consecutive_failures,
        }
    
    # ── Circuit breaker internals ───────────────────────────────
    
    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is currently open (vendor is skipped)."""
        if self._circuit_open_until is None:
            return False
        if time.time() >= self._circuit_open_until:
            # Cooldown expired — close circuit, try again
            self._circuit_open_until = None
            self._consecutive_failures = 0
            logger.info(f"[{self.VENDOR_NAME}] Circuit breaker reset")
            return False
        return True
    
    def _open_circuit(self, cooldown: int = None):
        """Open the circuit breaker (skip this vendor for `cooldown` seconds)."""
        cooldown = cooldown or self.CIRCUIT_COOLDOWN_SECONDS
        self._circuit_open_until = time.time() + cooldown
        logger.warning(
            f"[{self.VENDOR_NAME}] Circuit breaker OPEN for {cooldown}s "
            f"(after {self._consecutive_failures} failures)"
        )
    
    def _on_success(self):
        """Reset failure counter on successful search."""
        self._consecutive_failures = 0
    
    def _on_failure(self, error: Exception):
        """Track failure and open circuit if threshold reached."""
        self._consecutive_failures += 1
        logger.warning(
            f"[{self.VENDOR_NAME}] Search failed ({self._consecutive_failures}/"
            f"{self.MAX_CONSECUTIVE_FAILURES}): {error}"
        )
        if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            self._open_circuit()
