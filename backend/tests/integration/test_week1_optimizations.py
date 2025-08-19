#!/usr/bin/env python3
"""
Performance test specifically for Week 1 optimizations:
1. Database connection pooling
2. Models endpoint caching  
3. Async audit logging

This test measures the impact of these optimizations on API response times.
"""

import asyncio
import aiohttp
import time
import json
import statistics
from typing import List, Dict, Any

# Test configuration
PLATFORM_BASE_URL = "http://localhost:58000"
LITELLM_BASE_URL = "http://localhost:54000"
TEST_ITERATIONS = 10

class PerformanceTest:
    def __init__(self):
        self.results = {}
        
    async def time_request(self, session: aiohttp.ClientSession, method: str, url: str, 
                          headers: Dict = None, json_data: Dict = None) -> float:
        """Time a single HTTP request"""
        start_time = time.perf_counter()
        try:
            async with session.request(method, url, headers=headers, json=json_data) as response:
                await response.read()  # Ensure we read the full response
                end_time = time.perf_counter()
                return (end_time - start_time) * 1000  # Return milliseconds
        except Exception as e:
            print(f"Request failed: {e}")
            return -1
    
    async def test_models_endpoint_caching(self):
        """Test the models endpoint caching optimization"""
        print("Testing models endpoint caching...")
        
        async with aiohttp.ClientSession() as session:
            # Test platform models endpoint (should benefit from caching)
            platform_times = []
            litellm_times = []
            
            # Test LiteLLM direct access first (baseline)
            for i in range(TEST_ITERATIONS):
                try:
                    duration = await self.time_request(
                        session, "GET", f"{LITELLM_BASE_URL}/v1/models"
                    )
                    if duration > 0:
                        litellm_times.append(duration)
                        print(f"LiteLLM models #{i+1}: {duration:.2f}ms")
                except Exception as e:
                    print(f"LiteLLM test #{i+1} failed: {e}")
                    
                await asyncio.sleep(0.1)  # Small delay between requests
            
            # Test platform models endpoint (with caching)
            for i in range(TEST_ITERATIONS):
                try:
                    duration = await self.time_request(
                        session, "GET", f"{PLATFORM_BASE_URL}/api/v1/llm/models",
                        headers={"Authorization": "Bearer dummy_jwt_token"}  # Will fail auth but should still test routing
                    )
                    if duration > 0:
                        platform_times.append(duration)
                        print(f"Platform models #{i+1}: {duration:.2f}ms")
                except Exception as e:
                    print(f"Platform test #{i+1} failed: {e}")
                    
                await asyncio.sleep(0.1)
        
        return {
            "litellm_avg": statistics.mean(litellm_times) if litellm_times else 0,
            "litellm_min": min(litellm_times) if litellm_times else 0,
            "litellm_max": max(litellm_times) if litellm_times else 0,
            "platform_avg": statistics.mean(platform_times) if platform_times else 0,
            "platform_min": min(platform_times) if platform_times else 0,
            "platform_max": max(platform_times) if platform_times else 0,
            "overhead_ms": (statistics.mean(platform_times) - statistics.mean(litellm_times)) if platform_times and litellm_times else 0,
            "iterations": len(platform_times)
        }
    
    async def test_health_endpoints(self):
        """Test basic health endpoints to measure database connection performance"""
        print("Testing health endpoints...")
        
        async with aiohttp.ClientSession() as session:
            platform_health_times = []
            
            # Test platform health endpoint (uses database connection)
            for i in range(TEST_ITERATIONS):
                try:
                    duration = await self.time_request(
                        session, "GET", f"{PLATFORM_BASE_URL}/health"
                    )
                    if duration > 0:
                        platform_health_times.append(duration)
                        print(f"Platform health #{i+1}: {duration:.2f}ms")
                except Exception as e:
                    print(f"Health test #{i+1} failed: {e}")
                    
                await asyncio.sleep(0.1)
        
        return {
            "platform_health_avg": statistics.mean(platform_health_times) if platform_health_times else 0,
            "platform_health_min": min(platform_health_times) if platform_health_times else 0,
            "platform_health_max": max(platform_health_times) if platform_health_times else 0,
            "iterations": len(platform_health_times)
        }
    
    async def test_concurrent_requests(self):
        """Test concurrent request handling (benefits from connection pooling)"""
        print("Testing concurrent request handling...")
        
        async def make_concurrent_requests(session, num_concurrent=5):
            tasks = []
            for i in range(num_concurrent):
                task = self.time_request(session, "GET", f"{PLATFORM_BASE_URL}/health")
                tasks.append(task)
            
            start_time = time.perf_counter()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.perf_counter()
            
            successful_results = [r for r in results if isinstance(r, (int, float)) and r > 0]
            total_time = (end_time - start_time) * 1000
            
            return {
                "total_time_ms": total_time,
                "successful_requests": len(successful_results),
                "average_individual_time": statistics.mean(successful_results) if successful_results else 0
            }
        
        async with aiohttp.ClientSession() as session:
            # Test sequential requests
            sequential_start = time.perf_counter()
            sequential_times = []
            for i in range(5):
                duration = await self.time_request(session, "GET", f"{PLATFORM_BASE_URL}/health")
                if duration > 0:
                    sequential_times.append(duration)
            sequential_end = time.perf_counter()
            sequential_total = (sequential_end - sequential_start) * 1000
            
            # Test concurrent requests
            concurrent_result = await make_concurrent_requests(session, 5)
            
            return {
                "sequential_total_ms": sequential_total,
                "sequential_avg_individual": statistics.mean(sequential_times) if sequential_times else 0,
                "concurrent_total_ms": concurrent_result["total_time_ms"],
                "concurrent_avg_individual": concurrent_result["average_individual_time"],
                "concurrency_improvement_pct": ((sequential_total - concurrent_result["total_time_ms"]) / sequential_total * 100) if sequential_total > 0 else 0
            }
    
    async def run_all_tests(self):
        """Run all performance tests"""
        print("=" * 60)
        print("Week 1 Optimization Performance Test")
        print("=" * 60)
        
        # Test 1: Models endpoint caching
        models_results = await self.test_models_endpoint_caching()
        self.results["models_caching"] = models_results
        
        print(f"\nModels Endpoint Results:")
        print(f"  LiteLLM Direct: {models_results['litellm_avg']:.2f}ms avg ({models_results['litellm_min']:.2f}-{models_results['litellm_max']:.2f}ms)")
        print(f"  Platform API: {models_results['platform_avg']:.2f}ms avg ({models_results['platform_min']:.2f}-{models_results['platform_max']:.2f}ms)")
        print(f"  Overhead: {models_results['overhead_ms']:.2f}ms")
        
        # Test 2: Health endpoints (database connection pooling)
        health_results = await self.test_health_endpoints()
        self.results["health_endpoints"] = health_results
        
        print(f"\nHealth Endpoint Results:")
        print(f"  Platform Health: {health_results['platform_health_avg']:.2f}ms avg ({health_results['platform_health_min']:.2f}-{health_results['platform_health_max']:.2f}ms)")
        
        # Test 3: Concurrent requests (connection pooling benefit)
        concurrent_results = await self.test_concurrent_requests()
        self.results["concurrent_requests"] = concurrent_results
        
        print(f"\nConcurrent Request Results:")
        print(f"  Sequential (5 requests): {concurrent_results['sequential_total_ms']:.2f}ms total")
        print(f"  Concurrent (5 requests): {concurrent_results['concurrent_total_ms']:.2f}ms total")
        print(f"  Concurrency improvement: {concurrent_results['concurrency_improvement_pct']:.1f}%")
        
        # Save results
        timestamp = int(time.time())
        results_file = f"week1_optimization_results_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\nResults saved to: {results_file}")
        print("=" * 60)
        
        return self.results

async def main():
    test = PerformanceTest()
    results = await test.run_all_tests()
    
    # Summary
    print("\nSUMMARY:")
    print("=" * 60)
    
    models_overhead = results["models_caching"]["overhead_ms"]
    health_avg = results["health_endpoints"]["platform_health_avg"]
    concurrent_improvement = results["concurrent_requests"]["concurrency_improvement_pct"]
    
    print(f"Models endpoint overhead: {models_overhead:.2f}ms")
    print(f"Health endpoint average: {health_avg:.2f}ms")
    print(f"Concurrency improvement: {concurrent_improvement:.1f}%")
    
    if models_overhead < 200:
        print("✅ Models endpoint overhead is reasonable")
    else:
        print("⚠️  Models endpoint overhead is high - may need further optimization")
    
    if health_avg < 50:
        print("✅ Health endpoint response is fast")
    else:
        print("⚠️  Health endpoint response could be faster")
    
    if concurrent_improvement > 30:
        print("✅ Good concurrency improvement from connection pooling")
    else:
        print("⚠️  Concurrency improvement is modest")

if __name__ == "__main__":
    asyncio.run(main())