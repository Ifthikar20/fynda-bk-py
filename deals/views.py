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
        - "I am looking for a sony camera and my budget is $1200 that comes with a lens"
        - "best sony mirrorless camera under $1000"
    
    Response includes:
        - Parsed query (product, budget, requirements)
        - List of matching deals sorted by relevance
        - Related TikTok videos
        - Sample photos (Instagram)
        - Pinterest pins and trend ranking
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
        
        # Perform the deal search
        result = orchestrator.search(query)
        
        # Fetch related TikTok videos
        videos = tiktok_service.search_videos(query, limit=6)
        
        # Fetch sample photos from Instagram (e.g., photos taken with a camera)
        sample_photos = instagram_service.search_posts(query, limit=8)
        
        # Fetch Pinterest pins and trend data
        pinterest_pins = pinterest_service.search_pins(query, limit=6)
        pinterest_trend = pinterest_service.get_trend_data(query)
        
        # Serialize and return
        response_data = result.to_dict()
        response_data["videos"] = [v.to_dict() for v in videos]
        response_data["sample_photos"] = [p.to_dict() for p in sample_photos]
        response_data["pinterest_pins"] = [p.to_dict() for p in pinterest_pins]
        response_data["pinterest_trend"] = pinterest_trend.to_dict()
        
        serializer = SearchResponseSerializer(data=response_data)
        
        if serializer.is_valid():
            validated = serializer.validated_data
            validated["videos"] = response_data["videos"]
            validated["sample_photos"] = response_data["sample_photos"]
            validated["pinterest_pins"] = response_data["pinterest_pins"]
            validated["pinterest_trend"] = response_data["pinterest_trend"]
            return Response(validated)
        
        # If serialization fails, return raw data
        return Response(response_data)


class ImageUploadView(APIView):
    """
    Upload product screenshot for extraction and deal matching.
    
    POST /api/upload/
    
    Request: multipart/form-data with 'image' field
    
    Response includes:
        - Extracted product information
        - Matching deals if product is identified
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
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
            # Read image data
            image_data = image_file.read()
            
            # Analyze with Vision service
            analysis = vision_service.analyze_image(image_data=image_data)
            
            # If product identified, search for deals
            deals = []
            videos = []
            if analysis.product_name:
                query = analysis.product_name
                if analysis.brand:
                    query = f"{analysis.brand} {query}"
                
                result = orchestrator.search(query)
                deals = result.to_dict()["deals"][:10]
                
                # Also fetch TikTok videos
                videos = [v.to_dict() for v in tiktok_service.search_videos(query, limit=4)]
            
            return Response({
                "extracted": analysis.to_dict(),
                "deals": deals,
                "videos": videos,
                "message": "Image analyzed successfully" if analysis.product_name else "Could not identify product"
            })
            
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
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
