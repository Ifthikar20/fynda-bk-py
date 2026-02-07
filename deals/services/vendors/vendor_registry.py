"""
Vendor Registry

Central configuration for all available vendors.
Toggle vendors on/off via environment variables.
"""

from .base_vendor import VendorConfig, VendorCategory


# All available vendors
VENDOR_REGISTRY: dict[str, VendorConfig] = {
    
    # ===== AFFILIATE NETWORKS =====
    
    "rakuten": VendorConfig(
        id="rakuten",
        name="Rakuten",
        service_class="RakutenService",
        enabled=False,  # Enable when approved
        requires_auth=True,
        priority=80,
        category=VendorCategory.AFFILIATE,
        description="Rakuten Advertising - 2,500+ retailers"
    ),
    
    "cj": VendorConfig(
        id="cj",
        name="CJ Affiliate",
        service_class="CJService",
        enabled=False,
        requires_auth=True,
        priority=75,
        category=VendorCategory.AFFILIATE,
        description="Commission Junction - 3,000+ brands"
    ),
    
    "sovrn": VendorConfig(
        id="sovrn",
        name="Sovrn Commerce",
        service_class="SovrnService",
        enabled=False,
        requires_auth=True,
        priority=70,
        category=VendorCategory.AFFILIATE,
        description="Sovrn Commerce - 50,000+ merchants"
    ),
    
    "flexoffers": VendorConfig(
        id="flexoffers",
        name="FlexOffers",
        service_class="FlexOffersService",
        enabled=False,
        requires_auth=True,
        priority=65,
        category=VendorCategory.AFFILIATE,
        description="FlexOffers - Nordstrom, Target, Walmart"
    ),
    
    "shareasale": VendorConfig(
        id="shareasale",
        name="ShareASale",
        service_class="ShareASaleService",
        enabled=False,
        requires_auth=True,
        priority=60,
        category=VendorCategory.AFFILIATE,
        description="ShareASale - 16,000+ merchants"
    ),
    
    "awin": VendorConfig(
        id="awin",
        name="Awin",
        service_class="AwinService",
        enabled=False,
        requires_auth=True,
        priority=55,
        category=VendorCategory.AFFILIATE,
        description="Awin - Global affiliate network"
    ),
}


def get_vendor_config(vendor_id: str) -> VendorConfig | None:
    """Get configuration for a specific vendor."""
    return VENDOR_REGISTRY.get(vendor_id)


def get_all_vendors() -> list[VendorConfig]:
    """Get all registered vendors."""
    return list(VENDOR_REGISTRY.values())


def get_vendors_by_category(category: VendorCategory) -> list[VendorConfig]:
    """Get vendors filtered by category."""
    return [v for v in VENDOR_REGISTRY.values() if v.category == category]
