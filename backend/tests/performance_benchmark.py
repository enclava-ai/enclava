"""
Performance Benchmarking and Optimization Suite
Analyzes system performance, identifies bottlenecks, and measures improvements
"""

import asyncio
import time
import json
import statistics
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import sys
import concurrent.futures
from datetime import datetime

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

@dataclass
class PerformanceMetrics:
    """Performance measurement results"""
    operation: str
    avg_time: float
    min_time: float
    max_time: float
    median_time: float
    std_dev: float
    throughput: float  # operations per second
    success_rate: float
    total_operations: int
    total_time: float

@dataclass
class SystemResourceMetrics:
    """System resource usage metrics"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_io_read: int
    disk_io_write: int
    network_sent: int
    network_recv: int

class PerformanceBenchmark:
    """Comprehensive performance benchmarking suite"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: Dict[str, PerformanceMetrics] = {}
        self.resource_metrics: List[SystemResourceMetrics] = []
        self.start_time = time.time()
    
    async def measure_api_performance(self, iterations: int = 100) -> PerformanceMetrics:
        """Measure API endpoint performance"""
        print(f"🔥 Benchmarking API performance ({iterations} iterations)...")
        
        times = []
        successful = 0
        
        start_total = time.time()
        
        # Use curl for reliable testing
        for i in range(iterations):
            start = time.time()
            
            # Use subprocess to call curl
            import subprocess
            try:
                result = subprocess.run([
                    'curl', '-s', '-w', '%{time_total}', 
                    f'{self.base_url}/api/v1/modules/'
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    # Parse response time from curl
                    response_time = float(result.stderr.strip()) if result.stderr.strip() else (time.time() - start)
                    times.append(response_time)
                    successful += 1
                else:
                    times.append(time.time() - start)
                    
            except Exception as e:
                times.append(time.time() - start)
            
            # Small delay to avoid overwhelming the server
            if i % 10 == 0:
                await asyncio.sleep(0.01)
        
        total_time = time.time() - start_total
        
        if not times:
            return PerformanceMetrics(
                operation="api_performance",
                avg_time=0, min_time=0, max_time=0, median_time=0,
                std_dev=0, throughput=0, success_rate=0,
                total_operations=iterations, total_time=total_time
            )
        
        metrics = PerformanceMetrics(
            operation="api_performance",
            avg_time=statistics.mean(times),
            min_time=min(times),
            max_time=max(times),
            median_time=statistics.median(times),
            std_dev=statistics.stdev(times) if len(times) > 1 else 0,
            throughput=successful / total_time,
            success_rate=successful / iterations,
            total_operations=iterations,
            total_time=total_time
        )
        
        self.results["api_performance"] = metrics
        return metrics
    
    async def measure_concurrent_performance(self, concurrent_users: int = 10, requests_per_user: int = 10) -> PerformanceMetrics:
        """Measure performance under concurrent load"""
        print(f"🔥 Benchmarking concurrent performance ({concurrent_users} users, {requests_per_user} requests each)...")
        
        all_times = []
        successful = 0
        total_operations = concurrent_users * requests_per_user
        
        start_total = time.time()
        
        async def user_simulation(user_id: int) -> List[float]:
            """Simulate a single user making multiple requests"""
            user_times = []
            user_successful = 0
            
            for request in range(requests_per_user):
                start = time.time()
                
                import subprocess
                try:
                    result = subprocess.run([
                        'curl', '-s', '-w', '%{time_total}', 
                        f'{self.base_url}/api/v1/modules/'
                    ], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        response_time = float(result.stderr.strip()) if result.stderr.strip() else (time.time() - start)
                        user_times.append(response_time)
                        user_successful += 1
                    else:
                        user_times.append(time.time() - start)
                        
                except Exception:
                    user_times.append(time.time() - start)
                
                # Small delay between requests
                await asyncio.sleep(0.01)
            
            return user_times, user_successful
        
        # Run concurrent users
        tasks = [user_simulation(i) for i in range(concurrent_users)]
        results = await asyncio.gather(*tasks)
        
        # Collect all results
        for user_times, user_successful in results:
            all_times.extend(user_times)
            successful += user_successful
        
        total_time = time.time() - start_total
        
        if not all_times:
            return PerformanceMetrics(
                operation="concurrent_performance",
                avg_time=0, min_time=0, max_time=0, median_time=0,
                std_dev=0, throughput=0, success_rate=0,
                total_operations=total_operations, total_time=total_time
            )
        
        metrics = PerformanceMetrics(
            operation="concurrent_performance",
            avg_time=statistics.mean(all_times),
            min_time=min(all_times),
            max_time=max(all_times),
            median_time=statistics.median(all_times),
            std_dev=statistics.stdev(all_times) if len(all_times) > 1 else 0,
            throughput=successful / total_time,
            success_rate=successful / total_operations,
            total_operations=total_operations,
            total_time=total_time
        )
        
        self.results["concurrent_performance"] = metrics
        return metrics
    
    def collect_system_resources(self) -> SystemResourceMetrics:
        """Collect current system resource metrics"""
        try:
            import psutil
            
            # Get CPU and memory info
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            # Get disk I/O
            disk_io = psutil.disk_io_counters()
            
            # Get network I/O
            network_io = psutil.net_io_counters()
            
            return SystemResourceMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_mb=memory.used / (1024 * 1024),
                disk_io_read=disk_io.read_bytes if disk_io else 0,
                disk_io_write=disk_io.write_bytes if disk_io else 0,
                network_sent=network_io.bytes_sent if network_io else 0,
                network_recv=network_io.bytes_recv if network_io else 0
            )
        except ImportError:
            # Fallback if psutil not available
            return SystemResourceMetrics(
                timestamp=time.time(),
                cpu_percent=0, memory_percent=0, memory_mb=0,
                disk_io_read=0, disk_io_write=0,
                network_sent=0, network_recv=0
            )
    
    async def monitor_resources_during_test(self, duration: float = 60.0) -> List[SystemResourceMetrics]:
        """Monitor system resources during performance test"""
        print(f"📊 Monitoring system resources for {duration}s...")
        
        metrics = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            metric = self.collect_system_resources()
            metrics.append(metric)
            await asyncio.sleep(1.0)  # Collect every second
        
        self.resource_metrics.extend(metrics)
        return metrics
    
    async def analyze_module_performance(self) -> Dict[str, Any]:
        """Analyze individual module performance"""
        print("🔍 Analyzing module performance...")
        
        module_analysis = {}
        
        # Get module stats multiple times to analyze performance
        import subprocess
        
        for i in range(5):
            try:
                result = subprocess.run([
                    'curl', '-s', f'{self.base_url}/api/v1/modules/'
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    
                    for module in data.get('modules', []):
                        module_name = module['name']
                        stats = module.get('stats', {})
                        
                        if module_name not in module_analysis:
                            module_analysis[module_name] = {
                                'stats_count': len(stats),
                                'initialized': module.get('initialized', False),
                                'has_stats': bool(stats),
                                'version': module.get('version', 'unknown')
                            }
            except Exception as e:
                print(f"Warning: Failed to analyze modules: {e}")
            
            await asyncio.sleep(0.5)
        
        return module_analysis
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        print("📋 Generating performance report...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'test_duration': time.time() - self.start_time,
            'performance_metrics': {name: asdict(metrics) for name, metrics in self.results.items()},
            'system_resources': {
                'samples': len(self.resource_metrics),
                'avg_cpu': statistics.mean([m.cpu_percent for m in self.resource_metrics]) if self.resource_metrics else 0,
                'avg_memory': statistics.mean([m.memory_percent for m in self.resource_metrics]) if self.resource_metrics else 0,
                'peak_cpu': max([m.cpu_percent for m in self.resource_metrics]) if self.resource_metrics else 0,
                'peak_memory': max([m.memory_percent for m in self.resource_metrics]) if self.resource_metrics else 0,
            },
            'recommendations': self.generate_recommendations()
        }
        
        return report
    
    def generate_recommendations(self) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        # Analyze API performance
        if 'api_performance' in self.results:
            api_metrics = self.results['api_performance']
            
            if api_metrics.avg_time > 1.0:
                recommendations.append("⚠️ API response time is slow (>1s). Consider optimizing database queries and caching.")
            
            if api_metrics.success_rate < 0.95:
                recommendations.append("⚠️ API success rate is low (<95%). Check for connection timeouts and error handling.")
            
            if api_metrics.throughput < 10:
                recommendations.append("⚠️ Low API throughput (<10 req/s). Consider connection pooling and async optimizations.")
        
        # Analyze concurrent performance
        if 'concurrent_performance' in self.results:
            concurrent_metrics = self.results['concurrent_performance']
            
            if concurrent_metrics.avg_time > api_metrics.avg_time * 2:
                recommendations.append("⚠️ Performance degrades under load. Consider horizontal scaling or caching.")
        
        # Analyze resource usage
        if self.resource_metrics:
            avg_cpu = statistics.mean([m.cpu_percent for m in self.resource_metrics])
            avg_memory = statistics.mean([m.memory_percent for m in self.resource_metrics])
            
            if avg_cpu > 80:
                recommendations.append("⚠️ High CPU usage detected. Consider optimizing computational tasks.")
            
            if avg_memory > 80:
                recommendations.append("⚠️ High memory usage detected. Check for memory leaks and optimize data structures.")
        
        # Add positive recommendations if performance is good
        if not recommendations:
            recommendations.append("✅ System performance is within acceptable limits.")
            recommendations.append("💡 Consider implementing Redis caching for further performance gains.")
            recommendations.append("💡 Monitor performance regularly as the system scales.")
        
        return recommendations
    
    async def run_comprehensive_benchmark(self) -> Dict[str, Any]:
        """Run complete performance benchmark suite"""
        print("🚀 Starting Comprehensive Performance Benchmark")
        print("=" * 60)
        
        # Start resource monitoring in background
        monitor_task = asyncio.create_task(self.monitor_resources_during_test(30.0))
        
        try:
            # Test 1: Basic API Performance
            await self.measure_api_performance(50)
            
            # Test 2: Concurrent Load Performance  
            await self.measure_concurrent_performance(5, 10)
            
            # Test 3: Module Analysis
            module_analysis = await self.analyze_module_performance()
            
            # Wait for resource monitoring to complete
            await monitor_task
            
            # Generate final report
            report = self.generate_performance_report()
            report['module_analysis'] = module_analysis
            
            return report
            
        except Exception as e:
            print(f"❌ Benchmark failed: {e}")
            monitor_task.cancel()
            return {'error': str(e)}
    
    def print_results(self, report: Dict[str, Any]):
        """Print formatted benchmark results"""
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE BENCHMARK RESULTS")
        print("=" * 60)
        
        # Performance Metrics
        if 'performance_metrics' in report:
            print("\n🔥 Performance Metrics:")
            for test_name, metrics in report['performance_metrics'].items():
                print(f"\n  {test_name.upper()}:")
                print(f"    Average Response Time: {metrics['avg_time']:.3f}s")
                print(f"    Throughput: {metrics['throughput']:.1f} req/s")
                print(f"    Success Rate: {metrics['success_rate']:.1%}")
                print(f"    Min/Max Time: {metrics['min_time']:.3f}s / {metrics['max_time']:.3f}s")
        
        # System Resources
        if 'system_resources' in report:
            resources = report['system_resources']
            print(f"\n📈 System Resources:")
            print(f"    Average CPU: {resources['avg_cpu']:.1f}%")
            print(f"    Average Memory: {resources['avg_memory']:.1f}%")
            print(f"    Peak CPU: {resources['peak_cpu']:.1f}%")
            print(f"    Peak Memory: {resources['peak_memory']:.1f}%")
        
        # Module Analysis
        if 'module_analysis' in report:
            print(f"\n🔧 Module Analysis:")
            for module_name, analysis in report['module_analysis'].items():
                status = "✅" if analysis['initialized'] else "⏳"
                stats_info = f"({analysis['stats_count']} stats)" if analysis['has_stats'] else "(no stats)"
                print(f"    {status} {module_name} v{analysis['version']} {stats_info}")
        
        # Recommendations
        if 'recommendations' in report:
            print(f"\n💡 Recommendations:")
            for rec in report['recommendations']:
                print(f"    {rec}")
        
        print(f"\n⏱️  Total benchmark time: {report.get('test_duration', 0):.1f}s")
        print("=" * 60)

async def main():
    """Main benchmark execution"""
    benchmark = PerformanceBenchmark()
    
    try:
        # Run comprehensive benchmark
        report = await benchmark.run_comprehensive_benchmark()
        
        # Print results
        benchmark.print_results(report)
        
        # Save report to file
        report_file = Path("performance_report.json")
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n💾 Detailed report saved to: {report_file}")
        
        return report
        
    except Exception as e:
        print(f"❌ Benchmark execution failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Run the benchmark
    result = asyncio.run(main())
    
    # Exit with appropriate code
    if result and 'error' not in result:
        print("\n🎉 Benchmark completed successfully!")
        exit(0)
    else:
        print("\n❌ Benchmark failed!")
        exit(1)