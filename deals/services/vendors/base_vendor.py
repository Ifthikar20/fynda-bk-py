"""
Base Vendor Service

Abstract base class for all vendor integrations.
All vendors must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum


class VendorCategory(Enum):
    """Categories of vendors."""
    DEMO = "demo"           # Free demo APIs 
    AFFILIATE = "affiliate"  # Affiliate networks (require approval)
    DIRECT = "direct"        # Direct brand integrations


@dataclass
class VendorProduct:
    """Standardized product format across all vendors."""
    id: str
    title: str
    description: str
    price: float
    original_price: Optional[float] = None
    currency: str = "USD"
    image_url: str = ""
    product_url: str = ""
    affiliate_url: str = ""
    merchant_name: str = ""
    merchant_id: str = ""
    network: str = ""
    category: str = ""
    brand: str = ""
    in_stock: bool = True
    discount_percent: Optional[int] = None
    sku: Optional[str] = None
    upc: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class VendorConfig:
    """Configuration for a vendor."""
    id: str
    name: str
    service_class: str
    enabled: bool = True
    requires_auth: bool = False
    priority: int = 50
    category: VendorCategory = VendorCategory.DEMO
    env_toggle_key: Optional[str] = None
    description: str = ""
    
    @property
    def env_key(self) -> str:
        """Get the environment variable key for this vendor."""
        return self.env_toggle_key or f"VENDOR_{self.id.upper()}"


class BaseVendorService(ABC):
    """
    Abstract base class for all vendor services.
    
    All vendor implementations must inherit from this class
    and implement the required methods.
    """
    
    VENDOR_ID: str = ""
    VENDOR_NAME: str = ""
    
    def __init__(self):
        self.timeout = 10
        self._load_credentials()
    
    def _load_credentials(self):
        """Load any required credentials. Override in subclasses."""
        pass
    
    @abstractmethod
    def search_products(self, query: str, limit: int = 20) -> List[VendorProduct]:
        """
        Search for products matching the query.
        
        Args:
            query: Search term
            limit: Maximum number of results
            
        Returns:
            List of VendorProduct objects
        """
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
            "timeout": self.timeout,
        }
