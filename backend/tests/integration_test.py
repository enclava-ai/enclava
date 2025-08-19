"""
Integration test for the live module system
Tests all modules through the running API endpoints
"""

import asyncio
import json
import time
import httpx
from typing import Dict, Any

class LiveModuleIntegrationTest:
    """Test the live module system through API endpoints"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def test_all_modules_loaded(self):
        """Test that all 7 modules are loaded and operational"""
        print("🧪 Testing module loading...")
        
        response = await self.client.get(f"{self.base_url}/api/v1/modules/")
        assert response.status_code == 200
        
        data = response.json()
        print(f"✓ API Response: {response.status_code}")
        print(f"✓ Total modules: {data['total']}")
        
        # Verify we have all 7 modules
        assert data["total"] >= 7, f"Expected at least 7 modules, got {data['total']}"
        assert data["module_count"] >= 7
        assert data["initialized"] is True
        
        expected_modules = ['cache', 'analytics', 'rag', 'content', 'security', 'monitoring', 'config']
        loaded_modules = [mod["name"] for mod in data["modules"]]
        
        for expected in expected_modules:
            assert expected in loaded_modules, f"Module {expected} not found in {loaded_modules}"
            print(f"✓ Module '{expected}' is loaded")
        
        return data
    
    async def test_module_stats_availability(self, modules_data: Dict[str, Any]):
        """Test that all modules provide stats"""
        print("\n🧪 Testing module statistics...")
        
        stats_modules = []
        for module in modules_data["modules"]:
            module_name = module["name"]
            if "stats" in module:
                stats_modules.append(module_name)
                print(f"✓ Module '{module_name}' provides stats: {len(module['stats'])} metrics")
            else:
                print(f"⚠ Module '{module_name}' no stats available")
        
        # At least some modules should provide stats
        assert len(stats_modules) >= 3, f"Expected at least 3 modules with stats, got {len(stats_modules)}"
        return stats_modules
    
    async def test_specific_module_functionality(self, modules_data: Dict[str, Any]):
        """Test specific module functionality"""
        print("\n🧪 Testing specific module functionality...")
        
        modules_by_name = {mod["name"]: mod for mod in modules_data["modules"]}
        
        # Test Cache Module
        if "cache" in modules_by_name:
            cache_stats = modules_by_name["cache"].get("stats", {})
            expected_cache_fields = ["hits", "misses", "errors", "total_requests"]
            for field in expected_cache_fields:
                assert field in cache_stats, f"Cache module missing {field} stat"
            print("✓ Cache module stats structure verified")
        
        # Test Monitoring Module 
        if "monitoring" in modules_by_name:
            monitor_stats = modules_by_name["monitoring"].get("stats", {})
            expected_monitor_fields = ["current_cpu", "current_memory", "uptime"]
            for field in expected_monitor_fields:
                assert field in monitor_stats, f"Monitoring module missing {field} stat"
            print("✓ Monitoring module stats structure verified")
            print(f"  CPU: {monitor_stats.get('current_cpu', 'N/A')}%")
            print(f"  Memory: {monitor_stats.get('current_memory', 'N/A')}%")
            print(f"  Uptime: {monitor_stats.get('uptime', 'N/A')}s")
        
        # Test Security Module
        if "security" in modules_by_name:
            security_mod = modules_by_name["security"]
            assert security_mod.get("initialized", False), "Security module should be initialized"
            print("✓ Security module is initialized")
        
        # Test Config Module
        if "config" in modules_by_name:
            config_stats = modules_by_name["config"].get("stats", {})
            expected_config_fields = ["total_configs", "active_watchers", "config_versions"]
            for field in expected_config_fields:
                assert field in config_stats, f"Config module missing {field} stat"
            print("✓ Config module stats structure verified")
            print(f"  Configurations: {config_stats.get('total_configs', 'N/A')}")
            print(f"  Active watchers: {config_stats.get('active_watchers', 'N/A')}")
            print(f"  Versions: {config_stats.get('config_versions', 'N/A')}")
    
    async def test_module_performance(self):
        """Test module system performance"""
        print("\n🧪 Testing system performance...")
        
        # Test API response time
        start_time = time.time()
        response = await self.client.get(f"{self.base_url}/api/v1/modules/")
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 5.0, f"API response too slow: {response_time:.2f}s"
        print(f"✓ API response time: {response_time:.3f}s")
        
        # Test multiple rapid requests
        start_time = time.time()
        tasks = []
        for i in range(5):
            task = self.client.get(f"{self.base_url}/api/v1/modules/")
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # All requests should succeed
        for resp in responses:
            assert resp.status_code == 200
        
        print(f"✓ 5 concurrent requests completed in {total_time:.3f}s")
        print(f"✓ Average per request: {total_time/5:.3f}s")
    
    async def test_system_health(self):
        """Test overall system health"""
        print("\n🧪 Testing system health...")
        
        # Test health endpoint if available
        try:
            health_response = await self.client.get(f"{self.base_url}/health")
            if health_response.status_code == 200:
                print("✓ Health endpoint responding")
            else:
                print(f"⚠ Health endpoint returned {health_response.status_code}")
        except:
            print("⚠ Health endpoint not available")
        
        # Test root endpoint
        try:
            root_response = await self.client.get(f"{self.base_url}/")
            print(f"✓ Root endpoint responding: {root_response.status_code}")
        except Exception as e:
            print(f"⚠ Root endpoint error: {e}")
    
    async def run_all_tests(self):
        """Run all integration tests"""
        print("🚀 Starting Live Module Integration Tests")
        print("=" * 50)
        
        try:
            # Test 1: Module Loading
            modules_data = await self.test_all_modules_loaded()
            
            # Test 2: Module Stats
            stats_modules = await self.test_module_stats_availability(modules_data)
            
            # Test 3: Specific Functionality  
            await self.test_specific_module_functionality(modules_data)
            
            # Test 4: Performance
            await self.test_module_performance()
            
            # Test 5: System Health
            await self.test_system_health()
            
            print("\n" + "=" * 50)
            print("🎉 ALL INTEGRATION TESTS PASSED!")
            print(f"✓ {modules_data['total']} modules operational")
            print(f"✓ {len(stats_modules)} modules providing statistics")
            print("✓ Performance within acceptable limits")
            print("✓ System health verified")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Integration test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            await self.client.aclose()

async def run_quick_test():
    """Run a quick verification test"""
    print("🔧 Quick Module Verification Test")
    print("-" * 30)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get("http://localhost:8000/api/v1/modules/")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ System responding: {data['total']} modules loaded")
                print(f"✅ Module count: {data['module_count']}")
                print(f"✅ System initialized: {data['initialized']}")
                
                # List all modules
                for module in data["modules"]:
                    status = "🟢" if module.get("initialized", False) else "🟡"
                    stats_count = len(module.get("stats", {}))
                    print(f"   {status} {module['name']} v{module['version']} ({stats_count} stats)")
                
                return True
            else:
                print(f"❌ API returned {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        # Quick test
        result = asyncio.run(run_quick_test())
        sys.exit(0 if result else 1)
    else:
        # Full integration test
        test_runner = LiveModuleIntegrationTest()
        result = asyncio.run(test_runner.run_all_tests())
        sys.exit(0 if result else 1)