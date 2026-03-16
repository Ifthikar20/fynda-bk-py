"""
Auto-Indexing Service — Pings Google & Bing when blog posts are published.

Approaches used:
1. Google Sitemap Ping (simple HTTP GET)
2. IndexNow Protocol (Bing, Yandex, DuckDuckGo, etc.)
3. Google Search Console Indexing API (if credentials configured)
"""

import logging
import requests
import uuid
from django.conf import settings

logger = logging.getLogger(__name__)

SITE_URL = getattr(settings, 'SITE_URL', 'https://outfi.ai')
SITEMAP_URL = f"{SITE_URL}/sitemap.xml"

# IndexNow key — generate once and reuse
INDEXNOW_KEY = getattr(settings, 'INDEXNOW_KEY', None)


def ping_google_sitemap():
    """Ping Google to re-crawl the sitemap."""
    try:
        url = f"https://www.google.com/ping?sitemap={SITEMAP_URL}"
        resp = requests.get(url, timeout=10)
        logger.info(f"[Indexing] Google sitemap ping: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"[Indexing] Google sitemap ping failed: {e}")
        return False


def ping_bing_sitemap():
    """Ping Bing to re-crawl the sitemap."""
    try:
        url = f"https://www.bing.com/ping?sitemap={SITEMAP_URL}"
        resp = requests.get(url, timeout=10)
        logger.info(f"[Indexing] Bing sitemap ping: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"[Indexing] Bing sitemap ping failed: {e}")
        return False


def submit_indexnow(urls):
    """
    Submit URLs via IndexNow protocol.
    Supported by Bing, Yandex, DuckDuckGo, Naver, Szen, etc.
    """
    key = INDEXNOW_KEY
    if not key:
        logger.info("[Indexing] IndexNow key not configured, skipping")
        return False

    if isinstance(urls, str):
        urls = [urls]

    try:
        payload = {
            "host": "outfi.ai",
            "key": key,
            "urlList": urls,
        }
        resp = requests.post(
            "https://api.indexnow.org/indexnow",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        logger.info(f"[Indexing] IndexNow submission: {resp.status_code} for {len(urls)} URL(s)")
        return resp.status_code in (200, 202)
    except Exception as e:
        logger.warning(f"[Indexing] IndexNow submission failed: {e}")
        return False


def submit_url_to_google_indexing_api(url):
    """
    Submit a URL to Google's Indexing API.
    Requires GOOGLE_INDEXING_CREDENTIALS_FILE in settings pointing to a
    service account JSON key file with Search Console access.
    """
    creds_file = getattr(settings, 'GOOGLE_INDEXING_CREDENTIALS_FILE', None)
    if not creds_file:
        logger.info("[Indexing] Google Indexing API credentials not configured, skipping")
        return False

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/indexing"]
        credentials = service_account.Credentials.from_service_account_file(
            creds_file, scopes=SCOPES
        )
        service = build("indexing", "v3", credentials=credentials)

        body = {"url": url, "type": "URL_UPDATED"}
        result = service.urlNotifications().publish(body=body).execute()
        logger.info(f"[Indexing] Google Indexing API success: {url} -> {result}")
        return True
    except ImportError:
        logger.warning("[Indexing] google-auth / google-api-python-client not installed")
        return False
    except Exception as e:
        logger.warning(f"[Indexing] Google Indexing API failed for {url}: {e}")
        return False


def notify_search_engines(post_url):
    """
    Main function — notify all search engines about a new/updated URL.
    Called automatically when a post is published.
    """
    logger.info(f"[Indexing] Submitting URL for indexing: {post_url}")

    results = {
        "google_sitemap": ping_google_sitemap(),
        "bing_sitemap": ping_bing_sitemap(),
        "indexnow": submit_indexnow(post_url),
        "google_api": submit_url_to_google_indexing_api(post_url),
    }

    success_count = sum(1 for v in results.values() if v)
    logger.info(f"[Indexing] Results: {results} ({success_count}/4 succeeded)")
    return results


def bulk_submit_all_published():
    """Submit all published post URLs for indexing. Used by management command."""
    from blog.models import Post

    posts = Post.objects.filter(status='published').order_by('-published_at')
    urls = [post.get_absolute_url() for post in posts]

    logger.info(f"[Indexing] Bulk submitting {len(urls)} published URLs")

    # Ping sitemaps once
    ping_google_sitemap()
    ping_bing_sitemap()

    # Submit all URLs via IndexNow (supports batch)
    if urls:
        submit_indexnow(urls)

    # Submit each to Google Indexing API individually
    for url in urls:
        submit_url_to_google_indexing_api(url)

    return len(urls)
