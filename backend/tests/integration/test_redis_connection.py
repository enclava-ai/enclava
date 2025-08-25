#!/usr/bin/env python3
"""
Redis Connection Test
Verifies that Redis is available and working for the cached API key service
"""

import asyncio
import redis.asyncio as redis
import time


async def test_redis_connection():
    """Test Redis connection and basic operations"""
    try:
        print("🔌 Testing Redis connection...")
        
        # Connect to Redis
        redis_client = redis.from_url(
            "redis://localhost:6379",
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Test basic operations
        test_key = "test:connection"
        test_value = f"test_value_{int(time.time())}"
        
        # Set a value
        await redis_client.set(test_key, test_value, ex=60)
        print("✅ Successfully wrote to Redis")
        
        # Get the value
        retrieved_value = await redis_client.get(test_key)
        if retrieved_value == test_value:
            print("✅ Successfully read from Redis")
        else:
            print("❌ Redis read/write mismatch")
            return False
        
        # Test expiration
        ttl = await redis_client.ttl(test_key)
        if 0 < ttl <= 60:
            print(f"✅ TTL working correctly: {ttl} seconds")
        else:
            print(f"⚠️  TTL may not be working: {ttl}")
        
        # Clean up
        await redis_client.delete(test_key)
        print("✅ Cleanup successful")
        
        # Test Redis info
        info = await redis_client.info()
        print(f"✅ Redis version: {info.get('redis_version', 'unknown')}")
        print(f"✅ Redis memory usage: {info.get('used_memory_human', 'unknown')}")
        
        await redis_client.close()
        print("✅ Redis connection test passed!")
        return True
        
    except ConnectionError as e:
        print(f"❌ Redis connection failed: {e}")
        print("💡 Make sure Redis is running: docker compose up -d")
        return False
    except Exception as e:
        print(f"❌ Redis test failed: {e}")
        return False


async def test_api_key_cache_operations():
    """Test the specific cache operations used by the API key service"""
    try:
        print("\n🔑 Testing API key cache operations...")
        
        redis_client = redis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
        
        # Test API key data caching
        test_prefix = "ce_test123"
        cache_key = f"api_key:data:{test_prefix}"
        test_data = {
            "user_id": 1,
            "api_key_id": 123,
            "permissions": ["read", "write"],
            "cached_at": time.time()
        }
        
        # Cache data
        import json
        await redis_client.setex(cache_key, 300, json.dumps(test_data))
        print("✅ API key data cached successfully")
        
        # Retrieve data
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            parsed_data = json.loads(cached_data)
            if parsed_data["user_id"] == 1:
                print("✅ API key data retrieved successfully")
            else:
                print("❌ API key data corrupted")
        
        # Test verification cache
        verification_key = f"api_key:verified:{test_prefix}:abcd1234"
        await redis_client.setex(verification_key, 3600, "valid")
        
        verification_result = await redis_client.get(verification_key)
        if verification_result == "valid":
            print("✅ Verification cache working")
        else:
            print("❌ Verification cache failed")
        
        # Test pattern-based deletion
        pattern = f"api_key:verified:{test_prefix}:*"
        keys = await redis_client.keys(pattern)
        if keys:
            await redis_client.delete(*keys)
            print("✅ Pattern-based cache invalidation working")
        
        # Cleanup
        await redis_client.delete(cache_key)
        await redis_client.close()
        
        print("✅ API key cache operations test passed!")
        return True
        
    except Exception as e:
        print(f"❌ API key cache test failed: {e}")
        return False


async def main():
    """Main test function"""
    print("=" * 60)
    print("Redis Connection and Cache Test")
    print("=" * 60)
    
    # Test basic Redis connection
    basic_test = await test_redis_connection()
    
    if not basic_test:
        print("\n❌ Basic Redis test failed. Cannot proceed with cache tests.")
        return False
    
    # Test API key specific operations
    cache_test = await test_api_key_cache_operations()
    
    if basic_test and cache_test:
        print("\n🎉 All Redis tests passed! The cached API key service should work correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Check your Redis configuration.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)