#!/usr/bin/env python3
"""
Test script to verify debugging endpoints
"""
import requests
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.security import create_access_token
from backend.app.db.database import SessionLocal
from backend.app.models.user import User

def get_auth_token():
    """Get an authentication token for testing"""
    db = SessionLocal()
    try:
        # Get first user (or create one for testing)
        user = db.query(User).first()
        if not user:
            # Create test user if none exists
            user = User(
                email="test@example.com",
                hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeZeUfkZMBs9kYZP6"  # password: password
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Create JWT token
        token = create_access_token(data={"sub": str(user.id)})
        return token
    finally:
        db.close()

def test_endpoint(url, token, method="GET", data=None):
    """Test an endpoint with authentication"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    if method == "GET":
        response = requests.get(f"http://localhost:3000{url}", headers=headers)
    elif method == "POST":
        response = requests.post(f"http://localhost:3000{url}", headers=headers, json=data)

    print(f"\n{method} {url}")
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        print("Response:")
        print(json.dumps(response.json(), indent=2))
    else:
        print("Error:", response.text)

    return response

def main():
    print("=== Testing Debugging Endpoints ===")

    # Get authentication token
    print("\n1. Getting authentication token...")
    token = get_auth_token()
    print(f"Token: {token[:50]}...")

    # Test system status
    print("\n2. Testing system status...")
    test_endpoint("/api-internal/v1/debugging/system/status", token)

    # Test getting chatbot list first
    print("\n3. Getting chatbot list...")
    response = test_endpoint("/api-internal/v1/chatbot/list", token)

    if response.status_code == 200:
        chatbots = response.json()
        if chatbots:
            chatbot_id = chatbots[0]["id"]
            print(f"\n4. Testing chatbot config for: {chatbot_id}")
            test_endpoint(f"/api-internal/v1/debugging/chatbot/{chatbot_id}/config", token)

            print(f"\n5. Testing RAG search for: {chatbot_id}")
            test_endpoint(f"/api-internal/v1/debugging/chatbot/{chatbot_id}/test-rag?query=What is security?", token)
        else:
            print("\n4. No chatbots found to test")
    else:
        print("\n4. Could not get chatbot list")

if __name__ == "__main__":
    main()