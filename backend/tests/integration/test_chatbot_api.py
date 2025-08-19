#!/usr/bin/env python3
"""
Test script to demonstrate chatbot API functionality

This script shows how to:
1. Create a chatbot-specific API key
2. Use the external chatbot API
3. Manage conversations
"""

import requests
import json

BASE_URL = "http://localhost:58000"
FRONTEND_URL = "http://localhost:53000"

def test_chatbot_api():
    print("🤖 Chatbot API Test")
    print("=" * 50)
    
    # For testing, you would need to:
    # 1. First create a chatbot through the UI
    # 2. Generate an API key for that chatbot  
    # 3. Use the API key to access the external endpoint
    
    print("\n📝 Steps to test:")
    print("1. Open the frontend at:", FRONTEND_URL)
    print("2. Create a new chatbot")
    print("3. Click the 🔑 (key) button on the chatbot card")
    print("4. Create a new API key")
    print("5. Copy the API key and use it below")
    
    # Example API key (you'll need to replace this with a real one)
    api_key = input("\nEnter your chatbot API key: ").strip()
    if not api_key:
        print("❌ No API key provided. Exiting.")
        return
    
    chatbot_id = input("Enter your chatbot ID: ").strip()
    if not chatbot_id:
        print("❌ No chatbot ID provided. Exiting.")
        return
    
    print(f"\n🔗 Testing external API endpoint: /api/v1/chatbot/external/{chatbot_id}/chat")
    
    # Test API call
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "message": "Hello! Can you help me test the API?",
        "conversation_id": None
    }
    
    try:
        print("\n📤 Sending request...")
        response = requests.post(
            f"{BASE_URL}/api/v1/chatbot/external/{chatbot_id}/chat",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"📡 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ Success! Response:")
            print(f"   Conversation ID: {data.get('conversation_id')}")
            print(f"   Response: {data.get('response')}")
            print(f"   Timestamp: {data.get('timestamp')}")
            if data.get('sources'):
                print(f"   Sources: {len(data['sources'])} found")
                
            # Test follow-up message
            print("\n🔄 Testing follow-up message...")
            payload2 = {
                "message": "Thank you! Can you remember what I just asked?",
                "conversation_id": data.get('conversation_id')
            }
            
            response2 = requests.post(
                f"{BASE_URL}/api/v1/chatbot/external/{chatbot_id}/chat",
                headers=headers,
                json=payload2,
                timeout=30
            )
            
            if response2.status_code == 200:
                data2 = response2.json()
                print("\n✅ Follow-up Success!")
                print(f"   Response: {data2.get('response')}")
            else:
                print(f"❌ Follow-up failed: {response2.status_code}")
                print(response2.text)
                
        else:
            print(f"❌ Request failed: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
    
    print("\n🎯 API Features:")
    print("✓ Chatbot-specific API keys")
    print("✓ Rate limiting (100 req/min by default)")
    print("✓ Conversation persistence")
    print("✓ Same authentication as main LLM API")
    print("✓ Restricted access to specific chatbot only")
    print("✓ Usage tracking and analytics")
    
    print(f"\n📚 Integration Example:")
    print(f"# ⚠️  IMPORTANT: Use port 58000 (backend) NOT 53000 (frontend)")
    print(f"curl -X POST '{BASE_URL}/api/v1/chatbot/external/{chatbot_id}/chat' \\")
    print(f"  -H 'Authorization: Bearer {api_key[:8]}...' \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"message\": \"Hello!\", \"conversation_id\": null}'")

if __name__ == "__main__":
    test_chatbot_api()