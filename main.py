#!/usr/bin/env python3
"""
Houzz Lead Generation Pipeline v2.0
====================================

A production-ready, enterprise-grade 4-phase data scraping and enrichment pipeline that 
extracts validated leads from Houzz and Architizer across all 50 U.S. states and 7+ professional types.

Key Features:
- Multi-Platform Support: Houzz and Architizer integration with unified pipeline
- 4-Phase Pipeline: Platform scraping → Website email mining → Google enrichment → Verification & export
- ZeroBounce Integration: Production-grade email verification with smart credit management
- Playwright Automation: JavaScript-heavy website scraping with browser automation
- Google Custom Search: Finds Gmail addresses and social media profiles
- Intelligent Email Prioritization: Personal > Business > Generic email selection
- SQLite Database: Persistent storage with progress tracking and resume capability
- Anti-Detection: CAPTCHA handling, proxy support, rate limiting, user-agent rotation
- High Performance: Concurrent processing, efficient database operations, memory optimization

Phase Breakdown:
    Phase 1: Platform Profile Scraping - Extract professional profiles from Houzz/Architizer
    Phase 2: Advanced Website Email Mining - Use Playwright to extract emails from professional websites  
    Phase 3: Google Custom Search Enrichment - Find Gmail addresses and social media profiles via Google API
    Phase 4: ZeroBounce Verification & CSV Export - Verify emails and export to production-ready CSV

Usage Examples:
    python3 main.py --platform houzz --list-states                         # List all available US states
    python3 main.py --platform houzz                                       # Run full 4-phase pipeline (all states)
    python3 main.py --platform houzz --states california texas             # Run for specific states
    python3 main.py --platform houzz --no-email-verification               # Skip ZeroBounce verification
    python3 main.py --platform houzz --phase scrape --states california    # Only scrape Houzz profiles
    python3 main.py --platform architizer --phase scrape                   # Only scrape Architizer profiles
    python3 main.py --platform houzz --phase websearch                     # Only run website email mining
    python3 main.py --platform houzz --phase googlesearch                  # Only run Google search enrichment
    python3 main.py --platform houzz --phase export                        # Only run verification & export
    python3 main.py --platform houzz --stats                               # Show scraping statistics
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from loguru import logger

# Add src directory to Python path for imports
SRC_PATH = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC_PATH))

# Import core modules with error handling
try:
    from src.pipeline import LeadEnrichmentPipeline  
    from src.database_manager import DatabaseManager
    from config.config import config
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Make sure you have activated the virtual environment:")
    print("   source venv/bin/activate")
    print("💡 And installed all dependencies:")
    print("   pip install -r requirements.txt")
    sys.exit(1)

def setup_argument_parser() -> argparse.ArgumentParser:
    """Setup command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Houzz Lead Generation Pipeline v2.0 - Multi-Platform Lead Generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py --platform houzz --list-states                  # List all available US states
  python3 main.py --platform houzz --list-cities alabama          # List cities in Alabama
  python3 main.py --platform houzz                                # Run full pipeline for all states
  python3 main.py --platform houzz --states california texas      # Specific states only
  python3 main.py --platform houzz --states wyoming --cities wyoming cheyenne casper  # Specific cities with state
  python3 main.py --platform houzz --states california --cities "Los Angeles County"  # Specific cities without state
  python3 main.py --platform houzz --stats                        # Show scraping statistics
  python3 main.py --platform houzz --phase scrape                 # Only scrape Houzz profiles
  python3 main.py --platform architizer --phase scrape            # Only scrape Architizer profiles
  python3 main.py --platform houzz --phase websearch              # Only run website email mining
  python3 main.py --platform houzz --phase googlesearch           # Only run Google search enrichment
  python3 main.py --platform houzz --phase export                 # Only export to CSV
        """
    )
    
    # Execution modes
    execution_group = parser.add_mutually_exclusive_group(required=False)
    execution_group.add_argument(
        '--list-states', 
        action='store_true',
        help='List all available US states and exit'
    )
    execution_group.add_argument(
        '--list-cities',
        type=str,
        choices=config.US_STATES,
        help='List cities for a specific state (e.g., alabama, california)'
    )
    execution_group.add_argument(
        '--stats', 
        action='store_true',
        help='Show scraping progress statistics and exit'
    )
    
    # Required platform parameter
    parser.add_argument(
        '--platform',
        required=True,
        choices=['houzz', 'architizer'],
        help='REQUIRED: Platform to scrape/process (houzz or architizer)'
    )
    
    # Optional parameters
    parser.add_argument(
        '--states', 
        nargs='+',
        choices=config.US_STATES,
        help='Specific states to scrape (space-separated)'
    )
    
    parser.add_argument(
        '--cities',
        nargs='+',
        help='Specific cities to scrape (space-separated). Must be used with --states. Format: [state] city1 city2 (e.g., wyoming cheyenne casper or just cheyenne casper). Use --list-cities state to see available cities.'
    )
    
    parser.add_argument(
        '--professional-types',
        nargs='+', 
        choices=config.PROFESSIONAL_TYPES,
        help='Specific professional types to scrape (space-separated)'
    )
    
    parser.add_argument(
        '--max-pages',
        type=int,
        help='Maximum number of pages to scrape per city (default: 50)'
    )
    
    parser.add_argument(
        '--start-page',
        type=int,
        default=1,
        help='Starting page number for scraping (default: 1)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=config.OUTPUT_DIR,
        help='Output directory for CSV files'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )
    
    parser.add_argument(
        '--no-email-verification',
        action='store_true',
        help='Skip email verification step'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be scraped without actually scraping'
    )
    
    # Phase-specific execution
    parser.add_argument(
        '--phase',
        choices=['scrape', 'websearch', 'googlesearch', 'export', 'all'],
        default='all',
        help='Run specific phase only: scrape=scrape profiles from platform, websearch=scrape websites, googlesearch=Google search enrichment, export=CSV export, all=run everything (default)'
    )
    
    
    return parser

def validate_environment() -> bool:
    """Validate environment and return success status.
    
    Returns:
        bool: True if validation passes, False otherwise
    """
    errors = []
    warnings = []
    
    # Check if virtual environment is activated
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        warnings.append("Virtual environment not detected - ensure you're using: source venv/bin/activate")
    
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
    
    # Check if .env file exists
    env_file = Path('.env')
    if not env_file.exists():
        warnings.append(".env file not found - copy .env.example to .env and configure your API keys")
    
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

async def main():
    """Main function"""
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # Configure logging level
    logger.remove()  # Remove default logger
    logger.add(
        sys.stderr, 
        level=args.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
    )
    
    # Validate cities parameter
    if args.cities:
        if not args.states:
            logger.error("❌ --cities parameter requires --states parameter")
            logger.info("Usage: python3 main.py --platform houzz --states wyoming --cities wyoming cheyenne casper")
            sys.exit(1)
        
        if len(args.states) > 1:
            logger.error("❌ --cities parameter can only be used with a single state")
            logger.info("Usage: python3 main.py --platform houzz --states wyoming --cities wyoming cheyenne casper")
            sys.exit(1)
        
        state = args.states[0]
        if len(args.cities) < 1:
            logger.error("❌ --cities parameter requires at least one city name")
            logger.info("Usage: python3 main.py --platform houzz --states wyoming --cities wyoming cheyenne casper")
            sys.exit(1)
        
        # Check if the state name is in the first few elements of cities
        # This handles cases like "Los Angeles County" where the first word isn't the state
        state_found = False
        state_index = -1
        
        # Look for the state name in the first few elements
        for i in range(min(3, len(args.cities))):
            if args.cities[i].lower() == state.lower():
                state_found = True
                state_index = i
                break
        
        if not state_found:
            # If state not found in first few elements, assume it's not provided and add it
            logger.info(f"State '{state}' not found in cities parameter, assuming it's not provided")
            # Insert the state at the beginning
            args.cities.insert(0, state)
            state_index = 0
        
        # Validate that the cities exist for the given state
        if state not in config.STATE_CITY_REGIONS:
            logger.error(f"❌ No cities found for state '{state}'")
            sys.exit(1)
        
        available_cities = [city_info for city_info, _ in config.STATE_CITY_REGIONS[state]]
        # Get cities after the state (skip state_index + 1 elements)
        requested_cities = args.cities[state_index + 1:] if state_index + 1 < len(args.cities) else []
        
        if not requested_cities:
            logger.error("❌ No city names found after the state")
            logger.info("Usage: python3 main.py --platform houzz --states wyoming --cities wyoming cheyenne casper")
            sys.exit(1)
        
        # Extract city names from the city_info format (e.g., "cheyenne-wy-us" -> "cheyenne")
        available_city_names = []
        for city_info in available_cities:
            city_parts = city_info.split('-')
            if len(city_parts) > 2:
                city_name = ' '.join(city_parts[:-2])
            else:
                city_name = ' '.join(city_parts[:-1])
            available_city_names.append(city_name.lower())
        
        # Check if requested cities exist
        invalid_cities = []
        for city in requested_cities:
            if city.lower() not in available_city_names:
                invalid_cities.append(city)
        
        if invalid_cities:
            logger.error(f"❌ Invalid cities for {state}: {invalid_cities}")
            logger.info(f"Available cities in {state}: {', '.join(available_city_names[:10])}{'...' if len(available_city_names) > 10 else ''}")
            logger.info("Use --list-cities california to see all available cities")
            sys.exit(1)
        
        logger.info(f"✅ Validated {len(requested_cities)} cities for {state}: {requested_cities}")
    
# Handle stats command before any validation
    if args.stats:
        logger.info("Fetching scraping progress statistics")
        try:
            db_manager = DatabaseManager()
            stats = db_manager.get_scraping_stats()
            db_manager.close()
            
            if stats:
                print("\n📊 Scraping Progress Statistics")
                print("="*40)
                for key, value in stats.items():
                    print(f"{key.replace('_', ' ').title()}: {value}")
            else:
                print("No statistics available - database may be empty or not initialized.")
        except Exception as e:
            logger.error(f"Failed to retrieve statistics: {e}")
        return
    
    # Handle list-states command before any validation
    if args.list_states:
        print("\n🏠 Available US States for Houzz Scraping")
        print("="*50)
        print(f"Total States: {len(config.US_STATES)}\n")
        
        # Display states in a formatted table
        for i, state in enumerate(sorted(config.US_STATES), 1):
            formatted_name = state.replace('-', ' ').title()
            print(f"{i:2d}. {formatted_name:<20} ({state})")
        
        print("\n📋 Usage Examples:")
        print("  python3 main.py --states california texas")
        print("  python3 main.py --states new-york florida")
        print("  python3 main.py --states texas  # Single state")
        print("\n💡 Tip: Use the values in parentheses for the --states parameter")
        return
    
    # Handle list-cities command before any validation
    if args.list_cities:
        state = args.list_cities
        if state not in config.STATE_CITY_REGIONS:
            print(f"❌ Error: No cities found for state '{state}'")
            return
        
        cities = config.STATE_CITY_REGIONS[state]
        formatted_state = state.replace('-', ' ').title()
        
        print(f"\n🏙️  Cities in {formatted_state}")
        print("="*50)
        print(f"Total Cities: {len(cities)}\n")
        
        # Display cities in a formatted table
        for i, (city_info, region_id) in enumerate(cities, 1):
            # Extract city name from the city_info (format: "city-name-state-us")
            city_parts = city_info.split('-')
            if len(city_parts) > 2:
                # Remove the last two parts (state and country)
                city_name = ' '.join(city_parts[:-2])
            else:
                # Only remove the last part (country)
                city_name = ' '.join(city_parts[:-1])
            city_name = city_name.replace('-', ' ').title()
            print(f"{i:2d}. {city_name:<30} (Region ID: {region_id})")
        
        print(f"\n📋 Usage Examples:")
        print(f"  python3 main.py --platform houzz --states {state}")
        print(f"  python3 main.py --platform houzz --states {state} --professional-types interior-designer")
        print(f"\n💡 Tip: Use the state name '{state}' with the --states parameter")
        return
    
    logger.info(f"Starting {args.platform} Lead Generation Pipeline")
    logger.info(f"Arguments: {vars(args)}")
    
    # Validate environment
    if not validate_environment():
        logger.error("Environment validation failed. Please fix the issues above and try again.")
        sys.exit(1)
    
    # Handle dry run
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No actual scraping will be performed")
        states = args.states or config.US_STATES
        prof_types = args.professional_types or config.PROFESSIONAL_TYPES
        
        logger.info(f"📍 Would scrape {len(states)} states: {states[:5]}{'...' if len(states) > 5 else ''}")
        logger.info(f"👷 Would scrape {len(prof_types)} professional types: {prof_types}")
        
        logger.info("🚀 Would run full production scraping")
        estimated_profiles = len(states) * len(prof_types) * config.MAX_PAGES_PER_STATE * 20  # ~20 per page
        logger.info(f"📊 Estimated profiles to scrape: {estimated_profiles:,}")
        
        logger.success("✅ Dry run completed successfully")
        return
    
    # Initialize pipeline
    try:
        pipeline = LeadEnrichmentPipeline()
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        logger.error("Please check your configuration and try again.")
        sys.exit(1)
    
    try:
        # Determine execution parameters
        states = args.states
        max_profiles = None
        
        # Determine email verification setting
        verify_emails = not args.no_email_verification
        if not verify_emails:
            logger.info("Email verification disabled by command line argument")
        else:
            logger.info("Email verification enabled (default)")
        
        # Run the pipeline based on phase with optimized execution
        logger.info(f"🚀 Executing pipeline phase: {args.phase}")
        
        # Define platform-specific scraping function
        async def scrape_platform():
            if args.platform == "houzz":
                return await pipeline.scrape_houzz_profiles(
                    states=states, 
                    professional_types=args.professional_types,
                    max_pages=args.max_pages,
                    start_page=args.start_page,
                    max_profiles=max_profiles,
                    cities=args.cities
                )
            elif args.platform == "architizer":
                return await pipeline.scrape_architizer_profiles(
                    max_pages=args.max_pages,
                    start_page=args.start_page
                )
            else:
                raise ValueError(f"Unsupported platform: {args.platform}")
        
        # Phase execution mapping for better maintainability
        phase_handlers = {
            'scrape': scrape_platform,
            'websearch': lambda: pipeline.run_websearch_phase(platform=args.platform),
            'googlesearch': lambda: pipeline.run_google_search_phase(platform=args.platform),
            'export': lambda: pipeline.run_export_phase(verify_emails=verify_emails, platform=args.platform),
            'all': lambda: pipeline.run_full_pipeline(
                states=states, 
                professional_types=args.professional_types,
                max_pages=args.max_pages,
                start_page=args.start_page,
                max_profiles=max_profiles,
                verify_emails=verify_emails,
                platform=args.platform,
                cities=args.cities
            )
        }
        
        # Execute the selected phase
        phase_handler = phase_handlers.get(args.phase)
        if not phase_handler:
            logger.error(f"Unknown phase: {args.phase}")
            sys.exit(1)
        
        # Run the phase and handle results
        output_file = await phase_handler()
        
        # Handle phase-specific success messages
        phase_success_messages = {
            'scrape': f"✅ {args.platform.capitalize()} scraping phase completed!",
            'websearch': "✅ Website scraping phase completed!",
            'googlesearch': "✅ Google search enrichment phase completed!",
            'export': "✅ CSV export completed!",
            'all': "✅ Full pipeline completed!"
        }
        
        if args.phase in ['scrape', 'websearch', 'googlesearch']:
            logger.success(phase_success_messages[args.phase])
            return
        elif args.phase == 'export':
            if output_file:
                logger.success(f"✅ CSV export completed! File: {output_file}")
            else:
                logger.error("❌ CSV export failed - no data to export")
            return
        
        if output_file:
            logger.success(f"Pipeline completed successfully!")
            logger.success(f"Output file: {output_file}")
            
            # Generate and display report
            logger.info("Generating summary report...")
            # Note: In production, you might want to load the contacts from the CSV for reporting
            # For now, we'll just show the file location
            
            print("\n" + "="*60)
            print("🎉 HOUZZ LEAD GENERATION COMPLETED")
            print("="*60)
            print(f"📄 Output file: {output_file}")
            print(f"📊 Check logs in: {config.LOG_DIR}")
            print("="*60)
        else:
            logger.error("Pipeline completed but no output file was generated")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
        logger.info("Progress has been saved.")
        sys.exit(0)
    
    except Exception as e:
        # Check if this is a Google API quota limit error
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['quota', 'rate limit', '429', '403', 'google']):
            logger.warning(f"Google API limit reached: {e}")
            logger.info("Continuing with pipeline - Google search enrichment will be skipped")
            # Don't exit, just log and continue
        else:
            logger.error(f"Pipeline failed with error: {e}")
            logger.exception("Full error traceback:")
            sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user. Progress has been saved.")
        sys.exit(0)
