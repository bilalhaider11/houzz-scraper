"""Phone Formatter Module for the Houzz Lead Generation Pipeline.

Optimized phone formatting functions that integrate with common_utils.
Provides backward compatibility while leveraging cached formatting functions.
"""

import re
from typing import Optional
from loguru import logger
import phonenumbers
from phonenumbers import PhoneNumberFormat

from .cache_manager import cached

@cached(ttl=3600, key_prefix="phone_format")
def _format_us_phone_cached(phone_input: str) -> Optional[str]:
    """Cached US phone formatting for better performance."""
    if not phone_input:
        return None
    
    try:
        # Use phonenumbers library for robust parsing
        parsed = phonenumbers.parse(phone_input, "US")
        if phonenumbers.is_valid_number(parsed):
            # Format as +1 (XXX) XXX-XXXX for US display format
            formatted = phonenumbers.format_number(parsed, PhoneNumberFormat.NATIONAL)
            # Add country code for consistency
            if not formatted.startswith('+1'):
                formatted = f"+1 {formatted.strip()}"
            return formatted
    except phonenumbers.NumberParseException:
        pass
    
    # Fallback to manual parsing for edge cases
    digits_only = re.sub(r'\D', '', phone_input)
    
    if len(digits_only) == 10:
        area_code = digits_only[:3]
        exchange = digits_only[3:6]
        number = digits_only[6:]
    elif len(digits_only) == 11 and digits_only.startswith('1'):
        area_code = digits_only[1:4]
        exchange = digits_only[4:7]
        number = digits_only[7:]
    else:
        logger.debug(f"Invalid phone number length: {phone_input} -> {digits_only}")
        return None
    
    # Basic validation - area code and exchange should be 3 digits
    if len(area_code) != 3 or len(exchange) != 3:
        logger.debug(f"Invalid area code or exchange length: {phone_input}")
        return None
    
    formatted = f"+1 ({area_code}) {exchange}-{number}"
    logger.debug(f"Formatted phone: {phone_input} -> {formatted}")
    return formatted

def format_us_phone_number(phone_input: str) -> Optional[str]:
    """Format phone number to valid US phone number format: +1 (XXX) XXX-XXXX
    
    This function provides backward compatibility while using optimized caching.
    Handles various input formats and returns None for invalid numbers.
    
    Args:
        phone_input: Phone number in various formats
        
    Returns:
        Formatted phone number or None if invalid
        
    Examples:
        >>> format_us_phone_number('5551234567')
        '+1 (555) 123-4567'
        >>> format_us_phone_number('1-555-123-4567')
        '+1 (555) 123-4567'
    """
    return _format_us_phone_cached(phone_input) if phone_input else None

def extract_and_format_phone(text: str) -> Optional[str]:
    """Extract and format the first valid US phone number found in text.
    
    Uses the common_utils phone extraction for consistency and performance.
    
    Args:
        text: Text containing potential phone numbers
        
    Returns:
        First valid formatted phone number found or None
    """
    if not text:
        return None
    
    # Use the optimized phone extraction from common_utils
    phones = phone_utils.extract_phone_numbers(text)
    
    # Format and return the first valid phone found
    for phone in phones:
        formatted = format_us_phone_number(phone)
        if formatted:
            return formatted
    
    return None

def validate_and_format_us_phone(phone_input: str) -> Optional[str]:
    """Validate and format phone number as US number with enhanced validation.
    
    This function provides comprehensive US phone number validation and formatting.
    It checks for valid US area codes, proper formatting, and ensures the number
    follows US phone number standards.
    
    Args:
        phone_input: Phone number in various formats
        
    Returns:
        Formatted US phone number (+1 (XXX) XXX-XXXX) or None if invalid
        
    Examples:
        >>> validate_and_format_us_phone('5551234567')
        '+1 (555) 123-4567'
        >>> validate_and_format_us_phone('1-555-123-4567')
        '+1 (555) 123-4567'
        >>> validate_and_format_us_phone('+44 20 7946 0958')
        None  # Not a US number
    """
    if not phone_input:
        return None
    
    try:
        # Use phonenumbers library for robust US parsing and validation
        parsed = phonenumbers.parse(phone_input, "US")
        
        # Check if it's a valid US number
        if not phonenumbers.is_valid_number(parsed):
            logger.debug(f"Invalid US phone number: {phone_input}")
            return None
        
        # Check if it's actually a US number (country code 1)
        if parsed.country_code != 1:
            logger.debug(f"Not a US phone number (country code {parsed.country_code}): {phone_input}")
            return None
        
        # Format as US national format
        formatted = phonenumbers.format_number(parsed, PhoneNumberFormat.NATIONAL)
        
        # Ensure it has the +1 prefix for consistency
        if not formatted.startswith('+1'):
            formatted = f"+1 {formatted.strip()}"
        
        logger.debug(f"Validated and formatted US phone: {phone_input} -> {formatted}")
        return formatted
        
    except phonenumbers.NumberParseException as e:
        logger.debug(f"Phone number parsing failed: {phone_input} - {e}")
        return None
