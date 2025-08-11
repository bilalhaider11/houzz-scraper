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
    """Enhanced database manager using connection pool for better performance"""
    
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
        """Create the professionals table if it doesn't exist and add tracking columns if needed"""
        try:
            with self._get_connection() as conn:
                # Check if table exists and if it has id column
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='professionals'")
                table_exists = cursor.fetchone() is not None
                
                if not table_exists:
                    # Create new table with ID as primary key
                    conn.execute("""
                        CREATE TABLE professionals (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            profile_url TEXT UNIQUE NOT NULL,  -- Generic URL field
                            platform TEXT NOT NULL DEFAULT 'houzz',     -- Platform identifier
                            name TEXT,
                            website TEXT,
                            professional_type TEXT,
                            phone TEXT,
                            emails TEXT,  -- Store as JSON: {"business": [...], "personal": [...]}
                            address TEXT,
                            zip_code TEXT,
                            rating REAL,
                            reviews_count INTEGER,
                            social_links TEXT,  -- Store as JSON string
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
                    logger.info("Created new professionals table with email verification columns")
                else:
                    # Migrate existing table to add ID column if needed
                    self._migrate_table_structure(conn)
                
            logger.info(f"Database table 'professionals' is ready")
        except sqlite3.Error as e:
            logger.error(f"Database error while creating table: {e}")
    
    def _migrate_table_structure(self, conn):
        """Migrate existing table to have ID column and update to new schema with profile_url and platform"""
        try:
            # Check if the table already has the new schema
            cursor = conn.execute("PRAGMA table_info(professionals)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Check if migration is needed
            has_profile_url = 'profile_url' in columns
            has_platform = 'platform' in columns
            has_houzz_url = 'houzz_url' in columns
            
            if has_profile_url and has_platform:
                logger.info("Database schema is already up to date.")
                return
            
            # Create a new table with the updated schema
            conn.execute("""
                CREATE TABLE professionals_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_url TEXT UNIQUE NOT NULL,  -- Generic URL field
                    platform TEXT NOT NULL DEFAULT 'houzz',     -- Platform identifier
                    name TEXT,
                    website TEXT,
                    professional_type TEXT,
                    phone TEXT,
                    emails TEXT,  -- Store as JSON: {"business": [...], "personal": [...]}
                    address TEXT,
                    zip_code TEXT,
                    rating REAL,
                    reviews_count INTEGER,
                    social_links TEXT,  -- Store as JSON string
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
            
            # Migrate data to the new table
            if has_houzz_url:
                # Migrate from old schema with houzz_url
                conn.execute("""
                    INSERT INTO professionals_new (
                        profile_url, platform, name, website, professional_type, phone, emails, 
                        address, zip_code, rating, reviews_count, social_links, 
                        typical_job_cost, followers_count, is_email_verified, website_scraped, 
                        google_search_done, is_completed, created_at, updated_at
                    )
                    SELECT 
                        houzz_url, 'houzz', name, website, professional_type, phone, emails, 
                        address, zip_code, rating, reviews_count, social_links, 
                        typical_job_cost, followers_count, is_email_verified, website_scraped, 
                        google_search_done, COALESCE(is_completed, 0), created_at, updated_at
                    FROM professionals
                """)
            else:
                # For completely new installations
                logger.info("Creating fresh database with new schema")
            
            # Remove the old table and rename the new table
            conn.execute("DROP TABLE professionals")
            conn.execute("ALTER TABLE professionals_new RENAME TO professionals")
            logger.info("Successfully migrated database table structure to new schema.")
        except sqlite3.Error as e:
            logger.error(f"Error migrating table structure: {e}")

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
                        address, zip_code, rating, reviews_count, social_links, 
                        typical_job_cost, followers_count, is_email_verified
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    json.dumps(profile.social_links),  # Serialize dict to JSON string
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
                if field_name == 'social_links' and isinstance(value, dict):
                    # Get current social links and merge with new value
                    cursor = conn.execute("SELECT social_links FROM professionals WHERE id = ?", (profile_id,))
                    row = cursor.fetchone()
                    if row:
                        current_social = json.loads(row[0]) if row[0] else {}
                        current_social.update(value)
                        value = json.dumps(current_social)
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
    
    def mark_google_search_done_by_id(self, profile_id: int):
        """Mark a profile's Google search as done by ID"""
        self.update_profile_field(profile_id, 'google_search_done', 1)
    
    def update_profile_linkedin(self, profile_id: int, linkedin_url: str):
        """Update profile LinkedIn URL by ID"""
        self.update_profile_field(profile_id, 'social_links', {'linkedin': linkedin_url})
    
    def update_profile_zipcode(self, profile_id: int, zipcode: str):
        """Update zipcode for a profile"""
        self.update_profile_field(profile_id, 'zip_code', zipcode)
    
    def get_profiles_for_google_search(self, platform: str, limit: int = 100, offset: int = 0) -> List[tuple]:
        """Get profiles that haven't had Google search done yet with pagination support"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, name, professional_type, emails, website, social_links, zip_code, address FROM professionals 
                    WHERE (google_search_done IS NULL OR google_search_done = 0)
                    AND platform = ?
                    ORDER BY id
                    LIMIT ? OFFSET ?
                """, (platform, limit, offset))
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Failed to get profiles for Google search: {e}")
            return []

    def get_all_profiles_for_export(self, platform: str, limit: int = 1000, offset: int = 0) -> List[dict]:
        """Get all profile data for export with pagination support"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        id, profile_url, platform, name, website, professional_type, phone, emails, 
                        address, zip_code, rating, reviews_count, social_links, 
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
                    # Parse social_links JSON
                    social_links = {}
                    if row[12]:  # social_links column
                        try:
                            social_links = json.loads(row[12])
                        except (json.JSONDecodeError, TypeError):
                            social_links = {}
                    
                    # Parse emails JSON
                    emails_data = {}
                    if row[7]:  # emails column
                        try:
                            emails_data = json.loads(row[7]) if isinstance(row[7], str) else row[7]
                        except (json.JSONDecodeError, TypeError):
                            emails_data = {}
                    
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
                        'social_links': row[12],  # Keep as JSON string for CSV export
                        'typical_job_cost': row[13],
                        'followers_count': row[14],
                        'is_email_verified': row[15],
                        'website_scraped': row[16],
                        'google_search_done': row[17],
                        'created_at': row[18],
                        'updated_at': row[19]
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
    
    def mark_profile_completed(self, profile_id: int):
        """Mark a profile as completed after export"""
        self.update_profile_field(profile_id, 'is_completed', 1)

    def get_scraping_stats(self, platform: str) -> dict:
        """Get statistics about scraping progress and completion status"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_profiles,
                        SUM(website_scraped) as websites_scraped,
                        SUM(google_search_done) as google_searches_done,
                        SUM(is_completed) as completed_profiles,
                        COUNT(*) - SUM(website_scraped) as websites_pending,
                        COUNT(*) - SUM(google_search_done) as google_searches_pending,
                        COUNT(*) - SUM(is_completed) as profiles_pending_completion
                    FROM professionals
                    WHERE platform = ?
                """, (platform,))
                row = cursor.fetchone()
                if row:
                    return {
                        'total_profiles': row[0],
                        'websites_scraped': row[1],
                        'google_searches_done': row[2],
                        'completed_profiles': row[3],
                        'websites_pending': row[4],
                        'google_searches_pending': row[5],
                        'profiles_pending_completion': row[6]
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
        print('profile', profile)
        if self.profile_exists(profile.profile_url):
            logger.info(f"Profile already exists, skipping: {profile.profile_url}")
            return False
        
        self.add_profile(profile)
        return True

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

