from decouple import config
import requests
from django.http import JsonResponse
import json
from django.shortcuts import redirect
from accounts.models import GHLAuthCredentials,Webhook, SmartVaultToken
from django.views.decorators.csrf import csrf_exempt
import logging
from django.views import View
from django.utils.decorators import method_decorator
import traceback
from django.shortcuts import redirect




logger = logging.getLogger(__name__)


GHL_CLIENT_ID = config("GHL_CLIENT_ID")
GHL_CLIENT_SECRET = config("GHL_CLIENT_SECRET")
GHL_REDIRECTED_URI = config("GHL_REDIRECTED_URI")
TOKEN_URL = "https://services.leadconnectorhq.com/oauth/token"
SCOPE = config("SCOPE")


SMARTVAULT_CLIENT_ID = config("SMARTVAULT_CLIENT_ID")
SMARTVAULT_CLIENT_SECRET = config("SMARTVAULT_CLIENT_SECRET")
SMARTVAULT_TOKEN_BASE_URL = "https://rest.smartvault.com/auto/auth"
SMARTVAULT_REDIRECT_URI=config("SMARTVAULT_REDIRECT_URI")

def auth_connect(request):
    auth_url = ("https://marketplace.leadconnectorhq.com/oauth/chooselocation?response_type=code&"
                f"redirect_uri={GHL_REDIRECTED_URI}&"
                f"client_id={GHL_CLIENT_ID}&"
                f"scope={SCOPE}"
                )
    return redirect(auth_url)



def callback(request):
    
    code = request.GET.get('code')

    if not code:
        return JsonResponse({"error": "Authorization code not received from OAuth"}, status=400)

    return redirect(f'{config("BASE_URI")}/accounts/auth/tokens?code={code}')


def tokens(request):
    authorization_code = request.GET.get("code")

    if not authorization_code:
        return JsonResponse({"error": "Authorization code not found"}, status=400)

    data = {
        "grant_type": "authorization_code",
        "client_id": GHL_CLIENT_ID,
        "client_secret": GHL_CLIENT_SECRET,
        "redirect_uri": GHL_REDIRECTED_URI,
        "code": authorization_code,
    }

    response = requests.post(TOKEN_URL, data=data)

    try:
        response_data = response.json()
        if not response_data:
            return

        obj, created = GHLAuthCredentials.objects.update_or_create(
            location_id= response_data.get("locationId"),
            defaults={
                "access_token": response_data.get("access_token"),
                "refresh_token": response_data.get("refresh_token"),
                "expires_in": response_data.get("expires_in"),
                "scope": response_data.get("scope"),
                "user_type": response_data.get("userType"),
                "company_id": response_data.get("companyId"),
                "user_id":response_data.get("userId"),

            }
        )
        return JsonResponse({
            "message": "Authentication successful",
            "access_token": response_data.get('access_token'),
            "token_stored": True
        })
        
    except requests.exceptions.JSONDecodeError:
        return JsonResponse({
            "error": "Invalid JSON response from API",
            "status_code": response.status_code,
            "response_text": response.text[:500]
        }, status=500)
    



def smartvaultauth_connect(request):
    
    auth_url = (
        f"https://my.smartvault.com/users/secure/IntegratedApplications.aspx"
        f"?client_id={SMARTVAULT_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={SMARTVAULT_REDIRECT_URI}"
    )
    return redirect(auth_url)



def smartvaultcallback(request):
    """
    This view will be used as the redirect_uri for SmartVault OAuth.
    It grabs the authorization_code and forwards it to your auth endpoint.
    """
    authorization_code = request.GET.get("code")

    if not authorization_code:
        return JsonResponse({"error": "Authorization code not found"}, status=400)

    # Redirect to your auth endpoint with the code
    return redirect(f"http://localhost:8000/accounts/smartvault/auth/?code={authorization_code}")
    



import json
import requests
from datetime import timedelta
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import SmartVaultToken
from decouple import config
import xml.etree.ElementTree as ET






@csrf_exempt
def smartvault_auth(request):
    if request.method == "GET":
        code = request.GET.get("code")
    elif request.method == "POST":
        try:
            body = json.loads(request.body)
            code = body.get("code")
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
    else:
        return JsonResponse({"error": "Only GET or POST allowed"}, status=405)

    if not code:
        return JsonResponse({"error": "Code is required"}, status=400)

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": SMARTVAULT_CLIENT_ID,
        "client_secret": SMARTVAULT_CLIENT_SECRET
    }

    response = requests.post(f"{SMARTVAULT_TOKEN_BASE_URL}/dtoken/2", json=payload)

    if response.status_code != 200:
        return JsonResponse({
            "error": "Failed to fetch tokens",
            "details": response.text
        }, status=response.status_code)

    # Parse XML response
    root = ET.fromstring(response.text)
    message = root.find("message")

    data = {
        "access_token": message.find("access_token").text,
        "refresh_token": message.find("refresh_token").text,
        "token_type": message.find("token_type").text,
        "expires_in": int(message.find("expires_in").text),
        "refresh_token_expires_in": int(message.find("refresh_token_expires_in").text),
        "id": message.find("id").text,
    }

    # Save to DB
    token, created = SmartVaultToken.objects.update_or_create(
        user_id=data["id"],
        defaults={
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "token_type": data["token_type"],
            "expires_at": timezone.now() + timedelta(seconds=data["expires_in"]),
            "refresh_expires_at": timezone.now() + timedelta(seconds=data["refresh_token_expires_in"]),
        }
    )

    return JsonResponse({
        "user_id": token.user_id,
        "access_token": token.access_token,
        "refresh_token": token.refresh_token,
        "token_type": token.token_type,
        "expires_at": token.expires_at,
        "refresh_expires_at": token.refresh_expires_at
    })


@csrf_exempt
def smartvault_refresh(request):


    token = SmartVaultToken.objects.all().first()
    payload = {
        "grant_type": "refresh_token",
        "client_secret": SMARTVAULT_CLIENT_SECRET,
        "refresh_token": token.refresh_token,
    }

    response = requests.post(f"{SMARTVAULT_TOKEN_BASE_URL}/rtoken/2", json=payload)

    if response.status_code != 200:
        return JsonResponse({
            "error": "Failed to refresh tokens",
            "details": response.text
        }, status=response.status_code)

    # Parse XML response
    root = ET.fromstring(response.text)
    message = root.find("message")

    data = {
        "access_token": message.find("access_token").text,
        "refresh_token": message.find("refresh_token").text,
        "token_type": message.find("token_type").text,
        "expires_in": int(message.find("expires_in").text),
        "refresh_token_expires_in": int(message.find("refresh_token_expires_in").text),
        "id": message.find("id").text,
    }

    # Save/Update in DB
    token, created = SmartVaultToken.objects.update_or_create(
        user_id=data["id"],
        defaults={
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "token_type": data["token_type"],
            "expires_at": timezone.now() + timedelta(seconds=data["expires_in"]),
            "refresh_expires_at": timezone.now() + timedelta(seconds=data["refresh_token_expires_in"]),
        }
    )

    return JsonResponse({
        "user_id": token.user_id,
        "access_token": token.access_token,
        "refresh_token": token.refresh_token,
        "token_type": token.token_type,
        "expires_at": token.expires_at,
        "refresh_expires_at": token.refresh_expires_at
    })




import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from .models import SmartVaultToken  # assumes you store access_token here

SMARTVAULT_BASE_URL = "https://rest.smartvault.com"


@csrf_exempt
def create_individual_client(request):
    """
    Django endpoint to create an individual SmartVault client.
    POST body: { "first_name": "", "last_name": "", "email": "", "phone": "" }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        first_name = body.get("first_name")
        last_name = body.get("last_name")
        email = body.get("email")
        phone = body.get("phone")

        if not first_name or not last_name or not email:
            return JsonResponse(
                {"error": "Missing required fields: first_name, last_name, email"},
                status=400,
            )

        # Fetch latest token
        token = SmartVaultToken.objects.first()
        if not token or not token.access_token:
            return JsonResponse({"error": "No SmartVault access token found"}, status=401)

        oauth_token = token.access_token
        headers = {
            "Authorization": f"Bearer {oauth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Get account info (to retrieve account_id)
        account_resp = requests.get(
            f"{SMARTVAULT_BASE_URL}/nodes/entity/SmartVault.Accounting.Firm",
            headers=headers,
        )
        if account_resp.status_code != 200:
            return JsonResponse(
                {"error": "Failed to fetch account info", "details": account_resp.text},
                status=500,
            )

        account_info = account_resp.json()
        if "entities" not in account_info or not account_info["entities"]:
            return JsonResponse({"error": "No account entities found"}, status=500)

        account_id = account_info["entities"][0]["id"]

        # Prepare SmartVault individual client data
        client_data = {
            "entity": {
                "meta_data": {
                    "entity_definition": "SmartVault.Accounting.Client"
                },
                "smart_vault": {
                    "accounting": {
                        "client": {
                            "type_qualifier": "individual",
                            "person": {
                                "names": [
                                    {
                                        "FirstName": first_name,
                                        "LastName": last_name,
                                    }
                                ],
                                "email_addresses": [{"address": email}],
                            },
                            "client_id": f"{first_name}_{last_name}_{int(now().timestamp())}",
                        }
                    }
                }
            }
        }

        if phone:
            client_data["entity"]["smart_vault"]["accounting"]["client"]["person"]["phone_numbers"] = [
                {"number": phone}
            ]

        # Create the client in SmartVault
        create_url = f"{SMARTVAULT_BASE_URL}/nodes/entity/SmartVault.Accounting.Firm/{account_id}/SmartVault.Accounting.FirmClient"
        create_resp = requests.put(create_url, headers=headers, json=client_data)

        if create_resp.status_code not in (200, 201):
            return JsonResponse(
                {"error": "Failed to create client", "details": create_resp.text},
                status=500,
            )

        return JsonResponse(
            {"status": "success", "smartvault_response": create_resp.json()}
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)





import json
import requests
import logging
from typing import Dict, Any
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings

logger = logging.getLogger(__name__)

class SmartVaultClientManager:
    """SmartVault Client Management API"""
    
    def __init__(self, base_url: str = "https://rest.smartvault.com"):
        self.base_url = base_url
    
    def create_person_client(self, oauth_token: str, account_id: str, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a SmartVault client as a person/individual
        """
        url = f"{self.base_url}/nodes/entity/SmartVault.Accounting.Firm/{account_id}/SmartVault.Accounting.FirmClient"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {oauth_token}"
        }
        
        # Fixed default structure for person client (matching API documentation)
        default_data = {
            "entity": {
                "meta_data": {
                    "entity_definition": "SmartVault.Accounting.Client"
                },
                "smart_vault": {
                    "accounting": {
                        "client": {
                            "type_qualifier": "Individual",
                            "persons": [  # Changed from "person" to "persons" (array)
                                {
                                    "names": [
                                        {
                                            "FirstName": "John",
                                            "MiddleName": "",
                                            "LastName": "Doe"
                                        }
                                    ],
                                    "email_addresses": [{"address": "john.doe@example.com"}],
                                    "phone_numbers": [{"Number": "+1234567890"}]  # Changed "number" to "Number"
                                }
                            ],
                            "client_salutation_override": "Mr.",
                            "end_of_fiscal_year": 12,
                            "tags": [],
                            "aliases": [],
                            "client_id": "DEFAULT_PERSON_CLIENT"
                        }
                    }
                }
            }
        }
        
        # Merge with provided data
        body = self._deep_merge(default_data, client_data)
        
        try:
            print(f"\n=== Creating SmartVault Person Client ===")
            client_info = body['entity']['smart_vault']['accounting']['client']
            person_name = client_info['persons'][0]['names'][0]  # Fixed path
            full_name = f"{person_name.get('FirstName', '')} {person_name.get('LastName', '')}"
            
            print(f"Account ID: {account_id}")
            print(f"Client ID: {client_info['client_id']}")
            print(f"Name: {full_name}")
            print(f"Request URL: {url}")
            print("Request Body:", json.dumps(body, indent=2))
            
            response = requests.put(url, headers=headers, json=body)
            
            print(f"Response Status: {response.status_code}")
            if response.status_code != 200:
                print(f"Error Response: {response.text}")
                
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            raise
        except Exception as e:
            print(f"Error creating person client: {e}")
            raise
    
    def _deep_merge(self, default: Dict[str, Any], custom: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        import copy
        result = copy.deepcopy(default)
        for key, value in custom.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result


@method_decorator(csrf_exempt, name='dispatch')
class SmartVaultWebhookView(View):
    """
    Webhook endpoint for creating SmartVault clients
    
    Expected POST payload:
    {
        "first_name": "John",
        "last_name": "Doe", 
        "email": "john.doe@example.com",
        "phone": "+1234567890",
        "client_id": "UNIQUE_CLIENT_ID"
    }
    """

    token = SmartVaultToken.objects.all().first()
    
    # Static configuration - Update these values
    OAUTH_ACCESS_TOKEN = token.access_token  # Your OAuth token
    ACCOUNT_ID = "mwdDxuks8kGhPsVdxb7U9A"  # Your SmartVault account ID
    
    def post(self, request):
        try:
            # Parse JSON payload
            try:
                payload = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid JSON payload'
                }, status=400)
            
            # Validate required fields
            required_fields = ['first_name', 'last_name']
            missing_fields = [field for field in required_fields if not payload.get(field)]
            
            if missing_fields:
                return JsonResponse({
                    'success': False,
                    'error': f'Missing required fields: {", ".join(missing_fields)}'
                }, status=400)
            
            # Extract client data from payload
            first_name = payload.get('first_name', '').strip()
            last_name = payload.get('last_name', '').strip()
            email = payload.get('email', '').strip()
            phone = payload.get('phone', '').strip()
            client_id=""
            if not client_id:
                if first_name:
                    client_id += first_name
                if last_name:
                    client_id+= last_name
                if email:
                    client_id+=str(len(email))         
            # Log the incoming request
            logger.info(f"Creating SmartVault client for: {first_name} {last_name} (ID: {client_id})")
            
            # Build client data structure - FIXED VERSION
            client_data = {
                "entity": {
                    "smart_vault": {
                        "accounting": {
                            "client": {
                                "type_qualifier": "Individual",
                                "persons": [  # Changed from "person" to "persons" (array)
                                    {
                                        "names": [
                                            {
                                                "FirstName": first_name,
                                                "MiddleName": "",
                                                "LastName": last_name
                                            }
                                        ],
                                        "email_addresses": [],  # Will be populated below
                                        "phone_numbers": []     # Will be populated below
                                    }
                                ],
                                "client_salutation_override": self._determine_salutation(first_name),
                                "end_of_fiscal_year": 12,
                                "tags": [
                                    {"value": "Individual"},
                                    {"value": "Webhook Created"}
                                ],
                                "aliases": [],
                                "client_id": client_id
                            }
                        }
                    }
                }
            }
            
            # Add email if provided
            if email:
                client_data["entity"]["smart_vault"]["accounting"]["client"]["persons"][0]["email_addresses"].append({
                    "address": email
                })
            
            # Add phone if provided - FIXED: Using "Number" instead of "number"
            if phone:
                client_data["entity"]["smart_vault"]["accounting"]["client"]["persons"][0]["phone_numbers"].append({
                    "Number": phone  # Changed from "number" to "Number"
                })
            
            # Create SmartVault client
            client_manager = SmartVaultClientManager()
            
            try:
                response = client_manager.create_person_client(
                    self.OAUTH_ACCESS_TOKEN,
                    self.ACCOUNT_ID,
                    client_data
                )
                
                logger.info(f"Successfully created SmartVault client: {client_id}")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Client created successfully',
                    'client_data': {
                        'client_id': client_id,
                        'name': f"{first_name} {last_name}",
                        'email': email or None,
                        'phone': phone or None
                    },
                    'smartvault_response': response
                })
                
            except requests.RequestException as e:
                logger.error(f"SmartVault API error for client {client_id}: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to create client in SmartVault',
                    'details': str(e)
                }, status=500)
            
        except Exception as e:
            logger.error(f"Unexpected error in webhook: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Internal server error',
                'details': str(e)
            }, status=500)
    
    def get(self, request):
        """Health check endpoint"""
        return JsonResponse({
            'status': 'SmartVault Webhook is running',
            'endpoint': '/api/smartvault/webhook/',
            'methods': ['POST'],
            'required_fields': ['first_name', 'last_name', 'client_id'],
            'optional_fields': ['email', 'phone']
        })
    
    def _determine_salutation(self, first_name: str) -> str:
        """Simple salutation determination based on common names"""
        # This is a basic implementation - you might want to use a more sophisticated approach
        common_male_names = ['john', 'james', 'robert', 'michael', 'william', 'david', 'richard', 'joseph', 'thomas', 'christopher']
        common_female_names = ['mary', 'patricia', 'jennifer', 'linda', 'elizabeth', 'barbara', 'susan', 'jessica', 'sarah', 'karen']
        
        name_lower = first_name.lower()
        
        if name_lower in common_male_names:
            return "Mr."
        elif name_lower in common_female_names:
            return "Ms."
        else:
            return "Mr."  # Default fallback
