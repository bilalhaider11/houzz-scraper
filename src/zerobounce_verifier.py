"""ZeroBounce Email Verification Module.

Provides ZeroBounce API integration for advanced email validation.
Used specifically in the export phase for final email verification.
"""

import asyncio
import aiohttp
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger
from config.config import config
from .database_manager import DatabaseManager


class ZeroBounceStatus(Enum):
    """ZeroBounce verification status enumeration"""
    VALID = "valid"
    INVALID = "invalid"
    CATCH_ALL = "catch-all"
    UNKNOWN = "unknown"
    SPAMTRAP = "spamtrap"
    ABUSE = "abuse"
    DISPOSABLE = "disposable"
    UNKNOWN_DOMAIN = "unknown_domain"


@dataclass(frozen=True)
class ZeroBounceResult:
    """ZeroBounce verification result"""
    email: str
    status: ZeroBounceStatus
    sub_status: str = ""
    confidence_score: float = 0.0
    mx_valid: bool = False
    smtp_server: str = ""
    smtp_check: bool = False
    catch_all: bool = False
    disposable: bool = False
    toxic: bool = False
    firstname: str = ""
    lastname: str = ""
    gender: str = ""
    country: str = ""
    region: str = ""
    city: str = ""
    zipcode: str = ""
    processed_at: str = ""


class ZeroBounceVerifier:
    """ZeroBounce API integration for advanced email verification"""
    
    def __init__(self):
        self.api_key = config.ZEROBOUNCE_API_KEY
        self.base_url = "https://api.zerobounce.net/v2"
        self.session = None
        
        if not self.api_key:
            logger.warning("⚠️ ZeroBounce API key not found. ZeroBounce verification will be disabled.")
            self.enabled = False
        else:
            logger.info("✅ ZeroBounce API key found. ZeroBounce verification enabled.")
            self.enabled = True
    
    async def __aenter__(self):
        """Async context manager entry"""
        if self.enabled:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={'User-Agent': 'HouzzScraper/1.0'}
            )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def verify_single_email(self, email: str) -> ZeroBounceResult:
        """Verify a single email using ZeroBounce API"""
        if not self.enabled or not self.api_key:
            return ZeroBounceResult(
                email=email,
                status=ZeroBounceStatus.UNKNOWN,
                sub_status="zerobounce_disabled"
            )
        
        try:
            url = f"{self.base_url}/validate"
            params = {
                'api_key': self.api_key,
                'email': email,
                'ip_address': ''  # Optional IP address
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"ZeroBounce API error: {response.status} - {error_text}")
                    return ZeroBounceResult(
                        email=email,
                        status=ZeroBounceStatus.UNKNOWN,
                        sub_status=f"api_error_{response.status}"
                    )
                
                data = await response.json()
                
                # Check for API error responses
                if 'error' in data:
                    logger.error(f"ZeroBounce API returned error: {data['error']}")
                    return ZeroBounceResult(
                        email=email,
                        status=ZeroBounceStatus.UNKNOWN,
                        sub_status=f"api_error: {data['error']}"
                    )
                
                # Parse ZeroBounce response
                status_str = data.get('status', 'unknown')
                sub_status = data.get('sub_status', '')
                
                # Map ZeroBounce status to our enum
                status_mapping = {
                    'valid': ZeroBounceStatus.VALID,
                    'invalid': ZeroBounceStatus.INVALID,
                    'catch-all': ZeroBounceStatus.CATCH_ALL,
                    'unknown': ZeroBounceStatus.UNKNOWN,
                    'spamtrap': ZeroBounceStatus.SPAMTRAP,
                    'abuse': ZeroBounceStatus.ABUSE,
                    'disposable': ZeroBounceStatus.DISPOSABLE,
                    'unknown_domain': ZeroBounceStatus.UNKNOWN_DOMAIN
                }
                
                status = status_mapping.get(status_str, ZeroBounceStatus.UNKNOWN)
                
                # Calculate confidence score
                confidence_score = 0.0
                if status == ZeroBounceStatus.VALID:
                    confidence_score = 0.95
                elif status == ZeroBounceStatus.CATCH_ALL:
                    confidence_score = 0.7
                elif status == ZeroBounceStatus.UNKNOWN:
                    confidence_score = 0.5
                elif status == ZeroBounceStatus.DISPOSABLE:
                    confidence_score = 0.1
                else:
                    confidence_score = 0.0
                
                return ZeroBounceResult(
                    email=email,
                    status=status,
                    sub_status=sub_status,
                    confidence_score=confidence_score,
                    mx_valid=data.get('mx_record', False),
                    smtp_server=data.get('smtp_server', ''),
                    smtp_check=data.get('smtp_check', False),
                    catch_all=data.get('catch_all', False),
                    disposable=data.get('disposable', False),
                    toxic=data.get('toxic', False),
                    firstname=data.get('firstname', ''),
                    lastname=data.get('lastname', ''),
                    gender=data.get('gender', ''),
                    country=data.get('country', ''),
                    region=data.get('region', ''),
                    city=data.get('city', ''),
                    zipcode=data.get('zipcode', ''),
                    processed_at=data.get('processed_at', '')
                )
                
        except Exception as e:
            logger.error(f"Error verifying email {email} with ZeroBounce: {e}")
            return ZeroBounceResult(
                email=email,
                status=ZeroBounceStatus.UNKNOWN,
                sub_status=f"error: {str(e)}"
            )
    
    async def verify_email_batch(self, emails: List[str], batch_size: int = 100) -> List[ZeroBounceResult]:
        """Verify a batch of emails with rate limiting"""
        if not self.enabled:
            logger.warning("ZeroBounce is disabled, returning empty results")
            return []
        
        results = []
        total_emails = len(emails)
        
        logger.info(f"🔍 Starting ZeroBounce verification of {total_emails} emails")
        
        for i in range(0, total_emails, batch_size):
            batch = emails[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_emails + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} emails)")
            
            # Process batch concurrently
            tasks = [self.verify_single_email(email) for email in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error in batch verification: {result}")
                    results.append(ZeroBounceResult(
                        email=batch[j],
                        status=ZeroBounceStatus.UNKNOWN,
                        sub_status=f"batch_error: {str(result)}"
                    ))
                else:
                    results.append(result)
            
            # Rate limiting - ZeroBounce allows 100 requests per day for free tier
            if batch_num < total_batches:
                await asyncio.sleep(1)  # 1 second delay between batches
        
        # Log summary
        status_counts = {}
        for result in results:
            status = result.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        logger.info(f"📊 ZeroBounce verification summary:")
        for status, count in status_counts.items():
            logger.info(f"   {status.upper()}: {count}")
        
        return results
    
    def filter_valid_emails(self, results: List[ZeroBounceResult]) -> List[str]:
        """Filter results to only include valid emails"""
        valid_emails = []
        total_emails = len(results)
        
        for result in results:
            if result.status == ZeroBounceStatus.VALID:
                valid_emails.append(result.email)
                logger.info(f"✅ Email {result.email} is VALID - including in results")
            else:
                logger.info(f"❌ Email {result.email} is {result.status.value.upper()} - excluding from results")
            # Only VALID status emails are considered valid
            # Catch-all, unknown, invalid, disposable, etc. are all excluded
        
        logger.info(f"📊 Email filtering summary: {len(valid_emails)}/{total_emails} emails are VALID")
        return valid_emails
    
    async def test_api_connection(self) -> bool:
        """Test ZeroBounce API connection by checking credits"""
        if not self.enabled or not self.api_key:
            logger.warning("ZeroBounce is disabled, cannot test connection")
            return False
        
        try:
            credits = await self.get_credits_remaining()
            if credits is not None:
                logger.info(f"✅ ZeroBounce API connection successful. Credits remaining: {credits}")
                return True
            else:
                logger.error("❌ ZeroBounce API connection failed")
                return False
        except Exception as e:
            logger.error(f"❌ ZeroBounce API connection test failed: {e}")
            return False

    async def get_credits_remaining(self) -> Optional[int]:
        """Get remaining ZeroBounce API credits"""
        if not self.enabled or not self.api_key:
            return None
        
        try:
            url = f"{self.base_url}/getcredits"
            params = {'api_key': self.api_key}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    credits = data.get('Credits', 0)
                    logger.info(f"ZeroBounce credits remaining: {credits}")
                    return credits
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get ZeroBounce credits: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting ZeroBounce credits: {e}")
            return None

    async def verify_database_emails(self, db_manager: DatabaseManager, platform: str = "houzz") -> None:
        """Verify emails in database using ZeroBounce API and update database."""
        logger.info(f"Starting ZeroBounce email verification for database profiles (platform: {platform})")
        
        # Check ZeroBounce API connection first
        if not await self.test_api_connection():
            logger.error("❌ ZeroBounce API connection failed. Skipping email verification.")
            return
        
        total_profiles = db_manager.get_total_profiles_for_email_verification(platform)
        logger.info(f"Total profiles available for ZeroBounce verification: {total_profiles}")
        
        if total_profiles == 0:
            logger.info("No profiles found that need email verification")
            return
            
        batch_size = 50  # Smaller batch size for ZeroBounce API limits
        total_verified = 0
        total_processed = 0
        verified_emails_cache = {}  # Cache to avoid duplicate ZeroBounce requests

        async def verify_email_list(emails: List[str]) -> List[str]:
            """Helper function to verify a list of emails with ZeroBounce"""
            if not emails:
                return []
            
            # Filter out already cached emails
            uncached_emails = [email for email in emails if email not in verified_emails_cache]
            
            if not uncached_emails:
                # All emails are cached, return valid ones
                return [email for email in emails if verified_emails_cache.get(email) == 'valid']
            
            logger.info(f"📧 Verifying {len(uncached_emails)} emails with ZeroBounce...")
            
            # Verify uncached emails with ZeroBounce
            results = await self.verify_email_batch(uncached_emails, batch_size=50)
            
            # Cache results
            for result in results:
                verified_emails_cache[result.email] = result.status.value
            
            # Use the filter_valid_emails method for consistency
            valid_emails = self.filter_valid_emails(results)
            
            # Return valid emails from the original list
            return [email for email in emails if email in valid_emails or verified_emails_cache.get(email) == 'valid']

        for offset in range(0, total_profiles, batch_size):
            profiles_to_verify = db_manager.get_profiles_for_email_verification(platform, limit=batch_size, offset=offset)
            logger.info(f"Processing verification batch starting at offset {offset} ({len(profiles_to_verify)} profiles)")

            for profile in profiles_to_verify:
                profile_id = profile['id']
                profile_name = profile['name']
                
                # Parse email data with error handling
                try:
                    email_data = json.loads(profile['emails'])
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Failed to parse email data for {profile_name} (ID: {profile_id}): {e}")
                    logger.error(f"Raw email data: {profile['emails']}")
                    total_processed += 1
                    continue
                
                logger.info(f"Processing profile: {profile_name} (ID: {profile_id})")
                
                # Verify personal emails first
                verified_personal = await verify_email_list(email_data.get('personal', []))
                
                # Only verify business emails if no personal emails verified
                verified_business = []
                if not verified_personal:
                    logger.info("No valid personal emails found, checking business emails")
                    verified_business = await verify_email_list(email_data.get('business', []))
                else:
                    logger.info("Valid personal emails found, keeping business emails as-is")
                    verified_business = email_data.get('business', [])

                # Only update database if we have verified emails
                if verified_personal or verified_business:
                    updated_email_data = {
                        'personal': verified_personal,
                        'business': verified_business
                    }
                    logger.info(f"✅ Updating {profile_name} with ZeroBounce verified emails - Personal: {verified_personal}, Business: {verified_business}")
                    db_manager.update_profile_emails_json(profile_id, updated_email_data)
                    total_verified += 1
                    # Only mark as email verified if we have valid emails
                    db_manager.mark_email_verified(profile_id)
                else:
                    logger.info(f"❌ No valid emails found for {profile_name} - not updating database")
                    # Don't mark as email verified if no valid emails found
                
                total_processed += 1
                
                await asyncio.sleep(0.5)  # Rate limit delay

        success_rate = (total_verified/total_processed)*100 if total_processed > 0 else 0
        logger.info(f"\n=== ZEROBOUNCE VERIFICATION SUMMARY ===")
        logger.info(f"Total profiles processed: {total_processed}")
        logger.info(f"Profiles with verified emails: {total_verified}")
        logger.info(f"Verification success rate: {success_rate:.1f}%")
        logger.info(f"Unique emails processed: {len(verified_emails_cache)}") 