#!/usr/bin/env python3
"""
Ollama Integration Test
Tests that Ollama models work properly through the LiteLLM proxy
"""

import asyncio
import aiohttp
import json
import time

# Ollama models from litellm_config.yaml
OLLAMA_MODELS = [
    "ollama-llama-3.1-nemotron",
    "ollama-mistral-nemo", 
    "ollama-gemini-2.0-flash",
    "ollama-qwen3-235b",
    "ollama-deepseek-r1",
    "ollama-mistral-small",
    "ollama-gemini-2.5-pro"
]

async def test_ollama_integration():
    async with aiohttp.ClientSession() as session:
        try:
            # Register and login a test user
            timestamp = int(time.time())
            user_data = {
                "email": f"ollamatest{timestamp}@example.com",
                "password": "TestPassword123!",
                "username": f"ollamatest{timestamp}"
            }
            
            print("🚀 Starting Ollama Integration Test")
            print("=" * 50)
            
            # Register user
            async with session.post("http://localhost:58000/api/v1/auth/register", json=user_data) as response:
                if response.status != 201:
                    error_data = await response.json()
                    print(f"❌ User registration failed: {error_data}")
                    return
                print("✅ User registered successfully")
            
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
            
            # Test 1: Check if Ollama models are listed
            print("\n📋 Testing model availability...")
            async with session.get("http://localhost:58000/api/v1/llm/models", headers=headers) as response:
                if response.status == 200:
                    models_data = await response.json()
                    available_models = [model.get('id', '') for model in models_data.get('data', [])]
                    
                    ollama_available = [model for model in OLLAMA_MODELS if model in available_models]
                    print(f"✅ Total models available: {len(available_models)}")
                    print(f"✅ Ollama models available: {len(ollama_available)}")
                    
                    if not ollama_available:
                        print("❌ No Ollama models found in model list")
                        return
                    
                    for model in ollama_available:
                        print(f"   • {model}")
                else:
                    error_data = await response.json()
                    print(f"❌ Failed to get models: {error_data}")
                    return
            
            # Test 2: Test chat completions with each available Ollama model
            print(f"\n💬 Testing chat completions...")
            successful_models = []
            failed_models = []
            
            test_messages = [
                {"role": "user", "content": "Say 'Hello from Ollama!' and nothing else."}
            ]
            
            for model in ollama_available[:3]:  # Test first 3 models to avoid timeout
                print(f"\n🤖 Testing model: {model}")
                
                chat_data = {
                    "model": model,
                    "messages": test_messages,
                    "max_tokens": 50,
                    "temperature": 0.1
                }
                
                try:
                    async with session.post(
                        "http://localhost:58000/api/v1/llm/chat/completions",
                        json=chat_data,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as chat_response:
                        if chat_response.status == 200:
                            chat_result = await chat_response.json()
                            message = chat_result.get("choices", [{}])[0].get("message", {}).get("content", "")
                            print(f"   ✅ Response: {message.strip()[:100]}...")
                            successful_models.append(model)
                        else:
                            error_data = await chat_response.json()
                            print(f"   ❌ Failed (HTTP {chat_response.status}): {error_data.get('detail', 'Unknown error')}")
                            failed_models.append(model)
                            
                except asyncio.TimeoutError:
                    print(f"   ⏰ Timeout - model may be loading or unavailable")
                    failed_models.append(model)
                except Exception as e:
                    print(f"   ❌ Error: {str(e)}")
                    failed_models.append(model)
                
                # Small delay between requests
                await asyncio.sleep(1)
            
            # Test 3: Test streaming response (if supported)
            print(f"\n🌊 Testing streaming response...")
            if successful_models:
                test_model = successful_models[0]
                stream_data = {
                    "model": test_model,
                    "messages": [{"role": "user", "content": "Count from 1 to 3, one number per line."}],
                    "max_tokens": 20,
                    "stream": True
                }
                
                try:
                    async with session.post(
                        "http://localhost:58000/api/v1/llm/chat/completions",
                        json=stream_data,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=20)
                    ) as stream_response:
                        if stream_response.status == 200:
                            content = await stream_response.text()
                            if "data:" in content:
                                print(f"   ✅ Streaming response received (partial): {content[:100]}...")
                            else:
                                print(f"   ℹ️ Non-streaming response: {content[:100]}...")
                        else:
                            error_data = await stream_response.json()
                            print(f"   ❌ Streaming failed: {error_data}")
                except Exception as e:
                    print(f"   ❌ Streaming error: {str(e)}")
            
            # Test 4: Test model with different parameters
            print(f"\n⚙️ Testing model parameters...")
            if successful_models:
                test_model = successful_models[0]
                param_tests = [
                    {"temperature": 0.0, "max_tokens": 10},
                    {"temperature": 0.8, "max_tokens": 30},
                ]
                
                for i, params in enumerate(param_tests):
                    chat_data = {
                        "model": test_model,
                        "messages": [{"role": "user", "content": f"Test {i+1}: Say hello briefly."}],
                        **params
                    }
                    
                    try:
                        async with session.post(
                            "http://localhost:58000/api/v1/llm/chat/completions",
                            json=chat_data,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=15)
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                message = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                                print(f"   ✅ Params {params}: {message.strip()[:50]}...")
                            else:
                                print(f"   ❌ Params test failed: HTTP {response.status}")
                    except Exception as e:
                        print(f"   ❌ Parameters test error: {str(e)}")
            
            # Summary
            print(f"\n📊 Test Summary")
            print("=" * 50)
            print(f"✅ Successful models: {len(successful_models)}")
            for model in successful_models:
                print(f"   • {model}")
            
            if failed_models:
                print(f"❌ Failed models: {len(failed_models)}")
                for model in failed_models:
                    print(f"   • {model}")
            
            print(f"\n{'🎉 Ollama integration working!' if successful_models else '⚠️ Ollama integration has issues'}")
            
        except Exception as e:
            print(f"❌ Test error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ollama_integration())