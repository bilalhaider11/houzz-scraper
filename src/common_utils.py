"""
Consolidated Utility Functions for Houzz Scraper
===============================================

This module contains common utility functions used across the project to eliminate
code duplication and provide consistent functionality.

"""

import re
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from fake_useragent import UserAgent
from loguru import logger

class CommonPhoneUtils:
    """Consolidated phone number utilities"""
    
    PHONE_PATTERNS = [
        re.compile(r'(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'),
        re.compile(r'(\+1\s?)?(\d{3})[-.\s]?(\d{3})[-.\s]?(\d{4})'),
        re.compile(r'(\+1\s?)?\((\d{3})\)\s?(\d{3})[-.\s]?(\d{4})')
    ]
    
    @classmethod
    def extract_phone_numbers(cls, text: str) -> List[str]:
        """Extract phone numbers from text"""
        phones = []
        
        for pattern in cls.PHONE_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple):
                    phone = ''.join(match)
                    phone = re.sub(r'[^\d]', '', phone)
                    if len(phone) >= 10:
                        phones.append(phone)
        
        return list(set(phones))


class CommonZipcodeUtils:
    """Consolidated zipcode extraction utilities"""
    
    ZIPCODE_PATTERNS = [
        r'\b(\d{5}(?:-\d{4})?)\b',  # 5-digit or ZIP+4 format
        r'([A-Z]{2}\s+\d{5})',  # State ZIP pattern
        r'\b\d{5}\b',  # Simple 5-digit
        r'\b\d{5}-\d{4}\b',  # ZIP+4 with hyphen
        r'\b\d{5}\s+\d{4}\b'  # ZIP+4 with space
    ]
    
    @classmethod
    def extract_zipcode(cls, address: str) -> Optional[str]:
        """
        Extract zipcode from address string.
        
        Args:
            address: Address string to extract zipcode from
            
        Returns:
            Extracted zipcode if found and valid, None otherwise
        """
        if not address or not isinstance(address, str):
            return None
        
        # Clean the address string
        cleaned_address = cls._clean_address(address)
        
        # Try to find zipcode using regex patterns
        for pattern in cls.ZIPCODE_PATTERNS:
            matches = re.findall(pattern, cleaned_address)
            if matches:
                # Take the first match
                zipcode = matches[0]
                
                # Validate the zipcode
                if cls._validate_zipcode(zipcode):
                    logger.info(f"✅ Extracted valid zipcode: {zipcode} from address: {address[:100]}...")
                    return zipcode
                else:
                    logger.warning(f"❌ Invalid zipcode format: {zipcode}")
        
        logger.debug(f"No valid zipcode found in address: {address[:100]}...")
        return None
    
    @classmethod
    def _clean_address(cls, address: str) -> str:
        """
        Clean address string for better zipcode extraction.
        
        Args:
            address: Raw address string
            
        Returns:
            Cleaned address string
        """
        if not address:
            return ""
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', address.strip())
        
        # Remove common punctuation that might interfere
        cleaned = re.sub(r'[^\w\s\-]', ' ', cleaned)
        
        # Normalize spaces around hyphens (for ZIP+4 format)
        cleaned = re.sub(r'\s*-\s*', '-', cleaned)
        
        return cleaned
    
    @classmethod
    def _validate_zipcode(cls, zipcode: str) -> bool:
        """
        Validate US zipcode format.
        
        Args:
            zipcode: Zipcode string to validate
            
        Returns:
            True if valid US zipcode format, False otherwise
        """
        if not zipcode:
            return False
        
        # Remove any extra whitespace
        zipcode = zipcode.strip()
        
        # Check 5-digit format
        if re.match(r'^\d{5}$', zipcode):
            return True
        
        # Check 9-digit format (ZIP+4)
        if re.match(r'^\d{5}-\d{4}$', zipcode):
            return True
        
        # Check ZIP+4 with space
        if re.match(r'^\d{5}\s+\d{4}$', zipcode):
            return True
        
        return False


class CommonWebUtils:
    """Consolidated web scraping utilities"""
    
    def __init__(self):
        self.ua = UserAgent()
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent"""
        try:
            return self.ua.random
        except:
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


# Create global instances for easy import
phone_utils = CommonPhoneUtils()
web_utils = CommonWebUtils()
zipcode_utils = CommonZipcodeUtils()

class WebUtils(CommonWebUtils):
    """Alias for CommonWebUtils for backward compatibility"""
    pass


class StateManager:
    """Manage scraping state and progress"""
    
    def __init__(self, state_file: str = "scraping_state.json"):
        self.state_file = state_file
        self.state = self.load_state()
    
    def load_state(self) -> Dict[str, Any]:
        """Load scraping state from file"""
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except:
            return {
                'houzz_completed_states': [],
                'houzz_completed_urls': [],
                'houzz_failed_urls': [],
                'architizer_completed_states': [],
                'architizer_completed_urls': [],
                'architizer_failed_urls': [],
                'last_updated': None
            }
    
    def save_state(self):
        """Save current state to file"""
        self.state['last_updated'] = datetime.now().isoformat()
        
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def mark_url_completed(self, url: str, platform: str = "houzz"):
        """Mark a URL as completed"""
        key = f'{platform}_completed_urls'
        if key not in self.state:
            self.state[key] = []
        if url not in self.state[key]:
            self.state[key].append(url)
            self.save_state()
    
    def mark_url_failed(self, url: str, platform: str = "houzz"):
        """Mark a URL as failed"""
        key = f'{platform}_failed_urls'
        if key not in self.state:
            self.state[key] = []
        if url not in self.state[key]:
            self.state[key].append(url)
            self.save_state()
    
    def is_url_completed(self, url: str, platform: str = "houzz") -> bool:
        """Check if URL is already completed"""
        key = f'{platform}_completed_urls'
        if key not in self.state:
            self.state[key] = []
        return url in self.state[key]
