"""
Background Removal API View

POST /api/mobile/tools/remove-bg/

Accepts a multipart image upload and returns a transparent PNG
with the background removed using rembg (U2Net model).
"""

import io
import base64
import logging
import time

from PIL import Image as PILImage
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_DIMENSION = 1024  # Resize large images before processing
MIN_DIMENSION = 64    # Upscale tiny images so rembg can process them


class RemoveBackgroundView(APIView):
    """
    Remove the background from an uploaded image.

    POST /api/mobile/tools/remove-bg/

    Request: multipart/form-data with 'image' field
    Response:
    {
        "image_base64": "<base64-encoded transparent PNG>",
        "width": 800,
        "height": 600,
        "processing_ms": 1230
    }
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    from outfi.throttles import RemoveBgAnonThrottle, RemoveBgUserThrottle, ImageBurstThrottle
    throttle_classes = [RemoveBgAnonThrottle, RemoveBgUserThrottle, ImageBurstThrottle]

    def post(self, request):
        if 'image' not in request.FILES:
            return Response(
                {"error": "No image file provided. Use 'image' field."},
                status=status.HTTP_400_BAD_REQUEST
            )

        image_file = request.FILES['image']

        # Validate using centralized preprocessor for type + size + magic bytes
        from core.image_preprocessor import ImageValidationError
        
        content_type = image_file.content_type
        if content_type not in ALLOWED_TYPES:
            return Response(
                {"error": f"Invalid file type. Allowed: {', '.join(ALLOWED_TYPES)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if image_file.size > MAX_FILE_SIZE:
            return Response(
                {"error": "File too large. Maximum size is 10MB."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate magic bytes (don't trust Content-Type alone)
        raw_peek = image_file.read(12)
        image_file.seek(0)
        from core.image_preprocessor import _validate_magic_bytes
        if not _validate_magic_bytes(raw_peek, content_type):
            return Response(
                {"error": "File content doesn't match declared type."},
                status=status.HTTP_400_BAD_REQUEST
            )

        start = time.time()

        try:
            # Read image
            image_data = image_file.read()
            try:
                pil_img = PILImage.open(io.BytesIO(image_data))
                pil_img.load()  # Force decode — catches truncated/corrupt images
            except Exception as img_err:
                logger.warning(f"Cannot decode image: {img_err}")
                return Response(
                    {"error": "Image could not be decoded. Try a different image."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            w_orig, h_orig = pil_img.size
            logger.info(f"BG remove input: {w_orig}x{h_orig} mode={pil_img.mode}")

            # Reject extremely tiny images (< 10px either dimension)
            if w_orig < 10 or h_orig < 10:
                return Response(
                    {"error": "Image is too small. Please use a larger image (at least 64x64)."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Convert palette/grayscale to RGBA for rembg
            if pil_img.mode not in ('RGB', 'RGBA'):
                pil_img = pil_img.convert('RGBA')

            # Upscale small images so rembg has enough detail to work with
            if max(pil_img.size) < MIN_DIMENSION:
                scale = MIN_DIMENSION / max(pil_img.size)
                new_w = max(int(pil_img.width * scale), MIN_DIMENSION)
                new_h = max(int(pil_img.height * scale), MIN_DIMENSION)
                pil_img = pil_img.resize((new_w, new_h), PILImage.LANCZOS)
                logger.info(f"Upscaled small image {w_orig}x{h_orig} → {new_w}x{new_h}")

            # Resize if too large (speeds up processing significantly)
            if max(pil_img.size) > MAX_DIMENSION:
                pil_img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), PILImage.LANCZOS)
                logger.info(f"Downscaled to {pil_img.size} before bg removal")

            # Convert to PNG bytes for rembg
            input_buf = io.BytesIO()
            pil_img.save(input_buf, format='PNG')
            input_bytes = input_buf.getvalue()

            # Remove background
            from rembg import remove
            output_bytes = remove(input_bytes)

            # Get output dimensions
            result_img = PILImage.open(io.BytesIO(output_bytes))
            w, h = result_img.size

            # Encode as base64
            result_b64 = base64.b64encode(output_bytes).decode('utf-8')

            elapsed = int((time.time() - start) * 1000)
            logger.info(f"Background removed in {elapsed}ms ({w}x{h})")

            return Response({
                "image_base64": result_b64,
                "width": w,
                "height": h,
                "processing_ms": elapsed,
            })

        except ImportError:
            logger.error("rembg is not installed. Run: pip install rembg[gpu]")
            return Response(
                {"error": "Background removal service not available."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.exception(f"Background removal failed: {e}")
            return Response(
                {"error": "Failed to process image. Please try a larger or clearer image."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
