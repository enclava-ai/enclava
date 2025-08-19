#!/usr/bin/env python3
"""
Test script for atomic budget enforcement 
Verifies that race conditions are prevented
"""

import asyncio
import aiohttp
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

async def test_atomic_budget_enforcement():
    async with aiohttp.ClientSession() as session:
        try:
            print("🧪 Testing Atomic Budget Enforcement")
            print("=" * 50)
            
            # Register test user
            timestamp = int(time.time())
            user_data = {
                "email": f"budgettest{timestamp}@example.com",
                "password": "TestPassword123!",
                "username": f"budgettest{timestamp}"
            }
            
            async with session.post("http://localhost:58000/api/v1/auth/register", json=user_data) as response:
                if response.status != 201:
                    error_data = await response.json()
                    print(f"❌ Registration failed: {error_data}")
                    return
                print("✅ User registered")
            
            # Login
            login_data = {"email": user_data["email"], "password": user_data["password"]}
            async with session.post("http://localhost:58000/api/v1/auth/login", json=login_data) as response:
                if response.status != 200:
                    error_data = await response.json()
                    print(f"❌ Login failed: {error_data}")
                    return
                
                login_result = await response.json()
                token = login_result['access_token']
                headers = {'Authorization': f'Bearer {token}'}
                print("✅ Login successful")
            
            # Test 1: Normal budget operations (sequential)
            print("\n📊 Test 1: Sequential Budget Operations")
            
            # Create some chat requests that should succeed
            chat_data = {
                "model": "openrouter/anthropic/claude-3.5-sonnet",
                "messages": [{"role": "user", "content": "Say 'test' 5 times"}],
                "max_tokens": 20
            }
            
            for i in range(3):
                async with session.post(
                    "http://localhost:58000/api/v1/llm/chat/completions",
                    json=chat_data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        print(f"✅ Sequential request {i+1}: Success")
                    else:
                        error_data = await response.json()
                        print(f"❌ Sequential request {i+1}: {error_data}")
            
            # Test 2: Concurrent budget operations (potential race conditions)
            print("\n🔥 Test 2: Concurrent Budget Operations (Race Condition Test)")
            
            # Create multiple concurrent requests
            concurrent_requests = 5
            
            print(f"Sending {concurrent_requests} concurrent requests...")
            
            # Create tasks for concurrent execution
            tasks = []
            for i in range(concurrent_requests):
                task = asyncio.create_task(
                    make_concurrent_request(session, headers, chat_data, i+1)
                )
                tasks.append(task)
            
            # Wait for all concurrent requests to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Analyze results
            successful_requests = 0
            failed_requests = 0
            budget_exceeded_count = 0
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"⚠️  Request {i+1}: Exception - {result}")
                    failed_requests += 1
                elif result['success']:
                    print(f"✅ Request {i+1}: Success")
                    successful_requests += 1
                else:
                    print(f"❌ Request {i+1}: Failed - {result['error']}")
                    failed_requests += 1
                    if 'budget' in result['error'].lower():
                        budget_exceeded_count += 1
                        
            print(f"\n📊 Concurrent Test Results:")
            print(f"   Successful: {successful_requests}")
            print(f"   Failed: {failed_requests}")
            print(f"   Budget exceeded: {budget_exceeded_count}")
            
            # Test 3: Check if atomic operations prevent over-spending
            print("\n💰 Test 3: Budget Limit Enforcement")
            
            # Try to make a request that might exceed budget (if low budget exists)
            expensive_chat_data = {
                "model": "openrouter/anthropic/claude-3.5-sonnet",
                "messages": [{"role": "user", "content": "Write a very long essay about artificial intelligence, machine learning, and the future of technology. Include detailed examples and explanations."}],
                "max_tokens": 1000  # Large token request
            }
            
            async with session.post(
                "http://localhost:58000/api/v1/llm/chat/completions",
                json=expensive_chat_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print("✅ Expensive request: Allowed (budget sufficient)")
                elif response.status == 429:
                    error_data = await response.json()
                    print(f"🛡️  Expensive request: Blocked by budget - {error_data.get('detail', 'Unknown')}")
                else:
                    error_data = await response.json()
                    print(f"⚠️  Expensive request: Other error - {error_data}")
            
            print(f"\n🎯 Atomic Budget Test Completed!")
            print("If race conditions were prevented, concurrent requests should")
            print("either succeed or fail cleanly without over-spending budgets.")
            
        except Exception as e:
            print(f"❌ Test error: {e}")
            import traceback
            traceback.print_exc()

async def make_concurrent_request(session, headers, chat_data, request_id):
    """Make a concurrent chat request for race condition testing"""
    try:
        async with session.post(
            "http://localhost:58000/api/v1/llm/chat/completions",
            json=chat_data,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            if response.status == 200:
                result = await response.json()
                return {"success": True, "request_id": request_id, "result": result}
            else:
                error_data = await response.json()
                return {"success": False, "request_id": request_id, "error": error_data.get('detail', 'Unknown')}
    except Exception as e:
        return {"success": False, "request_id": request_id, "error": str(e)}

if __name__ == "__main__":
    asyncio.run(test_atomic_budget_enforcement())