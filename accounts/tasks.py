
import requests
from celery import shared_task
from accounts.models import GHLAuthCredentials,SmartVaultToken
from decouple import config
from accounts.services import fetch_all_contacts, sync_opportunities

import xml.etree.ElementTree as ET
from django.utils import timezone
from datetime import timedelta


SMARTVAULT_BASE_URL = "https://rest.smartvault.com/auto/auth"

@shared_task
def make_api_call():
    credentials = GHLAuthCredentials.objects.first()
    
    print("credentials tokenL", credentials)
    refresh_token = credentials.refresh_token

    
    response = requests.post('https://services.leadconnectorhq.com/oauth/token', data={
        'grant_type': 'refresh_token',
        'client_id': config("GHL_CLIENT_ID"),
        'client_secret': config("GHL_CLIENT_SECRET"),
        'refresh_token': refresh_token
    })
    
    new_tokens = response.json()

    print("new tokens: ", new_tokens)

    obj, created = GHLAuthCredentials.objects.update_or_create(
            location_id= new_tokens.get("locationId"),
            defaults={
                "access_token": new_tokens.get("access_token"),
                "refresh_token": new_tokens.get("refresh_token"),
                "expires_in": new_tokens.get("expires_in"),
                "scope": new_tokens.get("scope"),
                "user_type": new_tokens.get("userType"),
                "company_id": new_tokens.get("companyId"),
                "user_id":new_tokens.get("userId"),

            }
        )
    

@shared_task
def contact_and_opportunity_sync_task():
    fetch_all_contacts()
    sync_opportunities()


@shared_task
def refresh_smartvault_token():
    """
    Background task to refresh SmartVault tokens and save to DB.
    """
    token = SmartVaultToken.objects.first()
    if not token:
        return {"error": "No SmartVault token found in DB."}

    payload = {
        "grant_type": "refresh_token",
        "client_secret": config("SMARTVAULT_CLIENT_SECRET"),
        "refresh_token": token.refresh_token,
    }

    response = requests.post(f"{SMARTVAULT_BASE_URL}/rtoken/2", json=payload)

    if response.status_code != 200:
        return {
            "error": "Failed to refresh tokens",
            "details": response.text
        }

    # Parse XML response
    root = ET.fromstring(response.text)
    message = root.find("message")

    if message is None:
        return {"error": "Invalid SmartVault response", "details": response.text}

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

    return {
        "user_id": token.user_id,
        "access_token": token.access_token,
        "refresh_token": token.refresh_token,
        "token_type": token.token_type,
        "expires_at": str(token.expires_at),
        "refresh_expires_at": str(token.refresh_expires_at),
    }
