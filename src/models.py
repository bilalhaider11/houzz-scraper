"""Data models for the Houzz Lead Generation Pipeline.

Optimized for performance with caching, validation, and efficient data handling.
All models include proper type hints, validation, and serialization methods.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from functools import lru_cache
from email_validator import validate_email as external_validate_email, EmailNotValidError

# Import phone formatting from phone_formatter for consistency
try:
    from .phone_formatter import format_us_phone_number
except ImportError:
    from phone_formatter import format_us_phone_number

# Cache for email validation to improve performance
@lru_cache(maxsize=1000)
def _validate_email_cached(email: str) -> Optional[str]:
    """Cached email validation to avoid repeated validation of same emails."""
    try:
        valid = external_validate_email(email)
        return valid.email
    except EmailNotValidError:
        return None

@dataclass
class ProfessionalProfile:
    """Generic professional profile data for multiple platforms (Houzz, Architizer, etc.)"""
    id: Optional[int] = None
    profile_url: Optional[str] = None  # Generic URL field
    platform: Optional[str] = None     # Platform identifier (houzz, architizer, etc.)
    name: Optional[str] = None
    website: Optional[str] = None
    professional_type: Optional[str] = None
    phone: Optional[str] = None
    emails: Optional[Any] = None  # Can be string or dict with {"personal": [...], "business": [...]}
    address: Optional[str] = None
    zip_code: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    social_links: Dict[str, str] = field(default_factory=dict)
    typical_job_cost: Optional[str] = None
    followers_count: Optional[int] = None
    is_email_verified: int = 0
    is_completed: int = 0
