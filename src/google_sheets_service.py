"""Google Sheets Integration Service for Pipeline Results

This service provides functionality to update Google Sheets when the pipeline
completes successfully. It handles authentication, data formatting, and 
updating the specified worksheet with pipeline results.
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from loguru import logger

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    logger.warning(f"Google Sheets dependencies not installed: {e}")
    logger.warning("Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2")

from config.config import config


class GoogleSheetsService:
    """Service for updating Google Sheets with pipeline results"""
    
    def __init__(self):
        self.service = None
        self.spreadsheet_id = config.GOOGLE_SHEETS_SPREADSHEET_ID
        self.worksheet_name = config.GOOGLE_SHEETS_WORKSHEET_NAME
        
        if not self.spreadsheet_id:
            logger.warning("Google Sheets integration disabled - no spreadsheet ID configured")
            return
            
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Sheets API service with credentials from environment variables"""
        try:
            credentials = self._get_credentials_from_env()
            
            if not credentials:
                logger.error("No valid Google Sheets credentials found in environment variables")
                return
            
            # Build the service
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("✅ Google Sheets service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {e}")
            self.service = None
    
    def _get_credentials_from_env(self):
        """Get credentials from environment variables"""
        try:
            # Check if all required environment variables are present
            required_vars = [
                'GOOGLE_SHEETS_CLIENT_EMAIL',
                'GOOGLE_SHEETS_PRIVATE_KEY', 
                'GOOGLE_SHEETS_PROJECT_ID'
            ]
            
            missing_vars = []
            for var in required_vars:
                if not getattr(config, var):
                    missing_vars.append(var)
            
            if missing_vars:
                logger.info(f"Missing required environment variables for Google Sheets: {missing_vars}")
                return None
            
            # Define the scopes for Google Sheets and Drive APIs
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Create credentials info dictionary with only essential fields
            service_account_info = {
                "type": "service_account",
                "project_id": config.GOOGLE_SHEETS_PROJECT_ID,
                "private_key": config.GOOGLE_SHEETS_PRIVATE_KEY.replace('\\n', '\n'),
                "client_email": config.GOOGLE_SHEETS_CLIENT_EMAIL,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
            
            # Create credentials from service account info
            credentials = Credentials.from_service_account_info(
                service_account_info,
                scopes=scopes
            )
            
            logger.info("✅ Google Sheets credentials loaded from environment variables")
            return credentials
            
        except Exception as e:
            logger.error(f"Failed to load credentials from environment variables: {e}")
            return None
    
    
    def is_available(self) -> bool:
        """Check if Google Sheets service is available and configured"""
        return (
            self.service is not None and 
            self.spreadsheet_id is not None
        )
    
    def update_pipeline_results(self, total_time_minutes: float, row_number: int) -> bool:
        """
        Update specific row in Google Sheets with pipeline completion results
        
        Args:
            stats: Pipeline statistics dictionary
            row_number: Row number to update (1-based)
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        if not self.is_available():
            logger.warning("Google Sheets service not available - skipping update")
            return False
        
        try:
            # Prepare the data for the 3 columns we want to update
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            time_to_scrape = round(total_time_minutes, 2)  # Convert to minutes
            is_scraped = "TRUE"
            
            # Create data row for the 3 columns: is_scraped, time_to_scrape, timestamp
            # These correspond to columns F, G, H (6th, 7th, 8th columns)
            row_data = [
                is_scraped,              # F: is_scraped
                time_to_scrape,  # G: time_to_scrape (in minutes)
                timestamp               # H: timestamp
            ]
            
            # Prepare the update request
            body = {
                'values': [row_data]
            }
            
            # Update specific columns in the specific row (F, G, H columns)
            range_name = f"{self.worksheet_name}!F{row_number}:H{row_number}"
            
            # Update the data (not append)
            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            updated_cells = result.get('updatedCells', 0)
            logger.info(f"✅ Successfully updated Google Sheets row {row_number}: {updated_cells} cells updated")
            logger.info(f"📊 Updated columns F-H in row {row_number} of spreadsheet: {self.spreadsheet_id}")
            
            return True
            
        except HttpError as e:
            logger.error(f"Google Sheets API error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to update Google Sheets: {e}")
            return False
    
    
    def test_connection(self) -> bool:
        """
        Test the connection to Google Sheets
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            # Try to get spreadsheet metadata
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            title = spreadsheet.get('properties', {}).get('title', 'Unknown')
            logger.info(f"✅ Google Sheets connection successful - Spreadsheet: {title}")
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets connection test failed: {e}")
            return False
    
    def update_profiles_sheet(self, stats: Dict[str, Any]) -> bool:
        """
        Update the profiles Google Sheet with profile names and emails
        
        Args:
            stats: Pipeline statistics dictionary containing profiles
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        if not self.is_available():
            logger.warning("Google Sheets service not available - skipping profile update")
            return False
        
        # Check if profiles spreadsheet is configured
        profiles_spreadsheet_id = config.GOOGLE_SHEETS_PROFILES_SPREADSHEET_ID
        profiles_worksheet_name = config.GOOGLE_SHEETS_PROFILES_WORKSHEET_NAME
        
        if not profiles_spreadsheet_id:
            logger.warning("Profiles Google Sheet not configured - skipping profile update")
            return False
        
        try:
            # Extract profiles from stats
            profiles = stats.get('profiles', [])
            if not profiles:
                logger.info("No profiles found in stats - skipping profile update")
                return True
            
            logger.info(f"📊 Updating profiles sheet with {len(profiles)} profiles...")
            
            # Prepare profile records
            profile_records = []
            
            for profile in profiles:
                name = profile.get('name', '')
                emails = profile.get('emails', [])
                
                # Handle both string and list email formats
                if isinstance(emails, str):
                    # Try to parse as JSON first, fallback to single email
                    try:
                        import json
                        emails = json.loads(emails)
                    except:
                        emails = [emails] if emails else []
                elif not isinstance(emails, list):
                    emails = []
                
                # Create a record for each email
                for email in emails:
                    if email:  # Only add non-empty emails
                        profile_records.append([
                            email,  # A: email
                            name,   # B: name
                            '',     # C: last_sent_date (empty)
                            '',     # D: templates_sent (empty)
                            '',     # E: workspace_used (empty)
                            '',     # F: replied (empty)
                            '',     # G: status (empty)
                            ''      # H: thread_id (empty)
                        ])
            
            if not profile_records:
                logger.info("No valid email addresses found in profiles - skipping profile update")
                return True
            
            # Prepare the update request
            body = {
                'values': profile_records
            }
            
            # Append the profile records to the profiles sheet (starting from column A)
            range_name = f"{profiles_worksheet_name}!A2:H"
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=profiles_spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            updated_rows = result.get('updates', {}).get('updatedRows', 0)
            logger.info(f"✅ Successfully updated profiles sheet: {updated_rows} profile records added")
            logger.info(f"📊 Added {len(profile_records)} profile records to spreadsheet: {profiles_spreadsheet_id}")
            
            return True
            
        except HttpError as e:
            logger.error(f"Google Sheets API error updating profiles: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to update profiles sheet: {e}")
            return False