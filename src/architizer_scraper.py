"""Architizer Scraper Module for Architecture Firm Lead Generation.

Optimized scraper inheriting from BaseScraper for consistent behavior and reduced code duplication.
Uses Playwright for dynamic content handling, Beautiful Soup for parsing,
comprehensive error handling, retry logic, and performance improvements.
"""

import asyncio
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, quote
from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup
from loguru import logger
from datetime import datetime

from src.models import ProfessionalProfile
from src.base_scraper import BaseScraper
from src.common_utils import WebUtils, StateManager, phone_utils, zipcode_utils
from src.email_service import email_service, EmailValidationStatus
from src.phone_formatter import validate_and_format_us_phone
from config.config import config

# Architizer URLs and constants
ARCHITIZER_BASE_URL = "https://architizer.com"
ARCHITIZER_FIRMS_URL = "https://architizer.com/firms/firm-location={location}"

class ArchitizerScraper(BaseScraper):
    """Production-ready Architizer scraper inheriting from BaseScraper"""
    
    def __init__(self, database_manager=None):
        super().__init__(database_manager)
        # Platform-specific initialization
        self.email_service = email_service
        logger.info("ArchitizerScraper initialized with BaseScraper functionality")

    async def __aenter__(self):
        """Async context manager entry"""
        self.playwright = await async_playwright().start()
        
        # Launch browser with optimized settings from BaseScraper
        self.browser = await self.playwright.chromium.launch(
            headless=config.HEADLESS,
            args=self.get_browser_args()
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup()

    async def create_or_rotate_page(self, page: Page = None) -> Page:
        """Create a new browser page with Architizer-specific configuration"""
        # Architizer-specific page configuration
        page_config = {
            'viewport': {'width': 1920, 'height': 1080},  # Larger viewport for better visibility
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        return await super().create_or_rotate_page(page, page_config)

    async def scrape_firms(self, location="United States", start_page: int = 1, max_pages: Optional[int] = None) -> List[ProfessionalProfile]:
        """Scrape firm profiles from Architizer and store them with pagination support."""
        logger.info(f"Starting Architizer scrape for {location} with pagination: start_page={start_page}, max_pages={max_pages}")
        
        # Use the new enhanced scraping method with load more functionality and pagination
        return await self.scrape_firms_with_load_more(location=location, start_page=start_page, max_pages=max_pages)
    
    async def scrape_firms_with_load_more(self, location="United States", start_page: int = 1, max_pages: Optional[int] = None) -> List[ProfessionalProfile]:
        """Comprehensive scraping with load more pagination - Two-phase approach"""
        logger.info(f"Starting comprehensive Architizer scrape for {location} with pagination: start_page={start_page}, max_pages={max_pages}")
        
        # Phase 1: Collect all URLs from all pages
        logger.info("🔄 Phase 1: Collecting all firm URLs from all pages...")
        all_firm_urls = await self._collect_all_firm_urls(location, start_page, max_pages)
        
        if not all_firm_urls:
            logger.error("No firm URLs collected")
            return []
        
        logger.info(f"✅ Phase 1 completed: Collected {len(all_firm_urls)} unique firm URLs")
        
        # Phase 2: Scrape individual profiles
        logger.info("🔄 Phase 2: Scraping individual firm profiles...")
        all_profiles = await self._scrape_all_profiles_from_urls(all_firm_urls)
        
        logger.info(f"✅ Phase 2 completed: Scraped {len(all_profiles)} profiles")
        return all_profiles

    async def _collect_all_firm_urls(self, location: str, start_page: int, max_pages: int) -> List[str]:
        """Phase 1: Collect all firm URLs from all pages without scraping individual profiles"""
        logger.info(f"🔄 Starting URL collection: location={location}, start_page={start_page}, max_pages={max_pages}")
        
        all_firm_urls = set()  # Use set to avoid duplicates
        page = None
        max_retries = 3

        for attempt in range(max_retries):
            try:
                page = await self.create_or_rotate_page(page)
                await page.route('**/*', self._log_network_request)
                
                # Navigate to the firms page
                url = ARCHITIZER_FIRMS_URL.format(location=quote(location))
                logger.info(f"Attempt {attempt + 1}: Navigating to firms URL: {url}")
                
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                logger.info("✅ Firms page loaded successfully")
                
                # Handle cookie consent
                await self._handle_cookie_consent(page)
                
                # Wait for content to load
                content_loaded = await self._wait_for_content_load_with_fallback(page)
                logger.info(f"Content loading status: {content_loaded}")
                
                # Calculate pages and limits
                total_count, items_per_page = await self._extract_total_count_and_calculate_pages(page)
                if total_count:
                    logger.info(f"📊 Total firms found: {total_count:,}")
                    logger.info(f"📄 Items per page: {items_per_page}")
                    estimated_pages = total_count // items_per_page + (1 if total_count % items_per_page else 0)
                    logger.info(f"📑 Estimated pages needed: {estimated_pages}")
                    
                    # Calculate effective estimated pages considering start_page
                    if start_page > 1:
                        remaining_pages = estimated_pages - start_page + 1
                        effective_estimated = max(remaining_pages, 1)
                        logger.info(f"🔄 Starting from page {start_page}, remaining pages: {remaining_pages}")
                    else:
                        effective_estimated = estimated_pages
                    
                    # Set max_pages based on whether it was provided or not
                    if max_pages is None:
                        max_pages = effective_estimated
                        logger.info(f"🔄 Setting max_pages to {max_pages} based on total count")
                    else:
                        original_max_pages = max_pages
                        if effective_estimated < max_pages:
                            logger.info(f"🔄 User requested {original_max_pages} pages, but only {effective_estimated} pages available. Using {original_max_pages}.")
                        else:
                            logger.info(f"🔄 Using user-provided max_pages: {original_max_pages} (estimated available: {effective_estimated})")
                else:
                    logger.warning(f"⚠️ Could not extract total count")
                    if max_pages is None:
                        logger.warning(f"⚠️ Using fallback max_pages: 50")
                        max_pages = 50
                    else:
                        logger.info(f"📋 Using provided max_pages: {max_pages} (no total count available)")

                # Collect URLs from all pages
                collected_urls = await self._collect_urls_from_all_pages(page, start_page, max_pages)
                all_firm_urls.update(collected_urls)
                
                self._handle_network_success()
                break  # Success, exit retry loop

            except Exception as e:
                self._handle_network_error()
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {self.current_delay} seconds...")
                    await self._adaptive_sleep()
                    if page:
                        try:
                            await page.close()
                        except:
                            pass
                        page = None
                else:
                    logger.error(f"All {max_retries} attempts failed")

        if page:
            try:
                await page.close()
            except:
                pass

        logger.info(f"✅ URL collection completed. Total unique URLs collected: {len(all_firm_urls)}")
        return list(all_firm_urls)

    async def _collect_urls_from_all_pages(self, page: Page, start_page: int, max_pages: int) -> List[str]:
        """Collect URLs from all pages using load more button"""
        logger.info(f"🔄 Starting URL collection from pages: start_page={start_page}, max_pages={max_pages}")
        
        all_urls = set()
        current_page = start_page
        pages_scraped = 0
        pages_to_scrape = max_pages
        
        logger.info(f"📊 Starting pagination: start_page={start_page}, max_pages={max_pages}, pages_to_scrape={pages_to_scrape}")
        
        while pages_scraped < pages_to_scrape:
            logger.info(f"🔄 Collecting URLs from page {current_page} ({pages_scraped + 1}/{pages_to_scrape})")
            logger.info(f"📊 Progress: {pages_scraped}/{pages_to_scrape} pages completed")
            
            # Debug page state
            await self._debug_page_state(page, f"Collecting URLs from page {current_page}")
            
            # Extract URLs from current page
            current_urls = await self._extract_firm_urls_from_page(page)
            logger.info(f"Found {len(current_urls)} firm URLs on current page")
            
            # Add new URLs to our collection
            new_urls = [url for url in current_urls if url not in all_urls]
            all_urls.update(current_urls)
            
            logger.info(f"New URLs added: {len(new_urls)} (total unique: {len(all_urls)})")
            
            if not new_urls:
                logger.info("⚠️ No new URLs found on current page - this might indicate we've reached the end of available content")
                logger.info(f"📊 Current stats: pages_scraped={pages_scraped}, pages_to_scrape={pages_to_scrape}, current_page={current_page}")
                break
            
            pages_scraped += 1
            current_page += 1
            
            # Try to click load more button for next iteration
            if pages_scraped < pages_to_scrape:
                load_more_clicked = await self._click_load_more_button(page)
                if not load_more_clicked:
                    logger.info("⚠️ No load more button found or all content loaded")
                    logger.info(f"📊 Current stats: pages_scraped={pages_scraped}, pages_to_scrape={pages_to_scrape}, current_page={current_page}")
                    logger.info(f"🔄 This might be the end of available content or the load more button is not available")
                    break
                
                # Wait for page content to load
                logger.info("⏳ Waiting for page content to load...")
                await asyncio.sleep(3)
        
        logger.info(f"✅ URL collection completed. Total unique URLs: {len(all_urls)}")
        return list(all_urls)

    async def _scrape_all_profiles_from_urls(self, firm_urls: List[str]) -> List[ProfessionalProfile]:
        """Phase 2: Scrape individual profiles from collected URLs"""
        logger.info(f"🔄 Starting profile scraping for {len(firm_urls)} URLs")
        
        all_profiles = []
        scraped_count = 0
        total_urls = len(firm_urls)
        
        # Create a new page for profile scraping
        page = await self.create_or_rotate_page()
        
        try:
            for i, firm_url in enumerate(firm_urls, 1):
                logger.info(f"🔄 Scraping profile {i}/{total_urls}: {firm_url}")
                
                try:
                    # Check if URL is already completed in state manager
                    if self.state_manager.is_url_completed(firm_url, platform="architizer"):
                        logger.info(f"Skipping already completed URL: {firm_url}")
                        continue
                    
                    # Scrape individual firm profile
                    profile = await self._scrape_individual_firm_profile(page, firm_url)
                    
                    if profile:
                        # Save to database
                        if self.database_manager:
                            try:
                                # Use thread executor to avoid blocking async execution
                                loop = asyncio.get_event_loop()
                                was_added = await loop.run_in_executor(
                                    self.executor, 
                                    self.database_manager.add_profile_if_not_exists, 
                                    profile
                                )
                                
                                if was_added:
                                    scraped_count += 1
                                    logger.info(f"✅ Scraped and saved new firm: {profile.name}")
                                else:
                                    scraped_count += 1
                                    logger.info(f"✅ Scraped firm (already exists): {profile.name}")
                                    
                            except Exception as db_error:
                                logger.error(f"Database error saving profile {profile.name}: {db_error}")
                                scraped_count += 1
                        else:
                            all_profiles.append(profile)
                            scraped_count += 1
                            logger.info(f"✅ Scraped firm: {profile.name}")
                        
                        # Mark URL as completed in state manager
                        self.state_manager.mark_url_completed(firm_url, platform="architizer")
                    else:
                        logger.warning(f"⚠️ Failed to scrape profile: {firm_url}")
                        # Mark URL as failed in state manager
                        self.state_manager.mark_url_failed(firm_url, platform="architizer")
                
                except Exception as e:
                    logger.error(f"❌ Error scraping profile {firm_url}: {e}")
                    # Mark URL as failed in state manager
                    self.state_manager.mark_url_failed(firm_url, platform="architizer")
                    continue
                
                # Progress update every 10 profiles
                if i % 10 == 0:
                    logger.info(f"📊 Progress: {i}/{total_urls} profiles processed, {scraped_count} successfully scraped")
        
        finally:
            await page.close()
        
        logger.info(f"✅ Profile scraping completed. Successfully scraped {scraped_count}/{total_urls} profiles")
        return all_profiles

    async def _scrape_all_firms_with_pagination(self, page: Page, scraped_urls: set, start_page: int, max_pages: int) -> List[ProfessionalProfile]:
        """Scrape all firms with load more functionality and pagination support."""
        firms = []
        current_page = 1  # Track current page number
        pages_to_scrape = max_pages  # Total pages we need to scrape
        
        logger.info(f"Starting pagination scraping: start_page={start_page}, max_pages={max_pages}, pages_to_scrape={pages_to_scrape}")
        
        # If start_page > 1, we need to load content until we reach the start_page
        if start_page > 1:
            logger.info(f"Starting from page {start_page}, loading {start_page - 1} pages first...")
            pages_to_load_before_start = start_page - 1
            
            for i in range(pages_to_load_before_start):
                logger.info(f"Loading page {i + 1} to reach start_page {start_page}...")
                
                # Mark current page URLs as processed without detailed extraction
                # (we'll do proper extraction during actual scraping)
                current_page_urls = await self._extract_firm_urls_from_page(page)
                logger.info(f"Found {len(current_page_urls)} firm URLs on page {i + 1}")
                
                # Mark URLs as processed to avoid duplicates (but don't mark as completed yet)
                for url in current_page_urls:
                    scraped_urls.add(url)
                
                # Try to click load more button for next iteration
                load_more_clicked = await self._click_load_more_button(page)
                if not load_more_clicked:
                    logger.warning(f"No load more button found after loading {i + 1} pages")
                    break
                
                # Wait for new content to load
                await asyncio.sleep(3)
                current_page += 1
                
                if current_page > start_page:
                    break
            
            logger.info(f"Reached page {current_page}, now starting actual scraping...")
        
        # Now start the actual scraping from the start_page
        logger.info(f"Starting actual scraping from page {current_page} (start_page={start_page})")
        pages_scraped = 0  # Track how many pages we've actually scraped
        
        while pages_scraped < pages_to_scrape:
            logger.info(f"🔄 Scraping page {current_page} ({pages_scraped + 1}/{pages_to_scrape})")
            logger.info(f"📊 Progress: {pages_scraped}/{pages_to_scrape} pages completed")
            
            # Debug current page state
            await self._debug_page_state(page, f"Scraping page {current_page}")
            
            # Extract URLs from current page
            current_page_urls = await self._extract_firm_urls_from_page(page)
            logger.info(f"Found {len(current_page_urls)} firm URLs on current page")
            
            # Filter out already scraped URLs
            new_urls = [url for url in current_page_urls if url not in scraped_urls]
            logger.info(f"New URLs to scrape: {len(new_urls)}")
            
            if not new_urls:
                logger.info("⚠️ No new URLs found on current page - this might indicate we've reached the end of available content")
                logger.info(f"📊 Current stats: pages_scraped={pages_scraped}, pages_to_scrape={pages_to_scrape}, current_page={current_page}")
                break
            print('new_urls', new_urls)
            # Scrape firms from current page
            for url in new_urls:
                try:
                    # Check if URL is already completed in state manager
                    if self.state_manager.is_url_completed(url, platform="architizer"):
                        logger.info(f"Skipping already completed URL: {url}")
                        scraped_urls.add(url)
                        continue
                    
                    firm_profile = await self._scrape_individual_firm_profile(page, url)
                    print('firm_profile', firm_profile)
                    if firm_profile:
                        firms.append(firm_profile)
                        scraped_urls.add(url)
                        
                        # Save to database if available
                        if self.database_manager:
                            try:
                                # Use thread executor to avoid blocking async execution
                                loop = asyncio.get_event_loop()
                                was_added = await loop.run_in_executor(
                                    self.executor, 
                                    self.database_manager.add_profile_if_not_exists, 
                                    firm_profile
                                )
                                
                                if was_added:
                                    self.saved_profiles_count += 1
                                    if self.saved_profiles_count % 10 == 0:  # Log every 10 saves
                                        logger.info(f"💾 Saved {self.saved_profiles_count} new profiles to database so far")
                                    logger.info(f"✅ Scraped and saved new firm: {firm_profile.name}")
                                else:
                                    logger.info(f"✅ Scraped firm (already exists): {firm_profile.name}")
                                    
                            except Exception as db_error:
                                logger.error(f"Database error saving profile {firm_profile.name}: {db_error}")
                        else:
                            logger.info(f"✅ Scraped firm: {firm_profile.name}")
                        
                        # Mark URL as completed in state manager
                        self.state_manager.mark_url_completed(url, platform="architizer")
                    else:
                        # Mark URL as failed if no profile was extracted
                        self.state_manager.mark_url_failed(url, platform="architizer")
                        logger.warning(f"No profile extracted from URL: {url}")
                        
                except Exception as e:
                    logger.error(f"Error scraping firm {url}: {e}")
                    # Mark URL as failed in state manager
                    self.state_manager.mark_url_failed(url, platform="architizer")
                    continue
            
            pages_scraped += 1
            
            # Check if we've reached the max_pages limit
            if pages_scraped >= pages_to_scrape:
                logger.info(f"Reached pages_to_scrape limit ({pages_to_scrape}), stopping at page {current_page}")
                break
            
            # Try to click load more button for next iteration
            load_more_clicked = await self._click_load_more_button(page)
            if not load_more_clicked:
                logger.info("⚠️ No load more button found, trying scroll-based pagination...")
                
                # Try scroll-based pagination as fallback
                scroll_success = await self._try_scroll_based_pagination(page)
                if not scroll_success:
                    logger.info("⚠️ Both load more button and scroll-based pagination failed")
                    logger.info(f"📊 Current stats: pages_scraped={pages_scraped}, pages_to_scrape={pages_to_scrape}, current_page={current_page}")
                    logger.info(f"🔄 This might be the end of available content")
                    break
                else:
                    logger.info("✅ Scroll-based pagination succeeded, continuing...")
            
            # Wait for new content to load and loaders to disappear
            logger.info(f"⏳ Waiting for page {current_page + 1} content to load...")
            await asyncio.sleep(3)
            current_page += 1
        
        logger.info(f"Completed pagination scraping. Total firms: {len(firms)}, Pages processed: {current_page}, Pages scraped: {pages_scraped}")
        
        # Log database summary if database manager is available
        if self.database_manager:
            logger.info(f"💾 Database summary: {self.saved_profiles_count} new profiles saved to database")
        
        return firms

    async def _extract_firm_urls_from_page(self, page: Page) -> List[str]:
        """Extract all firm URLs from the current page using BeautifulSoup."""
        try:
            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            firm_urls = []
            
            # Method 1: Direct firm links with href="/firms/" (comprehensive approach)
            firm_links = soup.find_all('a', href=True)
            for link in firm_links:
                href = link.get('href', '')
                # Only consider links that are potentially firm profiles
                if '/firms/' in href:
                    full_url = urljoin(ARCHITIZER_BASE_URL, href)
                    
                    # Skip project URLs (we want firm URLs only)
                    if '/projects/' in href:
                        continue

                    # Ensure it's a specific firm profile URL by checking the path structure
                    # Valid firm URL should have: /firms/firm-name/ or /firms/firm-name
                    # Invalid URLs: /firms/, /firms/firm-location=, etc.
                    if href.startswith('/firms/'):
                        # Extract the part after /firms/
                        firm_slug = href.replace('/firms/', '').strip('/')
                        
                        # Skip if it's empty or contains query parameters (like firm-location=)
                        if firm_slug and '=' not in firm_slug and not firm_slug.startswith('firm-location'):
                            firm_urls.append(full_url)
            # Method 2: Specific selectors based on your HTML structure (targeted approach)
            specific_selectors = [
                'a.black.fw-medium.ellipsis[href*="/firms/"]',  # Main firm name link
                'div.sc-hiwReK a[href*="/firms/"]', # Link around the firm logo/image
                'a.button.tiny[href*="/firms/"]', # Contact button link
            ]
            
            for selector in specific_selectors:
                try:
                    elements = soup.select(selector)
                    for element in elements:
                        href = element.get('href', '')
                        if '/firms/' in href:
                            full_url = urljoin(ARCHITIZER_BASE_URL, href)
                            
                            # Skip project URLs
                            if '/projects/' in href:
                                continue

                            # Apply same filtering logic as above
                            if href.startswith('/firms/'):
                                firm_slug = href.replace('/firms/', '').strip('/')
                                if firm_slug and '=' not in firm_slug and not firm_slug.startswith('firm-location'):
                                    firm_urls.append(full_url)
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            # Remove duplicates while preserving order
            unique_urls = []
            seen = set()
            for url in firm_urls:
                if url not in seen:
                    unique_urls.append(url)
                    seen.add(url)
            
            logger.info(f"Extracted {len(unique_urls)} unique firm URLs from page")
            
            # Debug: Show some extracted URLs
            if unique_urls:
                logger.info("Sample extracted URLs:")
                for i, url in enumerate(unique_urls[:3]):
                    logger.info(f"  {i+1}. {url}")
                if len(unique_urls) > 3:
                    logger.info(f"  ... and {len(unique_urls) - 3} more")
            
            return unique_urls
            
        except Exception as e:
            logger.error(f"Error extracting firm URLs: {e}")
            return []

    async def _debug_page_state(self, page: Page, message: str = ""):
        """Debug method to log current page state."""
        try:
            # Get page title
            title = await page.title()
            logger.debug(f"Page title: {title}")
            
            # Get current URL
            url = page.url
            logger.debug(f"Current URL: {url}")
            
            # Get page content length
            content = await page.content()
            logger.debug(f"Page content length: {len(content)} characters")
            
            # Check for specific elements
            firm_links = await page.query_selector_all('a[href*="/firms/"]')
            logger.debug(f"Found {len(firm_links)} firm links on page")
            
            # Check for load more button
            load_more_buttons = []
            for selector in ['button:has-text("Load More")', 'button:has-text("Show More")']:
                try:
                    button = await page.query_selector(selector)
                    if button and await button.is_visible():
                        load_more_buttons.append(selector)
                except:
                    pass
            
            logger.debug(f"Load more buttons found: {load_more_buttons}")
            
            if message:
                logger.info(f"🔍 Debug: {message}")
            
        except Exception as e:
            logger.error(f"Error in debug_page_state: {e}")

    async def _click_load_more_button(self, page: Page) -> bool:
        """Click the load more button if available and wait for content to load."""
        try:
            # Wait a bit for any dynamic content to load
            await asyncio.sleep(2)
            
            # Scroll to bottom to ensure load more button is visible
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            
            # Scroll a bit more to ensure we're at the very bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight + 100)")
            await asyncio.sleep(1)
            
            # Debug: Log all buttons on the page to understand the pagination mechanism
            logger.info("🔍 Debugging pagination - checking all buttons on page...")
            all_buttons = await page.query_selector_all('button, a[href], [role="button"]')
            logger.info(f"Found {len(all_buttons)} potential pagination elements")
            
            for i, button in enumerate(all_buttons[:10]):  # Log first 10 buttons
                try:
                    text = await button.text_content()
                    tag_name = await button.evaluate('el => el.tagName.toLowerCase()')
                    classes = await button.get_attribute('class') or ''
                    href = await button.get_attribute('href') or ''
                    logger.info(f"  Button {i+1}: {tag_name} '{text[:50]}' class='{classes[:50]}' href='{href[:50]}'")
                except Exception as e:
                    logger.debug(f"  Button {i+1}: Error getting info: {e}")
            
            # Try multiple selectors for load more button
            load_more_selectors = [
                # Specific selectors for the actual Architizer button
                'button:has-text("Load More…")',  # Note the ellipsis
                'button:has-text("Load More")',
                'button.button:has-text("Load More")',
                'div.flex-container button.button',
                'button[style*="margin: 40px auto"]',
                
                # Generic selectors as fallbacks
                'button:has-text("Show More")',
                'button:has-text("Load more")',
                'button:has-text("Show more")',
                'button:has-text("View More")',
                'button:has-text("view more")',
                'a:has-text("Load More")',
                'a:has-text("Show More")',
                'a:has-text("View More")',
                '[class*="load-more"]',
                '[class*="show-more"]',
                '[class*="view-more"]',
                'button[class*="load"]',
                'button[class*="more"]',
                'button[class*="view"]',
                '.load-more-button',
                '.show-more-button',
                '.view-more-button',
                '.pagination-next',
                '.next-page',
                '[data-testid*="load"]',
                '[data-testid*="more"]',
                '[aria-label*="load"]',
                '[aria-label*="more"]'
            ]
            
            for selector in load_more_selectors:
                try:
                    # Check if button exists and is visible
                    button = await page.query_selector(selector)
                    if button and await button.is_visible():
                        # Scroll to button to ensure it's in view
                        await button.scroll_into_view_if_needed()
                        await asyncio.sleep(1)
                        
                        # Try to click the button with retry logic
                        try:
                            await button.click()
                            logger.info(f"✅ Clicked load more button: {selector}")
                        except Exception as click_error:
                            logger.warning(f"Failed to click button with {selector}, trying JavaScript click: {click_error}")
                            # Fallback to JavaScript click
                            await page.evaluate("(element) => element.click()", button)
                            logger.info(f"✅ Clicked load more button via JavaScript: {selector}")
                        
                        # Wait for loaders to disappear (similar to initial page loading)
                        await self._wait_for_loaders_to_disappear(page)
                        
                        # Wait a bit for content to settle
                        await asyncio.sleep(2)
                        
                        logger.info("✅ Load more button clicked and content loaded")
                        return True
                        
                except Exception as e:
                    logger.debug(f"Load more selector {selector} not found or not clickable: {e}")
                    continue
            
            # Try JavaScript-based approach to find and click the button
            try:
                logger.info("🔍 Trying JavaScript-based button detection...")
                button_clicked = await page.evaluate("""
                    () => {
                        // Look for the specific Architizer load more button
                        const buttons = document.querySelectorAll('button');
                        for (const button of buttons) {
                            const text = button.textContent || '';
                            if (text.includes('Load More') || text.includes('Load More…')) {
                                console.log('Found load more button:', text);
                                button.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                
                if button_clicked:
                    logger.info("✅ Clicked load more button via JavaScript")
                    await asyncio.sleep(3)
                    await self._wait_for_loaders_to_disappear(page)
                    return True
                    
            except Exception as e:
                logger.debug(f"JavaScript-based button detection failed: {e}")
            
            logger.info("No load more button found")
            
            # Check if Architizer uses URL-based pagination instead
            current_url = page.url
            logger.info(f"Current URL: {current_url}")
            
            # Check if we can modify the URL for pagination
            if 'page=' in current_url:
                # Extract current page number and increment
                import re
                page_match = re.search(r'page=(\d+)', current_url)
                if page_match:
                    current_page_num = int(page_match.group(1))
                    next_page_num = current_page_num + 1
                    next_url = re.sub(r'page=\d+', f'page={next_page_num}', current_url)
                    logger.info(f"Trying URL-based pagination: {next_url}")
                    
                    try:
                        await page.goto(next_url, wait_until='domcontentloaded', timeout=30000)
                        await asyncio.sleep(3)
                        logger.info("✅ Successfully navigated to next page via URL")
                        return True
                    except Exception as e:
                        logger.error(f"Failed to navigate to next page via URL: {e}")
                        return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error clicking load more button: {e}")
            return False

    async def _try_scroll_based_pagination(self, page: Page) -> bool:
        """Try scroll-based pagination as a fallback when load more button is not found."""
        try:
            logger.info("🔄 Trying scroll-based pagination...")
            
            # Get current number of firm URLs
            current_urls = await self._extract_firm_urls_from_page(page)
            initial_count = len(current_urls)
            logger.info(f"Current firm URLs on page: {initial_count}")
            
            # Scroll to bottom of page to trigger lazy loading
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)
            
            # Scroll a bit more to ensure we trigger any lazy loading
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight + 1000)")
            await asyncio.sleep(2)
            
            # Check if new content was loaded
            new_urls = await self._extract_firm_urls_from_page(page)
            new_count = len(new_urls)
            logger.info(f"Firm URLs after scrolling: {new_count}")
            
            if new_count > initial_count:
                logger.info(f"✅ Scroll-based pagination worked! Found {new_count - initial_count} new firms")
                return True
            else:
                logger.info("❌ Scroll-based pagination did not load new content")
                return False
                
        except Exception as e:
            logger.error(f"Error in scroll-based pagination: {e}")
            return False

    async def _wait_for_loaders_to_disappear(self, page: Page, timeout: int = 15) -> bool:
        """Wait for loading spinners/indicators to disappear after clicking load more."""
        try:
            logger.info("⏳ Waiting for loaders to disappear after clicking load more...")
            
            # Common loader/spinner selectors
            loader_selectors = [
                '.loading-spinner-m',
                '[class*="loading"]',
                '[class*="spinner"]',
                '.loader',
                '[class*="skeleton"]',
                '[class*="shimmer"]',
                '.loading-indicator',
                '.spinner',
                '.loading',
                '[data-testid*="loading"]',
                '[aria-label*="loading"]',
                '[role="progressbar"]'
            ]
            
            start_time = asyncio.get_event_loop().time()
            
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                loaders_found = False
                
                for selector in loader_selectors:
                    try:
                        loader = await page.query_selector(selector)
                        if loader and await loader.is_visible():
                            loaders_found = True
                            logger.debug(f"Found visible loader: {selector}")
                            break
                    except Exception:
                        continue
                
                if not loaders_found:
                    logger.info("✅ All loaders have disappeared")
                    return True
                
                # Wait a bit before checking again
                await asyncio.sleep(0.5)
            
            logger.warning(f"⚠️ Timeout waiting for loaders to disappear after {timeout} seconds")
            return False
            
        except Exception as e:
            logger.error(f"Error waiting for loaders to disappear: {e}")
            return False

    async def _scrape_individual_firm_profile(self, page: Page, firm_url: str) -> Optional[ProfessionalProfile]:
        """Scrape individual firm profile page."""
        try:
            logger.info(f"Scraping individual firm profile: {firm_url}")
            
            # Navigate to the firm page
            await page.goto(firm_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)
            
            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract firm information
            firm_data = self._extract_firm_data_from_page(soup, firm_url)
            if firm_data:
                # Convert social_links dict to separate fields
                social_links = firm_data.get('social_links', {})
                
                return ProfessionalProfile(
                    profile_url=firm_url,
                    platform='architizer',
                    name=firm_data.get('name'),
                    website=firm_data.get('website'),
                    phone=firm_data.get('phone'),
                    emails=firm_data.get('emails'),  # Now contains JSON structure with personal/business classification
                    address="| ".join(firm_data.get('address')) if isinstance(firm_data.get('address'), list) else firm_data.get('address'),
                    zip_code=firm_data.get('zip_code'),  # Add zipcode to profile
                    professional_type=firm_data.get('professional_type'),
                    rating=firm_data.get('rating'),
                    reviews_count=firm_data.get('reviews_count'),
                    linkedin_links=social_links.get('linkedin', []),
                    facebook_links=social_links.get('facebook', []),
                    instagram_links=social_links.get('instagram', []),
                    twitter_links=social_links.get('twitter', []),
                    pinterest_links=social_links.get('pinterest', []),
                    youtube_links=social_links.get('youtube', []),
                    other_social_links=social_links.get('other', []),
                    typical_job_cost=firm_data.get('typical_job_cost'),
                    followers_count=firm_data.get('followers_count')
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error scraping individual firm profile {firm_url}: {e}")
            return None

    def _extract_firm_data_from_page(self, soup: BeautifulSoup, firm_url: str) -> Dict[str, Any]:
        """Extract firm data from individual firm page using BeautifulSoup."""
        firm_data = {}
        
        try:
            # Add the profile URL to the firm data
            firm_data['profile_url'] = firm_url
            
            # Extract firm name with multiple strategies
            name_selectors = [
                'h1',
                '.firm-name',
                '.company-name',
                '[class*="firm"] h1',
                '[class*="company"] h1',
                '.profile-title',
                '.business-name',
                'h1[class*="title"]',
                '.page-title',
                'title',  # Fallback to page title
            ]
            
            for selector in name_selectors:
                name_elem = soup.select_one(selector)
                if name_elem:
                    name_text = name_elem.get_text(strip=True)
                    if name_text and len(name_text) > 2:
                        firm_data['name'] = name_text
                        break
            
            # Extract website from the specific structure
            website_elem = soup.select_one('[id*="-websites"] a[href*="http"]')
            if website_elem and website_elem.get('href'):
                href = website_elem.get('href')
                # Remove utm_source parameter if present
                if '?utm_source=' in href:
                    href = href.split('?utm_source=')[0]
                firm_data['website'] = href
            else:
                # Fallback: try to find any website link
                website_elem = soup.select_one('a[href*="http"]:not([href*="architizer.com"]):not([href*="mailto:"]):not([href*="tel:"])')
                if website_elem and website_elem.get('href'):
                    href = website_elem.get('href')
                    if '?utm_source=' in href:
                        href = href.split('?utm_source=')[0]
                    firm_data['website'] = href
            
            # Extract phone from the specific structure
            phone_elems = soup.select('[id*="-phone_numbers"] .placeholder')
            if phone_elems:
                # Look for work phone first, then mobile, then fax
                work_phone = None
                mobile_phone = None
                fax_phone = None
                
                for phone_elem in phone_elems:
                    phone_text = phone_elem.get_text(strip=True)
                    # Extract phone number from text like "work: 323.424.7594"
                    import re
                    phone_pattern = r'[\+]?[1-9][\d\s\.\-\(\)]{0,20}'
                    phone_matches = re.findall(phone_pattern, phone_text)
                    if phone_matches:
                        phone = phone_matches[0].strip()
                        # Determine phone type and clean up
                        if phone.startswith('work:'):
                            work_phone = phone.split(':', 1)[1].strip()
                        elif phone.startswith('mobile:'):
                            mobile_phone = phone.split(':', 1)[1].strip()
                        elif phone.startswith('fax:'):
                            fax_phone = phone.split(':', 1)[1].strip()
                        else:
                            # If no prefix, assume it's a work phone
                            work_phone = phone
                
                # Prioritize work phone, then mobile, then fax
                if work_phone:
                    firm_data['phone'] = work_phone
                elif mobile_phone:
                    firm_data['phone'] = mobile_phone
                elif fax_phone:
                    firm_data['phone'] = fax_phone
            else:
                # Fallback: try to find phone in any element
                phone_elem = soup.select_one('[class*="phone"], a[href^="tel:"]')
                if phone_elem:
                    phone_text = phone_elem.get_text(strip=True)
                    import re
                    phone_pattern = r'[\+]?[1-9][\d\s\.\-\(\)]{0,20}'
                    phone_matches = re.findall(phone_pattern, phone_text)
                    if phone_matches:
                        firm_data['phone'] = phone_matches[0].strip()
            
            # Extract email from the specific structure
            email_elem = soup.select_one('[id*="-email_addresses"] a[href^="mailto:"]')
            if email_elem:
                email_href = email_elem.get('href')
                if email_href and email_href.startswith('mailto:'):
                    email = email_href.replace('mailto:', '')
                    firm_data['emails'] = email
            else:
                # Fallback: try to find email in any element
                email_elem = soup.select_one('a[href^="mailto:"]')
                if email_elem:
                    email_href = email_elem.get('href')
                    if email_href and email_href.startswith('mailto:'):
                        email = email_href.replace('mailto:', '')
                        firm_data['emails'] = email
            
            # Extract addresses from the specific structure (multiple addresses possible)
            address_elems = soup.select('[id*="-locations"] .placeholder')
            addresses = []
            for addr_elem in address_elems:
                addr_text = addr_elem.get_text(strip=True)
                if addr_text and len(addr_text) > 5:  # Reasonable address length
                    addresses.append(addr_text)
            
            if addresses:
                firm_data['address'] = addresses if len(addresses) > 1 else addresses[0]
                
                # Extract zipcode from addresses
                zipcode = None
                if isinstance(addresses, list):
                    # Try to extract zipcode from each address
                    for addr in addresses:
                        zipcode = zipcode_utils.extract_zipcode(addr)
                        if zipcode:
                            break
                else:
                    # Single address
                    zipcode = zipcode_utils.extract_zipcode(addresses)
                
                if zipcode:
                    firm_data['zip_code'] = zipcode
                    logger.info(f"✅ Extracted zipcode: {zipcode} from address")
                else:
                    logger.debug("No valid zipcode found in addresses")
                    
            else:
                # Fallback: try to find address in any element
                address_elem = soup.select_one('[class*="location"], [class*="address"]')
                if address_elem:
                    addr_text = address_elem.get_text(strip=True)
                    if addr_text and len(addr_text) > 5:
                        firm_data['address'] = addr_text
                        
                        # Extract zipcode from fallback address
                        zipcode = zipcode_utils.extract_zipcode(addr_text)
                        if zipcode:
                            firm_data['zip_code'] = zipcode
                            logger.info(f"✅ Extracted zipcode: {zipcode} from fallback address")
                        else:
                            logger.debug("No valid zipcode found in fallback address")
            
            # Extract social links from the specific structure
            social_links = {
                'linkedin': [],
                'facebook': [],
                'instagram': [],
                'twitter': [],
                'pinterest': [],
                'youtube': [],
                'other': []
            }
            social_elems = soup.select('[id*="-social_links"] a[href*="http"]')
            
            for social_elem in social_elems:
                href = social_elem.get('href', '')
                # Remove utm_source parameter if present
                if '?utm_source=' in href:
                    href = href.split('?utm_source=')[0]
                
                # Determine social platform from URL and add to appropriate list
                if 'linkedin.com' in href and href not in social_links['linkedin']:
                    social_links['linkedin'].append(href)
                elif ('twitter.com' in href or 'x.com' in href) and href not in social_links['twitter']:
                    social_links['twitter'].append(href)
                elif 'facebook.com' in href and href not in social_links['facebook']:
                    social_links['facebook'].append(href)
                elif 'instagram.com' in href and href not in social_links['instagram']:
                    social_links['instagram'].append(href)
                elif 'pinterest.com' in href and href not in social_links['pinterest']:
                    social_links['pinterest'].append(href)
                elif ('youtube.com' in href or 'youtu.be' in href) and href not in social_links['youtube']:
                    social_links['youtube'].append(href)
                elif 'behance.net' in href and href not in social_links['other']:
                    social_links['other'].append(href)
                elif 'dribbble.com' in href and href not in social_links['other']:
                    social_links['other'].append(href)
                else:
                    # Check if this is actually a social media link before adding to other
                    is_social = any(social in href for social in [
                        'behance.net', 'dribbble.com', 'tiktok.com', 'snapchat.com', 
                        'tumblr.com', 'reddit.com', 'medium.com', 'github.com',
                        'facebook', 'instagram', 'twitter', 'linkedin', 'pinterest', 'youtube', 'x.com'
                    ])
                    if is_social and href not in social_links['other']:
                        social_links['other'].append(href)
                
            firm_data['social_links'] = social_links
            
            # Fallback: try to find social links in any element if none found in specific structure
            if not any(social_links.values()):
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    href = link.get('href', '').lower()
                    if '?utm_source=' in href:
                        href = href.split('?utm_source=')[0]
                    
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
                    elif 'behance.net' in href and href not in social_links['other']:
                        social_links['other'].append(link.get('href'))
                    elif 'dribbble.com' in href and href not in social_links['other']:
                        social_links['other'].append(link.get('href'))
                    else:
                        # Check if this is actually a social media link before adding to other
                        is_social = any(social in href for social in [
                            'behance.net', 'dribbble.com', 'tiktok.com', 'snapchat.com', 
                            'tumblr.com', 'reddit.com', 'medium.com', 'github.com',
                            'facebook', 'instagram', 'twitter', 'linkedin', 'pinterest', 'youtube', 'x.com'
                        ])
                        if is_social and href not in social_links['other']:
                            social_links['other'].append(link.get('href'))
                
                firm_data['social_links'] = social_links
            
            # Extract professional type from the specific structure
            company_type_elem = soup.select_one('[id*="-company_type"] span')
            if company_type_elem:
                professional_type = company_type_elem.get_text(strip=True)
                if professional_type:
                    firm_data['professional_type'] = professional_type
            else:
                # Fallback: set default based on URL
                if '/firms/' in firm_url:
                    firm_data['professional_type'] = 'Architecture Firm'
            
            # Validate extracted data
            firm_data = self._validate_extracted_data(firm_data)
            
            logger.info(f"Extracted firm data: {firm_data.get('name', 'Unknown')}")
            return firm_data
            
        except Exception as e:
            logger.error(f"Error extracting firm data: {e}")
            return firm_data
    
    def _validate_extracted_data(self, firm_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and classify extracted email and phone data using centralized email service"""
        try:
            # Use centralized email service for validation and classification
            if 'emails' in firm_data and firm_data['emails']:
                email = firm_data['emails']
                validation_result = self.email_service.validate_email(email)
                
                if validation_result.status == EmailValidationStatus.VALID:
                    logger.info(f"✅ Valid email: {email}")
                    
                    # Classify the email into personal or business
                    classified_emails = self.email_service.classify_emails([email])
                    
                    # Store classified emails in JSON format
                    email_data = {
                        "personal": classified_emails.get('personal', []),
                        "business": classified_emails.get('business', [])
                    }
                    
                    # Log classification results
                    if email_data['personal']:
                        logger.info(f"📧 Classified as personal email: {email}")
                    elif email_data['business']:
                        logger.info(f"📧 Classified as business email: {email}")
                    else:
                        logger.warning(f"📧 Email not classified: {email}")
                    
                    # Replace single email with classified JSON structure
                    firm_data['emails'] = email_data
                else:
                    logger.warning(f"❌ Invalid email detected: {email} - {validation_result.sub_status}")
                    # Remove invalid email from final results
                    firm_data.pop('emails', None)
            else:
                # Remove email field if not present or empty
                firm_data.pop('emails', None)
            
            # Validate phone number - only add to final results if valid US number
            if 'phone' in firm_data and firm_data['phone']:
                phone = firm_data['phone']
                formatted_phone = validate_and_format_us_phone(phone)
                
                if formatted_phone:
                    firm_data['phone'] = formatted_phone
                    logger.info(f"✅ Valid US phone formatted: {phone} -> {formatted_phone}")
                    # Keep valid US phone in final results
                else:
                    logger.warning(f"❌ Invalid or non-US phone number: {phone}")
                    # Remove invalid phone from final results
                    firm_data.pop('phone', None)
            else:
                # Remove phone field if not present or empty
                firm_data.pop('phone', None)
            
            return firm_data
            
        except Exception as e:
            logger.error(f"Error validating extracted data: {e}")
            # Remove email and phone from final results if validation fails
            firm_data.pop('emails', None)
            firm_data.pop('phone', None)
            return firm_data
    
    async def _extract_total_count_and_calculate_pages(self, page: Page) -> tuple[Optional[int], int]:
        """Extract total count from the page and calculate pages needed"""
        try:
            # Wait for the count element to be present
            await page.wait_for_selector('h1.fs-l.mb-base', timeout=10000)
            
            # Extract the count text
            count_text = await page.evaluate("""
                () => {
                    const h1Element = document.querySelector('h1.fs-l.mb-base');
                    if (h1Element) {
                        return h1Element.textContent;
                    }
                    return null;
                }
            """)
            
            if count_text:
                logger.info(f"📋 Found count text: {count_text}")
                
                # Extract number from text like "Displaying 2,930 Architecture / Design Firms in United States"
                import re
                number_match = re.search(r'Displaying\s+([\d,]+)', count_text)
                
                if number_match:
                    # Remove commas and convert to integer
                    total_count = int(number_match.group(1).replace(',', ''))
                    
                    # Try to get actual items per page by counting firm URLs on current page
                    current_page_urls = await self._extract_firm_urls_from_page(page)
                    items_per_page = len(current_page_urls) if current_page_urls else 10
                    logger.info(f"📄 Actual items per page (from current page): {items_per_page}")
                    
                    # If we couldn't get items from current page, use a reasonable default
                    if items_per_page == 0:
                        items_per_page = 10
                        logger.info(f"📄 Using default items per page: {items_per_page}")
                    
                    logger.info(f"✅ Extracted total count: {total_count:,}")
                    return total_count, items_per_page
                else:
                    logger.warning(f"❌ Could not extract number from count text: {count_text}")
            else:
                logger.warning("❌ Could not find count element on page")
                
        except Exception as e:
            logger.error(f"Error extracting total count: {e}")
        
        return None, 10  # Default to 10 items per page if extraction fails
    
    async def _handle_cookie_consent(self, page: Page):
        """Handle cookie consent banner by accepting cookies"""
        try:
            logger.info("🍪 Checking for cookie consent banner...")
            
            # Wait a bit for the banner to load
            await asyncio.sleep(2)
            
            # Try multiple approaches to handle the OneTrust cookie banner
            cookie_handled = False
            
            # Approach 1: Click the "Accept All Cookies" button
            accept_selectors = [
                '#onetrust-accept-btn-handler',
                'button[id*="accept"]',
                'button:has-text("Accept All Cookies")',
                'button:has-text("Accept")',
                '[id*="accept"]'
            ]
            
            for selector in accept_selectors:
                try:
                    # Wait for the button to be visible
                    await page.wait_for_selector(selector, timeout=5000)
                    button = await page.query_selector(selector)
                    if button and await button.is_visible():
                        await button.click()
                        logger.info(f"✅ Clicked cookie accept button: {selector}")
                        cookie_handled = True
                        await asyncio.sleep(2)  # Wait for banner to disappear
                        break
                except Exception as e:
                    logger.debug(f"Cookie selector {selector} not found or not clickable: {e}")
                    continue
            
            # Also try to remove the cookie banner div entirely via JavaScript
            try:
                await page.evaluate("""
                    // Remove cookie consent SDK
                    const cookieBanner = document.getElementById('onetrust-consent-sdk');
                    if (cookieBanner) {
                        cookieBanner.remove();
                        console.log('Removed cookie consent banner');
                    }
                    
                    // Remove any overlay divs that might be blocking content
                    const overlays = document.querySelectorAll('[style*="z-index: 2147483"]');
                    overlays.forEach(overlay => overlay.remove());
                """)
                logger.info("✅ Removed cookie banner via JavaScript")
            except Exception as e:
                logger.debug(f"Error removing cookie banner via JS: {e}")
                
        except Exception as e:
            logger.debug(f"Error handling cookie consent: {e}")
    
    async def _log_network_request(self, route):
        """Log network requests to understand what's being loaded"""
        request = route.request
        logger.debug(f"🌐 Network request: {request.method} {request.url}")
        await route.continue_()

    async def set_page_headers(self, page: Page):
        """Set common HTTP headers for a page"""
        await page.set_extra_http_headers({
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })

    async def _wait_for_content_load_with_fallback(self, page: Page) -> bool:
        """Wait for content to load with comprehensive loader detection"""
        try:
            logger.info("⏳ Waiting for initial page content to load...")
            
            # Use the same comprehensive loader detection as the load more functionality
            loaders_disappeared = await self._wait_for_loaders_to_disappear(page, timeout=20)
            
            if loaders_disappeared:
                logger.info("✅ All initial loaders have disappeared")
            else:
                logger.warning("⚠️ Some loaders may still be visible, but continuing...")
            
            # Wait for content to be present
            await asyncio.sleep(2)
            
            # Check if page has content
            content = await page.content()
            if len(content) > 10000:  # Basic content check
                logger.info("✅ Content appears to be loaded")
                return True
            else:
                logger.warning("⚠️ Page content seems minimal")
                return False
                
        except Exception as e:
            logger.error(f"Error waiting for content: {e}")
            return False
