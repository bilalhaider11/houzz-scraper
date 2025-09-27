#!/usr/bin/env python3
"""
FastAPI Application for Houzz Lead Generation Pipeline v2.0
===========================================================

A production-ready FastAPI wrapper for the Houzz scraper that exposes HTTP endpoints
while maintaining all existing functionality and logic.

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import sys
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from loguru import logger

# Add src directory to Python path for imports
SRC_PATH = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC_PATH))

# FastAPI imports
from fastapi import FastAPI, HTTPException, BackgroundTasks
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
    platform: str = Field(..., description="Platform to scrape (houzz or architizer)")
    city: str = Field(..., description="Single city to scrape (e.g., 'chicago-il-us')")
    professional_type: str = Field(..., description="Single professional type to scrape (e.g., 'interior-designer')")
    max_pages: Optional[int] = Field(50, description="Maximum number of pages to scrape for this city/profession combination")
    start_page: int = Field(1, description="Starting page number for scraping")
    no_email_verification: bool = Field(False, description="Skip email verification step")

class ListCitiesResponse(BaseModel):
    """Response model for listing cities"""
    state: str
    cities: List[Dict[str, str]]
    total_count: int

class StatsResponse(BaseModel):
    """Response model for statistics"""
    stats: Dict[str, Any]

class ScrapeResponse(BaseModel):
    """Response model for scraping operations"""
    success: bool
    message: str
    output_file: Optional[str] = None
    profiles_scraped: Optional[int] = None
    execution_time: Optional[float] = None

class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: str
    status_code: int

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Houzz Lead Generation Pipeline API",
    description="Production-ready API for scraping and enriching leads from Houzz and Architizer",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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
    
    # Check API keys with detailed feedback
    api_checks = [
        (config.GOOGLE_SEARCH_API_KEY, "GOOGLE_SEARCH_API_KEY", "Google search enrichment will be limited"),
        (config.GOOGLE_SEARCH_CX, "GOOGLE_SEARCH_CX", "Google search enrichment will be limited")
    ]
    
    for api_key, key_name, warning_msg in api_checks:
        if not api_key:
            warnings.append(f"{key_name} not set - {warning_msg}")
    
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

def validate_city_and_profession(city: str, professional_type: str) -> tuple:
    """Validate single city and professional type"""
    # Validate professional type
    if professional_type not in config.PROFESSIONAL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid professional type: {professional_type}. Available types: {config.PROFESSIONAL_TYPES}"
        )
    
    # Find which state the city belongs to
    city_state = None
    for state, cities in config.STATE_CITY_REGIONS.items():
        city_infos = [city_info for city_info, _ in cities]
        if city in city_infos:
            city_state = state
            break
    
    if not city_state:
        # Try to find by city name (without state suffix)
        city_name = city.split('-')[0] if '-' in city else city
        for state, cities in config.STATE_CITY_REGIONS.items():
            for city_info, _ in cities:
                if city_info.startswith(city_name.lower()):
                    city_state = state
                    city = city_info  # Use the full city_info format
                    break
            if city_state:
                break
    
    if not city_state:
        # Show available cities for better error message
        all_cities = []
        for state, cities in config.STATE_CITY_REGIONS.items():
            all_cities.extend([city_info for city_info, _ in cities])
        
        available_preview = ', '.join(all_cities[:10])
        if len(all_cities) > 10:
            available_preview += '...'
        
        raise HTTPException(
            status_code=400,
            detail=f"City '{city}' not found. Available cities: {available_preview}"
        )
    
    logger.info(f"✅ Validated city '{city}' in state '{city_state}' with profession '{professional_type}'")
    return city, city_state

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Houzz Lead Generation Pipeline API v2.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "status": "running"
    }

@app.get("/health", response_model=Dict[str, str])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "API is running"}

@app.get("/list-cities/{state}", response_model=ListCitiesResponse)
async def list_cities(state: str):
    """List cities for a specific state"""
    try:
        if state not in config.STATE_CITY_REGIONS:
            raise HTTPException(
                status_code=404,
                detail=f"No cities found for state '{state}'"
            )
        
        cities = config.STATE_CITY_REGIONS[state]
        formatted_state = state.replace('-', ' ').title()
        
        # Format cities for response
        formatted_cities = []
        for city_info, region_id in cities:
            # Extract city name from the city_info (format: "city-name-state-us")
            city_parts = city_info.split('-')
            if len(city_parts) > 2:
                # Remove the last two parts (state and country)
                city_name = ' '.join(city_parts[:-2])
            else:
                # Only remove the last part (country)
                city_name = ' '.join(city_parts[:-1])
            city_name = city_name.replace('-', ' ').title()
            formatted_cities.append({
                "name": city_name,
                "region_id": region_id,
                "city_info": city_info
            })
        
        return ListCitiesResponse(
            state=formatted_state,
            cities=formatted_cities,
            total_count=len(formatted_cities)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing cities for {state}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list cities: {str(e)}")

@app.get("/list-professional-types", response_model=Dict[str, Any])
async def list_professional_types():
    """List all available professional types for scraping"""
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
                "home-builders": "Home Builder"
            }
        }
    except Exception as e:
        logger.error(f"Error listing professional types: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list professional types: {str(e)}")

@app.get("/list-all-cities", response_model=Dict[str, Any])
async def list_all_cities():
    """List all available cities across all states"""
    try:
        all_cities = []
        for state, cities in config.STATE_CITY_REGIONS.items():
            for city_info, region_id in cities:
                # Extract city name from the city_info
                city_parts = city_info.split('-')
                if len(city_parts) > 2:
                    city_name = ' '.join(city_parts[:-2])
                else:
                    city_name = ' '.join(city_parts[:-1])
                city_name = city_name.replace('-', ' ').title()
                
                all_cities.append({
                    "city_info": city_info,
                    "city_name": city_name,
                    "state": state,
                    "region_id": region_id
                })
        
        return {
            "cities": all_cities,
            "total_count": len(all_cities),
            "states": list(config.STATE_CITY_REGIONS.keys())
        }
    except Exception as e:
        logger.error(f"Error listing all cities: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list all cities: {str(e)}")

@app.get("/stats", response_model=StatsResponse)
async def get_stats(platform: Optional[str] = None):
    """Get scraping progress statistics
    
    Args:
        platform: Optional platform filter ('houzz' or 'architizer'). 
                 If not provided, returns combined stats for all platforms.
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
                    'google_searches_done': (houzz_stats.get('google_searches_done', 0) or 0) + (architizer_stats.get('google_searches_done', 0) or 0),
                    'completed_profiles': (houzz_stats.get('completed_profiles', 0) or 0) + (architizer_stats.get('completed_profiles', 0) or 0),
                    'websites_pending': (houzz_stats.get('websites_pending', 0) or 0) + (architizer_stats.get('websites_pending', 0) or 0),
                    'google_searches_pending': (houzz_stats.get('google_searches_pending', 0) or 0) + (architizer_stats.get('google_searches_pending', 0) or 0),
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

@app.get("/proxy-status", response_model=Dict[str, Any])
async def get_proxy_status():
    """Get proxy rotation status and statistics"""
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
        
        if config.USE_PROXY_ROTATION and scraper.proxy_list:
            proxy_stats.update(scraper.get_proxy_stats())
        else:
            proxy_stats.update({
                'message': 'Proxy rotation is disabled or no proxies configured',
                'total_proxies': 0
            })
        
        return proxy_stats
        
    except Exception as e:
        logger.error(f"Error getting proxy status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get proxy status: {str(e)}")

@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """Main scraping endpoint that runs the pipeline for a single city and profession"""
    import time
    start_time = time.time()
    
    try:
        # Validate platform
        if request.platform not in ['houzz', 'architizer']:
            raise HTTPException(
                status_code=400,
                detail="Platform must be 'houzz' or 'architizer'"
            )
        
        # Validate city and professional type
        validated_city, city_state = validate_city_and_profession(request.city, request.professional_type)
        
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
        
        # Determine email verification setting
        verify_emails = not request.no_email_verification
        if not verify_emails:
            logger.info("Email verification disabled by request parameter")
        else:
            logger.info("Email verification enabled (default)")
        
        # Run the complete pipeline for single city and profession
        logger.info(f"🚀 Starting {request.platform} pipeline for {validated_city} - {request.professional_type}")
        
        # Execute the full pipeline with single city and profession
        output_file = await pipeline.run_full_pipeline(
            city=validated_city,
            city_state=city_state,
            professional_type=request.professional_type,
            max_pages=request.max_pages,
            start_page=request.start_page,
            verify_emails=verify_emails,
            platform=request.platform
        )
        
        execution_time = time.time() - start_time
        
        if output_file:
            message = f"✅ {request.platform.capitalize()} pipeline completed successfully for {validated_city} - {request.professional_type}!"
            return ScrapeResponse(
                success=True,
                message=message,
                output_file=output_file,
                execution_time=execution_time
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
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
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
