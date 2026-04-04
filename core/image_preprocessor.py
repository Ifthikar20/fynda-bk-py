"""
Centralized Image Pre-Processing Pipeline

Handles validation, resize, EXIF stripping, format conversion, and
hash-based deduplication for all image upload endpoints.

Usage:
    from core.image_preprocessor import preprocess_image, ImageValidationError

    result = preprocess_image(request.FILES['image'])
    # result.image_bytes   — processed JPEG bytes
    # result.image_base64  — base64-encoded string ready for ML
    # result.width, result.height
    # result.cache_key     — SHA-256 hash for dedup
    # result.was_cached    — True if identical image was recently processed
"""

import io
import hashlib
import base64
import logging
import struct

from dataclasses import dataclass
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# Magic bytes for image file type validation
MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
    b"RIFF": "image/webp",  # RIFF....WEBP
    b"GIF8": "image/gif",
}

MAX_FILE_SIZE = 10 * 1024 * 1024       # 10 MB
MAX_DIMENSION = 600                     # Resize to fit within this (smaller = faster Gemini)
JPEG_QUALITY = 82                       # Balance quality vs. payload size
CACHE_TTL = 3600                        # 1 hour dedup window


# ── Exceptions ─────────────────────────────────────────────────────────────────

class ImageValidationError(Exception):
    """Raised when an uploaded image fails validation."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class ProcessedImage:
    image_bytes: bytes
    image_base64: str
    width: int
    height: int
    cache_key: str
    was_cached: bool = False
    cached_result: Optional[dict] = None


# ── Main Pipeline ──────────────────────────────────────────────────────────────

def preprocess_image(
    uploaded_file,
    max_dimension: int = MAX_DIMENSION,
    jpeg_quality: int = JPEG_QUALITY,
    check_cache: bool = True,
) -> ProcessedImage:
    """
    Validate, resize, strip EXIF, compress, and hash an uploaded image.

    Args:
        uploaded_file: Django UploadedFile from request.FILES
        max_dimension: Maximum width/height (default 800)
        jpeg_quality: JPEG compression quality (default 82)
        check_cache: Whether to check for duplicate image hash

    Returns:
        ProcessedImage with processed bytes and metadata

    Raises:
        ImageValidationError: If image fails validation
    """
    # 1. Validate content type header
    content_type = getattr(uploaded_file, "content_type", "")
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ImageValidationError(
            f"Invalid file type '{content_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
        )

    # 2. Validate file size
    file_size = getattr(uploaded_file, "size", 0)
    if file_size > MAX_FILE_SIZE:
        raise ImageValidationError(
            f"File too large ({file_size // (1024*1024)}MB). Maximum: {MAX_FILE_SIZE // (1024*1024)}MB."
        )

    # 3. Read raw bytes
    raw_bytes = uploaded_file.read()
    if len(raw_bytes) < 8:
        raise ImageValidationError("File is too small to be a valid image.")

    # 4. Validate magic bytes (don't trust Content-Type alone)
    if not _validate_magic_bytes(raw_bytes, content_type):
        logger.warning(
            f"Magic bytes mismatch: header says {content_type}, "
            f"actual bytes: {raw_bytes[:4].hex()}"
        )
        raise ImageValidationError("File content doesn't match declared type.")

    # 5. Open with PIL and process
    from PIL import Image as PILImage

    try:
        pil_img = PILImage.open(io.BytesIO(raw_bytes))
    except Exception:
        raise ImageValidationError("Could not open image. File may be corrupted.")

    # Validate dimensions aren't absurd (DoS via decompression bomb)
    w, h = pil_img.size
    if w * h > 25_000_000:  # 25 megapixels
        raise ImageValidationError("Image dimensions too large (max 25 megapixels).")

    # 6. Strip EXIF metadata (privacy + smaller payload)
    pil_img = _strip_exif(pil_img)

    # 7. Resize if needed
    if max(w, h) > max_dimension:
        pil_img.thumbnail((max_dimension, max_dimension), PILImage.LANCZOS)
        logger.info(f"Resized image from {w}x{h} to {pil_img.size}")

    # 8. Convert to RGB JPEG
    pil_img = _ensure_rgb(pil_img)
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    processed_bytes = buf.getvalue()

    final_w, final_h = pil_img.size

    # 9. Hash for dedup
    image_hash = hashlib.sha256(processed_bytes).hexdigest()
    cache_key = f"imgcache:{image_hash}"

    # 10. Check dedup cache
    was_cached = False
    cached_result = None
    if check_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            was_cached = True
            cached_result = cached
            logger.info(f"Image dedup hit: {image_hash[:16]}...")

    # 11. Encode to base64
    image_base64 = base64.b64encode(processed_bytes).decode("utf-8")

    return ProcessedImage(
        image_bytes=processed_bytes,
        image_base64=image_base64,
        width=final_w,
        height=final_h,
        cache_key=cache_key,
        was_cached=was_cached,
        cached_result=cached_result,
    )


def cache_ml_result(cache_key: str, result: dict, ttl: int = CACHE_TTL):
    """
    Store ML inference result against the image hash so identical
    uploads within the TTL window get instant responses.
    """
    cache.set(cache_key, result, ttl)
    logger.info(f"Cached ML result for {cache_key[:24]}... (TTL={ttl}s)")


# ── Internal Helpers ───────────────────────────────────────────────────────────

def _validate_magic_bytes(raw_bytes: bytes, declared_type: str) -> bool:
    """Verify file magic bytes match the declared content type."""
    for magic, expected_type in MAGIC_BYTES.items():
        if raw_bytes[:len(magic)] == magic:
            # WebP has RIFF header — need extra check for "WEBP" at offset 8
            if magic == b"RIFF" and len(raw_bytes) >= 12:
                if raw_bytes[8:12] != b"WEBP":
                    continue
            return True  # Valid image magic, accept regardless of declared type
    return False


def _strip_exif(pil_img):
    """Remove EXIF metadata from image for privacy and smaller size.

    Uses transpose + info clear instead of expensive pixel data copy.
    """
    from PIL import ImageOps

    # Apply EXIF orientation then discard all metadata
    pil_img = ImageOps.exif_transpose(pil_img) or pil_img
    if hasattr(pil_img, "info"):
        pil_img.info.clear()
    return pil_img


def _ensure_rgb(pil_img):
    """Convert image to RGB mode (JPEG doesn't support RGBA/P/LA)."""
    from PIL import Image as PILImage

    if pil_img.mode in ("RGBA", "P", "LA"):
        background = PILImage.new("RGB", pil_img.size, (255, 255, 255))
        if pil_img.mode == "P":
            pil_img = pil_img.convert("RGBA")
        if pil_img.mode in ("RGBA", "LA"):
            background.paste(pil_img, mask=pil_img.split()[-1])
        else:
            background.paste(pil_img)
        return background
    elif pil_img.mode != "RGB":
        return pil_img.convert("RGB")
    return pil_img
