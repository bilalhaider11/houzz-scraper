"""Lead Enrichment Pipeline for the Houzz Lead Generation System.

Optimized pipeline with improved phase management, error handling, and performance.
Integrates all components for efficient lead generation and enrichment.
"""

import asyncio
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from .houzz_scraper import HouzzScraper
from .website_scraper import PersonalEmailExtractor
from .models import ProfessionalProfile
from .google_searcher import GoogleSearcher
from .common_utils import StateManager
from .database_manager import DatabaseManager
from .zerobounce_verifier import ZeroBounceVerifier
from .email_service import email_service
from .cache_manager import cache_manager
from .architizer_scraper import ArchitizerScraper
from config.config import config


class LeadEnrichmentPipeline:
    """Main pipeline for scraping and enriching leads from Houzz"""
    
    def __init__(self):
        self.state_manager = StateManager()
        self.setup_logging()
        self.setup_directories()
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = Path(config.LOG_DIR)
        log_dir.mkdir(exist_ok=True)
        
        # Configure loguru
        logger.add(
            log_dir / "scraper_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="30 days",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
        )
        
    def setup_directories(self):
        """Setup required directories"""
        Path(config.OUTPUT_DIR).mkdir(exist_ok=True)
        Path(config.LOG_DIR).mkdir(exist_ok=True)
        
    async def run_full_pipeline(self, states: List[str] = None, professional_types: List[str] = None, max_pages: Optional[int] = None, start_page: int = 1, max_profiles: int = None, verify_emails: bool = True, platform: str = "houzz", cities: List[str] = None) -> str:
        """Run the complete lead generation pipeline"""
        logger.info(f"Starting full {platform} lead generation pipeline")
        
        # Step 1: Scrape profiles based on platform
        if platform == "houzz":
            logger.info("Phase 1: Scraping Houzz profiles")
            profiles = await self.scrape_houzz_profiles(
                states=states, 
                professional_types=professional_types,
                max_pages=max_pages,
                start_page=start_page,
                max_profiles=max_profiles,
                cities=cities
            )
            logger.info(f"Scraped {len(profiles)} Houzz profiles")
        elif platform == "architizer":
            logger.info("Phase 1: Scraping Architizer profiles")
            profiles = await self.scrape_architizer_profiles(max_pages=max_pages, start_page=start_page)
            logger.info(f"Scraped {len(profiles)} Architizer profiles")
        else:
            raise ValueError(f"Unsupported platform: {platform}")
        
        # Step 2: Website scraping phase (extract personal emails from websites)
        logger.info("Phase 2: Website scraping - extracting personal emails")
        try:
            await self.extract_personal_emails_from_websites(platform=platform)
            logger.info("Website scraping phase completed")
        except Exception as e:
            logger.error(f"Website scraping phase failed: {e}")
            logger.info("Continuing with remaining phases...")
        
        # Step 3: Google search enrichment phase
        logger.info("Phase 3: Google search enrichment - finding Gmail addresses and LinkedIn profiles")
        try:
            await self.perform_google_search_enrichment(platform=platform)
            logger.info("Google search enrichment phase completed")
        except Exception as e:
            logger.error(f"Google search enrichment phase failed: {e}")
            logger.info("Continuing with remaining phases...")
        
        # Step 4: Export to CSV with ZeroBounce verification
        logger.info("Phase 4: Exporting to CSV with ZeroBounce verification")
        try:
            output_file = await self.run_export_phase(verify_emails=verify_emails, platform=platform)
            if output_file:
                logger.info(f"Exported leads to {output_file}")
            else:
                logger.error("Failed to export leads")
        except Exception as e:
            logger.error(f"Export phase failed: {e}")
            output_file = None
        
        return output_file

    async def run_websearch_phase(self, platform: str = "houzz"):
        """Run website scraping phase for profiles that need it"""
        logger.info(f"Starting website scraping phase for {platform}")
        
        try:
            await self.extract_personal_emails_from_websites(platform=platform)
            logger.info("Website scraping phase completed")
            
        except Exception as e:
            logger.error(f"Error in run_websearch_phase: {e}")
    
    async def run_google_search_phase(self, platform: str = "houzz"):
        """Run Google search enrichment phase for profiles that need Gmail or LinkedIn information"""
        logger.info(f"Starting Google search enrichment phase for {platform}")
        
        try:
            await self.perform_google_search_enrichment(platform=platform)
            logger.info("Google search enrichment phase completed")
            
        except Exception as e:
            logger.error(f"Error in run_google_search_phase: {e}")
    
    async def extract_personal_emails_from_websites(self, platform: str = "houzz") -> None:
        """Extract personal emails from professional websites stored in database using advanced email scraping with Playwright"""
        logger.info("Starting advanced personal email extraction from websites using Playwright")
        db_manager = None
        
        try:
            db_manager = DatabaseManager()
            
            # Get total count for progress tracking
            total_profiles = db_manager.get_total_profiles_for_website_scraping(platform=platform)
            logger.info(f"Total profiles available for website scraping ({platform}): {total_profiles}")
            
            if total_profiles == 0:
                logger.info("No profiles found with websites to scrape")
                return
            
            # Track overall statistics
            total_processed = 0
            total_with_emails_found = 0  # Profiles where we found emails this run
            total_emails_updated = 0     # Profiles where we actually updated email data in DB
            batch_size = 100
            batch_number = 0
            offset = 0
            
            logger.info(f"Processing profiles in batches of {batch_size} using offset-based pagination with Playwright")
            
            # Initialize the email extractor with Playwright context manager
            async with PersonalEmailExtractor(max_concurrent_requests=10) as email_extractor:
                while offset < total_profiles:
                    batch_number += 1
                    
                    # Get next batch of profiles with details (id, name, website) for email scraping using offset
                    profiles_to_scrape = db_manager.get_profiles_with_details_for_website_scraping(
                        platform=platform,
                        limit=batch_size,
                        offset=offset
                    )
                    if not profiles_to_scrape:
                        logger.info(f"No more profiles found at offset {offset}")
                        break
                    
                    progress_percentage = (offset / total_profiles) * 100
                    logger.info(f"\n=== BATCH {batch_number} ({len(profiles_to_scrape)} profiles) - Progress: {progress_percentage:.1f}% ===")
                    logger.info(f"Processing profiles {offset+1} to {offset+len(profiles_to_scrape)} of {total_profiles}")
                    
                    # Create semaphore for controlling concurrent database writes
                    db_semaphore = asyncio.Semaphore(5)
                    
                    # Create concurrent tasks for all profiles in the batch
                    logger.info(f"Processing {len(profiles_to_scrape)} profiles in parallel...")
                    tasks = []
                    
                    for profile_data in profiles_to_scrape:
                        task = self._scrape_single_profile(
                            profile_data, email_extractor, db_manager, db_semaphore, platform
                        )
                        tasks.append(task)
                    
                    # Execute all tasks concurrently
                    batch_results_raw = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Process results and update counters
                    batch_results = []
                    for i, result in enumerate(batch_results_raw):
                        total_processed += 1
                        
                        if isinstance(result, Exception):
                            profile_id, name, website, existing_phone, existing_emails_json = profiles_to_scrape[i]
                            logger.error(f"Failed to process {name} ({website}): {result}")
                            batch_results.append((profile_id, name, [], []))
                            # Mark as attempted even if failed
                            try:
                                db_manager.mark_website_scraped_by_id(profile_id)
                            except Exception as e:
                                logger.error(f"Failed to mark {profile_id} as scraped: {e}")
                        else:
                            profile_id, name, personal_emails, business_emails, best_email, emails_updated = result
                            if best_email:
                                total_with_emails_found += 1
                            if emails_updated:
                                total_emails_updated += 1
                            batch_results.append((profile_id, name, personal_emails, business_emails))
                    
                    # Batch summary statistics
                    batch_with_emails = sum(1 for _, _, personal, business in batch_results if personal or business)
                    batch_success_rate = (batch_with_emails / len(batch_results) * 100) if batch_results else 0
                    overall_progress = (total_processed / total_profiles) * 100
                    
                    logger.info(f"\n=== BATCH {batch_number} SUMMARY ===")
                    logger.info(f"Batch processed: {len(batch_results)}")
                    logger.info(f"Batch with emails found: {batch_with_emails}")
                    logger.info(f"Batch success rate: {batch_success_rate:.1f}%")
                    logger.info(f"Overall progress: {total_processed}/{total_profiles} ({overall_progress:.1f}%) processed, {total_with_emails_found} with emails")
                    
                    # Move to next batch
                    offset += batch_size
                    logger.info(f"Proceeding to next batch (offset: {offset})...")
            
            # Final summary statistics
            email_find_rate = (total_with_emails_found / total_processed * 100) if total_processed > 0 else 0
            database_update_rate = (total_emails_updated / total_processed * 100) if total_processed > 0 else 0
            
            logger.info(f"\n=== FINAL WEBSITE SCRAPING EMAIL EXTRACTION SUMMARY ===")
            logger.info(f"📊 PROCESSING STATISTICS:")
            logger.info(f"  • Total profiles available for website scraping: {total_profiles}")
            logger.info(f"  • Total profiles processed this run: {total_processed}")
            logger.info(f"  • Profiles where emails were found: {total_with_emails_found} ({email_find_rate:.1f}%)")
            logger.info(f"  • Profiles where emails were updated in database: {total_emails_updated} ({database_update_rate:.1f}%)")
            logger.info(f"  • Total batches processed: {batch_number}")
            logger.info(f"")
            logger.info(f"🎯 EMAIL EXTRACTION RESULTS:")
            logger.info(f"  • Email discovery success rate: {email_find_rate:.1f}%")
            logger.info(f"  • Database update success rate: {database_update_rate:.1f}%")
            logger.info(f"  • Profiles still needing email extraction: {total_profiles - total_processed}")
            logger.info(f"")
            logger.info(f"✅ Advanced email extraction with Playwright completed for all available profiles")
            
        except Exception as e:
            logger.error(f"Error in extract_personal_emails_from_websites: {e}")
            logger.exception("Full traceback:")
        finally:
            if db_manager:
                db_manager.close()
    
    async def _scrape_single_profile(self, profile_data, email_extractor, db_manager, db_semaphore, platform):
        """Scrape a single profile for emails and phones with database concurrency control"""
        profile_id, name, website, existing_phone, existing_emails_json = profile_data
        if not website.startswith('http'):
            website = 'https://' + website
        emails_updated = False  # Track if we actually updated the database
        phone_updated = False   # Track if we actually updated the phone
        
        try:
            # Extract emails and phones using Playwright extractor
            extraction_result = await email_extractor.extract_emails_from_website_async(website, platform, existing_phone)
            personal_emails = extraction_result.get('personal', [])
            business_emails = extraction_result.get('business', [])
            extracted_phone = extraction_result.get('phone', None)

            # Update phone if found and platform is Architizer and no existing phone
            if extracted_phone and platform == "architizer" and not existing_phone:
                async with db_semaphore:
                    try:
                        db_manager.update_profile_phone(profile_id, extracted_phone)
                        logger.info(f"📞 Updated {name} with phone: {extracted_phone}")
                        phone_updated = True
                    except Exception as e:
                        logger.error(f"Failed to update phone for {name}: {e}")
                        phone_updated = False

            if personal_emails or business_emails:
                best_personal_email = personal_emails[0] if personal_emails else None
                best_business_email = business_emails[0] if business_emails else None
                best_email = best_personal_email or best_business_email

                logger.info(f"✓ Found personal emails for {name}: {personal_emails}")
                logger.info(f"✓ Found business emails for {name}: {business_emails}")

                # Parse existing emails JSON and merge with new ones
                async with db_semaphore:
                    try:
                        # Parse existing emails from the query result
                        existing_emails_data = {"personal": [], "business": []}
                        if existing_emails_json:
                            try:
                                if isinstance(existing_emails_json, str):
                                    existing_emails_data = json.loads(existing_emails_json)
                                else:
                                    existing_emails_data = existing_emails_json
                            except (json.JSONDecodeError, TypeError):
                                logger.warning(f"Could not parse existing emails for {name}: {existing_emails_json}")
                        
                        # Merge new emails with existing ones, avoiding duplicates
                        merged_emails = self._merge_emails_without_duplicates(
                            existing_emails_data, 
                            {"personal": personal_emails, "business": business_emails}
                        )
                        
                        # Save merged emails as JSON
                        db_manager.update_profile_emails_json(profile_id, merged_emails)
                        logger.info(f"📧 Updated {name} with merged emails: {merged_emails}")
                        emails_updated = True  # Successfully updated database
                    except Exception as e:
                        logger.error(f"Failed to update emails for {name}: {e}")
                        emails_updated = False

                return (profile_id, name, personal_emails, business_emails, best_email, emails_updated)
            else:
                logger.info(f"✗ No emails found for {name}")
                return (profile_id, name, [], [], None, emails_updated)

        except Exception as e:
            logger.error(f"Error extracting emails from {website}: {e}")
            return (profile_id, name, [], [], None, emails_updated)
        finally:
            # Mark website as scraped regardless of success
            async with db_semaphore:
                try:
                    db_manager.mark_website_scraped_by_id(profile_id)
                except Exception as e:
                    logger.error(f"Failed to mark website as scraped for {profile_id}: {e}")

    def _merge_emails_without_duplicates(self, existing_emails: dict, new_emails: dict) -> dict:
        """Merge new emails with existing ones, avoiding duplicates"""
        try:
            # Initialize with existing emails or empty structure
            if existing_emails and isinstance(existing_emails, dict):
                merged_emails = {
                    "personal": existing_emails.get("personal", []),
                    "business": existing_emails.get("business", [])
                }
            else:
                merged_emails = {"personal": [], "business": []}
            
            # Add new personal emails (avoiding duplicates)
            if new_emails.get("personal"):
                for email in new_emails["personal"]:
                    if email not in merged_emails["personal"]:
                        merged_emails["personal"].append(email)
            
            # Add new business emails (avoiding duplicates)
            if new_emails.get("business"):
                for email in new_emails["business"]:
                    if email not in merged_emails["business"]:
                        merged_emails["business"].append(email)
            
            logger.info(f"📧 Merged emails - Personal: {len(merged_emails['personal'])}, Business: {len(merged_emails['business'])}")
            return merged_emails
            
        except Exception as e:
            logger.error(f"Error merging emails: {e}")
            # Return new emails if merging fails
            return new_emails

    async def perform_google_search_enrichment(self, platform: str = "houzz", batch_size=25):
        """Perform Google search enrichment for profiles that need Gmail or LinkedIn information in production mode with pagination"""
        logger.info("Starting Google search enrichment with pagination")
        db_manager = None
        
        try:
            db_manager = DatabaseManager()
            google_searcher = GoogleSearcher()
            
            # Test Google API connection first
            if not google_searcher.test_api_connection():
                # Check if it's due to quota limits
                cache_stats = google_searcher.get_cache_stats()
                if cache_stats.get('quota_exceeded'):
                    logger.warning("Google Custom Search API quota exceeded, skipping Google search enrichment")
                    logger.info("Continuing with pipeline - other phases will still run")
                else:
                    logger.warning("Google Custom Search API not available, skipping Google search enrichment")
                    logger.info("Continuing with pipeline - other phases will still run")
                return
            
            total_processed = 0
            total_with_gmail = 0
            total_with_linkedin = 0
            total_with_zipcode = 0
            offset = 0
            
            while True:
                # Get profiles in batches
                profiles_to_search = db_manager.get_profiles_for_google_search(platform=platform, limit=batch_size, offset=offset)
                
                if not profiles_to_search:
                    logger.info("No more profiles found that need Google search enrichment")
                    break
                
                logger.info(f"Found {len(profiles_to_search)} profiles in this batch for Google search enrichment")
                
                # Log current quota status
                cache_stats = google_searcher.get_cache_stats()
                logger.info(f"Google API status: {cache_stats['request_count']}/{google_searcher.max_requests_per_day} requests used, quota exceeded: {cache_stats['quota_exceeded']}")
                
                for profile_id, name, professional_type, existing_email, website, social_links_json, zipcode, address in profiles_to_search:
                    total_processed += 1
                    
                    # Parse social_links JSON
                    social_links = {}
                    if social_links_json:
                        try:
                            social_links = json.loads(social_links_json) if isinstance(social_links_json, str) else social_links_json
                        except (json.JSONDecodeError, TypeError):
                            logger.debug(f"Could not parse social_links for {name}: {social_links_json}")
                            social_links = {}
                    
                    # Parse existing emails JSON
                    existing_emails_data = {'personal': [], 'business': []}
                    if existing_email:
                        try:
                            existing_emails_data = json.loads(existing_email) if isinstance(existing_email, str) else existing_email
                        except (json.JSONDecodeError, TypeError):
                            logger.debug(f"Could not parse existing emails for {name}: {existing_email}")
                            existing_emails_data = {'personal': [], 'business': []}
                    
                    logger.info(f"Processing Google search for {name} ({professional_type})")
                    
                    try:
                        # Perform Google search with social_links, address, and zipcode
                        search_results = google_searcher.search_professional_info(
                            name, professional_type, website=website, social_links=social_links, 
                            address=address, zipcode=zipcode
                        )
                        
                        personal_emails = search_results.get('personal_emails', [])
                        linkedin_profiles = search_results.get('linkedin_profiles', [])
                        found_zipcode = search_results.get('zipcode')
                        
                        # Update database with found information
                        updates_made = False
                        
                        # Merge new personal emails with existing ones (avoid duplicates)
                        if personal_emails:
                            new_emails_data = {"personal": personal_emails, "business": []}
                            merged_emails = self._merge_emails_without_duplicates(existing_emails_data, new_emails_data)
                            
                            # Check if any new emails were added
                            original_personal_count = len(existing_emails_data.get('personal', []))
                            new_personal_count = len(merged_emails.get('personal', []))
                            
                            if new_personal_count > original_personal_count:
                                db_manager.update_profile_emails_json(profile_id, merged_emails)
                                new_emails = merged_emails['personal'][original_personal_count:]
                                logger.info(f"✓ Updated {name} with new personal emails: {new_emails}")
                                total_with_gmail += 1
                                updates_made = True
                            else:
                                logger.info(f"No new personal emails found for {name} (all already exist)")
                        
                        if linkedin_profiles:
                            best_linkedin = linkedin_profiles[0]['url']  # Take the first LinkedIn profile
                            db_manager.update_profile_linkedin(profile_id, best_linkedin)
                            logger.info(f"✓ Updated {name} with LinkedIn: {best_linkedin}")
                            total_with_linkedin += 1
                            updates_made = True
                        
                        # Update zipcode if found and not already available
                        if found_zipcode and not zipcode:
                            db_manager.update_profile_zipcode(profile_id, found_zipcode)
                            logger.info(f"✓ Updated {name} with zipcode: {found_zipcode}")
                            total_with_zipcode += 1
                            updates_made = True
                        
                        if not updates_made:
                            logger.info(f"✗ No new information found for {name}")
                        
                        # Mark as searched regardless of results
                        db_manager.mark_google_search_done_by_id(profile_id)
                        
                        # Rate limiting for Google API (100 searches per day for free tier)
                        await asyncio.sleep(2)  # 2 second delay between searches
                        
                    except Exception as e:
                        logger.error(f"Error searching for {name}: {e}")
                        # Still mark as attempted to avoid retrying
                        db_manager.mark_google_search_done_by_id(profile_id)
                        continue
                
                # Move to next batch
                offset += batch_size
                logger.info(f"=== BATCH COMPLETED === Total processed: {total_processed}, Gmail found: {total_with_gmail}, LinkedIn found: {total_with_linkedin}, Zipcode found: {total_with_zipcode}")
        
        except Exception as e:
            logger.error(f"Error in perform_google_search_enrichment: {e}")
        finally:
            if db_manager:
                db_manager.close()

    async def run_export_phase(self, verify_emails: bool = True, platform: str = "houzz") -> str:
        """Run the CSV export phase with ZeroBounce email verification"""
        if verify_emails:
            logger.info("Starting export phase with ZeroBounce email verification")
        else:
            logger.info("Starting export phase (email verification disabled)")
        
        db_manager = DatabaseManager()
        
        try:
            # Step 1: ZeroBounce email verification (if enabled)
            if verify_emails:
                logger.info("Running ZeroBounce email verification")
                try:
                    async with ZeroBounceVerifier() as zerobounce:
                        await zerobounce.verify_database_emails(db_manager, platform)
                except Exception as e:
                    logger.warning(f"ZeroBounce email verification failed: {e}")
                    logger.info("Continuing with export without email verification")
            else:
                logger.info("Email verification disabled - skipping verification step")
            
            # Step 2: Export all profiles to CSV
            total_profiles = db_manager.get_total_profiles_for_export_count(platform=platform)
            batch_size = 1000  # Process in batches of 1000
            all_contacts = []
            exported_profile_ids = []

            logger.info(f"Found {total_profiles} profiles to export (not yet completed)")
            
            for offset in range(0, total_profiles, batch_size):
                profiles = db_manager.get_all_profiles_for_export(platform, limit=batch_size, offset=offset)
                all_contacts.extend(profiles)
                # Track profile IDs for marking as completed
                exported_profile_ids.extend([profile['id'] for profile in profiles])

            # Construct DataFrame from all contacts
            df = pd.DataFrame(all_contacts)

            # Reorder columns for specific platform exports
            if platform == "architizer":
                # Define the exact column order for Architizer export
                architizer_columns = [
                    'profile_url', 'name', 'website', 'emails', 'phone', 'address', 
                    'professional_type', 'social_links', 'is_email_verified', 'zip_code', 
                    'website_scraped', 'google_search_done', 'created_at', 'updated_at'
                ]
                
                # Filter DataFrame to only include the requested columns in the specified order
                available_columns = [col for col in architizer_columns if col in df.columns]
                df = df[available_columns]
                
                logger.info(f"Exported Architizer data with {len(available_columns)} columns: {available_columns}")

            # Export DataFrame to CSV
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{platform}_export_{timestamp}.csv"
            filepath = Path(config.OUTPUT_DIR) / filename
            df.to_csv(filepath, index=False)
            
            # Mark all exported profiles as completed
            logger.info(f"Marking {len(exported_profile_ids)} profiles as completed")
            for profile_id in exported_profile_ids:
                db_manager.mark_profile_completed(profile_id)

            logger.info(f"Successfully exported verified data to {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Error in run_export_phase: {e}")
            return ""
        finally:
            db_manager.close()

    async def scrape_architizer_profiles(self, max_pages: Optional[int] = None, start_page: int = 1) -> List[ProfessionalProfile]:
        profiles = []
        db_manager = None
        
        try:
            # Initialize database manager
            db_manager = DatabaseManager()
            logger.info("Database manager initialized for Architizer")

            async with ArchitizerScraper(db_manager) as scraper:
                profiles = await scraper.scrape_firms(start_page=start_page, max_pages=max_pages)
            logger.info(f"Total Architizer profiles scraped and stored: {len(profiles)}")
            return profiles

        except Exception as e:
            logger.error(f"Error in scrape_architizer_profiles: {e}")
            return profiles
        finally:
            # Ensure database connection is closed
            if db_manager:
                try:
                    db_manager.close()
                    logger.info("Database connection closed")
                except Exception as e:
                    logger.error(f"Error closing database connection: {e}")

    async def scrape_houzz_profiles(self, states: List[str] = None, professional_types: List[str] = None, max_pages: int = 50, start_page: int = 1, max_profiles: int = None, cities: List[str] = None) -> List[ProfessionalProfile]:
        profiles = []
        db_manager = None
        
        try:
            # Initialize database manager
            db_manager = DatabaseManager()
            logger.info("Database manager initialized")
            
            async with HouzzScraper(database_manager=db_manager) as scraper:
                # Use provided parameters or defaults
                target_states = states or config.US_STATES
                target_professional_types = professional_types or config.PROFESSIONAL_TYPES
                
                logger.info(f"Scraping configuration:")
                logger.info(f"  States: {len(target_states)} ({target_states[:3]}{'...' if len(target_states) > 3 else ''})")
                logger.info(f"  Professional types: {len(target_professional_types)} ({target_professional_types})")
                logger.info(f"  Max pages per city: {max_pages}")
                logger.info(f"  Starting page: {start_page}")
                if max_profiles:
                    logger.info(f"  Max profiles limit: {max_profiles}")
                if cities:
                    logger.info(f"  Specific cities: {cities}")
                
                # Scrape all combinations of states and professional types
                for state in target_states:
                    for prof_type in target_professional_types:
                        logger.info(f"\n🔍 Starting scrape for {prof_type} in {state}")
                        
                        # If cities are specified, filter to only those cities
                        if cities and state in cities[0].lower():
                            # Extract city names from the cities parameter (skip the first element which is the state)
                            requested_cities = cities[1:] if len(cities) > 1 else []
                            if requested_cities:
                                logger.info(f"Scraping specific cities in {state}: {requested_cities}")
                                state_profiles = await scraper.get_state_professionals_direct_filtered(
                                    state=state, 
                                    professional_type=prof_type, 
                                    max_pages=max_pages,
                                    start_page=start_page,
                                    target_cities=requested_cities
                                )
                            else:
                                logger.warning(f"No cities specified for {state}, skipping")
                                continue
                        else:
                            # Scrape all cities in the state (original behavior)
                            state_profiles = await scraper.get_state_professionals_direct(
                                state=state, 
                                professional_type=prof_type, 
                                max_pages=max_pages,
                                start_page=start_page
                            )
                        
                        profiles.extend(state_profiles)
                        
                        # Profiles are already saved immediately by the scraper
                        logger.info(f"✅ Scraped {len(state_profiles)} profiles for {state} - {prof_type} (saved automatically)")
                        
                        # Check if we've reached the max profiles limit
                        if max_profiles and len(profiles) >= max_profiles:
                            logger.info(f"🎯 Reached max profiles limit ({max_profiles}), stopping scrape")
                            return profiles[:max_profiles]
            
            logger.info(f"Total profiles scraped and stored: {len(profiles)}")
            return profiles
            
        except Exception as e:
            logger.error(f"Error in scrape_houzz_profiles: {e}")
            return profiles
        finally:
            # Ensure database connection is closed
            if db_manager:
                try:
                    db_manager.close()
                    logger.info("Database connection closed")
                except Exception as e:
                    logger.error(f"Error closing database connection: {e}")
 
