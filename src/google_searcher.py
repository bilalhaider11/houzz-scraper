"""Google Searcher Module for the Houzz Lead Generation Pipeline.

Optimized Google Custom Search integrations for improved query building,
result filtering, and consistency. Uses Google Search API for LinkedIn
and email discovery.
"""

import re
import requests
import time
import random
from typing import Dict, List, Optional, Any
from loguru import logger
from config.config import config
from .email_service import email_service, EmailValidationStatus

class GoogleSearcher:
    """Google search functionality using Google Custom Search API to find personal emails and LinkedIn profiles"""

    def __init__(self):
        self.api_key = config.GOOGLE_SEARCH_API_KEY if hasattr(config, 'GOOGLE_SEARCH_API_KEY') else None
        self.search_engine_id = config.GOOGLE_SEARCH_CX if hasattr(config, 'GOOGLE_SEARCH_CX') else None

        if not self.api_key or not self.search_engine_id:
            logger.warning("Google Custom Search API not configured. Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CX environment variables.")
            self._log_setup_instructions()
            
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        
        # Use centralized email service for validation and classification
        self.email_service = email_service
        
        # Cache for domain variations to avoid repeated processing
        self._domain_cache = {}
        
        # Rate limiting and retry settings
        self.last_request_time = 0
        self.min_delay_between_requests = 1.0  # Minimum 1 second between requests
        self.max_retries = 3
        self.quota_exceeded = False
        self.request_count = 0
        self.max_requests_per_day = 100  # Conservative limit for free tier

    def _log_setup_instructions(self):
        """Log setup instructions for developers to configure Google Custom Search API."""
        logger.info("To get these credentials:")
        logger.info("1. Go to https://console.developers.google.com/")
        logger.info("2. Create a project and enable Custom Search API")
        logger.info("3. Create credentials (API Key)")
        logger.info("4. Go to https://cse.google.com/cse/ to create a custom search engine")
        logger.info("5. Get the Search Engine ID (CX)")
    
    def _extract_domain_name(self, website: str) -> str:
        """Extract domain name from website URL for search queries"""
        if not website:
            return ""
        
        try:
            # Remove protocol and www
            domain = website.lower()
            domain = domain.replace('https://', '').replace('http://', '').replace('www.', '')
            # Remove trailing slash and path
            domain = domain.split('/')[0]
            # Remove .com, .org, etc. to get base name
            domain_parts = domain.split('.')
            if len(domain_parts) > 1:
                return domain_parts[0]  # Return the main domain name part
            return domain
        except:
            return ""
    
    def search_professional_info(self, name: str, professional_type: str, location: str = None, website: str = None, social_links: dict = None, address: str = None, zipcode: str = None) -> Dict[str, Any]:
        """
        Search for a professional's Gmail, LinkedIn, and zipcode information using Google Custom Search
        
        Args:
            name: Professional's name
            professional_type: Type of professional (e.g., "interior designer", "architect")
            location: Optional location to narrow search
            website: Professional's website URL
            social_links: Dictionary of social media links
            address: Professional's address for zipcode search
            zipcode: Existing zipcode (if any)
            
        Returns:
            Dictionary containing found Gmail addresses, LinkedIn profiles, and zipcode
        """
        if not self.api_key or not self.search_engine_id:
            logger.warning("Google Custom Search API not configured, skipping Google search")
            return {'personal_emails': [], 'linkedin_profiles': []}
        
        results = {
            'personal_emails': [],
            'linkedin_profiles': [],
            'zipcode': None
        }
        
        try:
            logger.info(f"🔍 Starting enhanced Google search for {name} ({professional_type})")
            
            # Log search context for debugging
            logger.debug(f"📋 Search context: website={website}, social_links={bool(social_links)}, location={location}")
            
            # Search for personal emails with enhanced logging
            personal_results = self._search_personal_emails(name, professional_type, location, website, social_links)
            results['personal_emails'] = personal_results
            
            # Search for LinkedIn profiles with enhanced logging
            linkedin_results = self._search_linkedin(name, professional_type, location, website, social_links)
            results['linkedin_profiles'] = linkedin_results
            
            # Search for zipcode if not already available
            if not zipcode and address:
                zipcode_result = self._search_zipcode(name, professional_type, address, website)
                results['zipcode'] = zipcode_result
            
            # Enhanced completion logging with performance metrics
            search_summary = f"📊 Search completed for {name}: "
            search_summary += f"📧 {len(personal_results)} email(s), 🔗 {len(linkedin_results)} LinkedIn profile(s)"
            if personal_results:
                search_summary += f" | Emails: {personal_results}"
            logger.info(search_summary)
            
        except Exception as e:
            logger.error(f"❌ Error performing Google search for {name}: {e}")
        
        return results
    
    def _search_personal_emails(self, name: str, professional_type: str, location: str = None, website: str = None, social_links: dict = None) -> List[str]:
        """Search specifically for personal email addresses using enhanced query format"""
        personal_emails = []
        
        try:
            # Extract domain variations from website and social links
            domain_variations = self._extract_domain_variations(website, social_links)
            
            # Construct advanced search query following the specified format:
            # "Name" ("domain.com" OR "go.domain" OR "Domain_Name") ("@gmail.com" OR "@outlook.com") professional_type "United States" OR "USA" site:domain.com OR site:linkedin.com OR site:facebook.com OR site:twitter.com OR site:x.com OR instagram.com
            
            query_parts = []
            
            # Add quoted name
            query_parts.append(f'"{name}"')
            
            # Add domain variations if available
            if domain_variations:
                domain_part = '(' + ' OR '.join([f'"{var}"' for var in domain_variations]) + ')'
                query_parts.append(domain_part)
            
            # Add personal email domains
            email_domains = '("@gmail.com" OR "@outlook.com" OR "@hotmail.com" OR "@yahoo.com" OR "@icloud.com" OR "@aol.com" OR "@protonmail.com" OR "@me.com")'
            query_parts.append(email_domains)
            
            # Add professional type for better targeting
            if professional_type:
                query_parts.append(f'"{professional_type}"')
            
            # Add USA filtering
            query_parts.append('("United States" OR "USA" OR "US")')
            
            # Add site restrictions
            site_restrictions = self._build_site_restrictions(website, social_links)
            if site_restrictions:
                query_parts.append(site_restrictions)
            
            query = ' '.join(query_parts)
            
            logger.debug(f"Enhanced Gmail search query: {query}")
            
            # Perform the search
            search_results = self._perform_google_search(query, num_results=10)
            
            # Enhanced logging for search results
            if search_results:
                total_results = search_results.get('searchInformation', {}).get('totalResults', '0')
                logger.info(f"🔍 Email search for {name}: {total_results} total results found")
                
                if 'items' in search_results:
                    logger.debug(f"📄 Processing {len(search_results['items'])} search result items")
                    
                    for idx, item in enumerate(search_results['items'], 1):
                        # Extract personal email addresses from title, snippet, and displayed link
                        text_to_search = " ".join([
                            item.get("title", ""),
                            item.get("snippet", ""),
                            item.get("displayLink", ""),
                            item.get("link", "")
                        ])
                        
                        logger.debug(f"📋 Result {idx}: {item.get('title', 'No title')[:50]}... | Domain: {item.get('displayLink', 'N/A')}")
                        
                        # Find personal email addresses in the text
                        found_emails = self._extract_personal_email_addresses(text_to_search)
                        if found_emails:
                            logger.info(f"✅ Found {len(found_emails)} potential emails in result {idx}: {found_emails}")
                        personal_emails.extend(found_emails)
                else:
                    logger.warning(f"⚠️ No search result items found for {name}")
            else:
                logger.warning(f"⚠️ No search results returned for {name}")
            
            # Remove duplicates while preserving order
            personal_emails = list(dict.fromkeys(personal_emails))

            # Validate emails using EmailVerifier with comprehensive validation
            if personal_emails:
                logger.info(f"Found {len(personal_emails)} potential emails for {name}, validating...")
                validated_emails = self._validate_emails_comprehensively(personal_emails, name)
                personal_emails = validated_emails
                logger.info(f"Validation complete: {len(validated_emails)}/{len(personal_emails)} emails passed validation for {name}")
            
        except Exception as e:
            logger.error(f"Error searching for personal email addresses for {name}: {e}")
        
        return personal_emails
    
    def _validate_emails_comprehensively(self, emails: List[str], name: str) -> List[str]:
        """Comprehensive email validation with detailed logging and business-friendly acceptance criteria (BASIC VALIDATION ONLY - NO ZEROBOUNCE)"""
        if not emails:
            return []
        
        logger.info(f"🔍 Starting comprehensive email validation for {name} ({len(emails)} emails) - Basic validation only (ZeroBounce disabled)")

        # Use the centralized email service's comprehensive validation method (BASIC VALIDATION ONLY)
        validated_emails = self.email_service.filter_valid_emails(emails)
        
        logger.info(f"📧 Validation complete for {name}: {len(validated_emails)}/{len(emails)} emails passed basic validation (no ZeroBounce)")
        
        return validated_emails
    
    
    def _search_linkedin(self, name: str, professional_type: str, location: str = None, website: str = None, social_links: dict = None) -> List[Dict[str, str]]:
        """Search specifically for LinkedIn profiles with better targeting"""
        linkedin_profiles = []
        
        try:
            # Extract business name variations for better targeting
            business_variations = self._extract_business_name_variations(name)
            
            # Construct targeted search query for LinkedIn
            query_parts = [
                f'"{name}"',
                "site:linkedin.com/in",
                "United States OR USA OR US"  # Focus on USA
            ]
            
            # Add professional type if available
            if professional_type:
                query_parts.append(professional_type)
            
            # Add business name variations to make search more specific
            if business_variations:
                business_part = '(' + ' OR '.join([f'"{var}"' for var in business_variations]) + ')'
                query_parts.append(business_part)
            
            # Add website domain if available for better targeting
            if website:
                domain_name = self._extract_domain_name(website)
                if domain_name:
                    query_parts.append(f'"{domain_name}"')
            
            if location:
                query_parts.append(location)
            
            query = " ".join(query_parts)
            
            logger.debug(f"Enhanced LinkedIn search query: {query}")
            
            # Perform the search
            search_results = self._perform_google_search(query, num_results=5)
            
            if search_results and 'items' in search_results:
                for item in search_results['items']:
                    link = item.get("link", "")
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    
                    # Check if it's a LinkedIn profile with enhanced relevance checking
                    if "linkedin.com/in/" in link and self._is_relevant_business_linkedin_profile(title, snippet, name, business_variations, professional_type):
                        linkedin_profiles.append({
                            'url': link,
                            'title': title,
                            'snippet': snippet
                        })
            
            if linkedin_profiles:
                logger.info(f"Found {len(linkedin_profiles)} relevant LinkedIn profile(s) for {name}")
            
        except Exception as e:
            logger.error(f"Error searching for LinkedIn profiles for {name}: {e}")
        
        return linkedin_profiles
    
    def _search_zipcode(self, name: str, professional_type: str, address: str, website: str = None) -> Optional[str]:
        """
        Search for zipcode information using Google Custom Search with a simple query.

        Args:
            name: Professional's name
            professional_type: Type of professional
            address: Professional's address
            website: Professional's website URL

        Returns:
            Best extracted zipcode if found, None otherwise
        """
        try:
            logger.info(f"🔍 Searching for zipcode for {name} ({professional_type})")

            if not address:
                logger.info(f"No address provided for {name}, cannot search for zipcode.")
                return None

            # Handle addresses that contain "| " which indicates a list format
            if "| " in address:
                logger.info(f"Address contains list format for {name}, processing each address separately")
                addresses = [addr.strip() for addr in address.split("| ")]
                all_zipcodes_found = []
                
                for addr in addresses:
                    if addr.strip():  # Skip empty addresses
                        query = f'{addr.strip()} zip code'
                        logger.debug(f"🔍 Zipcode search query for address '{addr.strip()}': {query}")
                        search_results = self._perform_google_search(query, num_results=3)
                        
                        if search_results and 'items' in search_results:
                            for item in search_results['items']:
                                text = (item.get('title', '') or '') + ' ' + (item.get('snippet', '') or '')
                                zipcodes = self._extract_zipcodes_from_text(text)
                                if zipcodes:
                                    all_zipcodes_found.extend(zipcodes)
                
                if all_zipcodes_found:
                    # Choose the best one from all addresses
                    from collections import Counter
                    zipcode_counts = Counter(all_zipcodes_found)
                    best_zipcode, _ = zipcode_counts.most_common(1)[0]
                    logger.info(f"✅ Found zipcode(s) {all_zipcodes_found} for {name} from multiple addresses, best: {best_zipcode}")
                    return best_zipcode
                
                logger.info(f"❌ No zipcode found for {name} from any of the addresses")
                return None
            else:
                # Use a simple query: "address" zip code
                query = f'{address} zip code'
                logger.debug(f"🔍 Simple zipcode search query: {query}")
                search_results = self._perform_google_search(query, num_results=5)

            zipcodes_found = []

            if search_results and 'items' in search_results:
                for item in search_results['items']:
                    text = (item.get('title', '') or '') + ' ' + (item.get('snippet', '') or '')
                    zipcodes = self._extract_zipcodes_from_text(text)
                    if zipcodes:
                        zipcodes_found.extend(zipcodes)

            if zipcodes_found:
                # Choose the best one (e.g., most common, or first)
                from collections import Counter
                zipcode_counts = Counter(zipcodes_found)
                best_zipcode, _ = zipcode_counts.most_common(1)[0]
                logger.info(f"✅ Found zipcode(s) {zipcodes_found} for {name}, best: {best_zipcode}")
                return best_zipcode

            logger.info(f"❌ No zipcode found for {name}")
            return None

        except Exception as e:
            logger.error(f"Error searching for zipcode for {name}: {e}")
            return None

    def _extract_zipcodes_from_text(self, text: str) -> List[str]:
        """
        Extract all zipcodes from text using regex patterns.

        Args:
            text: Text to search for zipcodes

        Returns:
            List of extracted zipcodes (may be empty)
        """
        if not text:
            return []

        # Import zipcode_utils from common_utils
        from .common_utils import zipcode_utils

        # Use the consolidated zipcode extraction utility, but get all matches
        # Assume zipcode_utils.extract_zipcodes returns a list, if not, fallback to set logic
        if hasattr(zipcode_utils, "extract_zipcodes"):
            return zipcode_utils.extract_zipcodes(text)
        else:
            # Fallback: use extract_zipcode and wrap in list if found
            zc = zipcode_utils.extract_zipcode(text)
            return [zc] if zc else []
    
    def _perform_google_search(self, query: str, num_results: int = 10) -> Optional[Dict]:
        """Perform actual Google Custom Search API request with rate limiting and retry logic"""
        
        # Check if quota is exceeded
        if self.quota_exceeded:
            logger.warning("Google Custom Search API quota exceeded, skipping request")
            return None
        
        # Check daily request limit
        if self.request_count >= self.max_requests_per_day:
            logger.warning(f"Daily request limit reached ({self.max_requests_per_day}), skipping request")
            return None
        
        # Rate limiting - ensure minimum delay between requests
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_delay_between_requests:
            sleep_time = self.min_delay_between_requests - time_since_last_request
            time.sleep(sleep_time)
        
        for attempt in range(self.max_retries):
            try:
                params = {
                    'key': self.api_key,
                    'cx': self.search_engine_id,
                    'q': query,
                    'num': min(num_results, 10),  # Google Custom Search API max is 10 per request
                    'gl': 'us',  # Country: US
                    'hl': 'en',  # Language: English
                }
                
                self.last_request_time = time.time()
                response = requests.get(self.base_url, params=params, timeout=30)
                self.request_count += 1
                
                if response.status_code == 200:
                    logger.debug(f"Google search successful for query: {query[:50]}...")
                    return response.json()
                elif response.status_code == 429:
                    # Rate limit exceeded - wait longer and retry
                    wait_time = (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                    logger.warning(f"Google Custom Search API rate limit exceeded, waiting {wait_time:.1f}s before retry {attempt + 1}/{self.max_retries}")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 403:
                    # Quota exceeded - mark as exceeded and stop
                    logger.error("Google Custom Search API quota exceeded or invalid credentials")
                    self.quota_exceeded = True
                    return None
                else:
                    logger.error(f"Google Custom Search API error: {response.status_code} - {response.text}")
                    if attempt == self.max_retries - 1:
                        return None
                    time.sleep(1)  # Brief delay before retry
                    continue
                    
            except requests.exceptions.Timeout:
                logger.error(f"Google Custom Search API request timed out (attempt {attempt + 1}/{self.max_retries})")
                if attempt == self.max_retries - 1:
                    return None
                time.sleep(1)
                continue
            except Exception as e:
                logger.error(f"Error making Google Custom Search API request: {e}")
                if attempt == self.max_retries - 1:
                    return None
                time.sleep(1)
                continue
        
        return None
    
    def _extract_domain_variations(self, website: str, social_links: dict = None) -> List[str]:
        """Extract domain variations from website URL and social links for enhanced search queries"""
        # Use cache key based on website and social links
        cache_key = f"{website}_{hash(str(social_links))}"
        if cache_key in self._domain_cache:
            return self._domain_cache[cache_key]
        
        variations = []
        
        if website:
            try:
                # Clean website URL
                domain = website.lower()
                domain = domain.replace('https://', '').replace('http://', '').replace('www.', '')
                domain = domain.split('/')[0]  # Remove path
                
                if '.' in domain:
                    # Extract main domain parts
                    domain_parts = domain.split('.')
                    main_domain = domain_parts[0]
                    
                    # Add variations
                    variations.append(domain)  # full domain like "domum.design"
                    variations.append(f"go.{main_domain}")  # "go.domum"
                    variations.append(f"{main_domain.title()}_Design")  # "Domum_Design"
                    variations.append(main_domain)  # "domum"
                    
            except Exception as e:
                logger.debug(f"Error extracting domain variations from {website}: {e}")
        
        # Extract variations from social links if available
        if social_links and isinstance(social_links, dict):
            for platform, url in social_links.items():
                if url and isinstance(url, str):
                    try:
                        # Extract handle or username from social URLs
                        if 'instagram.com/' in url.lower():
                            handle = url.split('/')[-1]
                            if handle and handle != 'instagram.com':
                                variations.append(handle)
                        elif 'facebook.com/' in url.lower():
                            handle = url.split('/')[-1]
                            if handle and handle != 'facebook.com':
                                variations.append(handle)
                        elif 'twitter.com/' in url.lower() or 'x.com/' in url.lower():
                            handle = url.split('/')[-1]
                            if handle and handle not in ['twitter.com', 'x.com']:
                                variations.append(handle)
                    except Exception as e:
                        logger.debug(f"Error extracting variation from social link {url}: {e}")
        
        # Remove duplicates and empty values
        variations = list(dict.fromkeys([v for v in variations if v]))
        
        # Cache the result
        self._domain_cache[cache_key] = variations
        
        return variations
    
    def _build_site_restrictions(self, website: str, social_links: dict = None) -> str:
        """Build site restrictions for search query"""
        sites = []
        
        # Add main website domain
        if website:
            try:
                domain = website.lower()
                domain = domain.replace('https://', '').replace('http://', '').replace('www.', '')
                domain = domain.split('/')[0]
                sites.append(f"site:{domain}")
            except:
                pass
        
        # Add common social media sites
        social_sites = [
            'site:linkedin.com',
            'site:facebook.com', 
            'site:twitter.com',
            'site:x.com',
            'site:instagram.com'
        ]
        sites.extend(social_sites)
        
        return ' OR '.join(sites) if sites else ''
    
    def _extract_personal_email_addresses(self, text: str) -> List[str]:
        """Extract email addresses from text using comprehensive regex pattern"""
        # Comprehensive email pattern that matches any valid email format
        # This includes both personal and business emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        found_emails = re.findall(email_pattern, text, re.IGNORECASE)
        
        # Filter out obviously fake or template emails
        filtered_emails = []
        for email in found_emails:
            email_lower = email.lower()
            # Skip common fake/template emails
            if not any(fake in email_lower for fake in [
                'example@', 'test@', 'sample@', 'your@', 'name@', 'email@',
                'user@', 'contact@', 'info@', 'noreply@', 'no-reply@',
                'admin@', 'support@', 'hello@', 'hi@', 'webmaster@',
                'postmaster@', 'abuse@', 'security@', 'mailer-daemon@',
                'daemon@', 'nobody@', 'root@', 'hostmaster@'
            ]):
                # Additional validation: check for reasonable email length and format
                if len(email) <= 254 and '@' in email and '.' in email.split('@')[1]:
                    filtered_emails.append(email)
        
        return filtered_emails
    
    def test_api_connection(self) -> bool:
        """Test if Google Custom Search API is working"""
        if not self.api_key or not self.search_engine_id:
            logger.error("Google Custom Search API credentials not configured")
            return False
        
        # Check if quota is already exceeded
        if self.quota_exceeded:
            logger.warning("Google Custom Search API quota already exceeded, skipping test")
            return False
        
        try:
            # Make a simple test search
            test_results = self._perform_google_search("test", num_results=1)
            
            if test_results is not None:
                logger.info("Google Custom Search API connection successful")
                return True
            else:
                if self.quota_exceeded:
                    logger.warning("Google Custom Search API quota exceeded during test")
                else:
                    logger.error("Google Custom Search API connection failed")
                return False
                
        except Exception as e:
            logger.error(f"Error testing Google Custom Search API: {e}")
            return False
    
    def clear_caches(self) -> None:
        """Clear all caches for fresh data"""
        self._domain_cache.clear()
        logger.info("Google searcher caches cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics for monitoring"""
        return {
            'domain_cache_size': len(self._domain_cache),
            'request_count': self.request_count,
            'quota_exceeded': self.quota_exceeded
        }
    
    def reset_quota_status(self) -> None:
        """Reset quota status for testing or new day"""
        self.quota_exceeded = False
        self.request_count = 0
        logger.info("Google Custom Search API quota status reset")
    
    def _extract_business_name_variations(self, name: str) -> List[str]:
        """Extract business name variations for better search targeting"""
        if not name:
            return []
        
        variations = []
        
        # Add the original name
        variations.append(name)
        
        # Remove common business suffixes and create variations
        business_suffixes = ['llc', 'inc', 'corp', 'ltd', 'company', 'co.', 'studio', 'design', 'interiors', 'interior', 'group', 'associates', 'architects']
        
        # Clean name by removing suffixes
        clean_name = name.lower()
        for suffix in business_suffixes:
            clean_name = clean_name.replace(f' {suffix}', '').replace(f'.{suffix}', '').replace(suffix, '')
        
        clean_name = clean_name.strip()
        if clean_name and clean_name != name.lower():
            variations.append(clean_name.title())
        
        # Extract individual words (meaningful ones)
        words = [word for word in clean_name.split() if len(word) > 2]
        if len(words) > 1:
            # Add combinations of words
            variations.extend(words)
            if len(words) == 2:
                variations.append(f"{words[0]} {words[1]}")
        
        # Remove duplicates and empty values
        variations = list(dict.fromkeys([v for v in variations if v and len(v) > 2]))
        
        return variations[:5]  # Limit to avoid overly long queries
    
    def _is_relevant_business_linkedin_profile(self, title: str, snippet: str, business_name: str, business_variations: List[str], professional_type: str) -> bool:
        """Enhanced relevance checking for LinkedIn profiles with business context"""
        if not title or not business_name:
            return False
        
        title_lower = title.lower()
        snippet_lower = snippet.lower() if snippet else ""
        combined_text = f"{title_lower} {snippet_lower}"
        
        # Check for business name matches
        business_matches = 0
        all_variations = [business_name] + (business_variations or [])
        
        for variation in all_variations:
            if variation and len(variation) > 2:
                variation_lower = variation.lower()
                if variation_lower in combined_text:
                    business_matches += 1
        
        # Check for professional type relevance
        if professional_type:
            prof_type_words = professional_type.lower().split()
            profession_matches = sum(1 for word in prof_type_words if word in combined_text)
        else:
            profession_matches = 0
        
        # Check for business-related keywords
        business_keywords = ['owner', 'founder', 'principal', 'ceo', 'president', 'director', 'manager', 'lead', 'senior']
        business_role_matches = sum(1 for keyword in business_keywords if keyword in combined_text)
        
        # Scoring system for relevance
        relevance_score = 0
        
        # Business name match is most important
        if business_matches > 0:
            relevance_score += business_matches * 3
        
        # Professional type match
        if profession_matches > 0:
            relevance_score += profession_matches * 2
        
        # Business role indicators
        if business_role_matches > 0:
            relevance_score += business_role_matches
        
        # Location indicators (US-based)
        us_indicators = ['united states', 'usa', 'us ', ' us,', 'california', 'new york', 'texas', 'florida', 'illinois']
        us_matches = sum(1 for indicator in us_indicators if indicator in combined_text)
        if us_matches > 0:
            relevance_score += 1
        
        # Filter out obviously irrelevant profiles
        irrelevant_indicators = ['student', 'intern', 'looking for', 'seeking', 'recent graduate']
        if any(indicator in combined_text for indicator in irrelevant_indicators):
            relevance_score -= 2
        
        # Require minimum relevance score
        return relevance_score >= 3
    
