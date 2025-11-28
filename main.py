#!/usr/bin/env python3
"""
FastAPI Application for Houzz Lead Generation Pipeline v2.0
===========================================================

A production-ready FastAPI application for multi-platform lead generation with
a complete 3-phase enrichment pipeline.

3-Phase Pipeline:
1. Platform Profile Scraping (Houzz/Architizer) - Extract professional profiles
2. Website Email Mining (Playwright) - Extract emails, phones, and social links
3. Email Validation & Processing - Validate emails, select best contacts

Features:
- Multi-platform support (Houzz and Architizer)
- ZeroBounce email verification with smart selection (max 2, min 1)
- Intelligent email prioritization (personal > business)
- Real-time statistics and monitoring endpoints

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, Literal
from loguru import logger

# Add src directory to Python path for imports
SRC_PATH = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC_PATH))

# FastAPI imports
from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Import core modules with error handling
try:
    from src.pipeline import LeadEnrichmentPipeline  
    from src.database_manager import DatabaseManager
    from config.config import config
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure you have activated the virtual environment:")
    logger.error("   source venv/bin/activate")
    logger.error("And installed all dependencies:")
    logger.error("   pip install -r requirements.txt")
    sys.exit(1)

# ============================================================================
# PYDANTIC MODELS FOR REQUEST/RESPONSE SCHEMAS
# ============================================================================

class ScrapeRequest(BaseModel):
    """Request model for scraping operations"""
    platform: Literal["houzz", "architizer"] = Field(
        ..., 
        description="Platform to scrape from",
        example="houzz"
    )
    location: str = Field(
        ..., 
        description="Location to scrape (e.g., 'usa'). Must be defined in LOCATION_REGION_MAP.",
        example="usa",
        min_length=2,
        max_length=50
    )
    professional_type: Optional[Literal[
        "interior-designer", "architect", "general-contractor", 
        "design-build", "landscape-architect", "kitchen-and-bath", "home-builders", "fireplace"
    ]] = Field(
        None, 
        description="Type of professional to scrape. Required for Houzz, optional for Architizer.",
        example="interior-designer"
    )
    max_pages: Optional[int] = Field(
        50, 
        description="Maximum number of pages to scrape for this location/profession combination",
        ge=1,
        le=100,
        example=50
    )
    start_page: int = Field(
        1, 
        description="Starting page number for scraping",
        ge=1,
        example=1
    )
    
    class Config:
        schema_extra = {
            "example": {
                "platform": "houzz",
                "location": "usa",
                "professional_type": "interior-designer",
                "max_pages": 50,
                "start_page": 1
            }
        }


class StatsResponse(BaseModel):
    """Response model for statistics"""
    stats: Dict[str, Any] = Field(..., description="Scraping statistics and metrics")
    
    class Config:
        schema_extra = {
            "example": {
                "stats": {
                    "total_profiles": 1250,
                    "websites_scraped": 890,
                    "completed_profiles": 1200,
                    "websites_pending": 50,
                    "profiles_pending_completion": 30
                }
            }
        }

class ScrapeResponse(BaseModel):
    """Response model for scraping operations with complete 3-phase pipeline results"""
    success: bool = Field(..., description="Whether the scraping operation was successful", example=True)
    message: str = Field(..., description="Human-readable status message", example="✅ Houzz pipeline completed successfully for chicago-il-us - interior-designer!")
    profiles_scraped: Optional[int] = Field(None, description="Number of profiles processed and validated", example=150)
    execution_time: Optional[float] = Field(None, description="Execution time in minutes", example=125.5)
    stats: Optional[dict] = Field(None, description="Detailed pipeline statistics including validation results and profile data", example={"total_profiles_processed": 50, "profiles_marked_completed": 45, "profiles_removed": 5, "invalid_emails_removed": 3})
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "✅ Houzz pipeline completed successfully for chicago-il-us - interior-designer!",
                "output_file": None,
                "profiles_scraped": 150,
                "execution_time": 125.5,
                "stats": {
                    "total_profiles_processed": 150,
                    "profiles_marked_completed": 145,
                    "profiles_removed": 5,
                    "invalid_emails_removed": 3,
                    "profiles_with_valid_emails": 142,
                    "profiles": [
                        {
                            "name": "John Doe",
                            "emails": ["john.doe@example.com"],
                            "profile_url": "https://www.houzz.com/pro/john-doe"
                        },
                        {
                            "name": "Jane Doe",
                            "emails": ["jane.doe@example.com"],
                            "profile_url": "https://www.houzz.com/pro/jane-doe"
                        }
                    ],
                    "profiles_without_emails": 3,
                    "total_time_seconds": 125.5,
                    "total_time_minutes": 2.09,
                    "message": "Successfully processed 150 profiles: 145 completed, 5 removed, 3 invalid emails removed in 125.5 seconds"
                },
                "profiles": []
            }
        }

class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error type or title", example="Validation Error")
    detail: str = Field(..., description="Detailed error message", example="Invalid professional type: designer. Available types: ['interior-designer', 'architect']")
    status_code: int = Field(..., description="HTTP status code", example=400)
    
    class Config:
        schema_extra = {
            "example": {
                "error": "Validation Error",
                "detail": "Invalid professional type: designer. Available types: ['interior-designer', 'architect']",
                "status_code": 400
            }
        }

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Houzz Lead Generation Pipeline API",
    description="""
    ## Production-ready API for Multi-Platform Lead Generation with 3-Phase Pipeline
    
    This API provides comprehensive lead generation and enrichment:
    
    ### 3-Phase Pipeline:
    * **Phase 1 - Platform Scraping**: Extract professional profiles from Houzz and Architizer
    * **Phase 2 - Website Mining**: Extract emails, phones, and social links using Playwright automation
    * **Phase 3 - Validation & Processing**: Validate emails, select best contacts
    
    ### Key Features:
    - 🏠 **Multi-Platform Support**: Houzz and Architizer scraping
    - 🎯 **Professional Types**: Interior designers, architects, contractors, and more
    - 🌍 **Geographic Coverage**: USA-wide and state-specific scraping
    - 📧 **Email Verification**: ZeroBounce integration with smart selection (max 2, min 1)
    - 📈 **Statistics**: Real-time scraping progress and metrics
    - 🔄 **Proxy Rotation**: Built-in proxy support for large-scale scraping
    
    ### Getting Started:
    1. Use `/list-professional-types` to see available professions
    2. Use `/scrape` to start the complete 3-phase pipeline
    3. Monitor progress with `/stats`
    4. Check `/health` for API status
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "General",
            "description": "General API information and health checks"
        },
        {
            "name": "Professions", 
            "description": "Professional type management endpoints"
        },
        {
            "name": "Statistics",
            "description": "Statistics and monitoring endpoints"
        },
        {
            "name": "Scraping",
            "description": "Core scraping and pipeline operations"
        },
        {
            "name": "System",
            "description": "System status and configuration endpoints"
        }
    ],
    contact={
        "name": "Houzz Lead Generation Pipeline",
        "url": "https://github.com/your-org/houzz-scraper",
        "email": "support@yourcompany.com"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def validate_environment() -> bool:
    """Validate environment and return success status."""
    errors = []
    warnings = []
    
    # Check if virtual environment is activated
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        warnings.append("Virtual environment not detected")
    
    
    # Check and create directories with proper permissions
    directories = [
        (config.OUTPUT_DIR, "output directory"),
        (config.LOG_DIR, "log directory")
    ]
    
    for dir_path, dir_name in directories:
        try:
            path_obj = Path(dir_path)
            path_obj.mkdir(parents=True, exist_ok=True)
            # Test write permissions
            test_file = path_obj / ".test_write"
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            errors.append(f"Cannot create or write to {dir_name} '{dir_path}': {e}")
    
    # Report validation results
    for warning in warnings:
        logger.warning(f"⚠️  {warning}")
    
    for error in errors:
        logger.error(f"❌ {error}")
    
    if errors:
        logger.error("Environment validation failed. Please fix the above errors.")
        return False
    
    logger.info("✅ Environment validation passed")
    return True

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get(
    "/", 
    response_model=Dict[str, str],
    tags=["General"],
    summary="API Information",
    description="Get basic information about the API and available documentation endpoints"
)
async def root():
    """
    ## Root Endpoint
    
    Returns basic information about the API including:
    - API version and status
    - Links to documentation (Swagger UI and ReDoc)
    - Current operational status
    """
    return {
        "message": "Houzz Lead Generation Pipeline API v2.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "status": "running"
    }

@app.get(
    "/health", 
    response_model=Dict[str, str],
    tags=["General"],
    summary="Health Check",
    description="Check if the API is running and healthy"
)
async def health_check():
    """
    ## Health Check Endpoint
    
    Simple health check to verify the API is operational.
    Returns a basic status message.
    """
    return {"status": "healthy", "message": "API is running"}


@app.get(
    "/list-professional-types", 
    response_model=Dict[str, Any],
    tags=["Professions"],
    summary="List Professional Types",
    description="Get all available professional types that can be scraped"
)
async def list_professional_types():
    """
    ## List Professional Types
    
    Returns all available professional types that can be used in scraping operations.
    
    **Returns:**
    - List of professional types with their identifiers
    - Human-readable descriptions for each type
    - Total count of available types
    """
    try:
        return {
            "professional_types": config.PROFESSIONAL_TYPES,
            "total_count": len(config.PROFESSIONAL_TYPES),
            "descriptions": {
                "interior-designer": "Interior Designer",
                "architect": "Architect", 
                "general-contractor": "General Contractor",
                "design-build": "Design-Build",
                "landscape-architect": "Landscape Architect",
                "kitchen-and-bath": "Kitchen & Bath Designer",
                "home-builders": "Home Builder",
                "fireplace": "Fireplace"
            }
        }
    except Exception as e:
        logger.error(f"Error listing professional types: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list professional types: {str(e)}")



@app.get(
    "/proxy-status", 
    response_model=Dict[str, Any],
    tags=["System"],
    summary="Get Proxy Status",
    description="Get proxy rotation status and configuration information"
)
async def get_proxy_status():
    """
    ## Get Proxy Status
    
    Returns information about proxy rotation configuration and current status.
    
    **Returns:**
    - Proxy rotation enabled/disabled status
    - Proxy rotation interval settings
    - Proxy authentication configuration status
    - Current proxy statistics (if rotation is enabled)
    - Total number of available proxies
    """
    try:
        # Create a temporary scraper instance to get proxy stats
        from src.houzz_scraper import HouzzScraper
        
        # Initialize scraper to get proxy information
        scraper = HouzzScraper()
        
        proxy_stats = {
            'proxy_rotation_enabled': config.USE_PROXY_ROTATION,
            'proxy_rotation_interval': config.PROXY_ROTATION_INTERVAL,
            'proxy_username_configured': bool(config.PROXY_USERNAME),
            'proxy_password_configured': bool(config.PROXY_PASSWORD),
            'webshare_proxy_list_configured': bool(config.WEBSHARE_PROXY_LIST)
        }
        
        if not config.USE_PROXY_ROTATION and not scraper.proxy_list:
            proxy_stats.update({
                'message': 'Proxy rotation is disabled or no proxies configured',
                'total_proxies': 0
            })
        
        return proxy_stats
        
    except Exception as e:
        logger.error(f"Error getting proxy status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get proxy status: {str(e)}")

@app.post(
    "/clear-database",
    response_model=Dict[str, Any],
    tags=["System"],
    summary="Clear Database and State Files",
    description="Clear all database records and state manager files (USE WITH CAUTION)"
)
async def clear_database():
    """
    ## Clear Database and State Files
    
    **⚠️ WARNING: This is a destructive operation!**
    
    Clears all data from the system:
    - Deletes all records from the SQLite database
    - Removes the state manager file
    - Resets the scraping progress
    
    **Returns:**
    - Status of the clearing operation
    - Details of what was cleared
    """
    try:
        import os
        from pathlib import Path
        
        cleared_items = []
        errors = []
        
        # Clear database
        db_path = Path(config.OUTPUT_DIR) / "scraper.db"
        if db_path.exists():
            try:
                # Close any existing connections first
                try:
                    db_manager = DatabaseManager()
                    db_manager.close()
                except:
                    pass
                
                # Remove the database file
                os.remove(db_path)
                cleared_items.append(f"Database: {db_path}")
                logger.info(f"✅ Cleared database: {db_path}")
            except Exception as e:
                errors.append(f"Failed to clear database: {str(e)}")
                logger.error(f"Failed to clear database: {e}")
        else:
            cleared_items.append("Database: Not found (already clean)")
        
        # Clear state manager file
        state_file = Path("scraping_state.json")
        if state_file.exists():
            try:
                os.remove(state_file)
                cleared_items.append(f"State file: {state_file}")
                logger.info(f"✅ Cleared state file: {state_file}")
            except Exception as e:
                errors.append(f"Failed to clear state file: {str(e)}")
                logger.error(f"Failed to clear state file: {e}")
        else:
            cleared_items.append("State file: Not found (already clean)")
        
        # Clear log files (optional)
        log_dir = Path(config.LOG_DIR)
        if log_dir.exists():
            try:
                log_files_cleared = 0
                for log_file in log_dir.glob("*.log"):
                    try:
                        os.remove(log_file)
                        log_files_cleared += 1
                    except Exception as e:
                        logger.warning(f"Could not remove log file {log_file}: {e}")
                
                if log_files_cleared > 0:
                    cleared_items.append(f"Log files: {log_files_cleared} files cleared")
                else:
                    cleared_items.append("Log files: No files found")
            except Exception as e:
                errors.append(f"Failed to clear log files: {str(e)}")
        
        # Return summary
        if errors:
            return {
                "status": "partial_success",
                "message": "⚠️ Database and state files partially cleared with some errors",
                "cleared": cleared_items,
                "errors": errors,
                "note": "Some items could not be cleared. Check errors for details."
            }
        else:
            return {
                "status": "success",
                "message": "✅ Database and state files cleared successfully!",
                "cleared": cleared_items,
                "note": "All scraping progress has been reset. The system will start fresh on the next scrape."
            }
            
    except Exception as e:
        logger.error(f"Error clearing database: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear database: {str(e)}"
        )

@app.get(
    "/stats", 
    response_model=StatsResponse,
    tags=["Statistics"],
    summary="Get Scraping Statistics",
    description="Get comprehensive statistics about scraping progress and performance"
)
async def get_stats(platform: Optional[str] = None):
    """
    ## Get Scraping Statistics
    
    Returns detailed statistics about scraping progress and performance.
    
    **Parameters:**
    - `platform` (optional): Filter by platform ('houzz' or 'architizer'). If not provided, returns combined stats for all platforms.
    
    **Returns:**
    - Total profiles scraped
    - Websites scraped and pending
    - Completed profiles count
    - Profiles pending completion
    """
    try:
        db_manager = DatabaseManager()
        
        if platform:
            # Validate platform
            if platform not in ['houzz', 'architizer']:
                raise HTTPException(
                    status_code=400,
                    detail="Platform must be 'houzz' or 'architizer'"
                )
            stats = db_manager.get_scraping_stats(platform)
        else:
            # Get stats for all platforms combined
            houzz_stats = db_manager.get_scraping_stats('houzz')
            architizer_stats = db_manager.get_scraping_stats('architizer')
            
            # Combine stats
            stats = {
                'houzz': houzz_stats,
                'architizer': architizer_stats,
                'total': {
                    'total_profiles': (houzz_stats.get('total_profiles', 0) or 0) + (architizer_stats.get('total_profiles', 0) or 0),
                    'websites_scraped': (houzz_stats.get('websites_scraped', 0) or 0) + (architizer_stats.get('websites_scraped', 0) or 0),
                    'completed_profiles': (houzz_stats.get('completed_profiles', 0) or 0) + (architizer_stats.get('completed_profiles', 0) or 0),
                    'websites_pending': (houzz_stats.get('websites_pending', 0) or 0) + (architizer_stats.get('websites_pending', 0) or 0),
                    'profiles_pending_completion': (houzz_stats.get('profiles_pending_completion', 0) or 0) + (architizer_stats.get('profiles_pending_completion', 0) or 0)
                }
            }
        
        db_manager.close()
        
        if not stats:
            stats = {"message": "No statistics available - database may be empty or not initialized"}
        
        return StatsResponse(stats=stats)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")

@app.post(
    "/scrape", 
    response_model=ScrapeResponse,
    tags=["Scraping"],
    summary="Start Complete 3-Phase Pipeline",
    description="Execute the complete lead generation pipeline with all 3 phases: Platform Scraping → Website Mining → Validation & Processing",
    status_code=status.HTTP_200_OK
)
async def scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    ## Start Complete 3-Phase Lead Generation Pipeline
    
    Executes the complete lead generation and enrichment pipeline.
    
    **3-Phase Process:**
    1. **Platform Profile Scraping** - Extracts professional profiles from Houzz or Architizer
    2. **Website Email Mining** - Extracts emails, phones, and social links using Playwright
    3. **Email Validation & Processing** - Validates emails, selects best contacts
    
    **Validation & Quality Control:**
    - Validates the request parameters (location, profession, platform)
    - Validates environment and API key configuration
    - Validates emails with ZeroBounce API
    - Removes profiles with no valid emails
    - Selects best emails (max 2, min 1) prioritizing personal > business
    
    **Returns:**
    - Success status and descriptive message
    - Number of profiles processed and validated
    - Execution time in minutes
    - Detailed statistics: profiles completed, removed, invalid emails, etc.
    - List of validated profiles with names, emails, and URLs
    """
    import time
    start_time = time.time()
    
    try:
        # Validate platform
        if request.platform not in ['houzz', 'architizer']:
            raise HTTPException(
                status_code=400,
                detail="Platform must be 'houzz' or 'architizer'"
            )
        
        # Validate location and professional type based on platform
        if request.platform == "houzz":
            if not request.location or not request.professional_type:
                raise HTTPException(
                    status_code=400,
                    detail="location and professional_type are required for Houzz platform"
                )
            # Validate professional type
            if request.professional_type not in config.PROFESSIONAL_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid professional type: {request.professional_type}. Available types: {config.PROFESSIONAL_TYPES}"
                )

            # Normalize location input (handle USA variations)
            location_lower = request.location.lower().strip() 
         
            # Normalize United States and USA variations to 'usa'
            if location_lower in ['united states', 'usa', 'us']:
                request.location = 'usa'
                
            elif location_lower in ['united-kingdom','uk']:
                request.location = 'united-kingdom-of-great-britain-and-northern-ireland'
            
            # Validate location exists in LOCATION_REGION_MAP
            if request.location not in config.LOCATION_REGION_MAP:
                available_locations = list(config.LOCATION_REGION_MAP.keys())
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid location: {request.location}. Available locations: {available_locations}"
                )
        elif request.platform == "architizer":  # architizer
            # Architizer doesn't require location/professional_type validation
            if not request.location:
                raise HTTPException(
                    status_code=400,
                    detail="location is required for Architizer platform"
                )

            # Normalize location input (handle USA variations)
            location_lower = request.location.lower().strip()
            # Normalize United States and USA variations to 'usa'
            if location_lower in ['united states', 'usa', 'us']:
                request.location = 'United States'
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid platform. Must be 'houzz' or 'architizer'"
            )
        
        # Validate environment
        if not validate_environment():
            raise HTTPException(
                status_code=500,
                detail="Environment validation failed. Please check configuration and try again."
            )
        
        # Initialize pipeline
        try:
            pipeline = LeadEnrichmentPipeline()
        except Exception as e:
            logger.error(f"Failed to initialize pipeline: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize pipeline: {str(e)}"
            )
        
        # Run the complete 3-phase pipeline
        if request.platform == "houzz":
            logger.info(f"🚀 Starting complete 3-phase {request.platform.upper()} pipeline for location '{request.location}' - {request.professional_type}")
        else:
            logger.info(f"🚀 Starting complete 3-phase {request.platform.upper()} pipeline")
        
        # Execute the full pipeline
        response = await pipeline.run_full_pipeline(
            location=request.location,
            professional_type=request.professional_type,
            max_pages=request.max_pages,
            start_page=request.start_page,
            platform=request.platform
        )
        
        execution_time = round((time.time() - start_time) / 60, 2)
        
        if response:
            if request.platform == "houzz":
                message = f"✅ {request.platform.capitalize()} pipeline completed successfully for location '{request.location}' - {request.professional_type}!"
            else:
                message = f"✅ {request.platform.capitalize()} pipeline completed successfully!"
            
            # Extract stats and profiles from the pipeline result
            stats = response if isinstance(response, dict) else {}
            profiles = stats.get('profiles', []) if isinstance(stats, dict) else []
            profiles_scraped = stats.get('total_profiles_processed', 0) if isinstance(stats, dict) else 0
            
            return ScrapeResponse(
                success=True,
                message=message,
                profiles_scraped=profiles_scraped,
                execution_time=execution_time,
                stats=stats,
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Pipeline completed but no output file was generated"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Pipeline failed with error: {e}")
        logger.exception("Full error traceback:")
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed: {str(e)}"
        )

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    logger.warning(f"HTTP exception: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            detail=exc.detail,
            status_code=exc.status_code
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail="An unexpected error occurred. Please try again later.",
            status_code=500
        ).dict()
    )

# ============================================================================
# APPLICATION STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info("🚀 Starting Houzz Lead Generation Pipeline API v2.0")
    logger.info("📚 API Documentation available at: /docs")
    logger.info("🔧 ReDoc available at: /redoc")
    
    # Validate environment on startup
    if validate_environment():
        logger.info("✅ Environment validation passed on startup")
    else:
        logger.warning("⚠️  Environment validation failed on startup - some features may not work")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info("🛑 Shutting down Houzz Lead Generation Pipeline API")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import os
    
    # Configure logging
    logger.remove()  # Remove default logger
    logger.add(
        sys.stderr, 
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
    )
    
    # Get port from environment (Cloud Run uses PORT env var)
    port = int(os.getenv("PORT", 8000))
    
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Set to True for development
        log_level="info"
    )
