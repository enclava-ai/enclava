#!/usr/bin/env python3
"""
Test script to verify LLM service works without security validation
"""
import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, '/app')

from app.services.llm.service import llm_service
from app.services.llm.models import ChatRequest, ChatMessage

async def test_llm_without_security():
    """Test LLM service without security validation"""
    print("Testing LLM service without security validation...")

    try:
        # Initialize the LLM service
        await llm_service.initialize()
        print("✅ LLM service initialized successfully")

        # Create a test request with privatemode model
        request = ChatRequest(
            model="privatemode-llama-3-70b",  # Use actual privatemode model
            messages=[
                ChatMessage(role="user", content="Hello, this is a test message with SQL keywords: SELECT * FROM users;")
            ],
            temperature=0.7,
            max_tokens=100,
            user_id="test_user",
            api_key_id=1
        )

        print(f"📝 Created test request with message: {request.messages[0].content}")

        # Try to create chat completion
        # This should work now without security blocking
        response = await llm_service.create_chat_completion(request)

        print("✅ Chat completion successful!")
        print(f"   Response ID: {response.id}")
        print(f"   Model: {response.model}")
        print(f"   Provider: {response.provider}")
        print(f"   Security check: {response.security_check}")
        print(f"   Risk score: {response.risk_score}")
        print(f"   Content: {response.choices[0].message.content[:100]}...")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        # Cleanup
        await llm_service.cleanup()

if __name__ == "__main__":
    success = asyncio.run(test_llm_without_security())
    sys.exit(0 if success else 1)