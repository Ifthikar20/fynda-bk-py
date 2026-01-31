"""
ML Service Client for integration with main Fynda Django app.

Usage in Django views:
    from utils.ml_client import visual_search
    
    results = await visual_search(image_data)
"""
import httpx
import base64
import logging
from typing import List, Dict, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

# ML Service URL - configure in Django settings
ML_SERVICE_URL = getattr(settings, 'ML_SERVICE_URL', 'http://localhost:8001')


async def visual_search(
    image_data: bytes,
    top_k: int = 10,
    timeout: float = 5.0
) -> List[Dict]:
    """
    Search for visually similar products.
    
    Args:
        image_data: Raw image bytes
        top_k: Number of results to return
        timeout: Request timeout in seconds
        
    Returns:
        List of product results with similarity scores
    """
    try:
        # Encode image to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ML_SERVICE_URL}/api/visual-search",
                json={
                    "image_base64": image_base64,
                    "top_k": top_k
                },
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("success"):
                logger.info(f"Visual search completed in {data.get('query_time_ms', 0)}ms")
                return data.get("results", [])
            else:
                logger.error("Visual search failed")
                return []
    
    except httpx.TimeoutException:
        logger.error(f"ML service timeout after {timeout}s")
        return []
    
    except Exception as e:
        logger.error(f"Visual search error: {e}")
        return []


async def index_product(
    product_id: str,
    image_url: str,
    metadata: Optional[Dict] = None,
    timeout: float = 10.0
) -> bool:
    """
    Index a product in the ML service.
    
    Args:
        product_id: Unique product ID
        image_url: URL of product image
        metadata: Product metadata (title, price, etc.)
        timeout: Request timeout in seconds
        
    Returns:
        True if indexed successfully
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ML_SERVICE_URL}/api/index-product",
                json={
                    "product_id": product_id,
                    "image_url": image_url,
                    "metadata": metadata or {}
                },
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("success", False)
    
    except Exception as e:
        logger.error(f"Index product error: {e}")
        return False


def visual_search_sync(image_data: bytes, top_k: int = 10) -> List[Dict]:
    """
    Synchronous version of visual_search for non-async contexts.
    """
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(visual_search(image_data, top_k))
