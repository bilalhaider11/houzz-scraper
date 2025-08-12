"""Database Connection Pool for Optimized Database Operations.

This module provides a connection pool to eliminate database connection management
duplication and improve performance across the application.
"""

import sqlite3
import threading
from typing import Optional, Dict, Any
from contextlib import contextmanager
from dataclasses import dataclass
from loguru import logger
from pathlib import Path


@dataclass(frozen=True)
class DatabasePoolConfig:
    """Configuration for database connection pool"""
    db_path: str = "data/scraper.db"
    enable_wal_mode: bool = True
    page_size: int = 4096
    cache_size: int = -2000  # 2MB cache
    timeout: int = 30
    batch_size: int = 100
    enable_foreign_keys: bool = True
    max_connections: int = 5
    connection_timeout: int = 60


class DatabaseConnectionPool:
    """Thread-safe database connection pool with optimized settings"""
    
    def __init__(self, config: Optional[DatabasePoolConfig] = None):
        self.config = config or DatabasePoolConfig()
        self.db_path = Path(self.config.db_path)
        self.db_path.parent.mkdir(exist_ok=True, parents=True)
        
        # Thread-local storage for connections
        self._local = threading.local()
        self._lock = threading.Lock()
        self._connection_count = 0
        
        # Initialize the database schema
        self._initialize_database()
        logger.info(f"Database pool initialized for {self.db_path}")
    
    def _create_optimized_connection(self) -> sqlite3.Connection:
        """Create optimized SQLite connection with performance settings"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.config.timeout,
            check_same_thread=False
        )
        
        # Apply optimizations
        conn.execute(f"PRAGMA page_size = {self.config.page_size}")
        conn.execute(f"PRAGMA cache_size = {self.config.cache_size}")
        
        if self.config.enable_wal_mode:
            conn.execute("PRAGMA journal_mode = WAL")
        
        if self.config.enable_foreign_keys:
            conn.execute("PRAGMA foreign_keys = ON")
        
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA temp_store = MEMORY")
        
        return conn
    
    def _initialize_database(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            self._create_tables(conn)
    
    def _create_tables(self, conn: sqlite3.Connection):
        """Create database tables if they don't exist"""
        try:
            # Check if table exists
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='professionals'")
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                conn.execute("""
                    CREATE TABLE professionals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        profile_url TEXT UNIQUE NOT NULL,
                        platform TEXT NOT NULL DEFAULT 'houzz',
                        name TEXT,
                        website TEXT,
                        professional_type TEXT,
                        phone TEXT,
                        emails TEXT,
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
                
                logger.info("Created professionals table with separate social media columns")
            else:
                logger.info("Professionals table already exists")
                
        except sqlite3.Error as e:
            logger.error(f"Database error while creating table: {e}")
    
    @contextmanager
    def get_connection(self):
        """Get a database connection from the pool"""
        if not hasattr(self._local, 'connection'):
            with self._lock:
                if self._connection_count < self.config.max_connections:
                    self._local.connection = self._create_optimized_connection()
                    self._connection_count += 1
                    logger.debug(f"Created new database connection (total: {self._connection_count})")
                else:
                    logger.warning("Connection pool limit reached, reusing existing connection")
                    # In a more sophisticated implementation, you might want to wait or create a new connection anyway
                    if not hasattr(self._local, 'connection'):
                        self._local.connection = self._create_optimized_connection()
        
        try:
            yield self._local.connection
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            # Reset connection on error
            if hasattr(self._local, 'connection'):
                try:
                    self._local.connection.close()
                except:
                    pass
                delattr(self._local, 'connection')
            raise
        finally:
            # Keep connection alive for reuse
            pass
    
    def close_all_connections(self):
        """Close all connections in the pool"""
        with self._lock:
            if hasattr(self._local, 'connection'):
                try:
                    self._local.connection.close()
                except:
                    pass
                delattr(self._local, 'connection')
            self._connection_count = 0
            logger.info("All database connections closed")
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        return {
            'active_connections': self._connection_count,
            'max_connections': self.config.max_connections,
            'db_path': str(self.db_path),
            'has_local_connection': hasattr(self._local, 'connection')
        }


# Global database pool instance
db_pool = DatabaseConnectionPool() 