from django.test import TestCase

# Create your tests here.
import requests
import json

def test_webhook():
    """Test the webhook endpoint"""
    
    webhook_url = "http://localhost:8000/accounts/smartvault/webhook/"
    
    # Test data
    test_payload = {
        "first_name": "TestTestSarahtest",
        "last_name": "TesttestJohnsontest", 
        "email": "testsarahtest.johnson@example.com",
        "phone": "+1555987630",
        "client_id": "SARAH_JOHNSON_2025_WEBHOOK_TEST_TEST1"
    }
    
    try:
        # Test POST request
        print("Testing webhook endpoint...")
        response = requests.post(
            webhook_url,
            json=test_payload,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # Test GET request (health check)
        print("\nTesting health check...")
        health_response = requests.get(webhook_url)
        print(f"Health Check: {json.dumps(health_response.json(), indent=2)}")
        
    except Exception as e:
        print(f"Error testing webhook: {e}")

if __name__ == "__main__":
    test_webhook()