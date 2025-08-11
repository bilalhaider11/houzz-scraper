"""Centralized Email Validation Service.

This module provides a unified email validation service to eliminate code duplication
across multiple modules and ensure consistent email validation behavior.
"""

import re
import dns.resolver
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from loguru import logger
from email_validator import validate_email, EmailNotValidError

from config.config import config


class EmailValidationStatus(Enum):
    """Email validation status enumeration"""
    VALID = "valid"
    INVALID = "invalid"
    DISPOSABLE = "disposable"
    NO_MX_RECORD = "no_mx_record"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EmailValidationResult:
    """Immutable email validation result"""
    email: str
    status: EmailValidationStatus
    sub_status: str = ""
    method: str = "basic_validation"
    normalized_email: Optional[str] = None
    domain: str = ""
    mx_valid: bool = False
    is_disposable: bool = False
    confidence_score: float = 0.0
    
    def __post_init__(self):
        """Post-initialization to set derived fields"""
        if self.email and '@' in self.email:
            domain = self.email.split('@')[1].lower()
            object.__setattr__(self, 'domain', domain)
            object.__setattr__(self, 'normalized_email', self.normalized_email or self.email.lower().strip())
            
            # Calculate confidence score based on validation results
            score = 0.0
            if self.status == EmailValidationStatus.VALID:
                score = 0.9 if self.mx_valid else 0.7
            elif self.status == EmailValidationStatus.DISPOSABLE:
                score = 0.1
            elif self.status == EmailValidationStatus.NO_MX_RECORD:
                score = 0.3
            
            object.__setattr__(self, 'confidence_score', score)


@dataclass(frozen=True)
class EmailServiceConfig:
    """Configuration for email validation service"""
    check_mx_records: bool = True
    timeout: int = 10
    disposable_domains: Set[str] = field(default_factory=lambda: {
        '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 
        'tempmail.org', 'yopmail.com', 'temp-mail.org', 'sharklasers.com',
        'throwaway.email', 'getnada.com', 'trashmail.com', 'maildrop.cc',
        'guerrillamailblock.com', 'spam4.me', 'tempinbox.com', 'sentry.wixpress.com',
        'domain.com'
    })


class EmailValidationService:
    """Centralized email validation service with caching and comprehensive validation"""
    
    def __init__(self, config: Optional[EmailServiceConfig] = None):
        self.config = config or EmailServiceConfig()
        logger.info("✅ Email validation service initialized")
    
    @lru_cache(maxsize=1000)
    def _check_mx_record(self, domain: str) -> bool:
        """Check if domain has MX record with caching"""
        if not self.config.check_mx_records:
            return True
        
        try:
            dns.resolver.resolve(domain, 'MX')
            return True
        except Exception as e:
            logger.debug(f"MX record check failed for {domain}: {e}")
            return False
    
    @lru_cache(maxsize=500)
    def _is_disposable_domain(self, domain: str) -> bool:
        """Check if domain is disposable with caching"""
        return domain.lower() in self.config.disposable_domains
    
    def _validate_email_format(self, email: str) -> Optional[EmailValidationResult]:
        """Validate email format using email-validator library"""
        if not email or not isinstance(email, str):
            return EmailValidationResult(
                email=email or "",
                status=EmailValidationStatus.INVALID,
                sub_status="empty_or_invalid_type"
            )
        
        try:
            # Use email-validator for comprehensive format validation
            valid = validate_email(email, check_deliverability=False)
            normalized_email = valid.email
            
            # Extract domain for further validation
            domain = normalized_email.split('@')[1].lower()
            
            # Check if it's a disposable domain
            is_disposable = self._is_disposable_domain(domain)
            
            if is_disposable:
                return EmailValidationResult(
                    email=email,
                    status=EmailValidationStatus.DISPOSABLE,
                    sub_status="disposable_domain",
                    normalized_email=normalized_email,
                    domain=domain,
                    is_disposable=True,
                    confidence_score=0.1
                )
            
            # Check MX records
            mx_valid = self._check_mx_record(domain)
            
            if not mx_valid:
                return EmailValidationResult(
                    email=email,
                    status=EmailValidationStatus.NO_MX_RECORD,
                    sub_status="no_mx_record",
                    normalized_email=normalized_email,
                    domain=domain,
                    mx_valid=False,
                    confidence_score=0.3
                )
            
            return EmailValidationResult(
                email=email,
                status=EmailValidationStatus.VALID,
                sub_status="valid_format_and_mx",
                normalized_email=normalized_email,
                domain=domain,
                mx_valid=True,
                confidence_score=0.9
            )
            
        except EmailNotValidError as e:
            return EmailValidationResult(
                email=email,
                status=EmailValidationStatus.INVALID,
                sub_status=str(e),
                confidence_score=0.0
            )
        except Exception as e:
            logger.error(f"Unexpected error validating email {email}: {e}")
            return EmailValidationResult(
                email=email,
                status=EmailValidationStatus.UNKNOWN,
                sub_status="validation_error",
                confidence_score=0.0
            )
    
    def validate_email(self, email: str) -> EmailValidationResult:
        """Validate a single email address"""
        return self._validate_email_format(email)
    
    def validate_multiple_emails(self, emails: List[str]) -> List[EmailValidationResult]:
        """Validate multiple email addresses"""
        results = []
        for email in emails:
            if email and isinstance(email, str):
                result = self.validate_email(email.strip())
                results.append(result)
        return results
    
    def filter_valid_emails(self, emails: List[str]) -> List[str]:
        """Filter and return only valid email addresses"""
        valid_emails = []
        for email in emails:
            if email and isinstance(email, str):
                result = self.validate_email(email.strip())
                if result.status == EmailValidationStatus.VALID:
                    valid_emails.append(result.normalized_email or email)
        return valid_emails
    
    def classify_emails(self, emails: List[str]) -> Dict[str, List[str]]:
        """Classify emails into personal and business categories"""
        personal_emails = []
        business_emails = []
        
        for email in emails:
            if not email or not isinstance(email, str):
                continue
                
            result = self.validate_email(email.strip())
            if result.status != EmailValidationStatus.VALID:
                continue
            
            # Simple classification based on domain patterns
            domain = result.domain.lower()
            
            # Personal email providers
            personal_domains = {
                'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
                'icloud.com', 'aol.com', 'live.com', 'msn.com',
                'protonmail.com', 'tutanota.com', 'mail.com'
            }
            
            if domain in personal_domains:
                personal_emails.append(result.normalized_email or email)
            else:
                business_emails.append(result.normalized_email or email)
        
        return {
            "personal": personal_emails,
            "business": business_emails
        }
    
    def extract_emails_from_text(self, text: str) -> List[str]:
        """Extract email addresses from text using regex"""
        if not text:
            return []
        
        # Comprehensive email regex pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        
        # Validate and return only valid emails
        return self.filter_valid_emails(emails)
    
    def get_validation_stats(self, results: List[EmailValidationResult]) -> Dict[str, int]:
        """Get statistics from validation results"""
        stats = {
            'total': len(results),
            'valid': 0,
            'invalid': 0,
            'disposable': 0,
            'no_mx_record': 0,
            'unknown': 0
        }
        
        for result in results:
            if result.status == EmailValidationStatus.VALID:
                stats['valid'] += 1
            elif result.status == EmailValidationStatus.INVALID:
                stats['invalid'] += 1
            elif result.status == EmailValidationStatus.DISPOSABLE:
                stats['disposable'] += 1
            elif result.status == EmailValidationStatus.NO_MX_RECORD:
                stats['no_mx_record'] += 1
            elif result.status == EmailValidationStatus.UNKNOWN:
                stats['unknown'] += 1
        
        return stats


# Global instance for use across modules
email_service = EmailValidationService() 