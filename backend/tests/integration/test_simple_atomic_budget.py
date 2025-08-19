#!/usr/bin/env python3
"""
Simple test for atomic budget enforcement
"""

import asyncio
import aiohttp
import time

async def test_simple_atomic_budget():
    async with aiohttp.ClientSession() as session:
        try:
            print("🔬 Simple Atomic Budget Test")
            print("=" * 40)
            
            # Register and login
            timestamp = int(time.time())
            user_data = {
                "email": f"atomictest{timestamp}@example.com",
                "password": "TestPassword123!",
                "username": f"atomictest{timestamp}"
            }
            
            async with session.post("http://localhost:58000/api/v1/auth/register", json=user_data) as response:
                if response.status == 201:
                    print("✅ User registered")
                else:
                    error_data = await response.json()
                    print(f"❌ Registration failed: {error_data}")
                    return
            
            # Login
            login_data = {"email": user_data["email"], "password": user_data["password"]}
            async with session.post("http://localhost:58000/api/v1/auth/login", json=login_data) as response:
                if response.status == 200:
                    login_result = await response.json()
                    token = login_result['access_token']
                    headers = {'Authorization': f'Bearer {token}'}
                    print("✅ Login successful")
                else:
                    error_data = await response.json()
                    print(f"❌ Login failed: {error_data}")
                    return
            
            # Test single chat request
            print("\n💬 Testing single chat request...")
            chat_data = {
                "model": "openrouter/anthropic/claude-3.5-sonnet",
                "messages": [{"role": "user", "content": "Say hello briefly"}],
                "max_tokens": 10
            }
            
            async with session.post(
                "http://localhost:58000/api/v1/llm/chat/completions",
                json=chat_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                print(f"Response status: {response.status}")
                if response.status == 200:
                    result = await response.json()
                    message = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    print(f"✅ Chat success: {message.strip()[:50]}...")
                    
                    # Check for budget warnings
                    if "budget_warnings" in result:
                        print(f"⚠️  Budget warnings: {len(result['budget_warnings'])}")
                        for warning in result["budget_warnings"]:
                            print(f"   - {warning.get('message', 'Unknown warning')}")
                    else:
                        print("ℹ️  No budget warnings")
                        
                elif response.status == 402:
                    error_data = await response.json()
                    print(f"🛡️  Budget limit hit: {error_data.get('detail', 'Unknown')}")
                else:
                    error_data = await response.json()
                    print(f"❌ Request failed: {error_data}")
            
            print("\n🎯 Simple atomic budget test completed!")
            
        except Exception as e:
            print(f"❌ Test error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple_atomic_budget())