"""
Background tasks for the deals app.

Auto-indexes Amazon product images into the FAISS visual search index
after each successful search, so the visual similarity model gradually
learns from real product data.
"""
import logging
import requests
from celery import shared_task

logger = logging.getLogger(__name__)


def _get_ml_url():
    """Lazy fetch of ML_SERVICE_URL to avoid import-time settings access."""
    from django.conf import settings
    return getattr(settings, 'ML_SERVICE_URL', 'http://localhost:8001')


@shared_task(
    name='deals.tasks.index_products_to_faiss',
    bind=True,
    max_retries=1,
    soft_time_limit=120,
    ignore_result=True,
    rate_limit='10/m',       # Max 10 indexing batches per minute
)
def index_products_to_faiss(self, deals_data: list):
    """
    Index a batch of product images into the ML service FAISS index.
    
    Called automatically after Amazon returns search results.
    Runs in the background so it doesn't slow down the user response.
    
    Args:
        deals_data: List of deal dicts with at minimum:
                    {id, title, price, image_url, merchant_name/source}
    """
    if not deals_data:
        return
    
    indexed = 0
    skipped = 0
    
    for deal in deals_data[:15]:  # Cap at 15 products per batch
        product_id = str(deal.get('id', ''))
        image_url = deal.get('image_url') or deal.get('image', '')
        
        if not product_id or not image_url:
            skipped += 1
            continue
        
        try:
            response = requests.post(
                f"{_get_ml_url()}/api/index-product",
                json={
                    "product_id": product_id,
                    "image_url": image_url,
                    "metadata": {
                        "title": deal.get('title', ''),
                        "price": float(deal.get('price', 0) or 0),
                        "image_url": image_url,
                        "merchant": deal.get('merchant_name') or deal.get('source', ''),
                        "category": deal.get('category', ''),
                    }
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    indexed += 1
                else:
                    skipped += 1  # Already exists
            else:
                skipped += 1
                
        except requests.RequestException as e:
            logger.debug(f"ML index skip for {product_id}: {e}")
            skipped += 1
    
    if indexed > 0:
        # Save the FAISS index after batch
        try:
            requests.post(f"{_get_ml_url()}/api/save-index", timeout=10)
        except requests.RequestException:
            pass
        
        logger.info(f"FAISS auto-index: {indexed} indexed, {skipped} skipped")
