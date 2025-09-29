"""Base Scraper Class for Web Scraping Operations.

This module provides a common base class for all scrapers to eliminate code duplication
and ensure consistent behavior across different scraping modules.
"""

import asyncio
import random
from typing import List, Optional, Dict, Any
from playwright.async_api import Page, Browser
from loguru import logger
from concurrent.futures import ThreadPoolExecutor

from .common_utils import WebUtils, StateManager, constants, nav_utils, log_utils
from config.config import config


class BaseScraper:
    """Simplified base class for all scrapers"""
    
    def __init__(self, database_manager=None):
        # Core utilities
        self.web_utils = WebUtils()
        self.state_manager = StateManager()
        self.database_manager = database_manager
        
        # Browser and proxy management
        self.browser: Optional[Browser] = None
        self.current_context = None
        self.proxy_list = self._get_proxy_list()
        self.current_proxy_index = 0
        
        # Performance tracking
        self.request_count = 0
        self.consecutive_errors = 0
        self.current_delay = 3.0
        self.max_delay = 30.0
        self.success_count = 0
        
        # Database operations
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.saved_profiles_count = 0

    def _get_proxy_list(self) -> List[str]:
        """Load proxies from config"""
        if config.USE_PROXY_ROTATION and config.WEBSHARE_PROXY_LIST:
            proxies = [p.strip() for p in config.WEBSHARE_PROXY_LIST.split(',')]
            logger.info(f"Loaded {len(proxies)} proxies for rotation")
            return proxies
        return []

    def get_next_proxy(self) -> Optional[Dict[str, Any]]:
        """Get the next proxy for rotation"""
        if not self.proxy_list:
            return None

        proxy_url = self.proxy_list[self.current_proxy_index]
        host, port = proxy_url.split(':')
        
        logger.info(f"Using proxy: {host}:{port}")
        
        return {
            'server': f'http://{host}:{port}',
            'username': config.PROXY_USERNAME,
            'password': config.PROXY_PASSWORD,
        }

    def rotate_proxy(self):
        """Rotate to the next proxy in the list"""
        if not self.proxy_list or not config.USE_PROXY_ROTATION:
            return
            
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
        current_proxy = self.proxy_list[self.current_proxy_index]
        logger.info(f"🔄 Rotated to proxy {self.current_proxy_index + 1}/{len(self.proxy_list)}: {current_proxy}")

    def _handle_network_error(self):
        """Handle network errors with adaptive rate limiting"""
        self.consecutive_errors += 1
        self.success_count = 0
        
        # Increase delay on consecutive errors
        if self.consecutive_errors > 3:
            self.current_delay = min(self.current_delay * 1.5, self.max_delay)
            logger.warning(f"Network error #{self.consecutive_errors}. Increasing delay to {self.current_delay}s")
        
        # Rotate proxy on consecutive errors
        if self.consecutive_errors > 5 and config.USE_PROXY_ROTATION:
            self.rotate_proxy()

    def _handle_network_success(self):
        """Handle successful network requests"""
        self.consecutive_errors = 0
        self.success_count += 1
        
        # Gradually reduce delay on success
        if self.success_count > 5 and self.current_delay > 3.0:
            self.current_delay = max(self.current_delay * 0.9, 3.0)
            logger.debug(f"Success streak. Reducing delay to {self.current_delay}s")
    
    def should_rotate_proxy(self) -> bool:
        """Check if proxy should be rotated based on interval"""
        if not self.proxy_list or not config.USE_PROXY_ROTATION or len(self.proxy_list) <= 1:
            return False
            
        return config.PROXY_ROTATION_INTERVAL > 0 and (self.request_count % config.PROXY_ROTATION_INTERVAL) == 0

    async def _adaptive_sleep(self, base_delay: float = None):
        """Adaptive sleep with jitter to avoid detection"""
        delay = base_delay or self.current_delay
        jitter = random.uniform(0.5, 1.5)
        actual_delay = delay * jitter
        
        logger.debug(f"Sleeping for {actual_delay:.2f}s")
        await asyncio.sleep(actual_delay)

    async def create_or_rotate_page(self, page: Page = None) -> Page:
        """Create a new page with proxy support and stealth settings"""
        # Close existing page if provided
        if page:
            try:
                await page.close()
            except Exception as e:
                logger.debug(f"Error closing page: {e}")

        # Rotate proxy if needed
        if self.should_rotate_proxy():
            self.rotate_proxy()

        # Prepare context options
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': self.web_utils.get_random_user_agent(),
            'locale': 'en-US',
            'timezone_id': 'America/New_York',
        }

        # Add proxy if available
        proxy = self.get_next_proxy()
        if proxy:
            context_options['proxy'] = proxy
            logger.info(f"🌐 Using proxy: {proxy['server']}")

        # Close existing context and create new one
        if self.current_context:
            try:
                await self.current_context.close()
            except Exception as e:
                logger.debug(f"Error closing context: {e}")

        self.current_context = await self.browser.new_context(**context_options)
        page = await self.current_context.new_page()
        
        # Set headers, block unnecessary resources, and enable request logging
        await self.set_page_headers(page)
        await page.route("**/*", self._block_unnecessary_resources)
        await page.route("**/*", self._log_network_request)
        
        return page

    async def set_page_headers(self, page: Page):
        """Set stealth headers for the page"""
        await page.set_extra_http_headers({
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })

    async def _block_unnecessary_resources(self, route):
        """Block unnecessary resources - only allow specific URLs we need"""
        url = route.request.url
        resource_type = route.request.resource_type
        
        # Import re for pattern matching
        import re
        
        # First check if it's from an allowed domain
        is_allowed_domain = any(domain in url.lower() for domain in constants.ALLOWED_DOMAINS)
        if not is_allowed_domain:
            await route.abort()
            return
        
        # Check if it matches our allowed URL patterns
        matches_allowed_pattern = any(re.match(pattern, url) for pattern in constants.ALLOWED_URL_PATTERNS)
        
        # Block if it doesn't match allowed patterns OR is a blocked resource type
        if not matches_allowed_pattern or resource_type in constants.BLOCKED_RESOURCE_TYPES:
            await route.abort()
            return
        
        await route.continue_()

    async def _log_network_request(self, route):
        """Log network requests for debugging - only log essential requests"""
        url = route.request.url
        
        # Only log requests that are essential for scraping
        essential_patterns = [
            r'https://www\.houzz\.com/professionals/.*?/.*?-.*?probr0-bo~.*?',  # Search pages
            r'https://www\.houzz\.com/professionals/.*?/.*?-pfvwus-pf~.*?'      # Profile pages
        ]
        
        import re
        if any(re.match(pattern, url) for pattern in essential_patterns):
            logger.info(f"🎯 Essential Request: {route.request.method} {url}")
        
        await route.continue_()

    async def navigate_to_url(self, page: Page, url: str, wait_until: str = 'domcontentloaded') -> bool:
        """Navigate to URL with standardized error handling"""
        return await nav_utils.navigate_with_retry(page, url, wait_until=wait_until)
    
    async def wait_for_elements(self, page: Page, selectors: List[str]) -> bool:
        """Wait for any of the provided selectors to appear"""
        return await nav_utils.wait_for_any_selector(page, selectors)
    
    async def _handle_navigation_error(self, error: Exception, attempt: int):
        """Handle navigation errors with proxy rotation if needed"""
        if attempt > 0:  # Only rotate proxy after first failure
            await self._rotate_proxy()
    
    async def _wait_for_content_load(self, page: Page) -> bool:
        """Wait for content to load with fallback strategies"""
        try:
            await page.wait_for_load_state('networkidle', timeout=30000)
            return True
        except Exception:
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=15000)
                return True
            except Exception:
                await page.wait_for_timeout(5000)
                return True

    def get_browser_args(self) -> List[str]:
        """Get browser launch arguments for stealth and performance - optimized for scraping only"""
        return [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-extensions',
            '--no-first-run',
            '--disable-default-apps',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--disable-ipc-flooding-protection',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-background-timer-throttling',
            '--disable-features=TranslateUI',
            '--disable-component-extensions-with-background-pages',
            '--no-default-browser-check',
            '--disable-popup-blocking',
            '--exclude-switches=enable-automation',
            '--disable-dev-tools',
            '--disable-plugins-discovery',
            '--disable-preconnect',
            '--disable-component-update',
            '--disable-sync',
            '--disable-features=VizDisplayCompositor,TranslateUI,BlinkGenPropertyTrees',
            '--user-agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"',
            '--lang=en-US,en',
            '--disable-client-side-phishing-detection',
            # Additional blocking for unnecessary resources
            '--disable-images',  # Block images
            '--disable-javascript',  # Disable JS for faster loading
            '--disable-domain-reliability',
            '--disable-hang-monitor',
            '--disable-speech-api',
            '--disable-web-resources',
            '--aggressive-cache-discard',
            '--aggressive-tab-discard'
        ]

    async def cleanup(self):
        """Cleanup all resources"""
        try:
            if self.current_context:
                await self.current_context.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
        except Exception as e:
            logger.debug(f"Error during cleanup: {e}")
        finally:
            if self.executor:
                self.executor.shutdown(wait=True)