"""Base Scraper Class for Web Scraping Operations.

This module provides a common base class for all scrapers to eliminate code duplication
and ensure consistent behavior across different scraping modules.
"""

import asyncio
import random
from typing import List, Optional, Dict, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from loguru import logger
from concurrent.futures import ThreadPoolExecutor

from .common_utils import WebUtils, StateManager
from config.config import config


class BaseScraper:
    """Base class for all scrapers with common functionality"""
    
    def __init__(self, database_manager=None):
        self.web_utils = WebUtils()
        self.state_manager = StateManager()
        self.browser: Optional[Browser] = None
        self.proxy_list = self._get_proxy_list()
        self.current_proxy_index = 0
        self.last_proxy_index = -1  # Track last selected proxy to avoid duplicates
        self.request_count = 0
        self.current_context = None
        self.database_manager = database_manager
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.saved_profiles_count = 0
        
        # Enhanced rate limiting and stability tracking
        self.network_error_count = 0
        self.consecutive_errors = 0
        self.last_error_time = None
        self.current_delay = 3.0  # Start with 3 second delay
        self.max_delay = 30.0    # Max 30 second delay
        self.success_count = 0   # Track consecutive successes

    def _get_proxy_list(self) -> List[str]:
        """Load proxies from config"""
        if config.USE_PROXY_ROTATION and config.WEBSHARE_PROXY_LIST:
            proxies = config.WEBSHARE_PROXY_LIST.split(',')
            logger.info(f"Loaded {len(proxies)} proxies for rotation.")
            return [p.strip() for p in proxies]
        return []

    def get_next_proxy(self) -> Optional[Dict[str, Any]]:
        """Get the next proxy for rotation"""
        if not self.proxy_list:
            return None

        proxy_url = self.proxy_list[self.current_proxy_index]
        
        # Standard proxy format
        proxy_parts = proxy_url.split(':')
        host = proxy_parts[0]
        port = int(proxy_parts[1])
        username = config.PROXY_USERNAME
        password = config.PROXY_PASSWORD
        
        logger.info(f"Using proxy: {host}:{port} with user: {username}")
        
        # For HTTP proxies, use http:// prefix
        return {
            'server': f'http://{host}:{port}',
            'username': username,
            'password': password,
        }

    def rotate_proxy(self):
        """Rotate to a random proxy in the list, avoiding the last selected one"""
        if self.proxy_list:
            # If we have more than one proxy, avoid selecting the same one twice
            if len(self.proxy_list) > 1:
                # Create a list of available indices excluding the last selected one
                available_indices = [i for i in range(len(self.proxy_list)) if i != self.last_proxy_index]
                self.current_proxy_index = random.choice(available_indices)
            else:
                # If only one proxy, just use it
                self.current_proxy_index = 0
            
            self.last_proxy_index = self.current_proxy_index
            logger.info(f"Randomly selected proxy {self.current_proxy_index + 1}/{len(self.proxy_list)}")

    def _handle_network_error(self):
        """Handle network errors with adaptive rate limiting"""
        self.network_error_count += 1
        self.consecutive_errors += 1
        self.success_count = 0
        
        # Adaptive delay based on error frequency
        if self.consecutive_errors > 3:
            self.current_delay = min(self.current_delay * 1.5, self.max_delay)
            logger.warning(f"Network error detected. Increasing delay to {self.current_delay}s")
        
        # Rotate proxy on consecutive errors
        if self.consecutive_errors > 5 and self.proxy_list:
            self.rotate_proxy()

    def _handle_network_success(self):
        """Handle successful network requests"""
        self.consecutive_errors = 0
        self.success_count += 1
        
        # Gradually reduce delay on success
        if self.success_count > 5 and self.current_delay > 3.0:
            self.current_delay = max(self.current_delay * 0.9, 3.0)
            logger.debug(f"Success streak. Reducing delay to {self.current_delay}s")

    async def _adaptive_sleep(self, base_delay: float = None):
        """Adaptive sleep based on network conditions"""
        delay = base_delay or self.current_delay
        
        # Add jitter to avoid detection
        jitter = random.uniform(0.5, 1.5)
        actual_delay = delay * jitter
        
        logger.debug(f"Sleeping for {actual_delay:.2f}s (base: {delay}s, jitter: {jitter:.2f})")
        await asyncio.sleep(actual_delay)

    async def create_or_rotate_page(self, page: Page = None, page_config: Optional[Dict[str, Any]] = None) -> Page:
        """Create a new page or rotate existing one with proxy support and optional custom configuration
        
        Args:
            page: Existing page to close (optional)
            page_config: Optional configuration dict with keys like:
                - viewport: {'width': int, 'height': int}
                - user_agent: str
                - locale: str
                - timezone_id: str
                - permissions: List[str]
                - extra_http_headers: Dict[str, str]
        """
        if page:
            try:
                await page.close()
            except Exception as e:
                logger.debug(f"Error closing page: {e}")

        # Default page configuration
        default_config = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': self.web_utils.get_random_user_agent(),
            'locale': 'en-US',
            'timezone_id': 'America/New_York',
            'permissions': ['geolocation'],
            'extra_http_headers': {
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'application/json, text/plain, */*',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        }

        # Merge custom configuration with defaults
        if page_config:
            # Deep merge for nested dictionaries
            for key, value in page_config.items():
                if key in default_config and isinstance(default_config[key], dict) and isinstance(value, dict):
                    default_config[key].update(value)
                else:
                    default_config[key] = value

        # Create new context with proxy if available
        proxy = self.get_next_proxy()
        context_options = default_config.copy()

        if proxy:
            context_options['proxy'] = proxy

        self.current_context = await self.browser.new_context(**context_options)
        page = await self.current_context.new_page()
        
        # Set additional headers
        await self.set_page_headers(page)
        
        # Enable request interception for logging
        await page.route("**/*", self._log_network_request)
        
        return page

    async def set_page_headers(self, page: Page):
        """Set page headers for better stealth"""
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

    async def _log_network_request(self, route):
        """Log network requests for debugging"""
        request = route.request
        logger.debug(f"Request: {request.method} {request.url}")
        await route.continue_()

    async def _wait_for_content_load_with_fallback(self, page: Page) -> bool:
        """Wait for content to load with multiple fallback strategies"""
        try:
            # Wait for network idle
            await page.wait_for_load_state('networkidle', timeout=30000)
            return True
        except Exception as e:
            logger.debug(f"Network idle timeout, trying DOM content loaded: {e}")
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=15000)
                return True
            except Exception as e2:
                logger.debug(f"DOM content loaded timeout, trying basic wait: {e2}")
                try:
                    await page.wait_for_timeout(5000)
                    return True
                except Exception as e3:
                    logger.error(f"All content load strategies failed: {e3}")
                    return False

    def get_browser_args(self) -> List[str]:
        """Get browser launch arguments for stealth"""
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
            '--disable-client-side-phishing-detection'
        ]

    async def cleanup(self):
        """Cleanup resources"""
        if self.current_context:
            await self.current_context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
        if self.executor:
            self.executor.shutdown(wait=True) 