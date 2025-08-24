"""
Workflow Execution Service
Handles workflow execution tracking with proper user context and audit trails
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, update
import json

from app.core.logging import get_logger
from app.models.workflow import WorkflowDefinition, WorkflowExecution, WorkflowStepLog, WorkflowStatus
from app.models.user import User
from app.utils.exceptions import APIException

logger = get_logger(__name__)


class WorkflowExecutionService:
    """Service for managing workflow executions with user context tracking"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_execution_record(
        self,
        workflow_id: str,
        user_context: Dict[str, Any],
        execution_params: Optional[Dict] = None
    ) -> WorkflowExecution:
        """Create a new workflow execution record with user context"""
        
        # Extract user information from context
        user_id = user_context.get("user_id") or user_context.get("id", "system")
        username = user_context.get("username", "system")
        session_id = user_context.get("session_id")
        
        # Create execution record
        execution_record = WorkflowExecution(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            status=WorkflowStatus.PENDING,
            input_data=execution_params or {},
            context={
                "user_id": user_id,
                "username": username,
                "session_id": session_id,
                "started_by": "workflow_execution_service",
                "created_at": datetime.utcnow().isoformat()
            },
            executed_by=str(user_id),
            started_at=datetime.utcnow()
        )
        
        try:
            self.db.add(execution_record)
            await self.db.commit()
            await self.db.refresh(execution_record)
            
            logger.info(f"Created workflow execution record {execution_record.id} for workflow {workflow_id} by user {username} ({user_id})")
            return execution_record
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create execution record: {e}")
            raise APIException(f"Failed to create execution record: {e}")
    
    async def start_execution(
        self, 
        execution_id: str,
        workflow_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mark execution as started and update context"""
        
        try:
            # Update execution record to running status
            stmt = update(WorkflowExecution).where(
                WorkflowExecution.id == execution_id
            ).values(
                status=WorkflowStatus.RUNNING,
                started_at=datetime.utcnow(),
                context=workflow_context or {}
            )
            
            await self.db.execute(stmt)
            await self.db.commit()
            
            logger.info(f"Started workflow execution {execution_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to start execution {execution_id}: {e}")
            return False
    
    async def complete_execution(
        self,
        execution_id: str,
        results: Dict[str, Any],
        step_history: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Mark execution as completed with results"""
        
        try:
            # Update execution record
            stmt = update(WorkflowExecution).where(
                WorkflowExecution.id == execution_id
            ).values(
                status=WorkflowStatus.COMPLETED,
                completed_at=datetime.utcnow(),
                results=results
            )
            
            await self.db.execute(stmt)
            
            # Log individual steps if provided
            if step_history:
                await self._log_execution_steps(execution_id, step_history)
            
            await self.db.commit()
            
            logger.info(f"Completed workflow execution {execution_id} with {len(results)} results")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to complete execution {execution_id}: {e}")
            return False
    
    async def fail_execution(
        self,
        execution_id: str,
        error_message: str,
        step_history: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Mark execution as failed with error details"""
        
        try:
            # Update execution record
            stmt = update(WorkflowExecution).where(
                WorkflowExecution.id == execution_id
            ).values(
                status=WorkflowStatus.FAILED,
                completed_at=datetime.utcnow(),
                error=error_message
            )
            
            await self.db.execute(stmt)
            
            # Log individual steps if provided
            if step_history:
                await self._log_execution_steps(execution_id, step_history)
            
            await self.db.commit()
            
            logger.error(f"Failed workflow execution {execution_id}: {error_message}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to record execution failure {execution_id}: {e}")
            return False
    
    async def cancel_execution(self, execution_id: str, reason: str = "User cancelled") -> bool:
        """Cancel a workflow execution"""
        
        try:
            stmt = update(WorkflowExecution).where(
                WorkflowExecution.id == execution_id
            ).values(
                status=WorkflowStatus.CANCELLED,
                completed_at=datetime.utcnow(),
                error=f"Cancelled: {reason}"
            )
            
            await self.db.execute(stmt)
            await self.db.commit()
            
            logger.info(f"Cancelled workflow execution {execution_id}: {reason}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to cancel execution {execution_id}: {e}")
            return False
    
    async def get_execution_status(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get current execution status and details"""
        
        try:
            stmt = select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
            result = await self.db.execute(stmt)
            execution = result.scalar_one_or_none()
            
            if execution:
                logger.debug(f"Retrieved execution status for {execution_id}: {execution.status}")
                return execution
            else:
                logger.warning(f"Execution {execution_id} not found")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get execution status for {execution_id}: {e}")
            return None
    
    async def get_user_executions(
        self, 
        user_id: str, 
        limit: int = 50, 
        status_filter: Optional[WorkflowStatus] = None
    ) -> List[WorkflowExecution]:
        """Get workflow executions for a specific user"""
        
        try:
            stmt = select(WorkflowExecution).where(WorkflowExecution.executed_by == str(user_id))
            
            if status_filter:
                stmt = stmt.where(WorkflowExecution.status == status_filter)
            
            stmt = stmt.order_by(WorkflowExecution.created_at.desc()).limit(limit)
            
            result = await self.db.execute(stmt)
            executions = result.scalars().all()
            
            logger.debug(f"Retrieved {len(executions)} executions for user {user_id}")
            return list(executions)
            
        except Exception as e:
            logger.error(f"Failed to get executions for user {user_id}: {e}")
            return []
    
    async def get_workflow_executions(
        self, 
        workflow_id: str, 
        limit: int = 50
    ) -> List[WorkflowExecution]:
        """Get all executions for a specific workflow"""
        
        try:
            stmt = select(WorkflowExecution).where(
                WorkflowExecution.workflow_id == workflow_id
            ).order_by(WorkflowExecution.created_at.desc()).limit(limit)
            
            result = await self.db.execute(stmt)
            executions = result.scalars().all()
            
            logger.debug(f"Retrieved {len(executions)} executions for workflow {workflow_id}")
            return list(executions)
            
        except Exception as e:
            logger.error(f"Failed to get executions for workflow {workflow_id}: {e}")
            return []
    
    async def get_execution_history(self, execution_id: str) -> List[WorkflowStepLog]:
        """Get detailed step history for an execution"""
        
        try:
            stmt = select(WorkflowStepLog).where(
                WorkflowStepLog.execution_id == execution_id
            ).order_by(WorkflowStepLog.started_at.asc())
            
            result = await self.db.execute(stmt)
            step_logs = result.scalars().all()
            
            logger.debug(f"Retrieved {len(step_logs)} step logs for execution {execution_id}")
            return list(step_logs)
            
        except Exception as e:
            logger.error(f"Failed to get execution history for {execution_id}: {e}")
            return []
    
    async def _log_execution_steps(
        self, 
        execution_id: str, 
        step_history: List[Dict[str, Any]]
    ):
        """Log individual step executions"""
        
        try:
            step_logs = []
            for step_data in step_history:
                step_log = WorkflowStepLog(
                    id=str(uuid.uuid4()),
                    execution_id=execution_id,
                    step_id=step_data.get("step_id", "unknown"),
                    step_name=step_data.get("step_name", "Unknown Step"),
                    step_type=step_data.get("step_type", "unknown"),
                    status=step_data.get("status", "completed"),
                    input_data=step_data.get("input_data", {}),
                    output_data=step_data.get("output_data", {}),
                    error=step_data.get("error"),
                    started_at=datetime.fromisoformat(step_data.get("started_at", datetime.utcnow().isoformat())),
                    completed_at=datetime.fromisoformat(step_data.get("completed_at", datetime.utcnow().isoformat())) if step_data.get("completed_at") else None,
                    duration_ms=step_data.get("duration_ms"),
                    retry_count=step_data.get("retry_count", 0)
                )
                step_logs.append(step_log)
            
            if step_logs:
                self.db.add_all(step_logs)
                logger.debug(f"Added {len(step_logs)} step logs for execution {execution_id}")
                
        except Exception as e:
            logger.error(f"Failed to log execution steps for {execution_id}: {e}")
    
    async def get_execution_statistics(
        self, 
        user_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get execution statistics for analytics"""
        
        try:
            from sqlalchemy import func
            from datetime import timedelta
            
            # Base query
            stmt = select(WorkflowExecution)
            
            # Apply filters
            if user_id:
                stmt = stmt.where(WorkflowExecution.executed_by == str(user_id))
            if workflow_id:
                stmt = stmt.where(WorkflowExecution.workflow_id == workflow_id)
            
            # Date filter
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            stmt = stmt.where(WorkflowExecution.created_at >= cutoff_date)
            
            # Get all matching executions
            result = await self.db.execute(stmt)
            executions = result.scalars().all()
            
            # Calculate statistics
            total_executions = len(executions)
            completed = len([e for e in executions if e.status == WorkflowStatus.COMPLETED])
            failed = len([e for e in executions if e.status == WorkflowStatus.FAILED])
            cancelled = len([e for e in executions if e.status == WorkflowStatus.CANCELLED])
            running = len([e for e in executions if e.status == WorkflowStatus.RUNNING])
            
            # Calculate average execution time for completed workflows
            completed_executions = [e for e in executions if e.status == WorkflowStatus.COMPLETED and e.started_at and e.completed_at]
            avg_duration = None
            if completed_executions:
                total_duration = sum([(e.completed_at - e.started_at).total_seconds() for e in completed_executions])
                avg_duration = total_duration / len(completed_executions)
            
            statistics = {
                "total_executions": total_executions,
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
                "running": running,
                "success_rate": (completed / total_executions * 100) if total_executions > 0 else 0,
                "failure_rate": (failed / total_executions * 100) if total_executions > 0 else 0,
                "average_duration_seconds": avg_duration,
                "period_days": days,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            logger.debug(f"Generated execution statistics: {statistics}")
            return statistics
            
        except Exception as e:
            logger.error(f"Failed to generate execution statistics: {e}")
            return {
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat()
            }
    
    def create_user_context(
        self, 
        user_id: str, 
        username: Optional[str] = None,
        session_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create standardized user context for workflow execution"""
        
        context = {
            "user_id": user_id,
            "username": username or f"user_{user_id}",
            "session_id": session_id or str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "source": "workflow_execution_service"
        }
        
        if additional_context:
            context.update(additional_context)
        
        return context
    
    def extract_user_context_from_request(self, request_context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user context from API request context"""
        
        # Try to get user from different possible sources
        user = request_context.get("user") or request_context.get("current_user")
        
        if user:
            if isinstance(user, dict):
                return self.create_user_context(
                    user_id=str(user.get("id", "unknown")),
                    username=user.get("username") or user.get("email"),
                    session_id=request_context.get("session_id")
                )
            else:
                # Assume user is a model instance
                return self.create_user_context(
                    user_id=str(getattr(user, 'id', 'unknown')),
                    username=getattr(user, 'username', None) or getattr(user, 'email', None),
                    session_id=request_context.get("session_id")
                )
        
        # Fallback to API key or system context
        api_key_id = request_context.get("api_key_id")
        if api_key_id:
            return self.create_user_context(
                user_id=f"api_key_{api_key_id}",
                username=f"API Key {api_key_id}",
                session_id=request_context.get("session_id"),
                additional_context={"auth_type": "api_key"}
            )
        
        # Last resort: system context
        return self.create_user_context(
            user_id="system",
            username="System",
            session_id=request_context.get("session_id"),
            additional_context={"auth_type": "system", "note": "No user context available"}
        )