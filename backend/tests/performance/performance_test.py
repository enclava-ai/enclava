#!/usr/bin/env python3
"""
Performance comparison test between Platform API and Direct LiteLLM
"""

import time
import json
import requests
import statistics
from datetime import datetime
from typing import Dict, List, Tuple

# Test configuration
PLATFORM_URL = "http://localhost:58000/api/v1/llm/chat/completions"
LITELLM_URL = "http://localhost:54000/chat/completions"
API_KEY = "ce_mMJNyEznKHJRvvNyyuwuQotuWJ2BvdD8"
LITELLM_KEY = "shifra-master-key"  # From docker-compose.yml

TEST_PROMPT = "What is the capital of France? Give a brief answer."
MODEL = "ollama-deepseek-r1"
MAX_TOKENS = 50
NUM_RUNS = 5

def make_platform_request() -> Tuple[float, Dict]:
    """Make request through platform API"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": TEST_PROMPT}
        ],
        "max_tokens": MAX_TOKENS
    }
    
    start_time = time.time()
    response = requests.post(PLATFORM_URL, headers=headers, json=payload)
    end_time = time.time()
    
    response_time = end_time - start_time
    
    if response.status_code == 200:
        return response_time, response.json()
    else:
        raise Exception(f"Platform API failed: {response.status_code} - {response.text}")

def make_litellm_request() -> Tuple[float, Dict]:
    """Make request directly to LiteLLM"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LITELLM_KEY}"
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": TEST_PROMPT}
        ],
        "max_tokens": MAX_TOKENS
    }
    
    start_time = time.time()
    response = requests.post(LITELLM_URL, headers=headers, json=payload)
    end_time = time.time()
    
    response_time = end_time - start_time
    
    if response.status_code == 200:
        return response_time, response.json()
    else:
        raise Exception(f"LiteLLM API failed: {response.status_code} - {response.text}")

def run_performance_test():
    """Run comprehensive performance test"""
    print("=" * 80)
    print("PERFORMANCE COMPARISON TEST")
    print("=" * 80)
    print(f"Test prompt: {TEST_PROMPT}")
    print(f"Model: {MODEL}")
    print(f"Max tokens: {MAX_TOKENS}")
    print(f"Number of runs: {NUM_RUNS}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    platform_times = []
    litellm_times = []
    platform_tokens = []
    litellm_tokens = []
    
    # Test Platform API
    print("Testing Platform API...")
    for i in range(NUM_RUNS):
        try:
            response_time, response_data = make_platform_request()
            platform_times.append(response_time)
            
            usage = response_data.get('usage', {})
            total_tokens = usage.get('total_tokens', 0)
            platform_tokens.append(total_tokens)
            
            print(f"  Run {i+1}: {response_time:.3f}s ({total_tokens} tokens)")
            time.sleep(1)  # Small delay between requests
        except Exception as e:
            print(f"  Run {i+1}: FAILED - {e}")
    
    print()
    
    # Test LiteLLM Direct
    print("Testing LiteLLM Direct...")
    for i in range(NUM_RUNS):
        try:
            response_time, response_data = make_litellm_request()
            litellm_times.append(response_time)
            
            usage = response_data.get('usage', {})
            total_tokens = usage.get('total_tokens', 0)
            litellm_tokens.append(total_tokens)
            
            print(f"  Run {i+1}: {response_time:.3f}s ({total_tokens} tokens)")
            time.sleep(1)  # Small delay between requests
        except Exception as e:
            print(f"  Run {i+1}: FAILED - {e}")
    
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    if platform_times and litellm_times:
        # Calculate statistics
        platform_avg = statistics.mean(platform_times)
        platform_min = min(platform_times)
        platform_max = max(platform_times)
        platform_median = statistics.median(platform_times)
        
        litellm_avg = statistics.mean(litellm_times)
        litellm_min = min(litellm_times)
        litellm_max = max(litellm_times)
        litellm_median = statistics.median(litellm_times)
        
        overhead_avg = platform_avg - litellm_avg
        overhead_percent = (overhead_avg / litellm_avg) * 100 if litellm_avg > 0 else 0
        
        print(f"Platform API (with authentication, budget enforcement, etc.):")
        print(f"  Average: {platform_avg:.3f}s")
        print(f"  Median:  {platform_median:.3f}s")
        print(f"  Min:     {platform_min:.3f}s")
        print(f"  Max:     {platform_max:.3f}s")
        print()
        
        print(f"LiteLLM Direct (bypassing platform):")
        print(f"  Average: {litellm_avg:.3f}s")
        print(f"  Median:  {litellm_median:.3f}s")
        print(f"  Min:     {litellm_min:.3f}s")
        print(f"  Max:     {litellm_max:.3f}s")
        print()
        
        print(f"Platform Overhead:")
        print(f"  Average overhead: {overhead_avg:.3f}s ({overhead_percent:+.1f}%)")
        print(f"  Median overhead:  {platform_median - litellm_median:.3f}s")
        print()
        
        # Token comparison
        if platform_tokens and litellm_tokens:
            platform_tokens_avg = statistics.mean(platform_tokens)
            litellm_tokens_avg = statistics.mean(litellm_tokens)
            
            print(f"Token Usage:")
            print(f"  Platform API avg: {platform_tokens_avg:.1f} tokens")
            print(f"  LiteLLM Direct avg: {litellm_tokens_avg:.1f} tokens")
            print()
        
        # Performance analysis
        print("Analysis:")
        if overhead_percent < 5:
            print("  ✅ Excellent: Platform adds minimal overhead (<5%)")
        elif overhead_percent < 15:
            print("  ⚡ Good: Platform adds reasonable overhead (<15%)")
        elif overhead_percent < 30:
            print("  ⚠️  Moderate: Platform adds noticeable overhead (<30%)")
        else:
            print("  🐌 High: Platform adds significant overhead (>30%)")
        
        print(f"  Platform overhead includes:")
        print(f"    - API key authentication and validation")
        print(f"    - Budget enforcement and usage tracking")
        print(f"    - Request logging and analytics")
        print(f"    - Rate limiting checks")
        print(f"    - Additional database operations")
        
    else:
        print("❌ Test failed - insufficient data collected")
    
    print("=" * 80)

if __name__ == "__main__":
    run_performance_test()