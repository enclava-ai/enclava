#!/usr/bin/env python3
"""
Quick performance comparison test
"""

import time
import requests
import json

# Configuration
API_KEY = "en_mMJNyEznKHJRvvNyyuwuQotuWJ2BvdD8"
LITELLM_KEY = "enclava-master-key"
TEST_PROMPT = "What is 2+2? Answer briefly."
MODEL = "ollama-deepseek-r1"

def test_platform_api():
    """Test platform API"""
    print("🔄 Testing Platform API...")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "max_tokens": 30
    }
    
    start_time = time.time()
    response = requests.post("http://localhost:58000/api/v1/llm/chat/completions", 
                           headers=headers, json=payload, timeout=30)
    end_time = time.time()
    
    response_time = end_time - start_time
    
    if response.status_code == 200:
        data = response.json()
        tokens = data.get('usage', {}).get('total_tokens', 0)
        content = data.get('choices', [{}])[0].get('message', {}).get('content', 'No response')
        print(f"✅ Platform API: {response_time:.3f}s ({tokens} tokens)")
        print(f"   Response: {content[:100]}...")
        return response_time, tokens
    else:
        print(f"❌ Platform API failed: {response.status_code} - {response.text}")
        return None, None

def test_litellm_direct():
    """Test LiteLLM direct"""
    print("🔄 Testing LiteLLM Direct...")
    
    headers = {
        "Content-Type": "application/json", 
        "Authorization": f"Bearer {LITELLM_KEY}"
    }
    
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "max_tokens": 30
    }
    
    start_time = time.time()
    response = requests.post("http://localhost:54000/chat/completions",
                           headers=headers, json=payload, timeout=30)
    end_time = time.time()
    
    response_time = end_time - start_time
    
    if response.status_code == 200:
        data = response.json()
        tokens = data.get('usage', {}).get('total_tokens', 0)
        content = data.get('choices', [{}])[0].get('message', {}).get('content', 'No response')
        print(f"✅ LiteLLM Direct: {response_time:.3f}s ({tokens} tokens)")
        print(f"   Response: {content[:100]}...")
        return response_time, tokens
    else:
        print(f"❌ LiteLLM Direct failed: {response.status_code} - {response.text}")
        return None, None

def main():
    print("=" * 60)
    print("QUICK PERFORMANCE COMPARISON")
    print("=" * 60)
    print(f"Prompt: {TEST_PROMPT}")
    print(f"Model: {MODEL}")
    print()
    
    # Test platform API
    platform_time, platform_tokens = test_platform_api()
    print()
    
    # Test LiteLLM direct
    litellm_time, litellm_tokens = test_litellm_direct()
    print()
    
    # Compare results
    if platform_time and litellm_time:
        overhead = platform_time - litellm_time
        overhead_percent = (overhead / litellm_time) * 100
        
        print("=" * 60)
        print("COMPARISON RESULTS")
        print("=" * 60)
        print(f"Platform API:     {platform_time:.3f}s")
        print(f"LiteLLM Direct:   {litellm_time:.3f}s")
        print(f"Platform Overhead: {overhead:.3f}s ({overhead_percent:+.1f}%)")
        print()
        
        if overhead_percent < 10:
            print("🚀 EXCELLENT: Platform adds minimal overhead!")
        elif overhead_percent < 25:
            print("⚡ GOOD: Platform adds reasonable overhead")
        elif overhead_percent < 50:
            print("⚠️  MODERATE: Platform adds noticeable overhead")
        else:
            print("🐌 HIGH: Platform adds significant overhead")
        
        print()
        print("Platform overhead includes:")
        print("  • API key authentication & validation")
        print("  • Budget enforcement & usage tracking") 
        print("  • Request logging & analytics")
        print("  • Rate limiting checks")
        print("  • Database operations")
    
    print("=" * 60)

if __name__ == "__main__":
    main()