import requests
import json
from datetime import datetime
import pytz
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import Opportunity, GHLAuthCredentials  # Replace 'myapp' with your actual app name
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GHLOpportunityFetcher:
    def __init__(self, access_token, location_id):
        self.access_token = access_token
        self.location_id = location_id
        self.base_url = "https://services.leadconnectorhq.com"
        self.headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}',
            'Version': '2021-07-28'
        }
        
        # Pipeline mappings
        self.pipelines = {
            "General Entity Pipeline": "XuGY5OWwnnVApR7udk2m",
            "Tax Onboarding Pipeline": "femeFj3B35BZTsOb04CZ", 
            "Refund Pipeline": "PUlGYnwwi8Z10yD8Nu1s"
        }
        
        # Cache for pipeline and user data
        self.pipeline_cache = {}
        self.user_cache = {}
        
        # Set timezone to US/Arizona
        self.timezone = pytz.timezone('US/Arizona')

    def fetch_pipeline_data(self):
        """Fetch and cache pipeline data"""
        try:
            url = f"{self.base_url}/opportunities/pipelines"
            params = {'locationId': self.location_id}
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            pipelines = data.get('pipelines', [])
            
            # Cache pipeline and stage information
            for pipeline in pipelines:
                pipeline_id = pipeline['id']
                self.pipeline_cache[pipeline_id] = {
                    'name': pipeline['name'],
                    'stages': {stage['id']: stage['name'] for stage in pipeline.get('stages', [])}
                }
            
            logger.info(f"Cached {len(pipelines)} pipelines")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching pipeline data: {e}")
            return False

    def fetch_user_data(self, user_id):
        """Fetch and cache user data"""
        if user_id in self.user_cache:
            return self.user_cache[user_id]
        
        try:
            url = f"{self.base_url}/users/{user_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            user_data = response.json()
            self.user_cache[user_id] = {
                'name': user_data.get('name', ''),
                'email': user_data.get('email', ''),
                'firstName': user_data.get('firstName', ''),
                'lastName': user_data.get('lastName', '')
            }
            
            logger.info(f"Cached user data for {user_id}")
            return self.user_cache[user_id]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching user data for {user_id}: {e}")
            return {'name': '', 'email': '', 'firstName': '', 'lastName': ''}

    def fetch_opportunities_for_pipeline(self, pipeline_name, pipeline_id):
        """Fetch all opportunities for a specific pipeline with pagination"""
        all_opportunities = []
        page = 1
        has_next_page = True
        start_after_id = None
        start_after = None
        
        logger.info(f"Fetching opportunities for pipeline: {pipeline_name}")
        
        while has_next_page:
            try:
                url = f"{self.base_url}/opportunities/search"
                params = {
                    'location_id': self.location_id,
                    'pipeline_id': pipeline_id,
                    'limit': 100  # Maximum limit per page
                }
                
                # Add pagination parameters if not first page
                if start_after_id:
                    params['startAfterId'] = start_after_id
                if start_after:
                    params['startAfter'] = start_after
                
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                opportunities = data.get('opportunities', [])
                meta = data.get('meta', {})
                
                all_opportunities.extend(opportunities)
                
                # Check if there's a next page
                next_page_url = meta.get('nextPageUrl')
                start_after_id = meta.get('startAfterId')
                start_after = meta.get('startAfter')
                
                has_next_page = bool(next_page_url and opportunities)
                
                logger.info(f"Fetched page {page} for {pipeline_name}: {len(opportunities)} opportunities")
                page += 1
                
                # Safety check to prevent infinite loops
                if page > 1000:
                    logger.warning(f"Reached maximum page limit for {pipeline_name}")
                    break
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching opportunities for {pipeline_name}, page {page}: {e}")
                break
        
        logger.info(f"Total opportunities fetched for {pipeline_name}: {len(all_opportunities)}")
        return all_opportunities

    def save_opportunity_to_db(self, opp_data, pipeline_name):
        """Save opportunity data to database"""
        try:
            # Get pipeline and stage names
            pipeline_id = opp_data.get('pipelineId', '')
            stage_id = opp_data.get('pipelineStageId', '')
            
            pipeline_info = self.pipeline_cache.get(pipeline_id, {})
            stage_name = pipeline_info.get('stages', {}).get(stage_id, '')
            
            # Get assigned user info
            assigned_to = opp_data.get('assignedTo', '')
            user_info = self.fetch_user_data(assigned_to) if assigned_to else {}
            
            # Get contact info
            contact = opp_data.get('contact', {})
            
            # Parse dates
            created_at = self.parse_datetime(opp_data.get('createdAt'))
            updated_at = self.parse_datetime(opp_data.get('updatedAt'))
            
            # Create or update opportunity
            opportunity, created = Opportunity.objects.update_or_create(
                id=opp_data.get('id'),
                defaults={
                    'name': opp_data.get('name', ''),
                    'monetary_value': opp_data.get('monetaryValue', 0),
                    'pipeline_id': pipeline_id,
                    'pipeline_name': pipeline_name,
                    'pipeline_stage_id': stage_id,
                    'pipeline_stage_name': stage_name,
                    'assigned_to': assigned_to,
                    'assigned_user_name': user_info.get('name', ''),
                    'assigned_user_email': user_info.get('email', ''),
                    'status': opp_data.get('status', ''),
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'contact_id': contact.get('id', ''),
                    'contact_name': contact.get('name', ''),
                    'contact_company_name': contact.get('companyName', ''),
                    'contact_email': contact.get('email', ''),
                    'contact_phone': contact.get('phone', ''),
                    'contact_tags': contact.get('tags', []),
                    'location_id': opp_data.get('locationId', '')
                }
            )
            
            action = "Created" if created else "Updated"
            logger.info(f"{action} opportunity: {opportunity.name} (ID: {opportunity.id})")
            return opportunity
            
        except Exception as e:
            logger.error(f"Error saving opportunity {opp_data.get('id', 'Unknown')}: {e}")
            return None

    def parse_datetime(self, date_string):
        """Parse datetime string to Django datetime object in US/Arizona timezone"""
        if not date_string:
            return timezone.now().astimezone(self.timezone)
        
        try:
            # Parse ISO format datetime (assumes UTC from API)
            dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            
            # If naive, assume UTC
            if timezone.is_naive(dt):
                dt = pytz.UTC.localize(dt)
            
            # Convert to US/Arizona timezone
            arizona_dt = dt.astimezone(self.timezone)
            
            # Make sure it's timezone-aware for Django
            return arizona_dt
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not parse datetime: {date_string}, error: {e}")
            return timezone.now().astimezone(self.timezone)

    def fetch_all_opportunities(self):
        """Main method to fetch all opportunities from specified pipelines"""
        logger.info("Starting opportunity fetch process...")
        
        # First, fetch and cache pipeline data
        if not self.fetch_pipeline_data():
            logger.error("Failed to fetch pipeline data. Aborting.")
            return False
        
        total_saved = 0
        
        # Fetch opportunities for each pipeline
        for pipeline_name, pipeline_id in self.pipelines.items():
            try:
                logger.info(f"\n--- Processing {pipeline_name} ---")
                
                # Fetch all opportunities for this pipeline
                opportunities = self.fetch_opportunities_for_pipeline(pipeline_name, pipeline_id)
                
                # Save each opportunity to database
                saved_count = 0
                for opp_data in opportunities:
                    if self.save_opportunity_to_db(opp_data, pipeline_name):
                        saved_count += 1
                
                logger.info(f"Saved {saved_count}/{len(opportunities)} opportunities for {pipeline_name}")
                total_saved += saved_count
                
            except Exception as e:
                logger.error(f"Error processing pipeline {pipeline_name}: {e}")
                continue
        
        logger.info(f"\n=== Process Complete ===")
        logger.info(f"Total opportunities saved: {total_saved}")
        return True


class Command(BaseCommand):
    """Django management command to run the opportunity fetcher"""
    help = 'Fetch opportunities from GoHighLevel API and save to database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=str,
            help='User ID to get credentials for (optional, will use first available if not specified)',
        )

    def handle(self, *args, **options):
        try:
            # Get credentials from database
            user_id = options.get('user_id')
            if user_id:
                credentials = GHLAuthCredentials.objects.get(user_id=user_id)
            else:
                credentials = GHLAuthCredentials.objects.first()
            
            if not credentials:
                self.stdout.write(
                    self.style.ERROR('No GHL credentials found in database')
                )
                return
            
            self.stdout.write(
                self.style.SUCCESS(f'Using credentials for user: {credentials.user_id}')
            )
            
            # Initialize fetcher
            fetcher = GHLOpportunityFetcher(
                access_token=credentials.access_token,
                location_id=credentials.location_id
            )
            
            # Start fetching
            success = fetcher.fetch_all_opportunities()
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS('Successfully completed opportunity fetch!')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Opportunity fetch completed with errors')
                )
                
        except GHLAuthCredentials.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'No credentials found for user ID: {user_id}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            )


# Standalone function for use outside Django management commands
def fetch_opportunities_standalone(access_token, location_id):
    """
    Standalone function to fetch opportunities
    Usage: fetch_opportunities_standalone('your_access_token', 'your_location_id')
    """
    fetcher = GHLOpportunityFetcher(access_token, location_id)
    return fetcher.fetch_all_opportunities()


def sync_opportunities():
    token = GHLAuthCredentials.objects.first()
    ACCESS_TOKEN = token.access_token
    LOCATION_ID = token.location_id

    fetch_opportunities_standalone(ACCESS_TOKEN, LOCATION_ID)
