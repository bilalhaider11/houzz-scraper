"""Lead Enrichment Pipeline for the Houzz Lead Generation System.

3-Phase Pipeline Architecture:
1. Platform Profile Scraping (Houzz/Architizer) - Extracts professional profiles
2. Website Email Mining (Playwright) - Extracts emails, phones, and social links from websites
3. Email Validation & Processing - Validates emails, selects best contacts, updates Google Sheets

Features:
- Multi-platform support (Houzz and Architizer)
- ZeroBounce email verification with smart email selection (max 2, min 1)
- Intelligent email prioritization (personal > business)
- Google Sheets integration for results tracking
- Parallel processing with async operations
- Resume capability and progress tracking
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
from .database_manager import DatabaseManager
from .zerobounce_verifier import ZeroBounceVerifier
from .architizer_scraper import ArchitizerScraper
from .google_sheets_service import GoogleSheetsService
from .email_prevalidation import EmailPreValidator
from config.config import config


class LeadEnrichmentPipeline:
    """Main pipeline for scraping and enriching leads from Houzz"""
    
    def __init__(self):
        self.setup_logging()
        self.setup_directories()
        self.google_sheets_service = GoogleSheetsService()
        self.email_prevalidator = EmailPreValidator()  # Pre-validation filter to save ZeroBounce credits
        
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
        """
        Run the complete 3-phase lead generation pipeline.
        
        Phase 1: Platform Profile Scraping - Extract professional profiles
        Phase 2: Website Email Mining - Extract emails, phones, and social links from websites
        Phase 3: Email Validation & Processing - Validate emails, select best contacts, update Google Sheets
        
        Args:
            location: Geographic location to scrape (e.g., 'usa', 'california')
            professional_type: Type of professional (required for Houzz)
            max_pages: Maximum number of pages to scrape
            start_page: Starting page number
            platform: Platform to scrape ('houzz' or 'architizer')
            row_number: Google Sheets row number to update with results
            
        Returns:
            Dictionary with pipeline statistics and results
        """
        start_time = datetime.now()
        logger.info(f"🚀 Starting complete 3-phase {platform.upper()} lead generation pipeline for location '{location}' - {professional_type}")
        
        # Step 1: Scrape profiles for single location and profession
        if platform == "houzz":
            logger.info(f"📋 PHASE 1: Platform Profile Scraping - Houzz profiles for location '{location}' and profession '{professional_type}'")
            profiles = await self.scrape_houzz_profiles(
                location=location,
                professional_type=professional_type,
                max_pages=max_pages,
                start_page=start_page
            )
            logger.info(f"✅ Phase 1 Complete: Scraped {len(profiles)} Houzz profiles for location '{location}' - {professional_type}")
        elif platform == "architizer":
            logger.info("📋 PHASE 1: Platform Profile Scraping - Architizer architectural firms")
            profiles = await self.scrape_architizer_profiles(location=location, max_pages=max_pages, start_page=start_page)
            logger.info(f"✅ Phase 1 Complete: Scraped {len(profiles)} Architizer profiles")
        else:
            raise ValueError(f"Unsupported platform: {platform}")
        
        # Step 2: Website scraping phase (extract emails, phones, and social links from websites)
        logger.info("🌐 PHASE 2: Website Email Mining - Extracting emails, phones, and social links using Playwright")
        try:
            await self.extract_personal_emails_from_websites(platform=platform)
            logger.info("✅ Phase 2 Complete: Website email mining finished successfully")
        except Exception as e:
            logger.error(f"❌ Phase 2 Failed: Website scraping phase encountered error: {e}")
            logger.info("⚠️  Continuing with remaining phases...")
        
        # Step 3: Email validation and processing with Google Sheets update
        logger.info("✅ PHASE 3: Email Validation & Processing - Validating emails with ZeroBounce, selecting best contacts (max 2, min 1, prioritizing personal emails), and updating Google Sheets")
        try:
            stats = await self.validate_and_process_emails(platform=platform, start_time=start_time)
            logger.info(f"✅ Phase 3 Complete: Email validation and processing finished successfully")

            logger.info(f"🎉 PIPELINE COMPLETE: All 3 phases finished successfully!")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Phase 3 Failed: Email validation phase encountered error: {e}")
            stats = {
                "total_profiles_processed": 0,
                "profiles_marked_completed": 0,
                "profiles_removed": 0,
                "invalid_emails_removed": 0,
                "error": str(e),
                "message": "Email validation failed"
            }
            return stats

    async def _validate_email_with_zerobounce(self, email: str) -> tuple[bool, dict]:
        """
        Validate email using ZeroBounce API with strict VALID-only acceptance
        
        Returns:
            tuple: (is_valid: bool, response_data: dict)
        """
        try:
            from .zerobounce_verifier import ZeroBounceVerifier, ZeroBounceStatus
            async with ZeroBounceVerifier() as verifier:
                result = await verifier.verify_single_email(email)
                
                # Log full ZeroBounce response for debugging
                response_data = {
                    "email": result.email,
                    "status": result.status.value,
                    "sub_status": result.sub_status,
                    "confidence_score": result.confidence_score,
                    "mx_valid": result.mx_valid,
                    "smtp_server": result.smtp_server,
                    "smtp_check": result.smtp_check,
                    "catch_all": result.catch_all,
                    "disposable": result.disposable,
                    "toxic": result.toxic,
                    "processed_at": result.processed_at
                }
                
                logger.info(f"🔍 ZeroBounce Response for {email}:")
                logger.info(f"   Status: {result.status.value}")
                logger.info(f"   Sub-Status: {result.sub_status}")
                logger.info(f"   MX Valid: {result.mx_valid}")
                logger.info(f"   Catch-All: {result.catch_all}")
                logger.info(f"   Disposable: {result.disposable}")
                logger.info(f"   Toxic: {result.toxic}")
                logger.info(f"   Confidence Score: {result.confidence_score}")
                
                # STRICT VALIDATION: ONLY accept "valid" status
                # Reject everything else: catch-all, unknown, do_not_mail, possible_trap, etc.
                if result.status == ZeroBounceStatus.VALID:
                    logger.info(f"✅ Email {email} ACCEPTED by ZeroBounce: VALID")
                    return True, response_data
                elif result.status == ZeroBounceStatus.DO_NOT_MAIL:
                    logger.warning(f"❌ Email {email} REJECTED by ZeroBounce: DO_NOT_MAIL (sub-status: {result.sub_status}) - DANGEROUS, may cause email blocking!")
                    return False, response_data
                elif result.status == ZeroBounceStatus.SPAMTRAP:
                    logger.warning(f"❌ Email {email} REJECTED by ZeroBounce: SPAMTRAP - DANGEROUS, may cause email blocking!")
                    return False, response_data
                elif result.status == ZeroBounceStatus.ABUSE:
                    logger.warning(f"❌ Email {email} REJECTED by ZeroBounce: ABUSE - DANGEROUS, may cause email blocking!")
                    return False, response_data
                elif result.status == ZeroBounceStatus.CATCH_ALL:
                    logger.info(f"❌ Email {email} REJECTED by ZeroBounce: CATCH-ALL (not accepting non-valid status)")
                    return False, response_data
                elif result.status == ZeroBounceStatus.INVALID:
                    logger.info(f"❌ Email {email} REJECTED by ZeroBounce: INVALID")
                    return False, response_data
                elif result.status == ZeroBounceStatus.DISPOSABLE:
                    logger.info(f"❌ Email {email} REJECTED by ZeroBounce: DISPOSABLE")
                    return False, response_data
                elif result.status == ZeroBounceStatus.UNKNOWN:
                    logger.info(f"❌ Email {email} REJECTED by ZeroBounce: UNKNOWN (sub-status: {result.sub_status})")
                    return False, response_data
                else:
                    # For any other unexpected statuses
                    logger.warning(f"❌ Email {email} REJECTED by ZeroBounce: {result.status.value} (sub-status: {result.sub_status})")
                    return False, response_data
            
        except Exception as e:
            logger.error(f"❌ ZeroBounce validation error for {email}: {e}")
            return False, {"error": str(e)}

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
        Phase 3: Email Validation & Processing
        
        This phase performs:
        1. Email validation using ZeroBounce API (checks deliverability)
        2. Smart email selection (max 2, min 1) prioritizing personal > business emails
        3. Profile cleanup (removes profiles with no valid emails)
        4. Profile completion marking (marks validated profiles as completed)
        5. Google Sheets update (updates results tracking sheet)
        
        Args:
            platform: Platform to process ('houzz' or 'architizer')
            start_time: Pipeline start time for calculating total duration
        
        Returns:
            Dictionary with detailed processing statistics including:
            - total_profiles_processed: Number of profiles validated
            - profiles_marked_completed: Number of profiles with valid emails
            - profiles_removed: Number of profiles removed due to no valid emails
            - invalid_emails_removed: Number of invalid emails filtered out
            - profiles: List of validated profiles with names, emails, and URLs
            - total_time_seconds/minutes: Execution time
        """
        logger.info("📧 Starting email validation and processing with ZeroBounce...")
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
                logger.info("ℹ️  No profiles found in database for validation")
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
            
            logger.info(f"📧 Processing {len(all_profiles)} profiles for ZeroBounce email validation...")
            logger.info(f"   • Pre-validation filtering: FREE checks before ZeroBounce (saves 20-30% credits)")
            logger.info(f"   • Efficient validation: Stop after finding 2-3 valid emails per profile")
            logger.info(f"   • Priority: Personal emails first, then business emails")
            logger.info(f"   • Strict acceptance: ONLY 'valid' status accepted (reject catch-all, unknown, do_not_mail, etc.)")
            logger.info(f"   • Will remove profiles with zero valid emails")
            
            # Process each profile with efficient validation
            validated_profiles = []
            profiles_removed = 0
            invalid_emails_removed_count = 0
            total_zerobounce_calls = 0  # Track ZeroBounce API calls
            total_prefiltered_emails = 0  # Track emails filtered by pre-validation (credits saved!)
            
            for profile in all_profiles:
                if profile.emails:
                    try:
                        # Parse existing emails
                        emails_json = json.loads(profile.emails) if isinstance(profile.emails, str) else profile.emails
                        
                        # Extract all emails
                        personal_emails = emails_json.get('personal', []) if isinstance(emails_json, dict) else []
                        business_emails = emails_json.get('business', []) if isinstance(emails_json, dict) else []
                        
                        logger.info(f"📧 Processing {profile.name}: {len(personal_emails)} personal, {len(business_emails)} business emails")
                        
                        # STEP 1: Combine emails with priority (personal > business)
                        # Create prioritized list with metadata
                        prioritized_emails = []
                        for email in personal_emails:
                            prioritized_emails.append({'email': email, 'type': 'personal'})
                        for email in business_emails:
                            prioritized_emails.append({'email': email, 'type': 'business'})
                        
                        logger.info(f"📋 Prioritized email list for {profile.name}: {[e['email'] for e in prioritized_emails]}")
                        
                        # STEP 2 & 3: Validate sequentially until we get 2-3 VALID emails
                        validated_emails = []
                        validated_personal = []
                        validated_business = []
                        target_email_count = 3  # Try to get 2-3 valid emails
                        prefiltered_count = 0  # Track emails filtered before ZeroBounce
                        
                        for email_data in prioritized_emails:
                            email = email_data['email']
                            email_type = email_data['type']
                            
                            # Stop if we already have enough valid emails
                            if len(validated_emails) >= target_email_count:
                                logger.info(f"✅ Already have {len(validated_emails)} valid emails for {profile.name}, stopping validation")
                                break
                            
                            # PRE-VALIDATION: Check with FREE filters BEFORE ZeroBounce
                            logger.info(f"🔍 Pre-validating {email_type} email #{len(validated_emails) + 1}: {email}")
                            prevalidation_result = self.email_prevalidator.should_validate_with_zerobounce(email)
                            
                            if not prevalidation_result.should_validate:
                                # Email filtered out by pre-validation (SAVED 1 ZEROBOUNCE CREDIT!)
                                prefiltered_count += 1
                                total_prefiltered_emails += 1  # Global counter
                                invalid_emails_removed_count += 1
                                logger.info(f"❌ {email_type} email pre-filtered (saved 1 credit): {email}")
                                logger.info(f"   Filter reason: {prevalidation_result.reason} (Status: {prevalidation_result.status.value})")
                                continue  # Skip ZeroBounce validation
                            
                            # Passed pre-validation, now validate with ZeroBounce
                            logger.info(f"✓ Passed pre-validation, validating with ZeroBounce: {email}")
                            is_valid, zerobounce_response = await self._validate_email_with_zerobounce(email)
                            total_zerobounce_calls += 1
                            
                            if is_valid:
                                validated_emails.append(email)
                                if email_type == 'personal':
                                    validated_personal.append(email)
                                else:
                                    validated_business.append(email)
                                logger.info(f"✅ Valid email #{len(validated_emails)} found: {email} ({email_type})")
                            else:
                                invalid_emails_removed_count += 1
                                logger.info(f"❌ Invalid {email_type} email rejected: {email} (Status: {zerobounce_response.get('status')}, Sub-Status: {zerobounce_response.get('sub_status')})")
                        
                        # Create validated emails JSON for database
                        validated_emails_json = {
                            'personal': validated_personal,
                            'business': validated_business
                        }
                        
                        if validated_emails:
                            # Update profile with selected emails (keep all valid emails, max 3)
                            profile.emails = validated_emails[:3]  # Keep max 3 valid emails
                            validated_profiles.append(profile)
                            
                            # Update database with validated emails and mark as completed
                            db_manager.update_profile_field(profile.id, 'emails', json.dumps(validated_emails_json))
                            db_manager.mark_profile_completed(profile.id)
                            db_manager.mark_email_verified(profile.id)
                            
                            logger.info(f"✅ {profile.name}: Successfully validated {len(validated_emails)} email(s) - Personal: {validated_personal}, Business: {validated_business}")
                            logger.info(f"   📊 Efficiency for this profile:")
                            logger.info(f"      • Pre-filtered: {prefiltered_count} emails (saved {prefiltered_count} credits with FREE checks)")
                            logger.info(f"      • Total emails: {len(prioritized_emails)} → Validated: {len(validated_emails)} → Saved: {len(prioritized_emails) - len(validated_emails)} credits")
                        else:
                            # Remove profile if no valid emails
                            await db_manager.remove_profile(profile.id)
                            profiles_removed += 1
                            logger.info(f"🗑️ Removed {profile.name} - no valid emails after validating {len(prioritized_emails)} emails")
                    
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
                "emails_prefiltered": total_prefiltered_emails,
                "profiles_with_valid_emails": len([p for p in validated_profiles if p.emails]),
                "total_zerobounce_calls": total_zerobounce_calls,
                "zerobounce_credits_saved": total_prefiltered_emails,
                "profiles": simplified_profiles,
                "total_time_seconds": round(total_time, 2),
                "total_time_minutes": round(total_time / 60, 2),
                "message": f"Successfully processed {len(all_profiles)} profiles: {len(validated_profiles)} completed, {profiles_removed} removed, {invalid_emails_removed_count} invalid emails removed"
            }
            
            logger.info(f"📊 Email Validation Summary: {stats['message']} in {stats['total_time_seconds']} seconds")
            logger.info(f"   • Profiles with valid emails: {stats['profiles_with_valid_emails']}")
            logger.info(f"   • Profiles removed (no valid emails): {profiles_removed}")
            logger.info(f"   • Invalid emails filtered out: {invalid_emails_removed_count}")
            logger.info(f"   • 💰 Emails pre-filtered (FREE): {total_prefiltered_emails} (saved {total_prefiltered_emails} ZeroBounce credits!)")
            logger.info(f"   • ZeroBounce API calls used: {total_zerobounce_calls}")
            logger.info(f"   • 📈 Efficiency: {total_prefiltered_emails}/{total_prefiltered_emails + total_zerobounce_calls} emails filtered for FREE ({round(total_prefiltered_emails/(total_prefiltered_emails + total_zerobounce_calls)*100 if (total_prefiltered_emails + total_zerobounce_calls) > 0 else 0, 1)}% credit savings)")
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
        """
        Phase 2: Website Email Mining with Playwright
        
        This phase performs:
        1. Website visiting using Playwright browser automation (handles JavaScript-heavy sites)
        2. Email extraction (categorizes as personal vs business emails)
        3. Phone number extraction (for Architizer platform when missing)
        4. Social link extraction (LinkedIn, Facebook, Instagram, Twitter, Pinterest, YouTube, etc.)
        5. Parallel batch processing for efficiency
        6. Smart deduplication and merging with existing data
        
        Args:
            platform: Platform to process ('houzz' or 'architizer')
        """
        logger.info("🌐 Starting advanced website email mining using Playwright browser automation...")
        db_manager = None
        
        try:
            db_manager = DatabaseManager()
            
            # Get total count for progress tracking
            total_profiles = db_manager.get_total_profiles_for_website_scraping(platform=platform)
            logger.info(f"📊 Total profiles available for website scraping ({platform.upper()}): {total_profiles}")
            
            if total_profiles == 0:
                logger.info("ℹ️  No profiles found with websites to scrape")
                return
            
            # Track overall statistics
            total_processed = 0
            total_with_emails_found = 0  # Profiles where we found emails this run
            total_emails_updated = 0     # Profiles where we actually updated email data in DB
            batch_size = 100
            batch_number = 0
            offset = 0
            
            logger.info(f"⚙️  Processing profiles in batches of {batch_size} using parallel Playwright instances")
            
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
                        logger.info(f"ℹ️  No more profiles found at offset {offset}")
                        break
                    
                    progress_percentage = (offset / total_profiles) * 100
                    logger.info(f"\n📦 BATCH {batch_number} ({len(profiles_to_scrape)} profiles) - Progress: {progress_percentage:.1f}%")
                    logger.info(f"   • Processing profiles {offset+1} to {offset+len(profiles_to_scrape)} of {total_profiles}")
                    
                    # Create semaphore for controlling concurrent database writes
                    db_semaphore = asyncio.Semaphore(5)
                    
                    # Create concurrent tasks for all profiles in the batch
                    logger.info(f"   • Launching {len(profiles_to_scrape)} parallel website scraping tasks...")
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
                    
                    logger.info(f"\n📊 BATCH {batch_number} SUMMARY")
                    logger.info(f"   • Batch processed: {len(batch_results)}")
                    logger.info(f"   • Emails found in batch: {batch_with_emails}")
                    logger.info(f"   • Batch success rate: {batch_success_rate:.1f}%")
                    logger.info(f"   • Overall progress: {total_processed}/{total_profiles} ({overall_progress:.1f}%) - {total_with_emails_found} profiles with emails")
                    
                    # Move to next batch
                    offset += batch_size
                    logger.info(f"   • Moving to next batch (offset: {offset})...\n")
            
            # Final summary statistics
            email_find_rate = (total_with_emails_found / total_processed * 100) if total_processed > 0 else 0
            database_update_rate = (total_emails_updated / total_processed * 100) if total_processed > 0 else 0
            
            logger.info(f"\n{'='*70}")
            logger.info(f"📊 FINAL WEBSITE MINING SUMMARY (Phase 2)")
            logger.info(f"{'='*70}")
            logger.info(f"Processing Statistics:")
            logger.info(f"  • Total profiles available: {total_profiles}")
            logger.info(f"  • Profiles processed: {total_processed}")
            logger.info(f"  • Emails found: {total_with_emails_found} ({email_find_rate:.1f}%)")
            logger.info(f"  • Database updates: {total_emails_updated} ({database_update_rate:.1f}%)")
            logger.info(f"  • Batches processed: {batch_number}")
            logger.info(f"")
            logger.info(f"Extraction Results:")
            logger.info(f"  • Email discovery rate: {email_find_rate:.1f}%")
            logger.info(f"  • Database update rate: {database_update_rate:.1f}%")
            logger.info(f"  • Profiles remaining: {total_profiles - total_processed}")
            logger.info(f"{'='*70}\n")
            
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

    async def   scrape_houzz_profiles(self, location: str, professional_type: str, max_pages: int = 50, start_page: int = 1) -> List[ProfessionalProfile]:
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
                
                # Scrape using the location-based   method
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
