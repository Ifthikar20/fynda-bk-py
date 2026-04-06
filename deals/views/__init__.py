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

from deals.services import orchestrator, tiktok_service, instagram_service, pinterest_service
from deals.serializers import SearchResponseSerializer
from deals.repositories import SharedStoryboardRepository
from users.repositories import SavedDealRepository


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
        from deals.query_sanitizer import sanitize_query, validate_query, get_pagination_params
        
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
    
    Rate limits:
        - Anon: 5/hour, Auth: 20/hour
        - Burst: 2/minute (anon), 5/minute (auth)
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    
    from fynda.throttles import ImageUploadAnonThrottle, ImageUploadUserThrottle, ImageBurstThrottle
    throttle_classes = [ImageUploadAnonThrottle, ImageUploadUserThrottle, ImageBurstThrottle]
    
    def post(self, request):
        import logging
        logger = logging.getLogger(__name__)
        from core.image_preprocessor import preprocess_image, cache_ml_result, ImageValidationError
        from deals.services.gemini_vision_service import gemini_vision

        if 'image' not in request.FILES:
            return Response(
                {"error": "No image file provided. Use 'image' field."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Centralized image pre-processing (validate, resize, strip EXIF, hash dedup)
            processed = preprocess_image(request.FILES['image'])
            image_base64 = processed.image_base64

            # If identical image was recently processed, return cached result
            if processed.was_cached and processed.cached_result:
                logger.info("Returning cached result for duplicate image")
                return Response(processed.cached_result)

        except ImageValidationError as e:
            return Response(
                {"error": e.message},
                status=e.status_code
            )

        try:

            # Step 1: Analyze image with Gemini Vision
            extracted = None
            search_queries = []

            try:
                result = gemini_vision.analyze_image(image_base64)
                if result and result.get("search_queries"):
                    items = result.get("items", [{}])
                    main_item = items[0] if items else {}
                    extracted = {
                        "caption": result.get("overall_style", ""),
                        "category": main_item.get("category", ""),
                        "type": main_item.get("type", ""),
                        "color": main_item.get("color", ""),
                        "brand": main_item.get("brand"),
                        "material": main_item.get("material", ""),
                        "pattern": main_item.get("pattern", ""),
                        "style": main_item.get("style", ""),
                    }
                    search_queries = result["search_queries"]
                    logger.info(f"Gemini identified product: {search_queries}")
            except Exception as e:
                logger.warning(f"Gemini vision failed: {e}")

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
            
            response_data = {
                "extracted": extracted,
                "search_queries": search_queries,
                "deals": all_deals,
                "videos": videos,
                "message": "Image analyzed successfully" if search_queries else "Could not identify product"
            }
            
            # Cache result against image hash for dedup
            cache_ml_result(processed.cache_key, response_data)
            
            return Response(response_data)
            
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
from deals.models import SharedStoryboard


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
        shared = SharedStoryboardRepository.create_shared(
            user=request.user,
            title=title,
            storyboard_data=storyboard_data,
            expires_at=expires_at,
            token=token,
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
        shared = SharedStoryboardRepository.get_by_token(token)
        if not shared:
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
        SharedStoryboardRepository.increment_views(shared)
        
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
        shares = SharedStoryboardRepository.get_user_storyboards(request.user)
        
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
            deleted = SharedStoryboardRepository.delete_by_id(request.user, share_id)
            if deleted:
                return Response({"message": "Shared storyboard deleted"})
            return Response(
                {"error": "Shared storyboard not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception:
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
        favorites = SavedDealRepository.get_user_deals(request.user)
        
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
        deal_id = request.data.get("deal_id")
        deal_data = request.data.get("deal_data", {})
        
        if not deal_id:
            return Response(
                {"error": "deal_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        favorite, created = SavedDealRepository.save_deal(
            user=request.user,
            deal_id=deal_id,
            deal_data=deal_data,
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
        deleted = SavedDealRepository.unsave_deal(
            user=request.user,
            deal_id=deal_id,
        )
        
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

from deals.featured import FEATURED_BRANDS, SEARCH_PROMPTS, QUICK_SUGGESTIONS, CATEGORIES as FEATURED_CATEGORIES


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
        from deals.services.vendors import vendor_manager as vm
        
        return Response({
            "vendors": vm.get_all_status(),
            "total_enabled": len(vm.get_enabled_vendors()),
            "total_loaded": len(vm.get_all_instances()),
        })

