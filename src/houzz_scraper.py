"""Houzz Scraper Module for the Houzz Lead Generation Pipeline.

Optimized scraper inheriting from BaseScraper for consistent behavior and reduced code duplication.
Uses Playwright for dynamic content handling and includes comprehensive data extraction.
"""

import asyncio
import re
import json
import aiohttp
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin
from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup
from loguru import logger
import random
from datetime import datetime

from .models import ProfessionalProfile
from .base_scraper import BaseScraper
from .common_utils import WebUtils, StateManager, zipcode_utils
from .url_cleaner import get_clean_target_url
from .phone_formatter import extract_and_format_phone
from config.config import config

# Professional type mapping for consistent naming
PROFESSIONAL_TYPE_MAPPING = {
    'interior-designer': 'Interior Designer',
    'architect': 'Architect',
    'general-contractor': 'General Contractor',
    'home-builders': 'Home Builder',
    'design-build': 'Design-Build',
    'landscape-architect': 'Landscape Architect',
    'kitchen-and-bath': 'Kitchen & Bath Designer'
}

class HouzzScraper(BaseScraper):
    """Production-ready Houzz scraper inheriting from BaseScraper"""
    
    def __init__(self, database_manager=None):
        super().__init__(database_manager)
        # Platform-specific initialization
        logger.info("HouzzScraper initialized with BaseScraper functionality")
    
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
        """Create a new browser page or rotate proxy and recreate if needed"""
        # Use BaseScraper's optimized page creation
        return await super().create_or_rotate_page(page)

    # Removed duplicated methods - now handled by BaseScraper:
    # set_page_headers, _handle_network_error, _handle_network_success, _adaptive_sleep
    
    
    async def get_state_professionals_direct(self, state: str, professional_type: str, max_pages: int = 50, start_page: int = 1, max_retries: int = 3) -> List[ProfessionalProfile]:
        """Extract professional data directly from listing pages using city-based URLs with retry logic"""
        professionals = []
        page = None

        try:
            # Get the profession parameter for the URL
            prof_param = config.PROFESSIONAL_TYPE_PARAMS.get(professional_type)
            if not prof_param:
                logger.error(f"No URL parameter found for profession type: {professional_type}")
                return professionals
            
            # Get cities for this state
            city_regions = config.STATE_CITY_REGIONS.get(state, [])
            if not city_regions:
                logger.error(f"No cities found for state: {state}")
                return professionals
            
            # Get the display name for this professional type
            display_professional_type = PROFESSIONAL_TYPE_MAPPING.get(professional_type, professional_type.title())
            
            for city_index, (city, region_id) in enumerate(city_regions):
                # Close previous page if exists
                if page:
                    await page.close()

                # Create or rotate page for this city
                page = await self.create_or_rotate_page()
                logger.info(f"✅ Created or rotated new page for {city}")

                # Use city-based URL format: /professionals/kitchen-and-bath/chicago-il-us-probr0-bo~t_11790~r_4887398
                base_url = f"{config.HOUZZ_PROFESSIONALS_URL}/{professional_type}/{city}-probr0-bo~{prof_param}~{region_id}"
                logger.info(f"Scraping {professional_type} in {city} ({state}): {base_url}")
                
                # Track pages scraped for this city
                pages_scraped_this_city = 0
                
                # Handle case where max_pages might be None
                max_pages_to_scrape = max_pages if max_pages is not None else 100
                for page_num in range(start_page, start_page + max_pages_to_scrape):
                    fi_param = (page_num -1) * 15
                    url = f"{base_url}?fi={fi_param}"
                    
                    if self.state_manager.is_url_completed(url, platform="houzz"):
                        logger.info(f"Skipping already completed URL: {url}")
                        continue
                    
                    last_exception = None

                    for attempt in range(max_retries):
                        try:
                            if attempt > 0:
                                logger.info(f"🔄 Retry attempt {attempt + 1}/{max_retries} for: {url}")
                            
                            # Increment request count and check for proxy rotation
                            self.request_count += 1
                            page = await self.create_or_rotate_page(page)
                            
                            # Add connection check and better error handling
                            try:
                                await page.goto(url, wait_until='domcontentloaded', timeout=config.TIMEOUT * 1000)
                                # Mark success for adaptive delay management
                                self._handle_network_success()
                            except Exception as goto_error:
                                # Handle network error for adaptive delay management
                                self._handle_network_error()
                                
                                # Check for specific network/connection errors that require context reset
                                error_str = str(goto_error).lower()
                                network_errors = [
                                    'net::err_network_changed', 'connection closed', 'connection reset',
                                    'timeout', 'err_internet_disconnected', 'err_network_access_denied',
                                    'err_proxy_connection_failed', 'connection refused', 
                                    'driver session', 'browser context', 'page closed'
                                ]
                                
                                if any(err in error_str for err in network_errors):
                                    logger.warning(f"🔄 Network error #{self.network_error_count} (consecutive: {self.consecutive_errors}): {goto_error}")
                                    
                                    # Use adaptive delay before recovery attempts
                                    await self._adaptive_sleep(3.0)  # Min 3 second delay
                                    
                                    # Aggressive recovery: close everything and start fresh
                                    recovery_success = False
                                    for recovery_attempt in range(2):  # Try recovery twice
                                        try:
                                            logger.info(f"🔧 Recovery attempt {recovery_attempt + 1}/2")
                                            
                                            # Close current page and context
                                            if page and not page.is_closed():
                                                await page.close()
                                            if self.current_context:
                                                await self.current_context.close()
                                            self.current_context = None
                                            
                                            # Wait a bit for cleanup
                                            await asyncio.sleep(2)
                                            
                                            # Force proxy rotation if using proxies
                                            if self.proxy_list:
                                                self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
                                                logger.info(f"🔄 Forced proxy rotation to index {self.current_proxy_index}")
                                            
                                            # Create new page with fresh context
                                            page = await self.create_or_rotate_page()
                                            
                                            # Use adaptive delay before retrying
                                            await self._adaptive_sleep(5.0)  # Min 5 second delay before retry
                                            
                                            # Retry the navigation with new context
                                            await page.goto(url, wait_until='domcontentloaded', timeout=config.TIMEOUT * 1000)
                                            logger.info(f"✅ Successfully recovered from network error")
                                            self._handle_network_success()  # Mark recovery success
                                            recovery_success = True
                                            break
                                            
                                        except Exception as recovery_error:
                                            logger.warning(f"❌ Recovery attempt {recovery_attempt + 1} failed: {recovery_error}")
                                            if recovery_attempt == 1:  # Last attempt
                                                logger.error(f"🚨 All recovery attempts failed, re-raising original error")
                                                raise goto_error
                                            await self._adaptive_sleep(8.0)  # Longer delay before next recovery attempt
                                    
                                    if not recovery_success:
                                        raise goto_error
                                        
                                else:
                                    # Non-network error, re-raise immediately
                                    raise goto_error
                            
                            await asyncio.sleep(random.uniform(2, 4))
                            
                            # Extract professionals directly from the listing page
                            page_professionals = await self.extract_professionals_from_listing_page(page, professional_type)
                            # If no professionals found, we've likely reached the end
                            if not page_professionals:
                                logger.info(f"No more professionals found on page {page_num} for {city}/{professional_type}")
                                break
                            
                            # Add professional type info to each profile using consistent mapping
                            for prof in page_professionals:
                                if not prof.professional_type or prof.professional_type.strip() == '':
                                    prof.professional_type = display_professional_type
                                    logger.debug(f"Set professional_type to '{display_professional_type}' for profile: {prof.name}")
                                else:
                                    logger.debug(f"Profile {prof.name} already has professional_type: '{prof.professional_type}'")
                            
                            professionals.extend(page_professionals)
                            logger.info(f"Extracted {len(page_professionals)} professionals from page {page_num}")
                            
                            # Show sample of extracted data
                            if page_professionals:
                                sample_names = [p.name for p in page_professionals[:3] if p.name]
                                logger.info(f"Sample professionals: {sample_names}")
                            
                            # Mark URL as completed
                            self.state_manager.mark_url_completed(url, platform="houzz")

                            # Increment pages scraped count for this city
                            pages_scraped_this_city += 1
                            
                            # Log the number of pages scraped for this profession in this state
                            logger.info(f"Successfully scraped page {page_num} for {city}/{professional_type} ({state})")
                            
                            # Adaptive delay between pages
                            await self._adaptive_sleep(3.0)
                            
                            break  # Break retry loop on success
                        except Exception as e:
                            last_exception = e
                            logger.warning(f"Error scraping page {page_num} for {city}/{professional_type} on attempt {attempt + 1}: {e}")
                            
                            if attempt < max_retries - 1:
                                retry_delay = (2 ** attempt) + random.uniform(2, 4)
                                logger.info(f"Retrying in {retry_delay:.1f} seconds...")
                                await asyncio.sleep(retry_delay)
                            else:
                                logger.error(f"❌ Final attempt failed: {url} due to {e}")
                                logger.debug("Attempting to reset the context to prevent future errors.")
                                try:
                                    if page:
                                        await page.close()
                                    if self.current_context:
                                        await self.current_context.close()
                                    # Reset proxy and context
                                    proxy = self.get_next_proxy()
                                    self.current_context = await self.browser.new_context(proxy=proxy)
                                except Exception as context_error:
                                    logger.error(f"Error resetting context: {context_error}")
                                self.state_manager.mark_url_failed(url, platform="houzz")
                                break

                # Log summary after completing this city
                logger.info(f"📊 Completed scraping {city} ({state}) for {professional_type}: scraped {pages_scraped_this_city} pages successfully")
                
                # Delay between cities
                await asyncio.sleep(random.uniform(2, 4))
        finally:
            if page:
                await page.close()

        return professionals
    
    async def get_state_professionals_direct_filtered(self, state: str, professional_type: str, max_pages: int = 50, start_page: int = 1, max_retries: int = 3, target_cities: List[str] = None) -> List[ProfessionalProfile]:
        """Extract professional data directly from listing pages using city-based URLs with retry logic, filtered to specific cities"""
        professionals = []
        page = None

        try:
            # Get the profession parameter for the URL
            prof_param = config.PROFESSIONAL_TYPE_PARAMS.get(professional_type)
            if not prof_param:
                logger.error(f"No URL parameter found for profession type: {professional_type}")
                return professionals
            
            # Get cities for this state
            city_regions = config.STATE_CITY_REGIONS.get(state, [])
            if not city_regions:
                logger.error(f"No cities found for state: {state}")
                return professionals
            
            # Filter cities based on target_cities
            if target_cities:
                # Convert target_cities to lowercase for case-insensitive matching
                target_cities_lower = [city.lower() for city in target_cities]
                
                # Filter city_regions to only include requested cities
                filtered_city_regions = []
                for city_info, region_id in city_regions:
                    # Extract city name from city_info (e.g., "cheyenne-wy-us" -> "cheyenne")
                    city_parts = city_info.split('-')
                    if len(city_parts) > 2:
                        city_name = ' '.join(city_parts[:-2])
                    else:
                        city_name = ' '.join(city_parts[:-1])
                    
                    if city_name.lower() in target_cities_lower:
                        filtered_city_regions.append((city_info, region_id))
                        logger.info(f"✅ Added {city_name} to filtered cities for {state}")
                
                if not filtered_city_regions:
                    logger.warning(f"No matching cities found for {state} with target cities: {target_cities}")
                    return professionals
                
                city_regions = filtered_city_regions
                logger.info(f"Filtered to {len(city_regions)} cities: {[city.split('-')[0] for city, _ in city_regions]}")
            
            # Get the display name for this professional type
            display_professional_type = PROFESSIONAL_TYPE_MAPPING.get(professional_type, professional_type.title())
            
            for city_index, (city, region_id) in enumerate(city_regions):
                # Close previous page if exists
                if page:
                    await page.close()

                # Create or rotate page for this city
                page = await self.create_or_rotate_page()
                logger.info(f"✅ Created or rotated new page for {city}")

                # Use city-based URL format: /professionals/kitchen-and-bath/chicago-il-us-probr0-bo~t_11790~r_4887398
                base_url = f"{config.HOUZZ_PROFESSIONALS_URL}/{professional_type}/{city}-probr0-bo~{prof_param}~{region_id}"
                logger.info(f"Scraping {professional_type} in {city} ({state}): {base_url}")
                
                # Track pages scraped for this city
                pages_scraped_this_city = 0
                
                # Handle case where max_pages might be None
                max_pages_to_scrape = max_pages if max_pages is not None else 100
                for page_num in range(start_page, start_page + max_pages_to_scrape):
                    fi_param = (page_num -1) * 15
                    url = f"{base_url}?fi={fi_param}"
                    
                    if self.state_manager.is_url_completed(url, platform="houzz"):
                        logger.info(f"Skipping already completed URL: {url}")
                        continue
                    
                    last_exception = None

                    for attempt in range(max_retries):
                        try:
                            if attempt > 0:
                                logger.info(f"🔄 Retry attempt {attempt + 1}/{max_retries} for: {url}")
                            
                            # Increment request count and check for proxy rotation
                            self.request_count += 1
                            page = await self.create_or_rotate_page(page)
                            
                            # Add connection check and better error handling
                            try:
                                await page.goto(url, wait_until='domcontentloaded', timeout=config.TIMEOUT * 1000)
                                # Mark success for adaptive delay management
                                self._handle_network_success()
                            except Exception as goto_error:
                                # Handle network error for adaptive delay management
                                self._handle_network_error()
                                
                                # Check for specific network/connection errors that require context reset
                                error_str = str(goto_error).lower()
                                network_errors = [
                                    'net::err_network_changed', 'connection closed', 'connection reset',
                                    'timeout', 'err_internet_disconnected', 'err_network_access_denied',
                                    'err_proxy_connection_failed', 'connection refused', 
                                    'driver session', 'browser context', 'page closed'
                                ]
                                
                                if any(err in error_str for err in network_errors):
                                    logger.warning(f"🔄 Network error #{self.network_error_count} (consecutive: {self.consecutive_errors}): {goto_error}")
                                    
                                    # Use adaptive delay before recovery attempts
                                    await self._adaptive_sleep(3.0)  # Min 3 second delay
                                    
                                    # Aggressive recovery: close everything and start fresh
                                    recovery_success = False
                                    for recovery_attempt in range(2):  # Try recovery twice
                                        try:
                                            logger.info(f"🔧 Recovery attempt {recovery_attempt + 1}/2")
                                            
                                            # Close current page and context
                                            if page and not page.is_closed():
                                                await page.close()
                                            if self.current_context:
                                                await self.current_context.close()
                                            self.current_context = None
                                            
                                            # Wait a bit for cleanup
                                            await asyncio.sleep(2)
                                            
                                            # Force proxy rotation if using proxies
                                            if self.proxy_list:
                                                self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
                                                logger.info(f"🔄 Forced proxy rotation to index {self.current_proxy_index}")
                                            
                                            # Create new page with fresh context
                                            page = await self.create_or_rotate_page()
                                            
                                            # Use adaptive delay before retrying
                                            await self._adaptive_sleep(5.0)  # Min 5 second delay before retry
                                            
                                            # Retry the navigation with new context
                                            await page.goto(url, wait_until='domcontentloaded', timeout=config.TIMEOUT * 1000)
                                            logger.info(f"✅ Successfully recovered from network error")
                                            self._handle_network_success()  # Mark recovery success
                                            recovery_success = True
                                            break
                                            
                                        except Exception as recovery_error:
                                            logger.warning(f"❌ Recovery attempt {recovery_attempt + 1} failed: {recovery_error}")
                                            if recovery_attempt == 1:  # Last attempt
                                                logger.error(f"🚨 All recovery attempts failed, re-raising original error")
                                                raise goto_error
                                            await self._adaptive_sleep(8.0)  # Longer delay before next recovery attempt
                                    
                                    if not recovery_success:
                                        raise goto_error
                                        
                                else:
                                    # Non-network error, re-raise immediately
                                    raise goto_error
                            
                            await asyncio.sleep(random.uniform(2, 4))
                            
                            # Extract professionals directly from the listing page
                            page_professionals = await self.extract_professionals_from_listing_page(page, professional_type)
                            # If no professionals found, we've likely reached the end
                            if not page_professionals:
                                logger.info(f"No more professionals found on page {page_num} for {city}/{professional_type}")
                                break
                            
                            # Add professional type info to each profile using consistent mapping
                            for prof in page_professionals:
                                if not prof.professional_type or prof.professional_type.strip() == '':
                                    prof.professional_type = display_professional_type
                                    logger.debug(f"Set professional_type to '{display_professional_type}' for profile: {prof.name}")
                                else:
                                    logger.debug(f"Profile {prof.name} already has professional_type: '{prof.professional_type}'")
                            
                            professionals.extend(page_professionals)
                            logger.info(f"Extracted {len(page_professionals)} professionals from page {page_num}")
                            
                            # Show sample of extracted data
                            if page_professionals:
                                sample_names = [p.name for p in page_professionals[:3] if p.name]
                                logger.info(f"Sample professionals: {sample_names}")
                            
                            # Mark URL as completed
                            self.state_manager.mark_url_completed(url, platform="houzz")

                            # Increment pages scraped count for this city
                            pages_scraped_this_city += 1
                            
                            # Log the number of pages scraped for this profession in this state
                            logger.info(f"Successfully scraped page {page_num} for {city}/{professional_type} ({state})")
                            
                            # Adaptive delay between pages
                            await self._adaptive_sleep(3.0)
                            
                            break  # Break retry loop on success
                        except Exception as e:
                            last_exception = e
                            logger.warning(f"Error scraping page {page_num} for {city}/{professional_type} on attempt {attempt + 1}: {e}")
                            
                            if attempt < max_retries - 1:
                                retry_delay = (2 ** attempt) + random.uniform(2, 4)
                                logger.info(f"Retrying in {retry_delay:.1f} seconds...")
                                await asyncio.sleep(retry_delay)
                            else:
                                logger.error(f"❌ Final attempt failed: {url} due to {e}")
                                logger.debug("Attempting to reset the context to prevent future errors.")
                                try:
                                    if page:
                                        await page.close()
                                    if self.current_context:
                                        await self.current_context.close()
                                    # Reset proxy and context
                                    proxy = self.get_next_proxy()
                                    self.current_context = await self.browser.new_context(proxy=proxy)
                                except Exception as context_error:
                                    logger.error(f"Error resetting context: {context_error}")
                                self.state_manager.mark_url_failed(url, platform="houzz")
                                break

                # Log summary after completing this city
                logger.info(f"📊 Completed scraping {city} ({state}) for {professional_type}: scraped {pages_scraped_this_city} pages successfully")
                
                # Delay between cities
                await asyncio.sleep(random.uniform(2, 4))
        finally:
            if page:
                await page.close()

        return professionals
    
    
    async def extract_professionals_from_listing_page(self, page: Page, professional_type: str = '') -> List[ProfessionalProfile]:
        """Extract professional data directly from listing page (Apify approach)"""
        professionals = []
        
        try:
            # Wait for professional listings to load
            wait_selectors = [
                '.hz-pro-search-results__item',
                '[class*="ProSearchResultsV2__StyledListItem"]',
                'li[class*="pro"]',
                '[class*="professional"]',
                '[class*="listing"]',
                'article',
                '[class*="BusinessDetails__StyledCell"]'
            ]
            
            waited = False
            for selector in wait_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=10000)
                    waited = True
                    logger.debug(f"Successfully waited for selector: {selector}")
                    break
                except:
                    continue
            
            if not waited:
                logger.warning("Could not find any professional listing elements")
                return professionals
            
            # Get page content for parsing
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find professional listing containers
            professional_containers = []

            # Try different selectors for professional cards
            container_selectors = [
                '.hz-pro-search-results__item',
                '[class*="ProSearchResultsV2__StyledListItem"]',
                'li[class*="pro"]',
                'article[class*="professional"]',
                '[class*="professional-card"]',
                '[class*="listing"]',
            ]
            
            for selector in container_selectors:
                containers = soup.select(selector)
                if containers:
                    professional_containers = containers
                    logger.debug(f"Found {len(containers)} professionals using selector: {selector}")
                    break
            
            # Extract data from each professional container
            for container in professional_containers:
                try:
                    profile = await self.extract_professional_from_container(container, page, professional_type)

                    if profile and profile.name:  # Only add if we got a name
                        professionals.append(profile)
                        logger.debug(f"Extracted professional: {profile.name}")
                except Exception as e:
                    logger.debug(f"Error extracting professional from container: {e}")
                    continue
            logger.info(f"Successfully extracted {len(professionals)} professionals from listing page")
            
        except Exception as e:
            logger.warning(f"Error extracting professionals from listing page: {e}")
        
        return professionals
    
    async def extract_professional_from_container(self, container, page: Page, professional_type: str = '') -> Optional[ProfessionalProfile]:
        """Extract professional data from a single container element by navigating to the profile page."""
        try:
            data = None
            script_tag = container.select_one('script[type="application/ld+json"]')

            if script_tag:
                try:
                    data = json.loads(script_tag.string)                           
                except json.JSONDecodeError as e:
                    logger.debug(f"JSON decode error: {e}")

            # First, extract the profile URL from the container
            link_elem = container.select_one('a[href*="pfvwus-pf~"]')
            if not link_elem or not link_elem.get('href'):
                logger.debug("No profile link found in container")
                return None

            profile_url = urljoin(config.HOUZZ_BASE_URL, link_elem.get('href'))
            
            # Navigate to the profile page to get all details
            profile = await self.scrape_professional_profile(profile_url, page, data, professional_type)

            return profile

        except Exception as e:
            logger.debug(f"Error extracting professional from container: {e}")
            return None

    
    async def scrape_professional_profile(self, profile_url: str, page: Page, data = None, professional_type: str = '', max_retries: int = 3) -> Optional[ProfessionalProfile]:
        """Scrape individual professional profile with retry logic for failures, reusing the provided page."""
        if self.state_manager.is_url_completed(profile_url, platform="houzz"):
            logger.info(f"Skipping already scraped profile: {profile_url}")
            return None
        
        # Get the display name for this professional type
        display_professional_type = PROFESSIONAL_TYPE_MAPPING.get(professional_type, professional_type.title())
        
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"🔄 Retry attempt {attempt + 1}/{max_retries} for: {profile_url}")
                
                # Increment request count and check for proxy rotation
                self.request_count += 1
                
                # Check if page is closed and recreate if needed
                try:
                    if page.is_closed():
                        page = await self.create_or_rotate_page(None)
                    else:
                        page = await self.create_or_rotate_page(page)
                except Exception:
                    # If page check fails, create a new one
                    page = await self.create_or_rotate_page(None)
                
                # Add network error handling for profile scraping
                try:
                    await page.goto(profile_url, wait_until='networkidle', timeout=config.TIMEOUT * 1000)
                except Exception as goto_error:
                    # Check for specific network errors that require context reset
                    error_str = str(goto_error).lower()
                    if any(err in error_str for err in ['net::err_network_changed', 'connection', 'timeout', 'tunnel_connection_failed', 'proxy']):
                        logger.warning(f"Network/proxy error detected in profile scraping, forcing context rotation: {goto_error}")
                        
                        # Handle network error
                        self._handle_network_error()
                        
                        # Force context rotation by closing current context
                        try:
                            if page:
                                await page.close()
                            if self.current_context:
                                await self.current_context.close()
                            self.current_context = None
                            
                            # Create new page with fresh context
                            page = await self.create_or_rotate_page()
                            # Retry the navigation with new context
                            await page.goto(profile_url, wait_until='networkidle', timeout=config.TIMEOUT * 1000)
                        except Exception as retry_error:
                            logger.error(f"Failed to recover from network error in profile scraping: {retry_error}")
                            # Try without proxy as last resort
                            try:
                                logger.warning("Attempting fallback without proxy")
                                if self.current_context:
                                    await self.current_context.close()
                                self.current_context = await self.browser.new_context(
                                    user_agent=self.web_utils.get_random_user_agent()
                                )
                                page = await self.current_context.new_page()
                                await self.set_page_headers(page)
                                await page.goto(profile_url, wait_until='networkidle', timeout=config.TIMEOUT * 1000)
                                logger.info("Successfully connected without proxy as fallback")
                            except Exception as fallback_error:
                                logger.error(f"Even fallback without proxy failed: {fallback_error}")
                                raise goto_error
                    else:
                        raise goto_error
                
                await asyncio.sleep(random.uniform(1, 2))
                
                # Extract profile data - pass the professional_type to ensure it's set during extraction
                profile = await self.extract_profile_data(page, profile_url, data, display_professional_type)
                print('profile', profile)
                # Double-check and set professional_type if still missing
                if profile and (not profile.professional_type or profile.professional_type.strip() == ''):
                    profile.professional_type = display_professional_type
                    logger.debug(f"Set professional_type to '{display_professional_type}' for profile: {profile.name}")
                elif profile and profile.professional_type:
                    logger.debug(f"Profile {profile.name} already has professional_type: '{profile.professional_type}'")
                
                if profile:
                    # Success! Mark as completed and return
                    self.state_manager.mark_url_completed(profile_url, platform="houzz")
                    if attempt > 0:
                        logger.info(f"✅ Successfully scraped profile on retry attempt {attempt + 1}: {profile.name} - {profile_url}")
                    else:
                        logger.info(f"Successfully scraped profile: {profile.name} - {profile_url}")
                    return profile
                else:
                    # No data extracted but no exception - this is a parsing issue, don't retry
                    logger.warning(f"No data extracted from profile (likely parsing issue): {profile_url}")
                    self.state_manager.mark_url_failed(profile_url, platform="houzz")
                    return None
            
            except Exception as e:
                last_exception = e
                error_msg = f"Error scraping profile (attempt {attempt + 1}/{max_retries}): {profile_url} - {e}"
                
                if attempt < max_retries - 1:
                    # Not the last attempt, prepare for retry
                    logger.warning(f"⚠️ {error_msg}")
                    retry_delay = (2 ** attempt) + random.uniform(2, 4)  # Exponential backoff: 2-6s, 4-8s
                    logger.info(f"Retrying in {retry_delay:.1f} seconds...")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    # Last attempt failed
                    logger.error(f"❌ Final attempt failed: {error_msg}")
                    break
        
        # All attempts failed
        logger.error(f"🚫 Failed to scrape profile after {max_retries} attempts: {profile_url}")
        if last_exception:
            logger.error(f"Final error: {last_exception}")
        self.state_manager.mark_url_failed(profile_url, platform="houzz")
        return None
    
    async def resolve_redirect(self, url: str) -> Optional[str]:
        """Resolve redirect to get the final URL using aiohttp"""
        try:
            # Set up proxy if available
            proxy = None
            if self.proxy_list:
                proxy_info = self.get_next_proxy()
                if proxy_info:
                    proxy = proxy_info['server']
                    # aiohttp expects proxy auth in URL format
                    username = proxy_info['username']
                    password = proxy_info['password']
                    proxy = proxy.replace('http://', f'http://{username}:{password}@')
            
            connector = aiohttp.TCPConnector(limit=10)
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    'User-Agent': self.web_utils.get_random_user_agent()
                }
            ) as session:
                async with session.head(
                    url, 
                    allow_redirects=True,
                    proxy=proxy
                ) as response:
                    final_url = str(response.url)
                    logger.debug(f"Resolved {url} -> {final_url}")
                    return final_url
                    
        except Exception as e:
            logger.debug(f"Error resolving redirect for {url}: {e}")
            return None
    
    async def extract_profile_data(self, page: Page, profile_url: str, data = None, professional_type: str = '') -> Optional[ProfessionalProfile]:
        """Extract data from professional profile page"""
        try:
            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            profile = ProfessionalProfile()
            profile.profile_url = profile_url
            profile.platform = 'houzz'
            
            # Set professional_type early to ensure it's saved to database
            if professional_type and professional_type.strip():
                profile.professional_type = professional_type
                logger.debug(f"Set professional_type to '{professional_type}' for profile during extraction")

            # Extract from Business Details section
            business_section = soup.find("section", id="business")
            if business_section:
                for cell in business_section.select('[class*="BusinessDetails__StyledCell"]'):
                    label = cell.select_one("h3")
                    value = cell.select_one("p, div")
                    
                    
                    if not label or not value:
                        continue
                    key = label.get_text(strip=True).lower()
                    if "business name" in key:
                        profile.name = value.get_text(strip=True)
                    elif "phone" in key:
                        raw_phone = value.get_text(strip=True)
                        profile.phone = extract_and_format_phone(raw_phone)
                    elif "website" in key and value.find("a"):
                        span_elem = cell.select_one("div span")
                        website_link = value.find("a")

                        if span_elem:
                            website_text = span_elem.get_text(strip=True)
                            if website_text:
                                # Clean and format the website text
                                if website_text.startswith('http') or website_text.startswith('www.'):
                                    profile.website = website_text
                                else:
                                    profile.website = f"https://{website_text}"                      
                        elif website_link:
                            # Fallback to href if no span found
                            profile.website = website_link.get("href")
                    elif "address" in key:
                        addr = value.get_text(" ", strip=True)
                        profile.address = addr
                        
                        # Extract zip code
                        zipcode = zipcode_utils.extract_zipcode(addr)
                        if zipcode:
                            profile.zip_code = zipcode
                        
                    elif "job cost" in key:
                        profile.typical_job_cost = value.get_text(strip=True)
                    elif "followers" in key:
                        num = re.search(r'\d+', value.get_text())
                        if num:
                            profile.followers_count = int(num.group())
                    elif "social" in key:
                        for a in cell.find_all("a", href=True):
                            href = a["href"]
                            aria = a.get("aria-label", "").lower()

                            # Resolve redirect to get the actual URL
                            try:
                                final_url = await self.resolve_redirect(href)
                                if not final_url:
                                    continue
                                
                                # Clean the final URL to remove login redirects and tracking params
                                cleaned_url = get_clean_target_url(final_url)
                                logger.debug(f"Cleaned social URL: {href} -> {final_url} -> {cleaned_url}")
                                
                            except Exception as e:
                                logger.debug(f"Could not resolve redirect for {href}: {e}")
                                continue

                            if "linkedin" in aria or "linkedin.com" in cleaned_url:
                                if cleaned_url not in profile.linkedin_links:
                                    profile.linkedin_links.append(cleaned_url)
                            elif "facebook" in aria or "facebook.com" in cleaned_url:
                                if cleaned_url not in profile.facebook_links:
                                    profile.facebook_links.append(cleaned_url)
                            elif "instagram" in aria or "instagram.com" in cleaned_url:
                                if cleaned_url not in profile.instagram_links:
                                    profile.instagram_links.append(cleaned_url)
                            elif "twitter" in aria or "twitter.com" in cleaned_url or "x.com" in cleaned_url:
                                if cleaned_url not in profile.twitter_links:
                                    profile.twitter_links.append(cleaned_url)
                            elif "pinterest" in aria or "pinterest.com" in cleaned_url:
                                if cleaned_url not in profile.pinterest_links:
                                    profile.pinterest_links.append(cleaned_url)
                            elif "youtube" in aria or "youtube.com" in cleaned_url:
                                if cleaned_url not in profile.youtube_links:
                                    profile.youtube_links.append(cleaned_url)
                            elif "behance" in aria or "behance.net" in cleaned_url:
                                if cleaned_url not in profile.other_social_links:
                                    profile.other_social_links.append(cleaned_url)
                            elif "dribbble" in aria or "dribbble.com" in cleaned_url:
                                if cleaned_url not in profile.other_social_links:
                                    profile.other_social_links.append(cleaned_url)
                            elif "blog" in aria or "other" in aria:
                                # Check if this is actually a social media link before adding to other_social_links
                                is_social = any(social in cleaned_url for social in [
                                    'behance.net', 'dribbble.com', 'tiktok.com', 'snapchat.com', 
                                    'tumblr.com', 'reddit.com', 'medium.com', 'github.com',
                                    'facebook', 'instagram', 'twitter', 'linkedin', 'pinterest', 'youtube', 'x.com'
                                ])
                                if is_social and cleaned_url not in profile.other_social_links:
                                    profile.other_social_links.append(cleaned_url)
            else:
                # Fallback to previous logic if section not found
                name_selectors = [
                    'h1[data-testid="professional-name"]',
                    '.pro-header h1',
                    '.professional-name',
                    'h1.hz-professional-name',
                    'h1[class*="professional"]',
                    'h1[class*="name"]',
                    '[data-testid*="name"] h1',
                    '[class*="professional"] h1',
                    '.pro-name h1',
                    'h1'
                ]
                for selector in name_selectors:
                    name_elem = soup.select_one(selector)
                    if name_elem:
                        profile.name = name_elem.get_text(strip=True)
                        break

            # Extract from JSON-LD data if fields are still missing
            if data:
                if not profile.name and data.get('name'):
                    profile.name = data.get('name')

                if not profile.phone and data.get('telephone'):
                    raw_phone = data['telephone']
                    profile.phone = extract_and_format_phone(raw_phone)
                
                address = data.get('address', {})
                if address:
                    postal = address.get('postalCode')

                    if not profile.zip_code and postal:
                        profile.zip_code = postal
                    if not profile.address:
                        city = address.get('addressLocality')
                        state = address.get('addressRegion')
                        street = address.get('streetAddress')
                        if street and city and state:
                            profile.address = f"{city}, {state}"

                # Extract website and social links from sameAs
                same_as = data.get('sameAs', [])
                for url in same_as:
                    if not (url and isinstance(url, str) and url.startswith(('http://', 'https://'))):
                        continue
                    
                    # Clean the URL to remove redirects and tracking parameters
                    cleaned_url = get_clean_target_url(url)

                    if 'linkedin.com' in cleaned_url and cleaned_url not in profile.linkedin_links:
                        profile.linkedin_links.append(cleaned_url)
                    elif 'facebook.com' in cleaned_url and cleaned_url not in profile.facebook_links:
                        profile.facebook_links.append(cleaned_url)
                    elif 'instagram.com' in cleaned_url and cleaned_url not in profile.instagram_links:
                        profile.instagram_links.append(cleaned_url)
                    elif ('twitter.com' in cleaned_url or 'x.com' in cleaned_url) and cleaned_url not in profile.twitter_links:
                        profile.twitter_links.append(cleaned_url)
                    elif 'pinterest.com' in cleaned_url and cleaned_url not in profile.pinterest_links:
                        profile.pinterest_links.append(cleaned_url)
                    elif 'youtube.com' in cleaned_url and cleaned_url not in profile.youtube_links:
                        profile.youtube_links.append(cleaned_url)
                    elif 'behance.net' in cleaned_url and cleaned_url not in profile.other_social_links:
                        profile.other_social_links.append(cleaned_url)
                    elif 'dribbble.com' in cleaned_url and cleaned_url not in profile.other_social_links:
                        profile.other_social_links.append(cleaned_url)
                    elif not profile.website and 'houzz.com' not in cleaned_url:
                        is_social = any(social in cleaned_url for social in ['facebook', 'instagram', 'twitter', 'linkedin', 'pinterest', 'youtube', 'x.com'])
                        if not is_social:
                            profile.website = cleaned_url
            
            # Extract contact info from page text
            page_text = soup.get_text()
            
            # Extract ratings and reviews
            try:
                # Look for rating in different formats
                rating_patterns = [
                    r'Average rating: (\d+\.?\d*) out of \d+ stars',
                    r'(\d+\.?\d*) out of \d+ stars',
                    r'(\d+\.?\d*) \| \d+ Review',
                    r'rating: (\d+\.?\d*)',
                    r'(\d+\.?\d*)\s*stars?'
                ]
                
                for pattern in rating_patterns:
                    rating_match = re.search(pattern, page_text, re.IGNORECASE)
                    if rating_match:
                        profile.rating = float(rating_match.group(1))
                        break
                
                # Extract review count
                review_patterns = [
                    r'\b(\d+)\s+reviews?\b',           # "31 reviews" or "1 review"
                    r'\b(\d+)\s+Reviews?\b',           # "31 Reviews" or "1 Review"
                    r'Reviews?\s*\(?(\d+)\)?',         # "Reviews (31)" or "Review 31"
                    r'\b(\d+)\s*Reviews?\s*(?:for|on)?', # "31 Reviews for", "31 Reviews on"
                ]

                for pattern in review_patterns:
                    review_match = re.search(pattern, page_text, re.IGNORECASE)                    
                    if review_match:
                        profile.reviews_count = int(review_match.group(1))
                        break
                        
            except Exception as e:
                logger.debug(f"Could not extract ratings/reviews: {e}")

            # Extract specific data from the HTML structure
            try:
                # Phone number from business details
                phone_pattern = r'Phone Number[^\n]*\n([^\n]+)'
                phone_match = re.search(phone_pattern, page_text)

                if phone_match and not profile.phone:
                    raw_phone = phone_match.group(1).strip()
                    profile.phone = extract_and_format_phone(raw_phone)
                
                # Extract zip code from address
                if not profile.zip_code:
                    zipcode = zipcode_utils.extract_zipcode(page_text)
                    if zipcode:
                        profile.zip_code = zipcode
                
            except Exception as e:
                logger.debug(f"Error extracting additional contact info: {e}")

            # Save profile immediately if database manager is available
            if profile and profile.name and self.database_manager:
                try:
                    # Use thread executor to avoid blocking async execution
                    loop = asyncio.get_event_loop()
                    was_added = await loop.run_in_executor(
                        self.executor, 
                        self.database_manager.add_profile_if_not_exists, 
                        profile
                    )
                    
                    if was_added:
                        self.saved_profiles_count += 1
                        if self.saved_profiles_count % 10 == 0:  # Log every 10 saves
                            logger.info(f"💾 Saved {self.saved_profiles_count} new profiles to database so far")
                            
                except Exception as e:
                    logger.error(f"Error saving profile to database: {e}")

            return profile if profile.name else None
        
        except Exception as e:
            logger.error(f"Error extracting profile data: {e}")
            return None
    

