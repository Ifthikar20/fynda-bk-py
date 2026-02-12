"""
Deal Views

API endpoints for searching, image upload, and deal retrieval.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
import io
import base64

from .services import orchestrator, tiktok_service, instagram_service, pinterest_service
from .serializers import SearchResponseSerializer


@method_decorator(ensure_csrf_cookie, name='dispatch')
class CsrfView(APIView):
    """
    Get CSRF token.
    
    GET /api/csrf/
    
    Sets CSRF cookie and returns token for use in headers.
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        return Response({
            "csrfToken": get_token(request),
            "message": "CSRF cookie set"
        })


class SearchView(APIView):
    """
    Search for deals using natural language queries.
    
    GET /api/search/?q=<query>&page=1&limit=20
    
    Query params:
        q       - Search query (required, 2-200 chars)
        page    - Page number (default: 1)
        limit   - Results per page (default: 20, max: 50)
        offset  - Alternative to page (overrides page if present)
    
    Response includes:
        - Parsed query (product, budget, requirements)
        - Paginated list of matching deals
        - Pagination metadata (total, page, has_more)
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        from .query_sanitizer import sanitize_query, validate_query, get_pagination_params
        
        # ── Sanitize & validate ───────────────────────
        raw_query = request.query_params.get('q', '')
        query = sanitize_query(raw_query)
        
        error = validate_query(query)
        if error:
            return Response(
                {"error": error},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ── Pagination params ─────────────────────────
        offset, limit = get_pagination_params(request)
        
        # ── Cache lookup (5-minute TTL) ──────────────
        import hashlib
        from django.core.cache import cache
        
        cache_key = f"search:{hashlib.md5(query.lower().encode()).hexdigest()}"
        cached = cache.get(cache_key)
        
        if cached:
            # Paginate cached results
            all_deals = cached.get('deals', [])
            page_deals = all_deals[offset:offset + limit]
            cached_copy = {**cached}
            cached_copy['deals'] = page_deals
            cached_copy['total'] = len(all_deals)
            cached_copy['page'] = (offset // limit) + 1
            cached_copy['limit'] = limit
            cached_copy['has_more'] = (offset + limit) < len(all_deals)
            cached_copy['total_pages'] = max(1, -(-len(all_deals) // limit))  # ceil division
            cached_copy['_cached'] = True
            return Response(cached_copy)
        
        # ── Search ────────────────────────────────────
        result = orchestrator.search(query)
        response_data = result.to_dict()
        
        # Cache full results (before pagination) for 5 minutes
        cache.set(cache_key, response_data, timeout=300)
        
        # ── Paginate ──────────────────────────────────
        all_deals = response_data.get('deals', [])
        page_deals = all_deals[offset:offset + limit]
        
        response_data['deals'] = page_deals
        response_data['total'] = len(all_deals)
        response_data['page'] = (offset // limit) + 1
        response_data['limit'] = limit
        response_data['has_more'] = (offset + limit) < len(all_deals)
        response_data['total_pages'] = max(1, -(-len(all_deals) // limit))
        
        # Auto-index returned products into FAISS (background)
        try:
            from .tasks import index_products_to_faiss
            if all_deals:
                index_products_to_faiss.delay(all_deals)
        except Exception:
            pass  # Never let indexing failure affect search
        
        return Response(response_data)


class InstantSearchView(APIView):
    """
    Cache-only search for instant results (<50ms).
    
    GET /api/search/instant/?q=<query>
    
    Returns cached results immediately if available.
    If no cache hit, returns empty list so the client
    knows to wait for the full /api/search/ response.
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        import hashlib
        from django.core.cache import cache
        
        query = request.query_params.get('q', '').strip().lower()
        if len(query) < 2:
            return Response({"deals": [], "cached": False})
        
        cache_key = f"search:{hashlib.md5(query.encode()).hexdigest()}"
        cached = cache.get(cache_key)
        
        if cached:
            deals = cached.get('deals', [])[:15]
            return Response({"deals": deals, "cached": True})
        
        return Response({"deals": [], "cached": False})


class ImageUploadView(APIView):
    """
    Upload product screenshot for extraction and deal matching.
    
    POST /api/upload/
    
    Request: multipart/form-data with 'image' field
    
    Response includes:
        - Extracted product attributes (colors, textures, caption)
        - Generated search queries
        - Matching deals from Amazon and other marketplaces
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    
    def _get_ml_url(self):
        """Get ML service URL from Django settings (resolves to http://ml:8001 in Docker)."""
        from django.conf import settings as django_settings
        base = getattr(django_settings, 'ML_SERVICE_URL', 'http://localhost:8001')
        return f"{base}/api/extract-attributes"
    
    def post(self, request):
        import requests
        import logging
        logger = logging.getLogger(__name__)
        
        if 'image' not in request.FILES:
            return Response(
                {"error": "No image file provided. Use 'image' field."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        image_file = request.FILES['image']
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
        if image_file.content_type not in allowed_types:
            return Response(
                {"error": f"Invalid file type. Allowed: {', '.join(allowed_types)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file size (max 10MB)
        if image_file.size > 10 * 1024 * 1024:
            return Response(
                {"error": "File too large. Maximum size is 10MB."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Read and encode image (resize for speed)
            image_data = image_file.read()
            
            # Resize image before sending to ML (saves network + processing time)
            from PIL import Image as PILImage
            pil_img = PILImage.open(io.BytesIO(image_data))
            if max(pil_img.size) > 800:
                pil_img.thumbnail((800, 800), PILImage.LANCZOS)
                logger.info(f"Resized upload to {pil_img.size}")
            # Convert RGBA/P to RGB (JPEG doesn't support transparency)
            if pil_img.mode in ('RGBA', 'P', 'LA'):
                background = PILImage.new('RGB', pil_img.size, (255, 255, 255))
                if pil_img.mode == 'P':
                    pil_img = pil_img.convert('RGBA')
                background.paste(pil_img, mask=pil_img.split()[-1])
                pil_img = background
            elif pil_img.mode != 'RGB':
                pil_img = pil_img.convert('RGB')
            buf = io.BytesIO()
            pil_img.save(buf, format='JPEG', quality=85)
            image_data = buf.getvalue()
            
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Step 1: Try to identify the product
            extracted = None
            search_queries = []
            
            # Primary: Own ML service (BLIP — free, fast, runs on EC2)
            try:
                ml_url = self._get_ml_url()
                logger.info(f"Calling ML service at {ml_url}")
                ml_response = requests.post(
                    ml_url,
                    json={"image_base64": image_base64},
                    timeout=30
                )
                if ml_response.status_code == 200:
                    ml_data = ml_response.json()
                    if ml_data.get("success"):
                        extracted = {
                            "caption": ml_data.get("caption", ""),
                            "colors": ml_data.get("colors", {}),
                            "textures": ml_data.get("textures", []),
                            "category": ml_data.get("category", ""),
                        }
                        search_queries = ml_data.get("search_queries", [])
                        logger.info(f"ML service identified product: {search_queries}")
                else:
                    logger.warning(f"ML service returned status {ml_response.status_code}")
            except requests.RequestException as e:
                logger.warning(f"ML service unavailable: {e}")
            
            # If ML service returned no queries, return a graceful empty response
            if not search_queries:
                return Response({
                    "extracted": extracted or {},
                    "search_queries": [],
                    "deals": [],
                    "videos": [],
                    "message": "Could not identify product. Try a clearer product image."
                })
            
            # Step 2: Search for deals using generated queries (IN PARALLEL)
            from concurrent.futures import ThreadPoolExecutor, as_completed
            all_deals = []
            videos = []
            
            def search_query(query):
                """Search a single query and return results."""
                try:
                    result = orchestrator.search(query)
                    return result.to_dict()["deals"]
                except Exception as e:
                    logger.warning(f"Search failed for query '{query}': {e}")
                    return []
            
            # Run all search queries in parallel
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(search_query, q): q for q in search_queries[:3]}
                for future in as_completed(futures):
                    for deal in future.result():
                        if not any(d.get("id") == deal.get("id") for d in all_deals):
                            all_deals.append(deal)
            
            # Fetch TikTok videos for first query
            if search_queries:
                try:
                    videos = [v.to_dict() for v in tiktok_service.search_videos(search_queries[0], limit=4)]
                except Exception:
                    pass
            
            # Sort by relevance and limit results
            all_deals = sorted(
                all_deals, 
                key=lambda d: d.get("relevance_score", 0), 
                reverse=True
            )[:15]
            
            return Response({
                "extracted": extracted,
                "search_queries": search_queries,
                "deals": all_deals,
                "videos": videos,
                "message": "Image analyzed successfully" if search_queries else "Could not identify product"
            })
            
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Image upload failed: {e}", exc_info=True)
            return Response(
                {"error": f"Failed to analyze image: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HealthView(APIView):
    """
    Health check endpoint.
    
    GET /api/health/
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        return Response({
            "status": "healthy",
            "service": "Fetch Bot API",
            "version": "1.0.0",
        })


# ============================================================
# Shared Storyboard Views
# ============================================================

from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
from .models import SharedStoryboard


class CreateSharedStoryboardView(APIView):
    """
    Create a shared storyboard link.
    
    POST /api/storyboard/share/
    
    Request body:
        - title: string (optional)
        - storyboard_data: object (required)
        - expires_in_days: number (optional, default: 30)
    
    Response:
        - token: string (the share token)
        - share_url: string (full URL to share)
        - expires_at: datetime
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        storyboard_data = request.data.get('storyboard_data', {})
        title = request.data.get('title', 'Fashion Storyboard')
        expires_in_days = request.data.get('expires_in_days', 30)
        
        if not storyboard_data:
            return Response(
                {"error": "storyboard_data is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate unique token
        token = SharedStoryboard.generate_token()
        
        # Calculate expiration
        expires_at = timezone.now() + timedelta(days=expires_in_days)
        
        # Create the shared storyboard
        shared = SharedStoryboard.objects.create(
            token=token,
            user=request.user,
            title=title,
            storyboard_data=storyboard_data,
            expires_at=expires_at
        )
        
        # Build share URL
        share_url = f"{request.scheme}://{request.get_host()}/share/{token}"
        
        return Response({
            "token": token,
            "share_url": share_url,
            "expires_at": expires_at.isoformat(),
            "id": str(shared.id)
        }, status=status.HTTP_201_CREATED)


class GetSharedStoryboardView(APIView):
    """
    Get a shared storyboard by token (public access).
    
    GET /api/storyboard/share/<token>/
    
    Response:
        - title: string
        - storyboard_data: object
        - created_at: datetime
        - view_count: number
    """
    permission_classes = [AllowAny]
    
    def get(self, request, token):
        try:
            shared = SharedStoryboard.objects.get(token=token)
        except SharedStoryboard.DoesNotExist:
            return Response(
                {"error": "Shared storyboard not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if expired
        if shared.expires_at and shared.expires_at < timezone.now():
            return Response(
                {"error": "This share link has expired"},
                status=status.HTTP_410_GONE
            )
        
        # Check if public
        if not shared.is_public:
            return Response(
                {"error": "This storyboard is not publicly accessible"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Increment view count
        shared.increment_views()
        
        return Response({
            "title": shared.title,
            "storyboard_data": shared.storyboard_data,
            "created_at": shared.created_at.isoformat(),
            "view_count": shared.view_count,
            "owner": shared.user.first_name or "Anonymous"
        })


class MySharedStoryboardsView(APIView):
    """
    List all shared storyboards for the authenticated user.
    
    GET /api/storyboard/my-shares/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        shares = SharedStoryboard.objects.filter(user=request.user)
        
        return Response({
            "shares": [
                {
                    "id": str(s.id),
                    "token": s.token,
                    "title": s.title,
                    "created_at": s.created_at.isoformat(),
                    "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                    "view_count": s.view_count,
                    "is_public": s.is_public,
                    "share_url": f"{request.scheme}://{request.get_host()}/share/{s.token}"
                }
                for s in shares
            ],
            "total": shares.count()
        })
    
    def delete(self, request):
        """Delete a shared storyboard"""
        share_id = request.data.get('id')
        if not share_id:
            return Response(
                {"error": "id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            shared = SharedStoryboard.objects.get(id=share_id, user=request.user)
            shared.delete()
            return Response({"message": "Shared storyboard deleted"})
        except SharedStoryboard.DoesNotExist:
            return Response(
                {"error": "Shared storyboard not found"},
                status=status.HTTP_404_NOT_FOUND
            )


# ============================================
# Saved Deals (Web API)
# ============================================

class SavedDealsView(APIView):
    """
    Saved deals for web frontend.
    
    GET /api/saved/        — list saved deals
    POST /api/saved/       — save a deal
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from users.models import SavedDeal
        
        favorites = SavedDeal.objects.filter(
            user=request.user
        ).order_by("-created_at")[:100]
        
        items = []
        for f in favorites:
            data = f.deal_data or {}
            items.append({
                "id": str(f.id),
                "deal_id": f.deal_id,
                "title": data.get("title", ""),
                "price": data.get("price"),
                "original_price": data.get("original_price"),
                "image": data.get("image_url") or data.get("image") or "",
                "source": data.get("source", ""),
                "url": data.get("url", ""),
                "saved_at": f.created_at.isoformat() if f.created_at else None,
            })
        
        return Response({
            "saved": items,
            "count": len(items),
        })
    
    def post(self, request):
        
        from users.models import SavedDeal
        
        deal_id = request.data.get("deal_id")
        deal_data = request.data.get("deal_data", {})
        
        if not deal_id:
            return Response(
                {"error": "deal_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        favorite, created = SavedDeal.objects.get_or_create(
            user=request.user,
            deal_id=deal_id,
            defaults={"deal_data": deal_data}
        )
        
        return Response(
            {"id": str(favorite.id), "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class SavedDealDetailView(APIView):
    """
    Single saved deal management for web.
    
    DELETE /api/saved/<deal_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, deal_id):
        
        from users.models import SavedDeal
        
        deleted, _ = SavedDeal.objects.filter(
            user=request.user,
            deal_id=deal_id
        ).delete()
        
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        return Response(
            {"error": "Saved deal not found"},
            status=status.HTTP_404_NOT_FOUND
        )


# ============================================
# Featured Content API
# ============================================

from django.views.decorators.cache import cache_page

from .featured import FEATURED_BRANDS, SEARCH_PROMPTS, QUICK_SUGGESTIONS, CATEGORIES as FEATURED_CATEGORIES


class FeaturedContentView(APIView):
    """
    Serve curated featured content for the landing page and category pages.

    GET /api/featured/                — all featured brands + search prompts
    GET /api/featured/?category=women — category-specific brands, trending, etc.

    Response is cached for 1 hour. No auth required.
    """
    permission_classes = [AllowAny]

    @method_decorator(cache_page(60 * 60))  # 1 hour cache
    def get(self, request):
        category = request.query_params.get('category')

        response_data = {
            "featured_brands": FEATURED_BRANDS,
            "search_prompts": SEARCH_PROMPTS,
            "quick_suggestions": QUICK_SUGGESTIONS,
        }

        if category and category in FEATURED_CATEGORIES:
            response_data["category"] = FEATURED_CATEGORIES[category]
        elif category:
            return Response(
                {"error": f"Unknown category: {category}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Include all category metadata for navigation
        response_data["categories"] = {
            slug: {
                "title": data["title"],
                "description": data["description"],
                "subcategories": data["subcategories"],
            }
            for slug, data in FEATURED_CATEGORIES.items()
        }

        return Response(response_data)


# ============================================
# Explore / Landing Page API
# ============================================

# Category → default search query mapping
EXPLORE_CATEGORY_QUERIES = {
    "all-products": "women men fashion outfit trending",
    "women": "women dress outfit trending fashion",
    "men": "men fashion jacket streetwear outfit",
    "shoes": "sneakers boots heels sandals trending",
    "accessories": "bag watch jewelry sunglasses trending",
    "beauty": "makeup skincare lipstick trending",
    "activewear": "gym workout leggings sports bra trending",
}


class ExploreView(APIView):
    """
    Explore page products — served through the backend.
    
    GET /api/explore/?category=all-products&limit=20
    
    This replaces the frontend's direct RapidAPI call,
    keeping the API key server-side and enabling caching,
    fashion filtering, and result ranking.
    """
    permission_classes = [AllowAny]
    
    @method_decorator(cache_page(30 * 60))  # 30 minute cache
    def get(self, request):
        category = request.query_params.get("category", "all-products")
        limit = min(int(request.query_params.get("limit", 20)), 50)
        
        query = EXPLORE_CATEGORY_QUERIES.get(category, "trending fashion clothing")
        result = orchestrator.search(query)
        
        deals = result.to_dict().get("deals", [])[:limit]
        
        return Response({
            "category": category,
            "query": query,
            "deals": deals,
            "total": len(deals),
            "sources": result.sources_with_results,
        })


# ============================================
# Vendor Status API
# ============================================

class VendorStatusView(APIView):
    """
    Check the status of all registered vendors.
    
    GET /api/vendors/status/
    
    Shows which vendors are enabled, loaded, configured,
    and whether their circuit breakers are open.
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        from .services.vendors import vendor_manager as vm
        
        return Response({
            "vendors": vm.get_all_status(),
            "total_enabled": len(vm.get_enabled_vendors()),
            "total_loaded": len(vm.get_all_instances()),
        })

