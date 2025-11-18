import sqlite3
import json
from dataclasses import dataclass
from typing import List, Optional, Any
from pathlib import Path
from loguru import logger

try:
    from .models import ProfessionalProfile
    from .database_pool import db_pool
except ImportError:
    from models import ProfessionalProfile
    from database_pool import db_pool


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuration for database operations"""
    db_path: str = "data/scraper.db"
    enable_wal_mode: bool = True
    page_size: int = 4096
    cache_size: int = -2000  # 2MB cache
    timeout: int = 30
    batch_size: int = 100
    enable_foreign_keys: bool = True


class DatabaseManager:
    """Fresh database manager with separate social media columns"""
    
    def __init__(self, config=None):
        self.config = config or DatabaseConfig()
        # Use the global database pool instead of creating individual connections
        self._pool = db_pool
        logger.info("Database manager initialized with connection pool")
    
    def _get_connection(self):
        """Get connection from pool"""
        return self._pool.get_connection()
    
    def _create_optimized_connection(self) -> sqlite3.Connection:
        """Create optimized SQLite connection - now handled by pool"""
        return self._pool._create_optimized_connection()
    
    def _initialize_database(self) -> None:
        """Initialize database schema - now handled by pool"""
        pass  # Pool handles initialization

    def create_table(self):
        """Create the professionals table with fresh schema including separate social media columns"""
        try:
            with self._get_connection() as conn:
                # Drop existing table to ensure fresh implementation
                conn.execute("DROP TABLE IF EXISTS professionals")
                
                # Create new table with separate social media columns
                conn.execute("""
                    CREATE TABLE professionals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        profile_url TEXT UNIQUE NOT NULL,
                        platform TEXT NOT NULL DEFAULT 'houzz',
                        name TEXT,
                        website TEXT,
                        professional_type TEXT,
                        phone TEXT,
                        emails TEXT,  -- Store as JSON: {"business": [...], "personal": [...]}
                        address TEXT,
                        zip_code TEXT,
                        rating REAL,
                        reviews_count INTEGER,
                        -- Separate social media link columns - each stores JSON array of links
                        linkedin_links TEXT DEFAULT '[]',  -- JSON array of LinkedIn URLs
                        facebook_links TEXT DEFAULT '[]',  -- JSON array of Facebook URLs
                        instagram_links TEXT DEFAULT '[]',  -- JSON array of Instagram URLs
                        twitter_links TEXT DEFAULT '[]',  -- JSON array of Twitter/X URLs
                        pinterest_links TEXT DEFAULT '[]',  -- JSON array of Pinterest URLs
                        youtube_links TEXT DEFAULT '[]',  -- JSON array of YouTube URLs
                        other_social_links TEXT DEFAULT '[]',  -- JSON array of other social URLs
                        typical_job_cost TEXT,
                        followers_count INTEGER,
                        is_email_verified INTEGER DEFAULT 0,
                        website_scraped INTEGER DEFAULT 0,
                        google_search_done INTEGER DEFAULT 0,
                        is_completed INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for better performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_profile_url ON professionals(profile_url)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_platform ON professionals(platform)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_website_scraped ON professionals(website_scraped)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_google_search_done ON professionals(google_search_done)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_is_completed ON professionals(is_completed)")
                
                logger.info("Created fresh professionals table with separate social media columns")
                
        except sqlite3.Error as e:
            logger.error(f"Database error while creating table: {e}")
    
    def add_profile(self, profile: ProfessionalProfile):
        """Add a single Professional Profile to the database"""
        logger.info(f"Preparing to add profile to database: {profile.name} ({profile.profile_url})")
        logger.debug(f"Profile professional_type: '{profile.professional_type}'")
        try:
            with self._get_connection() as conn:
                # Handle None values properly for database insertion
                # Handle emails - can be string or dict, serialize to JSON if dict
                if profile.emails is None:
                    emails_value = None
                elif isinstance(profile.emails, dict):
                    emails_value = json.dumps(profile.emails)
                else:
                    emails_value = profile.emails
                
                is_email_verified_value = profile.is_email_verified if profile.is_email_verified is not None else 0
                
                conn.execute("""
                    INSERT OR REPLACE INTO professionals (
                        profile_url, platform, name, website, professional_type, phone, emails, 
                        address, zip_code, rating, reviews_count, 
                        linkedin_links, facebook_links, instagram_links, twitter_links, 
                        pinterest_links, youtube_links, other_social_links,
                        typical_job_cost, followers_count, is_email_verified
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile.profile_url,
                    profile.platform or 'houzz',
                    profile.name,
                    profile.website,
                    profile.professional_type,
                    profile.phone,
                    emails_value,
                    profile.address,
                    profile.zip_code,
                    profile.rating,
                    profile.reviews_count,
                    json.dumps(profile.linkedin_links),
                    json.dumps(profile.facebook_links),
                    json.dumps(profile.instagram_links),
                    json.dumps(profile.twitter_links),
                    json.dumps(profile.pinterest_links),
                    json.dumps(profile.youtube_links),
                    json.dumps(profile.other_social_links),
                    profile.typical_job_cost,
                    profile.followers_count,
                    is_email_verified_value
                ))
                # Commit the transaction
                conn.commit()
            logger.info(f"Successfully added/updated profile in database: {profile.name} ({profile.profile_url}) with professional_type: '{profile.professional_type}'")
        except sqlite3.Error as e:
            logger.error(f"Database error adding profile {profile.name}: {e}")

    def get_profiles_with_details_for_website_scraping(self, platform: str, limit: int = 100, offset: int = 0) -> List[tuple]:
        """Get profiles with ID, name, website, phone, and emails for email scraping using pagination"""
        logger.debug(f"get_profiles_with_details_for_website_scraping called with platform: {platform}, limit: {limit}, offset: {offset}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, name, website, phone, emails FROM professionals
                    WHERE website_scraped = 0 AND website IS NOT NULL AND website != ''
                    AND platform = ?
                    ORDER BY id
                    LIMIT ? OFFSET ?
                """, (platform, limit, offset))
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Failed to get profiles with details for website scraping: {e}")
            return []
    
    def get_total_profiles_for_website_scraping(self, platform: str) -> int:
        """Get total count of profiles that can be scraped for websites"""
        
        logger.debug(f"get_total_profiles_for_website_scraping called with platform: {platform}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM professionals
                    WHERE website_scraped = 0 AND website IS NOT NULL AND website != ''
                    AND platform = ?
                """, (platform,))
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error(f"Failed to get total profiles count for website scraping: {e}")
            return 0
    
    def update_profile_field(self, profile_id: int, field_name: str, value: Any):
        """Generic method to update any single field in a profile"""
        try:
            with self._get_connection() as conn:
                # Handle special cases for complex fields
                if field_name.endswith('_links') and isinstance(value, list):
                    # For social media links, merge with existing links and remove duplicates
                    cursor = conn.execute(f"SELECT {field_name} FROM professionals WHERE id = ?", (profile_id,))
                    row = cursor.fetchone()
                    if row:
                        current_links = json.loads(row[0]) if row[0] else []
                        # Add new links and remove duplicates while preserving order
                        seen = set()
                        merged_links = []
                        for link in current_links + value:
                            if link not in seen:
                                seen.add(link)
                                merged_links.append(link)
                        value = json.dumps(merged_links)
                    else:
                        value = json.dumps(value)
                elif field_name == 'emails' and isinstance(value, dict):
                    value = json.dumps(value)
                
                # Build dynamic SQL query
                sql = f"UPDATE professionals SET {field_name} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                conn.execute(sql, (value, profile_id))
                # Commit the transaction
                conn.commit()
                
            logger.info(f"Updated {field_name} for profile ID {profile_id}: {value}")
        except sqlite3.Error as e:
            logger.error(f"Failed to update {field_name} for profile ID {profile_id}: {e}")

    def update_profile_emails_json(self, profile_id: int, email_data: dict):
        """Update profile emails with JSON format containing personal and business emails"""
        self.update_profile_field(profile_id, 'emails', email_data)
    
    def update_profile_phone(self, profile_id: int, phone: str):
        """Update profile phone number"""
        self.update_profile_field(profile_id, 'phone', phone)
    
    def mark_email_verified(self, profile_id: int):
        """Mark a profile's email as verified"""
        self.update_profile_field(profile_id, 'is_email_verified', 1)
    
    def mark_website_scraped_by_id(self, profile_id: int):
        """Mark a profile's website as scraped by ID"""
        self.update_profile_field(profile_id, 'website_scraped', 1)
    
    def mark_profile_completed(self, profile_id: int):
        """Mark a profile as completed after export"""
        self.update_profile_field(profile_id, 'is_completed', 1)
    
    def update_social_links(self, profile_id: int, social_links: dict):
        """Update social media links for a profile - handles merging and deduplication"""
        try:
            with self._get_connection() as conn:
                # Get current social links
                cursor = conn.execute("""
                    SELECT linkedin_links, facebook_links, instagram_links, twitter_links, 
                           pinterest_links, youtube_links, other_social_links
                    FROM professionals WHERE id = ?
                """, (profile_id,))
                row = cursor.fetchone()
                
                if row:
                    # Parse current links
                    current_links = {
                        'linkedin_links': json.loads(row[0]) if row[0] else [],
                        'facebook_links': json.loads(row[1]) if row[1] else [],
                        'instagram_links': json.loads(row[2]) if row[2] else [],
                        'twitter_links': json.loads(row[3]) if row[3] else [],
                        'pinterest_links': json.loads(row[4]) if row[4] else [],
                        'youtube_links': json.loads(row[5]) if row[5] else [],
                        'other_social_links': json.loads(row[6]) if row[6] else []
                    }
                    
                    # Merge new links with existing ones, removing duplicates
                    for platform, new_links in social_links.items():
                        if isinstance(new_links, list):
                            field_name = f"{platform}_links"
                            if field_name in current_links:
                                # Merge and deduplicate
                                seen = set()
                                merged_links = []
                                for link in current_links[field_name] + new_links:
                                    if link not in seen:
                                        seen.add(link)
                                        merged_links.append(link)
                                current_links[field_name] = merged_links
                    
                    # Update database with merged links
                    conn.execute("""
                        UPDATE professionals SET 
                            linkedin_links = ?, facebook_links = ?, instagram_links = ?, 
                            twitter_links = ?, pinterest_links = ?, youtube_links = ?, 
                            other_social_links = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (
                        json.dumps(current_links['linkedin_links']),
                        json.dumps(current_links['facebook_links']),
                        json.dumps(current_links['instagram_links']),
                        json.dumps(current_links['twitter_links']),
                        json.dumps(current_links['pinterest_links']),
                        json.dumps(current_links['youtube_links']),
                        json.dumps(current_links['other_social_links']),
                        profile_id
                    ))
                    conn.commit()
                    logger.info(f"Updated social links for profile ID {profile_id}")
                else:
                    logger.warning(f"Profile ID {profile_id} not found for social links update")
                    
        except sqlite3.Error as e:
            logger.error(f"Failed to update social links for profile ID {profile_id}: {e}")
    
    def update_profile_zipcode(self, profile_id: int, zipcode: str):
        """Update zipcode for a profile"""
        self.update_profile_field(profile_id, 'zip_code', zipcode)
    
    def get_all_profiles_for_export(self, platform: str, limit: int = 1000, offset: int = 0) -> List[dict]:
        """Get all profile data for export with pagination support"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        id, profile_url, platform, name, website, professional_type, phone, emails, 
                        address, zip_code, rating, reviews_count, 
                        linkedin_links, facebook_links, instagram_links, twitter_links,
                        pinterest_links, youtube_links, other_social_links,
                        typical_job_cost, followers_count, is_email_verified, website_scraped, 
                        google_search_done, created_at, updated_at
                    FROM professionals 
                    WHERE is_completed = 0 AND platform = ?
                    ORDER BY id
                    LIMIT ? OFFSET ?
                """, (platform, limit, offset))
                
                rows = cursor.fetchall()
                profiles = []
                
                for row in rows:
                    profile = {
                        'id': row[0],
                        'profile_url': row[1],
                        'platform': row[2],
                        'name': row[3],
                        'website': row[4],
                        'professional_type': row[5],
                        'phone': row[6],
                        'emails': row[7],  # Keep as JSON string for CSV export
                        'address': row[8],
                        'zip_code': row[9],
                        'rating': row[10],
                        'reviews_count': row[11],
                        'linkedin_links': row[12],  # Keep as JSON string for CSV export
                        'facebook_links': row[13],
                        'instagram_links': row[14],
                        'twitter_links': row[15],
                        'pinterest_links': row[16],
                        'youtube_links': row[17],
                        'other_social_links': row[18],
                        'typical_job_cost': row[19],
                        'followers_count': row[20],
                        'is_email_verified': row[21],
                        'website_scraped': row[22],
                        'google_search_done': row[23],
                        'created_at': row[24],
                        'updated_at': row[25]
                    }
                    profiles.append(profile)
                
                return profiles
                
        except sqlite3.Error as e:
            logger.error(f"Failed to get profiles for export: {e}")
            return []
    
    def get_total_profiles_for_export_count(self, platform: str) -> int:
        """Get total count of profiles that can be exported (not completed)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM professionals WHERE is_completed = 0 AND platform = ?", (platform,))
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error(f"Failed to get total profiles count for export: {e}")
            return 0
    
    def get_scraping_stats(self, platform: str) -> dict:
        """Get statistics about scraping progress and completion status"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_profiles,
                        SUM(website_scraped) as websites_scraped,
                        SUM(is_completed) as completed_profiles,
                        COUNT(*) - SUM(website_scraped) as websites_pending,
                        COUNT(*) - SUM(is_completed) as profiles_pending_completion
                    FROM professionals
                    WHERE platform = ?
                """, (platform,))
                row = cursor.fetchone()
                if row:
                    return {
                        'total_profiles': row[0],
                        'websites_scraped': row[1],
                        'completed_profiles': row[2],
                        'websites_pending': row[3],
                        'profiles_pending_completion': row[4]
                    }
        except sqlite3.Error as e:
            logger.error(f"Failed to get scraping stats: {e}")
        return {}

    def profile_exists(self, profile_url: str) -> bool:
        """Check if a profile already exists in the database"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT 1 FROM professionals WHERE profile_url = ? LIMIT 1", (profile_url,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            logger.error(f"Database error checking if profile exists {profile_url}: {e}")
            return False
    
    def add_profile_if_not_exists(self, profile: ProfessionalProfile) -> bool:
        """Add a profile only if it doesn't already exist. Returns True if added, False if already exists."""
        if self.profile_exists(profile.profile_url):
            logger.info(f"Profile already exists, skipping: {profile.profile_url}")
            return False
        
        self.add_profile(profile)
        return True

    async def remove_profile(self, profile_id: int) -> bool:
        """Remove a profile from the database"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM professionals WHERE id = ?", (profile_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"✅ Removed profile with ID {profile_id} from database")
                    return True
                else:
                    logger.warning(f"⚠️ Profile with ID {profile_id} not found for removal")
                    return False
                    
        except Exception as e:
            logger.error(f"Error removing profile {profile_id}: {e}")
            return False

    def close(self):
        """Close the database connection - now handled by pool"""
        logger.info("Database manager closed (connections managed by pool).")
    
    def get_profiles_for_email_verification(self, platform: str, limit: int = 100, offset: int = 0) -> List[dict]:
        """Get profiles that need email verification with pagination support"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        id, name, emails, is_email_verified
                    FROM professionals 
                    WHERE (is_email_verified IS NULL OR is_email_verified = 0) 
                    AND emails IS NOT NULL AND emails != '' AND emails != '{}'
                    AND is_completed = 0 AND platform = ?
                    ORDER BY id
                    LIMIT ? OFFSET ?
                """, (platform, limit, offset))
                
                rows = cursor.fetchall()
                profiles = []
                
                for row in rows:
                    profile = {
                        'id': row[0],
                        'name': row[1],
                        'emails': row[2],
                        'is_email_verified': row[3]
                    }
                    profiles.append(profile)
                
                return profiles
                
        except sqlite3.Error as e:
            logger.error(f"Failed to get profiles for email verification: {e}")
            return []
    
    def get_total_profiles_for_email_verification(self, platform: str) -> int:
        """Get total count of profiles that need email verification"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM professionals 
                    WHERE (is_email_verified IS NULL OR is_email_verified = 0) 
                    AND emails IS NOT NULL AND emails != '' AND emails != '{}'
                    AND is_completed = 0 AND platform = ?
                """, (platform,))
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error(f"Failed to get total profiles count for email verification: {e}")
            return 0

