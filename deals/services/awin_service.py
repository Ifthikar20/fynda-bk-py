"""
Awin Affiliate Service
Generates affiliate tracking deep links for Awin partner retailers
"""
import os
import urllib.parse
from typing import Optional, Dict

class AwinAffiliateService:
    """
    Service for generating Awin affiliate tracking links.
    
    Awin Deep Link Format:
    https://www.awin1.com/cread.php?awinmid={advertiser_id}&awinaffid={publisher_id}&ued={encoded_url}
    
    Optional parameters:
    - clickref: Custom tracking reference (up to 50 chars)
    - p: Sub-ID for additional tracking
    """
    
    BASE_URL = "https://www.awin1.com/cread.php"
    
    # Publisher ID from environment or default
    PUBLISHER_ID = os.getenv('AWIN_PUBLISHER_ID', '2754350')
    
    # Advertiser IDs - Add more as you get approved
    # Get these from Awin dashboard after advertiser approval
    ADVERTISER_MAP: Dict[str, str] = {
        # Fashion Retailers
        'asos': '',          # Apply at: Awin > Advertisers > Join
        'nordstrom': '',     # Apply at: Awin > Advertisers > Join
        'farfetch': '',      # Apply at: Awin > Advertisers > Join
        'net-a-porter': '',  # Apply at: Awin > Advertisers > Join
        'revolve': '',       # Apply at: Awin > Advertisers > Join
        'mytheresa': '',     # Apply at: Awin > Advertisers > Join
        'ssense': '',        # Apply at: Awin > Advertisers > Join
        'boohoo': '',        # Apply at: Awin > Advertisers > Join
        'prettylittlething': '',  # Apply at: Awin > Advertisers > Join
        'missguided': '',    # Apply at: Awin > Advertisers > Join
        
        # Department Stores
        'macys': '',         
        'bloomingdales': '', 
        'saks': '',          
        
        # Demo/placeholder - remove in production
        'demo': '00000',
    }
    
    @classmethod
    def get_advertiser_id(cls, source: str) -> Optional[str]:
        """
        Get Awin advertiser ID for a given source/retailer.
        Returns None if retailer is not in Awin network or not yet approved.
        """
        if not source:
            return None
        
        # Normalize source name
        normalized = source.lower().strip().replace(' ', '-').replace('_', '-')
        
        # Try exact match first
        if normalized in cls.ADVERTISER_MAP:
            advertiser_id = cls.ADVERTISER_MAP[normalized]
            return advertiser_id if advertiser_id else None
        
        # Try partial match
        for key, value in cls.ADVERTISER_MAP.items():
            if key in normalized or normalized in key:
                return value if value else None
        
        return None
    
    @classmethod
    def generate_deep_link(
        cls,
        destination_url: str,
        advertiser_id: str,
        click_ref: Optional[str] = None,
        sub_id: Optional[str] = None
    ) -> str:
        """
        Generate an Awin tracking deep link.
        
        Args:
            destination_url: The product/page URL on retailer's site
            advertiser_id: Awin advertiser ID (merchant ID)
            click_ref: Optional click reference for tracking (max 50 chars)
            sub_id: Optional sub-ID for additional tracking
            
        Returns:
            Full Awin tracking URL
        """
        # URL encode the destination
        encoded_url = urllib.parse.quote(destination_url, safe='')
        
        # Build query parameters
        params = {
            'awinmid': advertiser_id,
            'awinaffid': cls.PUBLISHER_ID,
            'ued': encoded_url,
        }
        
        # Add optional parameters
        if click_ref:
            params['clickref'] = click_ref[:50]  # Max 50 chars
        if sub_id:
            params['p'] = sub_id
        
        # Build the URL
        query_string = urllib.parse.urlencode(params, safe='')
        return f"{cls.BASE_URL}?{query_string}"
    
    @classmethod
    def get_affiliate_url(
        cls,
        product_url: str,
        source: str,
        product_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Get affiliate URL for a product if available.
        Falls back to original URL if retailer not supported.
        
        Args:
            product_url: Original product URL
            source: Retailer/source name
            product_id: Optional product ID for tracking
            user_id: Optional user ID for tracking
            
        Returns:
            Affiliate URL if retailer supported, otherwise original URL
        """
        advertiser_id = cls.get_advertiser_id(source)
        
        if not advertiser_id:
            # Retailer not in Awin network or not approved yet
            return product_url
        
        # Build click reference for tracking
        click_ref = None
        if product_id:
            click_ref = f"p{product_id}"
            if user_id:
                click_ref += f"_u{user_id}"
        
        return cls.generate_deep_link(
            destination_url=product_url,
            advertiser_id=advertiser_id,
            click_ref=click_ref
        )
    
    @classmethod
    def is_supported_retailer(cls, source: str) -> bool:
        """Check if retailer is supported by Awin and has an advertiser ID."""
        return cls.get_advertiser_id(source) is not None


# Convenience function for quick access
def get_awin_affiliate_url(product_url: str, source: str, product_id: str = None) -> str:
    """
    Quick helper to get Awin affiliate URL.
    Returns original URL if retailer not in Awin network.
    """
    return AwinAffiliateService.get_affiliate_url(
        product_url=product_url,
        source=source,
        product_id=product_id
    )
