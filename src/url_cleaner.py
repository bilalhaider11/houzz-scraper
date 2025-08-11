"""URL Cleaner Module for the Houzz Lead Generation Pipeline.

Optimized for performance with caching, pattern matching, and comprehensive URL cleaning.
Handles redirect extraction, tracking parameter removal, and URL normalization.
"""

import urllib.parse
import re
from typing import Tuple
from dataclasses import dataclass

@dataclass(frozen=True)
class URLPatterns:
    """Immutable container for URL cleaning patterns for better performance."""
    redirect_patterns: Tuple[str, ...] = (
        r'[?&]next=([^&]+)',                    # Facebook, Instagram ?next=
        r'[?&]redirect=([^&]+)',                # Generic redirect
        r'[?&]return_to=([^&]+)',               # GitHub, some others
        r'[?&]url=([^&]+)',                     # Generic URL param
        r'[?&]trk=([^&]+)',                     # LinkedIn
        r'[?&]redirect_after_login=([^&]+)',    # Twitter/X
        r'[?&]u=([^&]+)',                       # Short URL services
        r'[?&]target=([^&]+)',                  # Generic target param
    )
    
    tracking_params: frozenset = frozenset({
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'fbclid', 'gclid', 'msclkid', 'twclid', 'ref', 'source', 'medium', 
        'campaign', '_fb_noscript', 'refsrc', 'ref_src', 'igshid', 'trk',
        'mc_cid', 'mc_eid', 'hsCtaTracking', '_hsenc', '_hsmi',  # Email tracking
        'si', 'feature', 'app', 'via',  # YouTube, social sharing
    })
    
    profile_patterns: Tuple[str, ...] = (
        r'facebook\.com/[^/?]+$',
        r'instagram\.com/[^/?]+$',
        r'linkedin\.com/in/[^/?]+$',
        r'linkedin\.com/company/[^/?]+$',
        r'twitter\.com/[^/?]+$',
        r'x\.com/[^/?]+$',
        r'github\.com/[^/?]+$',
        r'behance\.net/[^/?]+$',
    )

# Global patterns instance for reuse
_URL_PATTERNS = URLPatterns()

from .cache_manager import cached

@cached(ttl=3600, key_prefix="url_redirect")
def _extract_redirect_target(url: str) -> str:
    """Cached extraction of redirect target from URL."""
    for pattern in _URL_PATTERNS.redirect_patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            # Extract and decode the target URL
            extracted = match.group(1)
            decoded = urllib.parse.unquote(extracted)
            # Double decode in case of double encoding
            return urllib.parse.unquote_plus(decoded)
    return url

@cached(ttl=3600, key_prefix="url_trailing")
def _should_add_trailing_slash(url: str) -> bool:
    """Cached check if URL should have trailing slash for consistency."""
    return any(
        re.search(pattern, url, re.IGNORECASE) 
        for pattern in _URL_PATTERNS.profile_patterns
    )

@cached(ttl=3600, key_prefix="url_query")
def _clean_query_params(query_string: str) -> str:
    """Remove tracking parameters from query string efficiently."""
    if not query_string:
        return ""
    
    query_params = urllib.parse.parse_qs(query_string)
    cleaned_params = {
        k: v for k, v in query_params.items() 
        if k.lower() not in _URL_PATTERNS.tracking_params
    }
    
    return urllib.parse.urlencode(cleaned_params, doseq=True)

@cached(ttl=3600, key_prefix="url_clean")
def get_clean_target_url(messy_url: str) -> str:
    """
    Extract and clean target URLs from redirect URLs with comprehensive cleaning.
    
    Optimized with caching for better performance on repeated URLs.
    Handles multiple redirect patterns, tracking parameter removal, and URL normalization.
    
    Args:
        messy_url (str): URL that might be a login redirect or have tracking params
        
    Returns:
        str: Clean target URL with tracking params removed and proper formatting
        
    Examples:
        >>> get_clean_target_url('https://facebook.com/login?next=https%3A//example.com')
        'https://example.com'
        >>> get_clean_target_url('https://example.com?utm_source=google&id=123')
        'https://example.com?id=123'
    """
    if not messy_url or not isinstance(messy_url, str):
        return messy_url or ""
    
    # Step 1: Extract target URL from redirect patterns (cached)
    target_url = _extract_redirect_target(messy_url.strip())
    
    # Step 2: Parse URL for cleaning
    try:
        parsed = urllib.parse.urlparse(target_url)
    except Exception:
        # If URL parsing fails, return original
        return messy_url
    
    # Step 3: Clean query parameters
    cleaned_query = _clean_query_params(parsed.query)
    
    # Step 4: Reconstruct URL with cleaned parameters
    cleaned_parsed = parsed._replace(query=cleaned_query)
    target_url = urllib.parse.urlunparse(cleaned_parsed)
    
    # Step 5: Add trailing slash for profile pages if needed (cached check)
    if _should_add_trailing_slash(target_url) and not target_url.endswith('/'):
        target_url += '/'
    
    return target_url

