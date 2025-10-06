"""Lead Enrichment Pipeline for the Houzz Lead Generation System.

Optimized pipeline with improved phase management, error handling, and performance.
Integrates all components for efficient lead generation and enrichment.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from .houzz_scraper import HouzzScraper
from .website_scraper import PersonalEmailExtractor
from .models import ProfessionalProfile
from .google_searcher import GoogleSearcher
from .database_manager import DatabaseManager
from .zerobounce_verifier import ZeroBounceVerifier
from .architizer_scraper import ArchitizerScraper
from .google_sheets_service import GoogleSheetsService
from config.config import config


class LeadEnrichmentPipeline:
    """Main pipeline for scraping and enriching leads from Houzz"""
    
    def __init__(self):
        self.setup_logging()
        self.setup_directories()
        self.google_sheets_service = GoogleSheetsService()
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = Path(config.LOG_DIR)
        log_dir.mkdir(exist_ok=True)
        
        # Configure loguru with optimized settings
        logger.add(
            log_dir / "scraper_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="30 days",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
            compression="zip",
            enqueue=True
        )
        
    def setup_directories(self):
        """Setup required directories"""
        Path(config.OUTPUT_DIR).mkdir(exist_ok=True)
        Path(config.LOG_DIR).mkdir(exist_ok=True)
        
    async def run_full_pipeline(self, location: str = None, professional_type: str = None, max_pages: Optional[int] = None, start_page: int = 1, platform: str = "houzz", row_number: int = None) -> str:
        """Run the complete lead generation pipeline for a single location and profession"""
        start_time = datetime.now()
        logger.info(f"Starting full {platform} lead generation pipeline for location '{location}' - {professional_type}")
        
        # Step 1: Scrape profiles for single location and profession
        if platform == "houzz":
            logger.info(f"Phase 1: Scraping Houzz profiles for location '{location}' and profession '{professional_type}'")
            profiles = await self.scrape_houzz_profiles(
                location=location,
                professional_type=professional_type,
                max_pages=max_pages,
                start_page=start_page
            )
            logger.info(f"Scraped {len(profiles)} Houzz profiles for location '{location}' - {professional_type}")
        elif platform == "architizer":
            logger.info("Phase 1: Scraping Architizer profiles")
            profiles = await self.scrape_architizer_profiles(location=location, max_pages=max_pages, start_page=start_page)
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
        
        # Step 4: Email validation and processing (with smart email selection)
        logger.info("Phase 4: Email validation and processing with smart email selection")
        try:
            stats = await self.validate_and_process_emails(platform=platform, start_time=start_time)
            logger.info(f"✅ Email validation and processing complete")
            
            # Step 5: Update Google Sheets with results (if enabled and successful)
            if stats and not stats.get('error'):
                await self._update_google_sheets(stats, row_number=row_number)
                await self._update_profiles_sheet(stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"Email validation phase failed: {e}")
            stats = {
                "total_profiles_processed": 0,
                "profiles_marked_completed": 0,
                "profiles_removed": 0,
                "invalid_emails_removed": 0,
                "error": str(e),
                "message": "Email validation failed"
            }
            return stats

    async def _validate_email_with_zerobounce(self, email: str) -> bool:
        """Validate email using ZeroBounce API"""
        try:
            from .zerobounce_verifier import ZeroBounceVerifier, ZeroBounceStatus
            verifier = ZeroBounceVerifier()
            result = await verifier.verify_single_email(email)
            
            # Handle different ZeroBounce statuses
            if result.status == ZeroBounceStatus.VALID:
                return True
            elif result.status == ZeroBounceStatus.INVALID:
                return False
            elif result.status == ZeroBounceStatus.UNKNOWN:
                # If ZeroBounce returns unknown (API error, etc.), do basic validation
                logger.warning(f"ZeroBounce returned unknown status for {email}: {result.sub_status}")
                # Do basic email format validation as fallback
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                return bool(re.match(email_pattern, email))
            else:
                # For other statuses (catch-all, disposable, etc.), consider invalid
                logger.info(f"Email {email} marked as invalid due to status: {result.status}")
                return False
            
        except Exception as e:
            logger.error(f"ZeroBounce validation error for {email}: {e}")
            # If validation fails completely, do basic email format validation
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return bool(re.match(email_pattern, email))

    def _select_best_emails(self, emails_json: dict) -> Optional[List[str]]:
        """
        Select the best emails (max 2, min 1) from personal and business emails.
        Priority: Personal emails first, then business emails if needed.
        
        Args:
            emails_json: Dictionary with 'personal' and 'business' email lists
        
        Returns:
            List of selected emails (1-2 emails), or None if no emails available
        """
        try:
            personal_emails = emails_json.get('personal', []) if isinstance(emails_json, dict) else []
            business_emails = emails_json.get('business', []) if isinstance(emails_json, dict) else []
            
            selected_emails = []
            
            # Step 1: Prioritize personal emails (take up to 2)
            if personal_emails:
                selected_emails.extend(personal_emails[:2])
            
            # Step 2: If we have less than 2 emails, add business emails
            if len(selected_emails) < 2 and business_emails:
                remaining_slots = 2 - len(selected_emails)
                selected_emails.extend(business_emails[:remaining_slots])
            
            # Return None if no emails found (will trigger profile removal)
            return selected_emails if selected_emails else None
            
        except Exception as e:
            logger.error(f"Error selecting best emails: {e}")
            return None

    async def validate_and_process_emails(self, platform: str = "houzz", start_time: datetime = None) -> Dict[str, Any]:
        """
        Step 4: Email validation and processing phase.
        - Validates emails via ZeroBounce
        - Selects max 2 emails (min 1 required) with priority: personal > business
        - Removes profiles with no valid emails
        - Marks validated profiles as completed
        
        Args:
            platform: Platform to process (default: "houzz")
        
        Returns:
            Dictionary with processing statistics
        """
        logger.info("Phase 4: Email validation and processing")
        db_manager = None
        
        try:
            db_manager = DatabaseManager()
            
            # Get profiles that need email validation
            all_profiles_data = db_manager.get_all_profiles_for_export(platform, limit=10000)
            
            # Convert to ProfessionalProfile objects
            all_profiles = []
            for profile_data in all_profiles_data:
                profile = ProfessionalProfile(
                    id=profile_data['id'],
                    name=profile_data['name'],
                    profile_url=profile_data['profile_url'],
                    professional_type=profile_data['professional_type'],
                    website=profile_data['website'],
                    phone=profile_data['phone'],
                    emails=profile_data['emails'],
                    platform=profile_data['platform'],
                    is_email_verified=profile_data['is_email_verified']
                )
                all_profiles.append(profile)
            
            if not all_profiles:
                logger.info("No profiles found in database for validation")
                return {
                    "total_profiles_processed": 0,
                    "profiles_marked_completed": 0,
                    "profiles_removed": 0,
                    "invalid_emails_removed": 0,
                    "profiles_with_valid_emails": 0,
                    "profiles": [],
                    "total_time_seconds": 0,
                    "total_time_minutes": 0,
                    "message": "No profiles to validate"
                }
            
            logger.info(f"🔍 Processing {len(all_profiles)} profiles for email validation...")
            
            # Process each profile
            validated_profiles = []
            profiles_removed = 0
            invalid_emails_removed_count = 0
            for profile in all_profiles:
                if profile.emails:
                    try:
                        # Parse existing emails
                        emails_json = json.loads(profile.emails) if isinstance(profile.emails, str) else profile.emails
                        
                        # Extract all emails for validation
                        personal_emails = emails_json.get('personal', []) if isinstance(emails_json, dict) else []
                        business_emails = emails_json.get('business', []) if isinstance(emails_json, dict) else []
                        
                        # Validate personal emails
                        validated_personal = []
                        for email in personal_emails:
                            is_valid = await self._validate_email_with_zerobounce(email)
                            if is_valid:
                                validated_personal.append(email)
                            else:
                                invalid_emails_removed_count += 1
                                logger.info(f"❌ Invalid personal email removed: {email} from {profile.name}")
                        
                        # Validate business emails
                        validated_business = []
                        for email in business_emails:
                            is_valid = await self._validate_email_with_zerobounce(email)
                            if is_valid:
                                validated_business.append(email)
                            else:
                                invalid_emails_removed_count += 1
                                logger.info(f"❌ Invalid business email removed: {email} from {profile.name}")
                        
                        # Create validated emails JSON
                        validated_emails_json = {
                            'personal': validated_personal,
                            'business': validated_business
                        }
                        
                        # Select best emails (max 2, min 1) - prioritize personal over business
                        selected_emails = self._select_best_emails(validated_emails_json)
                        
                        if selected_emails:
                            # Update profile with selected emails
                            profile.emails = selected_emails
                            validated_profiles.append(profile)
                            
                            # Update database with validated emails and mark as completed
                            db_manager.update_profile_field(profile.id, 'emails', json.dumps(validated_emails_json))
                            db_manager.mark_profile_completed(profile.id)
                            db_manager.mark_email_verified(profile.id)
                            
                            logger.info(f"✅ {profile.name}: Selected {len(validated_emails_json)} email(s): {validated_emails_json}")
                        else:
                            # Remove profile if no valid emails
                            await db_manager.remove_profile(profile.id)
                            profiles_removed += 1
                            logger.info(f"🗑️ Removed {profile.name} - no valid emails after validation")
                    
                    except Exception as e:
                        logger.error(f"Error processing emails for {profile.name}: {e}")
                else:
                    # Remove profiles without any emails
                    await db_manager.remove_profile(profile.id)
                    profiles_removed += 1
                    logger.info(f"🗑️ Removed {profile.name} - no emails to validate")

            # Calculate statistics
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()

            # Create simplified profile list with only name, emails, and profile_url
            simplified_profiles = []
            for profile in validated_profiles:
                simplified_profiles.append({
                    "name": profile.name,
                    "emails": profile.emails,
                    "profile_url": profile.profile_url
                })

            stats = {
                "total_profiles_processed": len(all_profiles),
                "profiles_marked_completed": len(validated_profiles),
                "profiles_removed": profiles_removed,
                "invalid_emails_removed": invalid_emails_removed_count,
                "profiles_with_valid_emails": len([p for p in validated_profiles if p.emails]),
                "profiles": simplified_profiles,
                "total_time_seconds": round(total_time, 2),
                "total_time_minutes": round(total_time / 60, 2),
                "message": f"Successfully processed {len(all_profiles)} profiles: {len(validated_profiles)} completed, {profiles_removed} removed, {invalid_emails_removed_count} invalid emails removed"
            }
            
            logger.info(f"✅ Email validation complete: {stats['message']} in {stats['total_time_seconds']} seconds")
            return stats
        
        except Exception as e:
            logger.error(f"Email validation phase failed: {e}")
            return {
                "total_profiles_processed": 0,
                "profiles_marked_completed": 0,
                "profiles_removed": 0,
                "invalid_emails_removed": 0,
                "error": str(e),
                "message": "Email validation failed"
            }
        finally:
            if db_manager:
                db_manager.close()

    
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
                            # Don't mark as scraped if there was an error
                            logger.warning(f"Not marking {profile_id} as scraped due to processing error")
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
            # Extract emails, phones, and social links using Playwright extractor
            extraction_result = await email_extractor.extract_emails_from_website_async(website, platform, existing_phone)
            personal_emails = extraction_result.get('personal', [])
            business_emails = extraction_result.get('business', [])
            extracted_phone = extraction_result.get('phone', None)
            extracted_social_links = extraction_result.get('social_links', {})

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

            # Update social links if found
            if extracted_social_links and any(extracted_social_links.values()):
                async with db_semaphore:
                    try:
                        db_manager.update_social_links(profile_id, extracted_social_links)
                        total_social_links = sum(len(links) for links in extracted_social_links.values())
                        logger.info(f"🔗 Updated {name} with {total_social_links} social links: {extracted_social_links}")
                    except Exception as e:
                        logger.error(f"Failed to update social links for {name}: {e}")

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
            # Mark website as scraped if we successfully processed it (even if no results found)
            # Only don't mark if there was an error during processing
            async with db_semaphore:
                try:
                    db_manager.mark_website_scraped_by_id(profile_id)
                    logger.info(f"✅ Marked {profile_id} as website scraped (processing completed)")
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
                
                for profile_id, name, professional_type, existing_email, website, linkedin_links_json, facebook_links_json, instagram_links_json, twitter_links_json, pinterest_links_json, youtube_links_json, other_social_links_json, zipcode, address in profiles_to_search:
                    total_processed += 1
                    
                    # Parse social links from separate columns
                    social_links = {}
                    for platform, links_json in [
                        ('linkedin', linkedin_links_json),
                        ('facebook', facebook_links_json),
                        ('instagram', instagram_links_json),
                        ('twitter', twitter_links_json),
                        ('pinterest', pinterest_links_json),
                        ('youtube', youtube_links_json),
                        ('other', other_social_links_json)
                    ]:
                        if links_json:
                            try:
                                links = json.loads(links_json) if isinstance(links_json, str) else links_json
                                if links:
                                    social_links[platform] = links
                            except (json.JSONDecodeError, TypeError):
                                logger.debug(f"Could not parse {platform} links for {name}: {links_json}")
                    
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
                        social_profiles = search_results.get('social_profiles', {})
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
                        
                        # Process social media profiles
                        if social_profiles:
                            # Map platform names to database column names
                            platform_mapping = {
                                'linkedin': 'linkedin_links',
                                'facebook': 'facebook_links',
                                'instagram': 'instagram_links', 
                                'twitter': 'twitter_links',
                                'x': 'twitter_links',  # X.com goes to twitter_links
                                'pinterest': 'pinterest_links',
                                'youtube': 'youtube_links',
                            }
                            for platform, profiles in social_profiles.items():
                                if profiles and platform in platform_mapping:
                                    platform_urls = [profile['url'] for profile in profiles]
                                    column_name = platform_mapping[platform]
                                    db_manager.update_profile_field(profile_id, column_name, platform_urls)
                                    logger.info(f"✓ Updated {name} with {platform}: {platform_urls}")
                                    if platform == 'linkedin':
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
                        
                        # Mark as searched if processing completed (even if no new information found)
                        # Only don't mark if there was an error during processing
                        db_manager.mark_google_search_done_by_id(profile_id)
                        logger.info(f"✅ Marked {profile_id} as Google search done (processing completed)")
                        
                        # Rate limiting for Google API (100 searches per day for free tier)
                        await asyncio.sleep(2)  # 2 second delay between searches
                        
                    except Exception as e:
                        logger.error(f"Error searching for {name}: {e}")
                        # Don't mark as attempted if there was an error
                        logger.warning(f"❌ Not marking {profile_id} as Google search done due to error")
                        continue
                
                # Move to next batch
                offset += batch_size
                logger.info(f"=== BATCH COMPLETED === Total processed: {total_processed}, Gmail found: {total_with_gmail}, LinkedIn found: {total_with_linkedin}, Zipcode found: {total_with_zipcode}")
        
        except Exception as e:
            logger.error(f"Error in perform_google_search_enrichment: {e}")
        finally:
            if db_manager:
                db_manager.close()

    async def scrape_architizer_profiles(self, location: str, max_pages: Optional[int] = None, start_page: int = 1) -> List[ProfessionalProfile]:
        profiles = []
        db_manager = None
        
        try:
            # Initialize database manager
            db_manager = DatabaseManager()
            logger.info("Database manager initialized for Architizer")

            async with ArchitizerScraper(db_manager) as scraper:
                # Use default location "United States" - Architizer scrapes all firms
                profiles = await scraper.scrape_firms(location=location, start_page=start_page, max_pages=max_pages)
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

    async def scrape_houzz_profiles(self, location: str, professional_type: str, max_pages: int = 50, start_page: int = 1) -> List[ProfessionalProfile]:
        """Scrape Houzz profiles for a single location and profession"""
        profiles = []
        db_manager = None
        
        try:
            # Initialize database manager
            db_manager = DatabaseManager()
            logger.info(f"Database manager initialized for location '{location}' scraping")
            
            async with HouzzScraper(database_manager=db_manager) as scraper:
                logger.info(f"Scraping configuration:")
                logger.info(f"  Location: {location}")
                logger.info(f"  Professional type: {professional_type}")
                logger.info(f"  Max pages: {max_pages}")
                logger.info(f"  Starting page: {start_page}")
                
                # Scrape using the location-based method
                logger.info(f"\n🔍 Starting scrape for {professional_type} at location '{location}'")
                
                # Use the new location-based scraping method
                location_profiles = await scraper.get_professionals_by_location(
                    location=location,
                    professional_type=professional_type, 
                    max_pages=max_pages,
                    start_page=start_page
                )
                
                profiles.extend(location_profiles)
                
                # Profiles are already saved immediately by the scraper
                logger.info(f"✅ Scraped {len(location_profiles)} profiles for location '{location}' - {professional_type} (saved automatically)")
            
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

    async def _update_google_sheets(self, stats: Dict[str, Any], row_number: int = None) -> None:
        """
        Update Google Sheets with pipeline completion results
        
        Args:
            stats: Pipeline statistics dictionary
            row_number: Row number to update (1-based). If None, will skip update.
        """
        try:
            if not self.google_sheets_service.is_available():
                logger.info("Google Sheets integration not available - skipping update")
                return
            
            # Skip update if no row number provided
            if row_number is None:
                logger.info("No row number provided - skipping Google Sheets update")
                return

            profiles_processed = stats.get('total_profiles_processed', 0)
            if profiles_processed <= 0:
                logger.info("No profiles processed - skipping Google Sheets update")
                return
            
            logger.info(f"📊 Updating Google Sheets row {row_number} with pipeline results...")
            
            # Test connection first
            if not self.google_sheets_service.test_connection():
                logger.warning("Google Sheets connection test failed - skipping update")
                return
            
            # Update with results
            success = self.google_sheets_service.update_pipeline_results(
                total_time_minutes=stats.get('total_time_minutes', 0),
                row_number=row_number
            )
            
            if success:
                logger.info(f"✅ Google Sheets row {row_number} updated successfully with pipeline results")
            else:
                logger.warning(f"⚠️ Failed to update Google Sheets row {row_number}")
                
        except Exception as e:
            logger.error(f"Error updating Google Sheets: {e}")
            # Don't raise the exception - Google Sheets update failure shouldn't break the pipeline

    async def _update_profiles_sheet(self, stats: Dict[str, Any]) -> None:
        """
        Update Google Sheets profiles sheet with profile names and emails
        
        Args:
            stats: Pipeline statistics dictionary containing profiles
        """
        try:
            if not self.google_sheets_service.is_available():
                logger.info("Google Sheets service not available - skipping profiles sheet update")
                return
            
            logger.info("📊 Updating profiles sheet with profile data...")
            
            # Update profiles sheet
            success = self.google_sheets_service.update_profiles_sheet(stats)
            
            if success:
                logger.info("✅ Profiles sheet updated successfully")
            else:
                logger.warning("⚠️ Failed to update profiles sheet")
                
        except Exception as e:
            logger.error(f"Error updating profiles sheet: {e}")
            # Don't raise the exception - Profiles sheet update failure shouldn't break the pipeline
