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

from .services import orchestrator, vision_service, tiktok_service, instagram_service, pinterest_service
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
    
    GET /api/search/?q=<query>
    
    Example queries:
        - "sony camera $1200 with lens"
        - "best sony mirrorless camera under $1000"
    
    Response includes:
        - Parsed query (product, budget, requirements)
        - List of matching deals from affiliate networks (CJ, Rakuten, ShareASale)
        - Metadata (total results, sources, search time)
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        query = request.query_params.get('q', '').strip()
        
        if not query:
            return Response(
                {"error": "Missing required parameter 'q' (search query)"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(query) < 3:
            return Response(
                {"error": "Query must be at least 3 characters long"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Perform the deal search (affiliate networks only)
        result = orchestrator.search(query)
        
        # Return clean response with only affiliate deals
        response_data = result.to_dict()
        
        # Auto-index returned products into FAISS (background)
        try:
            from .tasks import index_products_to_faiss
            if response_data.get('deals'):
                index_products_to_faiss.delay(response_data['deals'])
        except Exception:
            pass  # Never let indexing failure affect search
        
        return Response(response_data)


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
        import base64
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
            # Read and encode image
            image_data = image_file.read()
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
            
            # Fallback: OpenAI Vision (if ML service failed or returned no queries)
            if not search_queries:
                try:
                    analysis = vision_service.analyze_image(image_data=image_data)
                    extracted = analysis.to_dict()
                    if analysis.product_name:
                        query = analysis.product_name
                        if analysis.brand:
                            query = f"{analysis.brand} {query}"
                        search_queries = [query]
                        logger.info(f"OpenAI Vision fallback identified: {search_queries}")
                except Exception as e:
                    logger.warning(f"OpenAI Vision fallback also failed: {e}")
            
            # If we still have no queries, return a graceful empty response
            if not search_queries:
                return Response({
                    "extracted": extracted or {},
                    "search_queries": [],
                    "deals": [],
                    "videos": [],
                    "message": "Could not identify product. Try a clearer product image."
                })
            
            # Step 2: Search for deals using generated queries
            all_deals = []
            videos = []
            
            for query in search_queries[:3]:  # Use top 3 queries
                try:
                    result = orchestrator.search(query)
                    for deal in result.to_dict()["deals"]:
                        # Avoid duplicates
                        if not any(d.get("id") == deal.get("id") for d in all_deals):
                            all_deals.append(deal)
                except Exception as e:
                    logger.warning(f"Search failed for query '{query}': {e}")
                
                # Fetch TikTok videos for first query only
                if not videos:
                    try:
                        videos = [v.to_dict() for v in tiktok_service.search_videos(query, limit=4)]
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
