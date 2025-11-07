"""
Pre-validation filtering for emails before ZeroBounce API calls.
Saves 20-30% of ZeroBounce credits by filtering obvious bad emails using FREE checks.
"""

import re
import dns.resolver
from loguru import logger
from dataclasses import dataclass
from enum import Enum


class PreValidationStatus(Enum):
    """Pre-validation filter status"""
    PASS = "pass"  # Worth validating with ZeroBounce
    INVALID_FORMAT = "invalid_format"
    DISPOSABLE_DOMAIN = "disposable_domain"
    NO_MX_RECORDS = "no_mx_records"
    ROLE_BASED = "role_based"
    TYPO_DOMAIN = "typo_domain"
    SUSPICIOUS_PATTERN = "suspicious_pattern"


@dataclass
class PreValidationResult:
    """Result of pre-validation check"""
    email: str
    should_validate: bool
    status: PreValidationStatus
    reason: str


class EmailPreValidator:
    """
    Pre-validation filter to check emails BEFORE calling ZeroBounce API.
    All checks are FREE and fast.
    """
    
    # Common disposable email domains (FREE check, no API)
    DISPOSABLE_DOMAINS = {
        'mailinator.com', 'guerrillamail.com', 'temp-mail.org', 'throwaway.email',
        '10minutemail.com', 'tempmail.com', 'maildrop.cc', 'sharklasers.com',
        'guerrillamail.info', 'grr.la', 'guerrillamail.biz', 'guerrillamail.de',
        'spam4.me', 'trashmail.com', 'yopmail.com', 'fakeinbox.com',
        'mailnesia.com', 'mintemail.com', 'getnada.com', 'throwawaymail.com',
        'mytemp.email', 'tempinbox.com', 'emailondeck.com', 'mailcatch.com',
        'dispostable.com', 'tmpmail.org', 'mohmal.com', 'spamgourmet.com',
        'mailexpire.com', 'trashmail.ws', 'tempemail.net', 'jetable.org',
        'mailforspam.com', 'deadaddress.com', 'harakirimail.com', 'mail-temporaire.fr',
        'boun.cr', 'inbox.com', 'spambox.us', 'spamfree24.org'
    }
    
    # DANGEROUS role-based emails (filter these - likely do_not_mail/spam trap)
    DANGEROUS_ROLE_BASED = {
        'noreply', 'no-reply', 'donotreply', 'do-not-reply',
        'postmaster', 'hostmaster', 'webmaster',
        'abuse', 'spam',
        'mailer-daemon', 'bounce', 'unsubscribe', 'optout', 'opt-out',
        'notifications', 'alerts', 'automated',
        'system', 'robot', 'bot', 'daemon'
    }
    
    # Common typo domains (gmail.com -> gmial.com)
    TYPO_DOMAINS = {
        'gmial.com': 'gmail.com',
        'gmai.com': 'gmail.com',
        'gmil.com': 'gmail.com',
        'gmaill.com': 'gmail.com',
        'yahooo.com': 'yahoo.com',
        'yaho.com': 'yahoo.com',
        'hotmial.com': 'hotmail.com',
        'hotmai.com': 'hotmail.com',
        'outlok.com': 'outlook.com',
        'outloo.com': 'outlook.com',
        'iclou.com': 'icloud.com',
        'icoud.com': 'icloud.com',
    }
    
    def __init__(self):
        """Initialize pre-validator"""
        self.mx_cache = {}  # Cache MX lookups to avoid repeated DNS queries
        logger.info("✅ Email pre-validator initialized")
    
    def validate_email_format(self, email: str) -> bool:
        """
        Basic email format validation (FREE, regex-based)
        
        Returns:
            bool: True if format is valid
        """
        # RFC 5322 simplified pattern
        email_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$'
        
        if not re.match(email_pattern, email):
            return False
        
        # Additional checks
        local, domain = email.rsplit('@', 1)
        
        # Local part shouldn't be too long
        if len(local) > 64:
            return False
        
        # Domain shouldn't be too long
        if len(domain) > 255:
            return False
        
        # No consecutive dots
        if '..' in email:
            return False
        
        # No leading/trailing dots in local part
        if local.startswith('.') or local.endswith('.'):
            return False
        
        return True
    
    def is_disposable_domain(self, email: str) -> bool:
        """
        Check if email is from a disposable/temporary email service (FREE, local list)
        
        Returns:
            bool: True if disposable domain
        """
        try:
            domain = email.split('@')[1].lower()
            return domain in self.DISPOSABLE_DOMAINS
        except (IndexError, AttributeError):
            return False
    
    def is_dangerous_role_based(self, email: str) -> bool:
        """
        Check if email is a DANGEROUS role-based email (FREE, pattern matching)
        Only filters emails that are likely spam traps or will never respond
        
        Returns:
            bool: True if dangerous role-based (should filter)
        """
        try:
            local_part = email.split('@')[0].lower()
            
            # Check exact matches with dangerous prefixes
            if local_part in self.DANGEROUS_ROLE_BASED:
                return True
            
            # Check if starts with dangerous prefix
            for prefix in self.DANGEROUS_ROLE_BASED:
                if local_part.startswith(prefix):
                    return True
            
            return False
        except (IndexError, AttributeError):
            return False
    
    def has_typo_domain(self, email: str) -> bool:
        """
        Check if email has a common typo domain (FREE, local list)
        
        Returns:
            bool: True if typo domain detected
        """
        try:
            domain = email.split('@')[1].lower()
            return domain in self.TYPO_DOMAINS
        except (IndexError, AttributeError):
            return False
    
    def has_mx_records(self, email: str) -> bool:
        """
        Check if domain has MX records (FREE, DNS lookup)
        If no MX records, domain can't receive email
        
        Returns:
            bool: True if MX records exist
        """
        try:
            domain = email.split('@')[1].lower()
            
            # Check cache first
            if domain in self.mx_cache:
                return self.mx_cache[domain]
            
            # DNS lookup for MX records
            try:
                mx_records = dns.resolver.resolve(domain, 'MX')
                has_mx = len(mx_records) > 0
                
                # Cache result
                self.mx_cache[domain] = has_mx
                return has_mx
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
                # Domain doesn't exist or has no MX records
                self.mx_cache[domain] = False
                return False
            except Exception as e:
                # DNS query failed (timeout, network issue, etc.)
                # In case of error, assume it might be valid (don't filter out)
                logger.debug(f"MX lookup failed for {domain}: {e}")
                return True  # Don't filter out on errors
                
        except (IndexError, AttributeError):
            return False
    
    def has_suspicious_pattern(self, email: str) -> bool:
        """
        Check for suspicious patterns (FREE, pattern matching)
        
        Returns:
            bool: True if suspicious pattern detected
        """
        try:
            local_part = email.split('@')[0].lower()
            
            # Too many numbers (likely bot/spam)
            digit_count = sum(c.isdigit() for c in local_part)
            if len(local_part) > 0 and digit_count / len(local_part) > 0.7:
                return True
            
            # Random character strings (e.g., asdfghjkl@)
            if len(set(local_part)) < 3 and len(local_part) > 5:
                return True
            
            # Excessive special characters
            special_count = sum(c in '._+-' for c in local_part)
            if len(local_part) > 0 and special_count / len(local_part) > 0.5:
                return True
            
            return False
        except (IndexError, AttributeError):
            return False
    
    def should_validate_with_zerobounce(self, email: str) -> PreValidationResult:
        """
        Main pre-validation check. Run all FREE checks before ZeroBounce.
        
        Args:
            email: Email address to check
        
        Returns:
            PreValidationResult: Result with should_validate flag and reason
        """
        email = email.strip().lower()
        
        # Check 1: Basic format (fastest, free)
        if not self.validate_email_format(email):
            return PreValidationResult(
                email=email,
                should_validate=False,
                status=PreValidationStatus.INVALID_FORMAT,
                reason="Invalid email format"
            )
        
        # Check 2: Disposable domains (fast, free)
        if self.is_disposable_domain(email):
            return PreValidationResult(
                email=email,
                should_validate=False,
                status=PreValidationStatus.DISPOSABLE_DOMAIN,
                reason="Disposable/temporary email service"
            )
        
        # Check 3: DANGEROUS role-based emails only (fast, free)
        # Note: We keep useful business emails like support@, info@, contact@, sales@
        if self.is_dangerous_role_based(email):
            return PreValidationResult(
                email=email,
                should_validate=False,
                status=PreValidationStatus.ROLE_BASED,
                reason="Dangerous role-based email (noreply, postmaster, abuse, etc.)"
            )
        
        # Check 4: Typo domains (fast, free)
        if self.has_typo_domain(email):
            return PreValidationResult(
                email=email,
                should_validate=False,
                status=PreValidationStatus.TYPO_DOMAIN,
                reason=f"Typo domain (did you mean {self.TYPO_DOMAINS[email.split('@')[1]]}?)"
            )
        
        # Check 5: Suspicious patterns (fast, free)
        if self.has_suspicious_pattern(email):
            return PreValidationResult(
                email=email,
                should_validate=False,
                status=PreValidationStatus.SUSPICIOUS_PATTERN,
                reason="Suspicious email pattern"
            )
        
        # Check 6: MX records (slower but still free, do last)
        if not self.has_mx_records(email):
            return PreValidationResult(
                email=email,
                should_validate=False,
                status=PreValidationStatus.NO_MX_RECORDS,
                reason="Domain has no MX records (can't receive email)"
            )
        
        # All checks passed - worth validating with ZeroBounce
        return PreValidationResult(
            email=email,
            should_validate=True,
            status=PreValidationStatus.PASS,
            reason="Passed all pre-validation checks"
        )
    

