"""Website Scraper Module for the Houzz Lead Generation Pipeline.

Optimized web scraping with better structure, performance, and error handling.
Leverages Playwright for dynamic content extraction and advanced email scraping.
"""

import asyncio
import re
from typing import List, Dict, Tuple, Set, Optional
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from loguru import logger
import random
from dotenv import load_dotenv

from .email_service import email_service, EmailValidationStatus
from .phone_formatter import validate_and_format_us_phone
from config.config import config

# Load environment variables
load_dotenv()

class PersonalEmailExtractor:
    """Advanced email extractor that scrapes and validates emails from websites with business/personal separation using Playwright"""
    
    def __init__(self, max_concurrent_requests: int = 3):
        self.max_concurrent_requests = max_concurrent_requests
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.playwright = None
        self.browser = None
        
        # Use centralized email service for validation and classification
        self.email_service = email_service
        
        # Contact page patterns
        self.contact_patterns = [
            '/contact', '/contact-us', '/contact.html', '/contact.php',
            '/about', '/about-us', '/about.html', '/team'
        ]
    
    async def __aenter__(self):
        """Async context manager entry - initialize Playwright"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=config.HEADLESS,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup Playwright"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def extract_emails_from_website_async(self, website_url: str, platform: str = "houzz", existing_phone: Optional[str] = None) -> Dict[str, any]:
        """Extract emails and social links from a website and classify into personal and business (async version)"""
        logger.info(f"Extracting emails and social links from: {website_url}")
        
        if not website_url or not website_url.startswith(('http://', 'https://')):
            logger.warning(f"Invalid website URL: {website_url}")
            return {"personal": [], "business": [], "phone": None, "social_links": {}}
        
        all_emails = set()
        all_phones = set()
        all_social_links = {
            'linkedin': [],
            'facebook': [],
            'instagram': [],
            'twitter': [],
            'pinterest': [],
            'youtube': [],
            'other': []
        }
        pages_to_check = [website_url]

        # Add contact pages
        base_url = f"{urlparse(website_url).scheme}://{urlparse(website_url).netloc}"
        for pattern in self.contact_patterns:
            pages_to_check.append(urljoin(base_url, pattern))
        
        logger.info(f"📄 Found {len(pages_to_check)} pages to check")
        logger.info(f"🌐 Base URL: {base_url}")
        
        # Skip pre-filtering - let the main scraper handle all pages with its robust retry logic
        logger.info(f"🚀 Ready to scrape all {len(pages_to_check)} pages: {pages_to_check[:5]}{'...' if len(pages_to_check) > 5 else ''}")

        # Process all pages - try one phase first, then two phases if needed
        max_concurrent_per_phase = 20  # Increased from 10 to handle more pages
        
        if len(pages_to_check) <= max_concurrent_per_phase:
            # Single phase - process all pages at once
            logger.info(f"🔄 Processing all {len(pages_to_check)} pages in single phase")
            all_emails, all_phones, pages_scraped, all_social_links = await self._process_pages_single_phase(pages_to_check, max_concurrent_per_phase, platform, existing_phone)
        else:
            # Two-phase approach for large numbers of pages
            logger.info(f"🔄 Processing {len(pages_to_check)} pages in two phases (max {max_concurrent_per_phase} per phase)")
            all_emails, all_phones, pages_scraped, all_social_links = await self._process_pages_two_phases(pages_to_check, max_concurrent_per_phase, platform, existing_phone)

        # Log scraped emails before validation
        if all_emails:
            logger.info(f"📧 Scraped {len(all_emails)} raw emails from {pages_scraped} pages: {list(all_emails)[:5]}{'...' if len(all_emails) > 5 else ''}")
            logger.debug(f"All scraped emails: {list(all_emails)}")
        else:
            logger.info(f"📧 No emails found on website after checking {pages_scraped} pages")
        
        # Log scraped phones
        if all_phones:
            logger.info(f"📞 Scraped {len(all_phones)} raw phone numbers from {pages_scraped} pages: {list(all_phones)[:5]}{'...' if len(all_phones) > 5 else ''}")
            logger.debug(f"All scraped phones: {list(all_phones)}")
        else:
            logger.info(f"📞 No phone numbers found on website after checking {pages_scraped} pages")
        
        # Validate and classify emails using centralized email service (BASIC VALIDATION ONLY - NO ZEROBOUNCE)
        logger.info("🔍 Starting basic email validation (ZeroBounce disabled)")
        validated_emails = [email for email in all_emails if self.email_service.validate_email(email).status == EmailValidationStatus.VALID]
        
        classified_emails = self.email_service.classify_emails(validated_emails)
        
        # Validate and format phone numbers
        validated_phone = None
        if all_phones:
            logger.info("🔍 Starting phone number validation and formatting")
            for phone in all_phones:
                formatted_phone = validate_and_format_us_phone(phone)
                if formatted_phone:
                    validated_phone = formatted_phone
                    logger.info(f"✅ Valid US phone formatted: {phone} -> {formatted_phone}")
                    break
            if not validated_phone:
                logger.warning(f"❌ No valid US phone numbers found among: {list(all_phones)}")
        
        # Log validation results
        if validated_emails:
            logger.info(f"✅ {len(validated_emails)} emails passed basic validation (no ZeroBounce): {validated_emails[:3]}{'...' if len(validated_emails) > 3 else ''}")
        else:
            logger.info("❌ No emails passed basic validation")
        
        result = classified_emails
        result["phone"] = validated_phone
        result["social_links"] = all_social_links
        return result

    async def _process_pages_single_phase(self, pages_to_check: List[str], max_concurrent: int, platform: str, existing_phone: Optional[str]) -> Tuple[Set[str], Set[str], int, Dict[str, List[str]]]:
        """Process all pages in a single phase"""
        all_emails = set()
        all_phones = set()
        all_social_links = {
            'linkedin': [],
            'facebook': [],
            'instagram': [],
            'twitter': [],
            'pinterest': [],
            'youtube': [],
            'other': []
        }
        pages_scraped = 0
        
        # Process pages concurrently with rate limiting
        tasks = []
        async with asyncio.Semaphore(max_concurrent):  # Limit concurrent requests
            for page_url in pages_to_check:
                task = self._extract_emails_and_phones_from_page_async(page_url, platform, existing_phone)
                tasks.append(task)
        
        # Wait for all tasks to complete
        page_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect emails and phones from all pages
        for i, result in enumerate(page_results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to extract from {pages_to_check[i]}: {result}")
                continue
            elif result:
                emails, phones, social_links = result
                all_emails.update(emails)
                all_phones.update(phones)
                for platform_key, links in social_links.items():
                    all_social_links[platform_key].extend(links)
                pages_scraped += 1
        
        return all_emails, all_phones, pages_scraped, all_social_links

    async def _process_pages_two_phases(self, pages_to_check: List[str], max_concurrent_per_phase: int, platform: str, existing_phone: Optional[str]) -> Tuple[Set[str], Set[str], int, Dict[str, List[str]]]:
        """Process pages in two phases to handle large numbers of pages"""
        all_emails = set()
        all_phones = set()
        all_social_links = {
            'linkedin': [],
            'facebook': [],
            'instagram': [],
            'twitter': [],
            'pinterest': [],
            'youtube': [],
            'other': []
        }
        total_pages_scraped = 0
        
        # Split pages into two phases
        mid_point = len(pages_to_check) // 2
        phase1_pages = pages_to_check[:mid_point]
        phase2_pages = pages_to_check[mid_point:]
        
        logger.info(f"📊 Phase 1: {len(phase1_pages)} pages, Phase 2: {len(phase2_pages)} pages")
        
        # Phase 1
        logger.info("🔄 Starting Phase 1...")
        phase1_emails, phase1_phones, phase1_scraped, phase1_social_links = await self._process_pages_single_phase(phase1_pages, max_concurrent_per_phase, platform, existing_phone)
        all_emails.update(phase1_emails)
        all_phones.update(phase1_phones)
        total_pages_scraped += phase1_scraped
        # Merge social links from phase 1
        for platform_key, links in phase1_social_links.items():
            all_social_links[platform_key].extend(links)
        logger.info(f"✅ Phase 1 complete: {phase1_scraped} pages scraped, {len(phase1_emails)} emails found, {len(phase1_phones)} phones found")
        
        # Small delay between phases
        await asyncio.sleep(2)
        
        # Phase 2
        logger.info("🔄 Starting Phase 2...")
        phase2_emails, phase2_phones, phase2_scraped, phase2_social_links = await self._process_pages_single_phase(phase2_pages, max_concurrent_per_phase, platform, existing_phone)
        all_emails.update(phase2_emails)
        all_phones.update(phase2_phones)
        total_pages_scraped += phase2_scraped
        # Merge social links from phase 2
        for platform_key, links in phase2_social_links.items():
            all_social_links[platform_key].extend(links)
        logger.info(f"✅ Phase 2 complete: {phase2_scraped} pages scraped, {len(phase2_emails)} emails found, {len(phase2_phones)} phones found")
        
        # Remove duplicates from social links
        for platform_key in all_social_links:
            all_social_links[platform_key] = list(set(all_social_links[platform_key]))
        
        logger.info(f"🎯 Total: {total_pages_scraped} pages scraped, {len(all_emails)} unique emails found, {len(all_phones)} unique phones found, {sum(len(links) for links in all_social_links.values())} social links found")
        
        return all_emails, all_phones, total_pages_scraped, all_social_links

    async def _extract_emails_and_phones_from_page_async(self, url: str, platform: str, existing_phone: Optional[str], max_retries: int = 3) -> Tuple[Set[str], Set[str], Dict[str, List[str]]]:
        """Extract emails, phones, and social links from a single page using Playwright with robust retry logic"""
        async with self.semaphore:  # Rate limiting
            emails = set()
            phones = set()
            social_links = {
                'linkedin': [],
                'facebook': [],
                'instagram': [],
                'twitter': [],
                'pinterest': [],
                'youtube': [],
                'other': []
            }
            last_exception = None
            
            for attempt in range(max_retries):
                page = None
                context = None
                
                try:
                    if attempt > 0:
                        logger.info(f"🔄 Retry attempt {attempt + 1}/{max_retries} for: {url}")
                        # Exponential backoff with jitter
                        delay = (2 ** attempt) + random.uniform(1, 3)
                        await asyncio.sleep(delay)
                    
                    # Create new context and page for each attempt with improved settings
                    context = await self.browser.new_context(
                        user_agent=random.choice([
                            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        ]),
                        viewport={
                            "width": random.randint(1200, 1920),
                            "height": random.randint(800, 1080)
                        }
                    )
                    
                    page = await context.new_page()
                    
                    # Set headers to appear more like a real browser
                    await page.set_extra_http_headers({
                        'Accept': 'application/json, text/plain, */*',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                    })
                    
                    # Try different wait strategies based on attempt
                    wait_strategies = ['networkidle', 'domcontentloaded', 'load']
                    wait_until = wait_strategies[min(attempt, len(wait_strategies) - 1)]
                    
                    # Progressive timeout reduction for faster failure detection
                    timeout = max(15000 - (attempt * 5000), 10000)  # 15s, 10s, 10s
                    
                    # Navigate to the page with adaptive timeout and wait strategy
                    await page.goto(url, wait_until=wait_until, timeout=timeout)
                    
                    # Wait for dynamic content to load (reduced on retries)
                    content_wait = max(2 - attempt * 0.5, 0.5)
                    await asyncio.sleep(random.uniform(content_wait, content_wait + 1))
                    
                    # Get page content
                    content = await page.content()
                    
                    # Check if we got meaningful content - if too small, skip without retry
                    if len(content) < 100:  # Very small page, might be an error page
                        logger.debug(f"⏭️ Skipping {url} - content too small ({len(content)} chars)")
                        break  # Skip without retry - no point retrying empty pages
                    
                    # Extract from raw HTML
                    emails.update(self._regex_extract_emails(content))
                    
                    # Extract phones if platform is Architizer and no existing phone
                    if platform == "architizer" and not existing_phone:
                        phones.update(self._regex_extract_phones(content))
                    
                    # Extract from parsed HTML
                    soup = BeautifulSoup(content, 'html.parser')
                    emails.update(self._soup_extract_emails(soup))
                    
                    # Extract phones from parsed HTML if platform is Architizer and no existing phone
                    if platform == "architizer" and not existing_phone:
                        phones.update(self._soup_extract_phones(soup))
                    
                    # Extract social links from the page
                    page_social_links = self._extract_social_links(soup, url)
                    for platform_key, links in page_social_links.items():
                        for link in links:
                            if link not in social_links[platform_key]:
                                social_links[platform_key].append(link)
                    
                    # Success! Log and break retry loop
                    if attempt > 0:
                        logger.info(f"✅ Successfully scraped {url} on attempt {attempt + 1}")
                    else:
                        logger.debug(f"✅ Successfully scraped {url}")
                    
                    break  # Exit retry loop on success
                    
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()
                    
                    # Log different types of errors appropriately and determine retry strategy
                    should_retry = True  # Default to retry unless explicitly set to False
                    
                    if 'timeout' in error_str:
                        logger.warning(f"⏱️ Timeout for {url} (attempt {attempt + 1}/{max_retries}): {e}")
                        # Timeout errors should be retried - might be temporary network issue
                        should_retry = True
                    elif 'net::err_network_changed' in error_str:
                        logger.warning(f"🌐 Network changed error for {url} (attempt {attempt + 1}/{max_retries}): {e}")
                        # Network change errors should be retried - network might stabilize
                        should_retry = True
                    elif 'connection' in error_str and 'reset' in error_str:
                        logger.warning(f"🔌 Connection reset for {url} (attempt {attempt + 1}/{max_retries}): {e}")
                        # Connection reset errors should be retried - might be temporary
                        should_retry = True
                    elif 'net::err_name_not_resolved' in error_str or 'dns' in error_str:
                        logger.warning(f"🔍 DNS/Resolution error for {url}: {e}")
                        should_retry = False  # Don't retry DNS errors - domain issue won't resolve
                    elif 'net::err_connection_refused' in error_str:
                        logger.warning(f"🚫 Connection refused for {url}: {e}")
                        should_retry = False  # Don't retry connection refused - server not accepting connections
                    elif 'net::err_connection_timed_out' in error_str:
                        logger.warning(f"⏰ Connection timed out for {url} (attempt {attempt + 1}/{max_retries}): {e}")
                        # Connection timeout should be retried - might be temporary slowness
                        should_retry = True
                    elif 'ssl' in error_str or 'certificate' in error_str or 'cert' in error_str:
                        # For certificate errors, try fallback to HTTP if HTTPS failed
                        if url.startswith('https://') and attempt == 0:
                            http_url = url.replace('https://', 'http://')
                            logger.warning(f"🔒 SSL/Certificate error for {url}: {e}")
                            logger.info(f"🔄 Attempting HTTP fallback: {http_url}")
                            try:
                                # Try HTTP version on next iteration
                                url = http_url
                                continue
                            except Exception:
                                pass
                        else:
                            logger.warning(f"🔒 SSL/Certificate error for {url}: {e}")
                            should_retry = False  # Don't retry SSL/Certificate errors after HTTP attempt
                    elif 'net::err_invalid_response' in error_str:
                        logger.warning(f"📄 Invalid response error for {url}: {e}")
                        should_retry = False  # Don't retry invalid response errors - server issue
                    elif 'net::err_http_response_code_failure' in error_str:
                        logger.warning(f"🚨 HTTP response code failure for {url}: {e}")
                        should_retry = False  # Don't retry HTTP error codes (4xx/5xx) - server issue
                    elif 'protocol error' in error_str and 'navigate' in error_str:
                        logger.warning(f"🌐 Protocol/Navigation error for {url}: {e}")
                        should_retry = False  # Don't retry protocol errors - invalid URL format
                    elif 'net::err_too_many_redirects' in error_str:
                        logger.warning(f"🔄 Too many redirects error for {url}: {e}")
                        should_retry = False  # Don't retry redirect loops - server configuration issue
                    elif 'net::err_blocked_by_client' in error_str:
                        logger.warning(f"🛡️ Blocked by client for {url}: {e}")
                        should_retry = False  # Don't retry blocked requests - security/policy issue
                    elif 'net::err_aborted' in error_str:
                        logger.warning(f"⏹️ Request aborted for {url} (attempt {attempt + 1}/{max_retries}): {e}")
                        # Aborted requests might be retryable - could be network instability
                        should_retry = True
                    else:
                        logger.warning(f"❌ Unknown error scraping {url} (attempt {attempt + 1}/{max_retries}): {e}")
                        # Unknown errors default to retry to be safe
                        should_retry = True
                    
                    # Break out of retry loop if we shouldn't retry
                    if not should_retry:
                        logger.info(f"⏭️ Skipping retries for {url} due to non-retryable error type")
                        break
                    
                    # Don't retry on final attempt
                    if attempt == max_retries - 1:
                        logger.error(f"🚫 Final attempt failed for {url}: {e}")
                        
                finally:
                    # Cleanup resources
                    if page:
                        try:
                            await page.close()
                        except:
                            pass
                    if context:
                        try:
                            await context.close()
                        except:
                            pass
            
            # Log final result
            if emails or phones or any(social_links.values()):
                logger.debug(f"📧 Found {len(emails)} emails, {len(phones)} phones, {sum(len(links) for links in social_links.values())} social links on {url}")
            else:
                logger.debug(f"📭 No emails, phones, or social links found on {url}")
            
            return emails, phones, social_links
    
    def _regex_extract_emails(self, html_content: str) -> Set[str]:
        """Extract emails using regex patterns"""
        emails = set()
        
        patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
            r'"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})"',
            r"'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                email = match if isinstance(match, str) else match
                if self._is_valid_email(email):
                    emails.add(email.lower())
                else:
                    logger.debug(f"🚫 Filtered out invalid email pattern: {email}")
        
        return emails
    
    def _regex_extract_phones(self, html_content: str) -> Set[str]:
        """Extract phone numbers using regex patterns"""
        phones = set()
        
        # Phone number patterns
        patterns = [
            r'[\+]?[1-9][\d\s\.\-\(\)]{0,20}',  # General phone pattern
            r'\(\d{3}\)\s*\d{3}-\d{4}',  # (XXX) XXX-XXXX
            r'\d{3}-\d{3}-\d{4}',  # XXX-XXX-XXXX
            r'\d{3}\.\d{3}\.\d{4}',  # XXX.XXX.XXXX
            r'\d{10}',  # XXXXXXXXXX
            r'\+1\s*\(\d{3}\)\s*\d{3}-\d{4}',  # +1 (XXX) XXX-XXXX
            r'\+1\s*\d{3}-\d{3}-\d{4}',  # +1 XXX-XXX-XXXX
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                phone = match.strip()
                # Basic validation - should have at least 10 digits
                digits_only = re.sub(r'\D', '', phone)
                if len(digits_only) >= 10:
                    phones.add(phone)
        
        return phones
    
    def _soup_extract_emails(self, soup: BeautifulSoup) -> Set[str]:
        """Extract emails from parsed HTML"""
        emails = set()
        
        # Mailto links
        mailto_links = soup.find_all('a', href=lambda x: x and x.startswith('mailto:'))
        for link in mailto_links:
            email = link.get('href').replace('mailto:', '').split('?')[0]
            if self._is_valid_email(email):
                emails.add(email.lower())
        
        # Contact sections
        contact_selectors = [
            'div.contact', 'div.contact-info', 'section.contact',
            'div.about', 'div.team-member', 'div.staff',
            'footer', 'div.owner', 'div.founder'
        ]
        
        for selector in contact_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text()
                emails.update(self._regex_extract_emails(text))
        
        return emails
    
    def _soup_extract_phones(self, soup: BeautifulSoup) -> Set[str]:
        """Extract phone numbers from parsed HTML"""
        phones = set()
        
        # Phone-specific selectors
        phone_selectors = [
            'a[href^="tel:"]',  # Tel links
            '[class*="phone"]',  # Elements with "phone" in class
            '[id*="phone"]',     # Elements with "phone" in id
            'span.phone', 'div.phone', 'p.phone',
            'span.tel', 'div.tel', 'p.tel',
            'span.telephone', 'div.telephone', 'p.telephone',
        ]
        
        # Extract from phone-specific elements
        for selector in phone_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text()
                phones.update(self._regex_extract_phones(text))
        
        # Contact sections
        contact_selectors = [
            'div.contact', 'div.contact-info', 'section.contact',
            'div.about', 'div.team-member', 'div.staff',
            'footer', 'div.owner', 'div.founder'
        ]
        
        for selector in contact_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text()
                phones.update(self._regex_extract_phones(text))
        
        return phones
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email using centralized email service (BASIC VALIDATION ONLY - NO ZEROBOUNCE)"""
        result = self.email_service.validate_email(email)
        is_valid = result.status == EmailValidationStatus.VALID
        if not is_valid:
            logger.debug(f"🚫 Basic validation failed for {email}: {result.sub_status}")
        return is_valid
    
    def _extract_social_links(self, soup: BeautifulSoup, page_url: str) -> Dict[str, List[str]]:
        """Extract social media links from website"""
        social_links = {
            'linkedin': [],
            'facebook': [],
            'instagram': [],
            'twitter': [],
            'pinterest': [],
            'youtube': [],
            'other': []
        }
        
        # Find all links on the page
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '').lower()
            
            # Skip internal links and non-social links
            if not href.startswith(('http://', 'https://')):
                continue
            
            # Clean the URL
            if '?utm_source=' in href:
                href = href.split('?utm_source=')[0]
            
            # Categorize social links
            if 'linkedin.com' in href and href not in social_links['linkedin']:
                social_links['linkedin'].append(link.get('href'))
            elif ('twitter.com' in href or 'x.com' in href) and href not in social_links['twitter']:
                social_links['twitter'].append(link.get('href'))
            elif 'facebook.com' in href and href not in social_links['facebook']:
                social_links['facebook'].append(link.get('href'))
            elif 'instagram.com' in href and href not in social_links['instagram']:
                social_links['instagram'].append(link.get('href'))
            elif 'pinterest.com' in href and href not in social_links['pinterest']:
                social_links['pinterest'].append(link.get('href'))
            elif ('youtube.com' in href or 'youtu.be' in href) and href not in social_links['youtube']:
                social_links['youtube'].append(link.get('href'))
            elif any(social in href for social in ['behance.net', 'dribbble.com', 'tiktok.com', 'snapchat.com', 'tumblr.com', 'reddit.com', 'medium.com', 'github.com']):
                if href not in social_links['other']:
                    social_links['other'].append(link.get('href'))
        
        return social_links
    
    

