"""
Analytics service for request tracking, usage metrics, and performance monitoring
Integrated with the core app for budget tracking and token usage analysis.
"""
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.core.config import settings
from app.core.logging import get_logger
from app.models.usage_tracking import UsageTracking
from app.models.api_key import APIKey
from app.models.budget import Budget
from app.models.user import User

logger = get_logger(__name__)


@dataclass
class RequestEvent:
    """Enhanced request event data structure with budget integration"""
    timestamp: datetime
    method: str
    path: str
    status_code: int
    response_time: float
    user_id: Optional[int] = None
    api_key_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_size: int = 0
    response_size: int = 0
    error_message: Optional[str] = None
    
    # Token and cost tracking
    model: Optional[str] = None
    request_tokens: int = 0
    response_tokens: int = 0
    total_tokens: int = 0
    cost_cents: int = 0
    
    # Budget information
    budget_ids: List[int] = None
    budget_warnings: List[str] = None


@dataclass
class UsageMetrics:
    """Usage metrics including costs and tokens"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    requests_per_minute: float
    error_rate: float
    
    # Token and cost metrics
    total_tokens: int
    total_cost_cents: int
    avg_tokens_per_request: float
    avg_cost_per_request_cents: float
    
    # Budget metrics
    total_budget_cents: int
    used_budget_cents: int
    budget_usage_percentage: float
    active_budgets: int
    
    # Time-based metrics
    top_endpoints: List[Dict[str, Any]]
    status_codes: Dict[str, int]
    top_models: List[Dict[str, Any]]
    timestamp: datetime


@dataclass
class SystemHealth:
    """System health including budget and usage analysis"""
    status: str  # healthy, warning, critical
    score: int   # 0-100
    issues: List[str]
    recommendations: List[str]
    
    # Performance metrics
    avg_response_time: float
    error_rate: float
    requests_per_minute: float
    
    # Budget health
    budget_usage_percentage: float
    budgets_near_limit: int
    budgets_exceeded: int
    
    timestamp: datetime


class AnalyticsService:
    """Analytics service for comprehensive request and usage tracking"""
    
    def __init__(self, db: Session):
        self.db = db
        self.enabled = True
        self.events: deque = deque(maxlen=10000)  # Keep last 10k events in memory
        self.metrics_cache = {}
        self.cache_ttl = 300  # 5 minutes cache TTL
        
        # Statistics counters
        self.endpoint_stats = defaultdict(lambda: {
            "count": 0,
            "total_time": 0,
            "errors": 0,
            "avg_time": 0,
            "total_tokens": 0,
            "total_cost_cents": 0
        })
        self.status_codes = defaultdict(int)
        self.model_stats = defaultdict(lambda: {
            "count": 0,
            "total_tokens": 0,
            "total_cost_cents": 0
        })
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_old_events())
    
    async def track_request(self, event: RequestEvent):
        """Track a request event with comprehensive metrics"""
        if not self.enabled:
            return
        
        try:
            # Add to events queue
            self.events.append(event)
            
            # Update endpoint stats
            endpoint = f"{event.method} {event.path}"
            stats = self.endpoint_stats[endpoint]
            stats["count"] += 1
            stats["total_time"] += event.response_time
            stats["avg_time"] = stats["total_time"] / stats["count"]
            stats["total_tokens"] += event.total_tokens
            stats["total_cost_cents"] += event.cost_cents
            
            if event.status_code >= 400:
                stats["errors"] += 1
            
            # Update status code stats
            self.status_codes[str(event.status_code)] += 1
            
            # Update model stats
            if event.model:
                model_stats = self.model_stats[event.model]
                model_stats["count"] += 1
                model_stats["total_tokens"] += event.total_tokens
                model_stats["total_cost_cents"] += event.cost_cents
            
            # Clear metrics cache to force recalculation
            self.metrics_cache.clear()
            
            logger.debug(f"Tracked request: {endpoint} - {event.status_code} - {event.response_time:.3f}s")
            
        except Exception as e:
            logger.error(f"Error tracking request: {e}")
    
    async def get_usage_metrics(self, hours: int = 24, user_id: Optional[int] = None, 
                               api_key_id: Optional[int] = None) -> UsageMetrics:
        """Get comprehensive usage metrics including costs and budgets"""
        cache_key = f"usage_metrics_{hours}_{user_id}_{api_key_id}"
        
        # Check cache
        if cache_key in self.metrics_cache:
            cached_time, cached_data = self.metrics_cache[cache_key]
            if datetime.utcnow() - cached_time < timedelta(seconds=self.cache_ttl):
                return cached_data
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Build query filters
            filters = [UsageTracking.created_at >= cutoff_time]
            if user_id:
                filters.append(UsageTracking.user_id == user_id)
            if api_key_id:
                filters.append(UsageTracking.api_key_id == api_key_id)
            
            # Get usage tracking records
            usage_records = self.db.query(UsageTracking).filter(and_(*filters)).all()
            
            # Get recent events from memory
            recent_events = [e for e in self.events if e.timestamp >= cutoff_time]
            if user_id:
                recent_events = [e for e in recent_events if e.user_id == user_id]
            if api_key_id:
                recent_events = [e for e in recent_events if e.api_key_id == api_key_id]
            
            # Calculate basic request metrics
            total_requests = len(recent_events)
            successful_requests = sum(1 for e in recent_events if e.status_code < 400)
            failed_requests = total_requests - successful_requests
            
            if total_requests > 0:
                avg_response_time = sum(e.response_time for e in recent_events) / total_requests
                requests_per_minute = total_requests / (hours * 60)
                error_rate = (failed_requests / total_requests) * 100
            else:
                avg_response_time = 0
                requests_per_minute = 0
                error_rate = 0
            
            # Calculate token and cost metrics from database
            total_tokens = sum(r.total_tokens for r in usage_records)
            total_cost_cents = sum(r.cost_cents for r in usage_records)
            
            if total_requests > 0:
                avg_tokens_per_request = total_tokens / total_requests
                avg_cost_per_request_cents = total_cost_cents / total_requests
            else:
                avg_tokens_per_request = 0
                avg_cost_per_request_cents = 0
            
            # Get budget information
            budget_query = self.db.query(Budget).filter(Budget.is_active == True)
            if user_id:
                budget_query = budget_query.filter(
                    or_(Budget.user_id == user_id, Budget.api_key_id.in_(
                        self.db.query(APIKey.id).filter(APIKey.user_id == user_id).subquery()
                    ))
                )
            
            budgets = budget_query.all()
            active_budgets = len(budgets)
            total_budget_cents = sum(b.limit_cents for b in budgets)
            used_budget_cents = sum(b.current_usage_cents for b in budgets)
            
            if total_budget_cents > 0:
                budget_usage_percentage = (used_budget_cents / total_budget_cents) * 100
            else:
                budget_usage_percentage = 0
            
            # Top endpoints from memory
            endpoint_counts = defaultdict(int)
            for event in recent_events:
                endpoint = f"{event.method} {event.path}"
                endpoint_counts[endpoint] += 1
            
            top_endpoints = [
                {"endpoint": endpoint, "count": count}
                for endpoint, count in sorted(endpoint_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            
            # Status codes from memory
            status_counts = defaultdict(int)
            for event in recent_events:
                status_counts[str(event.status_code)] += 1
            
            # Top models from database
            model_usage = self.db.query(
                UsageTracking.model,
                func.count(UsageTracking.id).label('count'),
                func.sum(UsageTracking.total_tokens).label('tokens'),
                func.sum(UsageTracking.cost_cents).label('cost')
            ).filter(and_(*filters)).filter(
                UsageTracking.model.is_not(None)
            ).group_by(UsageTracking.model).order_by(desc('count')).limit(10).all()
            
            top_models = [
                {
                    "model": model,
                    "count": count,
                    "total_tokens": tokens or 0,
                    "total_cost_cents": cost or 0
                }
                for model, count, tokens, cost in model_usage
            ]
            
            # Create metrics object
            metrics = UsageMetrics(
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                avg_response_time=round(avg_response_time, 3),
                requests_per_minute=round(requests_per_minute, 2),
                error_rate=round(error_rate, 2),
                total_tokens=total_tokens,
                total_cost_cents=total_cost_cents,
                avg_tokens_per_request=round(avg_tokens_per_request, 1),
                avg_cost_per_request_cents=round(avg_cost_per_request_cents, 2),
                total_budget_cents=total_budget_cents,
                used_budget_cents=used_budget_cents,
                budget_usage_percentage=round(budget_usage_percentage, 2),
                active_budgets=active_budgets,
                top_endpoints=top_endpoints,
                status_codes=dict(status_counts),
                top_models=top_models,
                timestamp=datetime.utcnow()
            )
            
            # Cache the result
            self.metrics_cache[cache_key] = (datetime.utcnow(), metrics)
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting usage metrics: {e}")
            return UsageMetrics(
                total_requests=0, successful_requests=0, failed_requests=0,
                avg_response_time=0, requests_per_minute=0, error_rate=0,
                total_tokens=0, total_cost_cents=0, avg_tokens_per_request=0,
                avg_cost_per_request_cents=0, total_budget_cents=0,
                used_budget_cents=0, budget_usage_percentage=0, active_budgets=0,
                top_endpoints=[], status_codes={}, top_models=[],
                timestamp=datetime.utcnow()
            )
    
    async def get_system_health(self) -> SystemHealth:
        """Get comprehensive system health including budget status"""
        try:
            # Get recent metrics
            metrics = await self.get_usage_metrics(hours=1)
            
            # Calculate health score
            health_score = 100
            issues = []
            recommendations = []
            
            # Check error rate
            if metrics.error_rate > 10:
                health_score -= 30
                issues.append(f"High error rate: {metrics.error_rate:.1f}%")
                recommendations.append("Investigate error patterns and root causes")
            elif metrics.error_rate > 5:
                health_score -= 15
                issues.append(f"Elevated error rate: {metrics.error_rate:.1f}%")
                recommendations.append("Monitor error trends")
            
            # Check response time
            if metrics.avg_response_time > 5.0:
                health_score -= 25
                issues.append(f"High response time: {metrics.avg_response_time:.2f}s")
                recommendations.append("Optimize slow endpoints and database queries")
            elif metrics.avg_response_time > 2.0:
                health_score -= 10
                issues.append(f"Elevated response time: {metrics.avg_response_time:.2f}s")
                recommendations.append("Monitor performance trends")
            
            # Check budget usage
            if metrics.budget_usage_percentage > 90:
                health_score -= 20
                issues.append(f"Budget usage critical: {metrics.budget_usage_percentage:.1f}%")
                recommendations.append("Review budget limits and usage patterns")
            elif metrics.budget_usage_percentage > 75:
                health_score -= 10
                issues.append(f"Budget usage high: {metrics.budget_usage_percentage:.1f}%")
                recommendations.append("Monitor spending trends")
            
            # Check for budgets near or over limit
            budgets = self.db.query(Budget).filter(Budget.is_active == True).all()
            budgets_near_limit = sum(1 for b in budgets if b.current_usage_cents >= b.limit_cents * 0.8)
            budgets_exceeded = sum(1 for b in budgets if b.is_exceeded)
            
            if budgets_exceeded > 0:
                health_score -= 25
                issues.append(f"{budgets_exceeded} budgets exceeded")
                recommendations.append("Address budget overruns immediately")
            elif budgets_near_limit > 0:
                health_score -= 10
                issues.append(f"{budgets_near_limit} budgets near limit")
                recommendations.append("Review budget allocations")
            
            # Determine overall status
            if health_score >= 90:
                status = "healthy"
            elif health_score >= 70:
                status = "warning"
            else:
                status = "critical"
            
            return SystemHealth(
                status=status,
                score=max(0, health_score),
                issues=issues,
                recommendations=recommendations,
                avg_response_time=metrics.avg_response_time,
                error_rate=metrics.error_rate,
                requests_per_minute=metrics.requests_per_minute,
                budget_usage_percentage=metrics.budget_usage_percentage,
                budgets_near_limit=budgets_near_limit,
                budgets_exceeded=budgets_exceeded,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return SystemHealth(
                status="error", score=0,
                issues=[f"Health check failed: {str(e)}"],
                recommendations=["Check system logs and restart services"],
                avg_response_time=0, error_rate=0, requests_per_minute=0,
                budget_usage_percentage=0, budgets_near_limit=0,
                budgets_exceeded=0, timestamp=datetime.utcnow()
            )
    
    async def get_cost_analysis(self, days: int = 30, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get detailed cost analysis and trends"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            
            # Build query filters
            filters = [UsageTracking.created_at >= cutoff_time]
            if user_id:
                filters.append(UsageTracking.user_id == user_id)
            
            # Get usage records
            usage_records = self.db.query(UsageTracking).filter(and_(*filters)).all()
            
            # Cost by model
            cost_by_model = defaultdict(int)
            tokens_by_model = defaultdict(int)
            requests_by_model = defaultdict(int)
            
            for record in usage_records:
                if record.model:
                    cost_by_model[record.model] += record.cost_cents
                    tokens_by_model[record.model] += record.total_tokens
                    requests_by_model[record.model] += 1
            
            # Daily cost trends
            daily_costs = defaultdict(int)
            for record in usage_records:
                day = record.created_at.date().isoformat()
                daily_costs[day] += record.cost_cents
            
            # Cost by endpoint
            cost_by_endpoint = defaultdict(int)
            for record in usage_records:
                cost_by_endpoint[record.endpoint] += record.cost_cents
            
            # Calculate efficiency metrics
            total_cost = sum(cost_by_model.values())
            total_tokens = sum(tokens_by_model.values())
            total_requests = len(usage_records)
            
            efficiency_metrics = {
                "cost_per_token": (total_cost / total_tokens) if total_tokens > 0 else 0,
                "cost_per_request": (total_cost / total_requests) if total_requests > 0 else 0,
                "tokens_per_request": (total_tokens / total_requests) if total_requests > 0 else 0
            }
            
            return {
                "period_days": days,
                "total_cost_cents": total_cost,
                "total_cost_dollars": total_cost / 100,
                "total_tokens": total_tokens,
                "total_requests": total_requests,
                "efficiency_metrics": efficiency_metrics,
                "cost_by_model": dict(cost_by_model),
                "tokens_by_model": dict(tokens_by_model),
                "requests_by_model": dict(requests_by_model),
                "daily_costs": dict(daily_costs),
                "cost_by_endpoint": dict(cost_by_endpoint),
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting cost analysis: {e}")
            return {"error": str(e)}
    
    async def _cleanup_old_events(self):
        """Cleanup old events from memory"""
        while self.enabled:
            try:
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                
                # Remove old events
                while self.events and self.events[0].timestamp < cutoff_time:
                    self.events.popleft()
                
                # Clear old cache entries
                current_time = datetime.utcnow()
                expired_keys = []
                for key, (cached_time, _) in self.metrics_cache.items():
                    if current_time - cached_time > timedelta(seconds=self.cache_ttl):
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self.metrics_cache[key]
                
                # Sleep for 1 hour before next cleanup
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in analytics cleanup: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    def cleanup(self):
        """Cleanup analytics resources"""
        self.enabled = False
        self.events.clear()
        self.metrics_cache.clear()
        self.endpoint_stats.clear()
        self.status_codes.clear()
        self.model_stats.clear()


# Global analytics service will be initialized in main.py
analytics_service = None


def get_analytics_service():
    """Get the global analytics service instance"""
    if analytics_service is None:
        raise RuntimeError("Analytics service not initialized")
    return analytics_service


def init_analytics_service():
    """Initialize the global analytics service"""
    global analytics_service
    # Initialize without database session - will be provided per request
    analytics_service = InMemoryAnalyticsService()
    logger.info("Analytics service initialized")


class InMemoryAnalyticsService:
    """Analytics service that works without a persistent database session"""
    
    def __init__(self):
        self.enabled = True
        self.events: deque = deque(maxlen=10000)  # Keep last 10k events in memory
        self.metrics_cache = {}
        self.cache_ttl = 300  # 5 minutes cache TTL
        
        # Statistics counters
        self.endpoint_stats = defaultdict(lambda: {
            "count": 0,
            "total_time": 0,
            "errors": 0,
            "avg_time": 0,
            "total_tokens": 0,
            "total_cost_cents": 0
        })
        self.status_codes = defaultdict(int)
        self.model_stats = defaultdict(lambda: {
            "count": 0,
            "total_tokens": 0,
            "total_cost_cents": 0
        })
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_old_events())
    
    async def track_request(self, event: RequestEvent):
        """Track a request event with comprehensive metrics"""
        if not self.enabled:
            return
        
        try:
            # Add to events queue
            self.events.append(event)
            
            # Update endpoint stats
            endpoint = f"{event.method} {event.path}"
            stats = self.endpoint_stats[endpoint]
            stats["count"] += 1
            stats["total_time"] += event.response_time
            stats["avg_time"] = stats["total_time"] / stats["count"]
            stats["total_tokens"] += event.total_tokens
            stats["total_cost_cents"] += event.cost_cents
            
            if event.status_code >= 400:
                stats["errors"] += 1
            
            # Update status code stats
            self.status_codes[str(event.status_code)] += 1
            
            # Update model stats
            if event.model:
                model_stats = self.model_stats[event.model]
                model_stats["count"] += 1
                model_stats["total_tokens"] += event.total_tokens
                model_stats["total_cost_cents"] += event.cost_cents
            
            # Clear metrics cache to force recalculation
            self.metrics_cache.clear()
            
            logger.debug(f"Tracked request: {endpoint} - {event.status_code} - {event.response_time:.3f}s")
            
        except Exception as e:
            logger.error(f"Error tracking request: {e}")
    
    async def get_usage_metrics(self, hours: int = 24, user_id: Optional[int] = None, 
                               api_key_id: Optional[int] = None) -> UsageMetrics:
        """Get comprehensive usage metrics including costs and budgets"""
        cache_key = f"usage_metrics_{hours}_{user_id}_{api_key_id}"
        
        # Check cache
        if cache_key in self.metrics_cache:
            cached_time, cached_data = self.metrics_cache[cache_key]
            if datetime.utcnow() - cached_time < timedelta(seconds=self.cache_ttl):
                return cached_data
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Get recent events from memory
            recent_events = [e for e in self.events if e.timestamp >= cutoff_time]
            if user_id:
                recent_events = [e for e in recent_events if e.user_id == user_id]
            if api_key_id:
                recent_events = [e for e in recent_events if e.api_key_id == api_key_id]
            
            # Calculate basic request metrics
            total_requests = len(recent_events)
            successful_requests = sum(1 for e in recent_events if e.status_code < 400)
            failed_requests = total_requests - successful_requests
            
            if total_requests > 0:
                avg_response_time = sum(e.response_time for e in recent_events) / total_requests
                requests_per_minute = total_requests / (hours * 60)
                error_rate = (failed_requests / total_requests) * 100
            else:
                avg_response_time = 0
                requests_per_minute = 0
                error_rate = 0
            
            # Calculate token and cost metrics from events
            total_tokens = sum(e.total_tokens for e in recent_events)
            total_cost_cents = sum(e.cost_cents for e in recent_events)
            
            if total_requests > 0:
                avg_tokens_per_request = total_tokens / total_requests
                avg_cost_per_request_cents = total_cost_cents / total_requests
            else:
                avg_tokens_per_request = 0
                avg_cost_per_request_cents = 0
            
            # Mock budget information (since we don't have DB access here)
            total_budget_cents = 100000  # $1000 default
            used_budget_cents = total_cost_cents
            
            if total_budget_cents > 0:
                budget_usage_percentage = (used_budget_cents / total_budget_cents) * 100
            else:
                budget_usage_percentage = 0
            
            # Top endpoints from memory
            endpoint_counts = defaultdict(int)
            for event in recent_events:
                endpoint = f"{event.method} {event.path}"
                endpoint_counts[endpoint] += 1
            
            top_endpoints = [
                {"endpoint": endpoint, "count": count}
                for endpoint, count in sorted(endpoint_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            
            # Status codes from memory
            status_counts = defaultdict(int)
            for event in recent_events:
                status_counts[str(event.status_code)] += 1
            
            # Top models from events
            model_usage = defaultdict(lambda: {"count": 0, "tokens": 0, "cost": 0})
            for event in recent_events:
                if event.model:
                    model_usage[event.model]["count"] += 1
                    model_usage[event.model]["tokens"] += event.total_tokens
                    model_usage[event.model]["cost"] += event.cost_cents
            
            top_models = [
                {
                    "model": model,
                    "count": data["count"],
                    "total_tokens": data["tokens"],
                    "total_cost_cents": data["cost"]
                }
                for model, data in sorted(model_usage.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
            ]
            
            # Create metrics object
            metrics = UsageMetrics(
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                avg_response_time=round(avg_response_time, 3),
                requests_per_minute=round(requests_per_minute, 2),
                error_rate=round(error_rate, 2),
                total_tokens=total_tokens,
                total_cost_cents=total_cost_cents,
                avg_tokens_per_request=round(avg_tokens_per_request, 1),
                avg_cost_per_request_cents=round(avg_cost_per_request_cents, 2),
                total_budget_cents=total_budget_cents,
                used_budget_cents=used_budget_cents,
                budget_usage_percentage=round(budget_usage_percentage, 2),
                active_budgets=1,  # Mock value
                top_endpoints=top_endpoints,
                status_codes=dict(status_counts),
                top_models=top_models,
                timestamp=datetime.utcnow()
            )
            
            # Cache the result
            self.metrics_cache[cache_key] = (datetime.utcnow(), metrics)
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting usage metrics: {e}")
            return UsageMetrics(
                total_requests=0, successful_requests=0, failed_requests=0,
                avg_response_time=0, requests_per_minute=0, error_rate=0,
                total_tokens=0, total_cost_cents=0, avg_tokens_per_request=0,
                avg_cost_per_request_cents=0, total_budget_cents=0,
                used_budget_cents=0, budget_usage_percentage=0, active_budgets=0,
                top_endpoints=[], status_codes={}, top_models=[],
                timestamp=datetime.utcnow()
            )
    
    async def get_system_health(self) -> SystemHealth:
        """Get comprehensive system health including budget status"""
        try:
            # Get recent metrics
            metrics = await self.get_usage_metrics(hours=1)
            
            # Calculate health score
            health_score = 100
            issues = []
            recommendations = []
            
            # Check error rate
            if metrics.error_rate > 10:
                health_score -= 30
                issues.append(f"High error rate: {metrics.error_rate:.1f}%")
                recommendations.append("Investigate error patterns and root causes")
            elif metrics.error_rate > 5:
                health_score -= 15
                issues.append(f"Elevated error rate: {metrics.error_rate:.1f}%")
                recommendations.append("Monitor error trends")
            
            # Check response time
            if metrics.avg_response_time > 5.0:
                health_score -= 25
                issues.append(f"High response time: {metrics.avg_response_time:.2f}s")
                recommendations.append("Optimize slow endpoints and database queries")
            elif metrics.avg_response_time > 2.0:
                health_score -= 10
                issues.append(f"Elevated response time: {metrics.avg_response_time:.2f}s")
                recommendations.append("Monitor performance trends")
            
            # Check budget usage
            if metrics.budget_usage_percentage > 90:
                health_score -= 20
                issues.append(f"Budget usage critical: {metrics.budget_usage_percentage:.1f}%")
                recommendations.append("Review budget limits and usage patterns")
            elif metrics.budget_usage_percentage > 75:
                health_score -= 10
                issues.append(f"Budget usage high: {metrics.budget_usage_percentage:.1f}%")
                recommendations.append("Monitor spending trends")
            
            # Determine overall status
            if health_score >= 90:
                status = "healthy"
            elif health_score >= 70:
                status = "warning"
            else:
                status = "critical"
            
            return SystemHealth(
                status=status,
                score=max(0, health_score),
                issues=issues,
                recommendations=recommendations,
                avg_response_time=metrics.avg_response_time,
                error_rate=metrics.error_rate,
                requests_per_minute=metrics.requests_per_minute,
                budget_usage_percentage=metrics.budget_usage_percentage,
                budgets_near_limit=0,  # Mock values since no DB access
                budgets_exceeded=0,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return SystemHealth(
                status="error", score=0,
                issues=[f"Health check failed: {str(e)}"],
                recommendations=["Check system logs and restart services"],
                avg_response_time=0, error_rate=0, requests_per_minute=0,
                budget_usage_percentage=0, budgets_near_limit=0,
                budgets_exceeded=0, timestamp=datetime.utcnow()
            )
    
    async def get_cost_analysis(self, days: int = 30, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get detailed cost analysis and trends"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            
            # Get events from memory
            events = [e for e in self.events if e.timestamp >= cutoff_time]
            if user_id:
                events = [e for e in events if e.user_id == user_id]
            
            # Cost by model
            cost_by_model = defaultdict(int)
            tokens_by_model = defaultdict(int)
            requests_by_model = defaultdict(int)
            
            for event in events:
                if event.model:
                    cost_by_model[event.model] += event.cost_cents
                    tokens_by_model[event.model] += event.total_tokens
                    requests_by_model[event.model] += 1
            
            # Daily cost trends
            daily_costs = defaultdict(int)
            for event in events:
                day = event.timestamp.date().isoformat()
                daily_costs[day] += event.cost_cents
            
            # Cost by endpoint
            cost_by_endpoint = defaultdict(int)
            for event in events:
                endpoint = f"{event.method} {event.path}"
                cost_by_endpoint[endpoint] += event.cost_cents
            
            # Calculate efficiency metrics
            total_cost = sum(cost_by_model.values())
            total_tokens = sum(tokens_by_model.values())
            total_requests = len(events)
            
            efficiency_metrics = {
                "cost_per_token": (total_cost / total_tokens) if total_tokens > 0 else 0,
                "cost_per_request": (total_cost / total_requests) if total_requests > 0 else 0,
                "tokens_per_request": (total_tokens / total_requests) if total_requests > 0 else 0
            }
            
            return {
                "period_days": days,
                "total_cost_cents": total_cost,
                "total_cost_dollars": total_cost / 100,
                "total_tokens": total_tokens,
                "total_requests": total_requests,
                "efficiency_metrics": efficiency_metrics,
                "cost_by_model": dict(cost_by_model),
                "tokens_by_model": dict(tokens_by_model),
                "requests_by_model": dict(requests_by_model),
                "daily_costs": dict(daily_costs),
                "cost_by_endpoint": dict(cost_by_endpoint),
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting cost analysis: {e}")
            return {"error": str(e)}
    
    async def _cleanup_old_events(self):
        """Cleanup old events from memory"""
        while self.enabled:
            try:
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                
                # Remove old events
                while self.events and self.events[0].timestamp < cutoff_time:
                    self.events.popleft()
                
                # Clear old cache entries
                current_time = datetime.utcnow()
                expired_keys = []
                for key, (cached_time, _) in self.metrics_cache.items():
                    if current_time - cached_time > timedelta(seconds=self.cache_ttl):
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self.metrics_cache[key]
                
                # Sleep for 1 hour before next cleanup
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in analytics cleanup: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    def cleanup(self):
        """Cleanup analytics resources"""
        self.enabled = False
        self.events.clear()
        self.metrics_cache.clear()
        self.endpoint_stats.clear()
        self.status_codes.clear()
        self.model_stats.clear()