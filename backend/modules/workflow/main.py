"""
Workflow Module Implementation

This module provides workflow orchestration capabilities including:
- Chaining multiple LLM calls
- Conditional logic execution  
- Data transformations
- Workflow state management
- Parallel and sequential execution
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.logging import get_logger
from app.services.litellm_client import LiteLLMClient
from app.services.base_module import Permission
from app.db.database import SessionLocal
from app.models.workflow import WorkflowDefinition as DBWorkflowDefinition, WorkflowExecution as DBWorkflowExecution

# Import protocols for type hints and dependency injection
from ..protocols import ChatbotServiceProtocol, LiteLLMClientProtocol

logger = get_logger(__name__)


class WorkflowStepType(str, Enum):
    """Types of workflow steps"""
    LLM_CALL = "llm_call"
    CONDITION = "condition"
    TRANSFORM = "transform"
    PARALLEL = "parallel"
    LOOP = "loop"
    DELAY = "delay"
    CHATBOT = "chatbot"
    # Brand-AI inspired step types
    AI_GENERATION = "ai_generation"
    AGGREGATE = "aggregate"
    OUTPUT = "output"
    EMAIL = "email"
    STATUS_UPDATE = "status_update"
    FILTER = "filter"
    MAP = "map"
    REDUCE = "reduce"


class WorkflowStatus(str, Enum):
    """Workflow execution statuses"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowContext:
    """Context passed through workflow execution"""
    workflow_id: str
    execution_id: str
    variables: Dict[str, Any]
    results: Dict[str, Any]
    metadata: Dict[str, Any]
    step_history: List[Dict[str, Any]]


class WorkflowStep(BaseModel):
    """Base workflow step definition"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: WorkflowStepType
    config: Dict[str, Any] = Field(default_factory=dict)
    conditions: Optional[List[str]] = None  # JavaScript-like expressions
    retry_count: int = 0
    timeout: Optional[int] = None
    enabled: bool = True


class LLMCallStep(WorkflowStep):
    """LLM call step configuration"""
    type: WorkflowStepType = WorkflowStepType.LLM_CALL
    model: str
    messages: List[Dict[str, str]]
    parameters: Dict[str, Any] = Field(default_factory=dict)
    output_variable: str = "result"


class ConditionalStep(WorkflowStep):
    """Conditional execution step"""
    type: WorkflowStepType = WorkflowStepType.CONDITION
    condition: str  # JavaScript-like expression
    true_steps: List[WorkflowStep] = Field(default_factory=list)
    false_steps: List[WorkflowStep] = Field(default_factory=list)


class TransformStep(WorkflowStep):
    """Data transformation step"""
    type: WorkflowStepType = WorkflowStepType.TRANSFORM
    input_variable: str
    output_variable: str
    transformation: str  # Python expression or JSON path


class ParallelStep(WorkflowStep):
    """Parallel execution step"""
    type: WorkflowStepType = WorkflowStepType.PARALLEL
    steps: List[WorkflowStep] = Field(default_factory=list)
    wait_for_all: bool = True


class ChatbotStep(WorkflowStep):
    """Chatbot interaction step"""
    type: WorkflowStepType = WorkflowStepType.CHATBOT
    chatbot_id: str  # ID of the chatbot instance to use
    message_template: str  # Template for user message (supports variable interpolation)
    conversation_id: Optional[str] = None  # Existing conversation ID (optional)
    output_variable: str = "chatbot_response"  # Variable name to store response
    context_variables: Optional[Dict[str, str]] = None  # Map workflow vars to chatbot context
    create_new_conversation: bool = False  # Whether to create a new conversation each time
    save_conversation_id: Optional[str] = None  # Variable to save conversation ID to


# Brand-AI inspired step classes
class AIGenerationStep(WorkflowStep):
    """AI Generation step for various operations"""
    type: WorkflowStepType = WorkflowStepType.AI_GENERATION
    operation: str  # 'market_research', 'brand_names', 'analysis', etc.
    model: str = "openrouter/anthropic/claude-3.5-sonnet"
    prompt_template: Optional[str] = None
    variables: Dict[str, Any] = Field(default_factory=dict)
    category: Optional[str] = None  # For brand naming categories
    temperature: float = 0.7
    max_tokens: int = 1000
    output_key: str = "result"


class AggregateStep(WorkflowStep):
    """Aggregate multiple inputs into single output"""
    type: WorkflowStepType = WorkflowStepType.AGGREGATE
    strategy: str = "merge"  # 'merge', 'concat', 'sum', 'average'
    input_keys: List[str] = Field(default_factory=list)
    output_key: str = "aggregated_result"


class FilterStep(WorkflowStep):
    """Filter data based on conditions"""
    type: WorkflowStepType = WorkflowStepType.FILTER
    input_key: str
    output_key: str
    filter_expression: str  # Python expression to evaluate
    keep_original: bool = False


class MapStep(WorkflowStep):
    """Transform each item in a collection"""
    type: WorkflowStepType = WorkflowStepType.MAP
    input_key: str
    output_key: str
    transform_expression: str  # Python expression for transformation
    parallel: bool = False


class ReduceStep(WorkflowStep):
    """Reduce collection to single value"""
    type: WorkflowStepType = WorkflowStepType.REDUCE
    input_key: str
    output_key: str
    reduce_expression: str  # Python expression for reduction
    initial_value: Any = None


class OutputStep(WorkflowStep):
    """Save data to output destination"""
    type: WorkflowStepType = WorkflowStepType.OUTPUT
    input_key: str
    destination: str = "database"  # 'database', 'file', 'api'
    format: str = "json"
    save_path: Optional[str] = None


class EmailStep(WorkflowStep):
    """Send email notifications"""
    type: WorkflowStepType = WorkflowStepType.EMAIL
    recipient: str
    subject: str
    template: str
    variables: Dict[str, Any] = Field(default_factory=dict)
    continue_on_failure: bool = True


class StatusUpdateStep(WorkflowStep):
    """Update workflow or external status"""
    type: WorkflowStepType = WorkflowStepType.STATUS_UPDATE
    status_key: str
    status_value: str
    target: str = "workflow"  # 'workflow', 'external'
    webhook_url: Optional[str] = None


class WorkflowDefinition(BaseModel):
    """Complete workflow definition"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    version: str = "1.0.0"
    steps: List[WorkflowStep]
    variables: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timeout: Optional[int] = None


class WorkflowExecution(BaseModel):
    """Workflow execution state"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    results: Dict[str, Any] = Field(default_factory=dict)


class WorkflowEngine:
    """Core workflow execution engine"""
    
    def __init__(self, litellm_client: LiteLLMClient, chatbot_service: Optional[ChatbotServiceProtocol] = None):
        self.litellm_client = litellm_client
        self.chatbot_service = chatbot_service
        self.executions: Dict[str, WorkflowExecution] = {}
        self.workflows: Dict[str, WorkflowDefinition] = {}
    
    async def execute_workflow(self, workflow: WorkflowDefinition, 
                             input_data: Dict[str, Any] = None) -> WorkflowExecution:
        """Execute a workflow definition"""
        execution = WorkflowExecution(
            workflow_id=workflow.id,
            status=WorkflowStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        
        # Initialize context
        context = WorkflowContext(
            workflow_id=workflow.id,
            execution_id=execution.id,
            variables={**workflow.variables, **(input_data or {})},
            results={},
            metadata={},
            step_history=[]
        )
        
        try:
            # Execute steps
            await self._execute_steps(workflow.steps, context)
            
            execution.status = WorkflowStatus.COMPLETED
            execution.results = context.results
            execution.completed_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            execution.status = WorkflowStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.utcnow()
        
        self.executions[execution.id] = execution
        return execution
    
    async def _execute_steps(self, steps: List[WorkflowStep], context: WorkflowContext):
        """Execute a list of workflow steps"""
        for step in steps:
            if not step.enabled:
                continue
                
            # Check conditions
            if step.conditions and not self._evaluate_conditions(step.conditions, context):
                logger.info(f"Skipping step {step.id} due to unmet conditions")
                continue
            
            logger.info(f"Executing step: {step.name} ({step.type})")
            context.step_history.append({
                "step_id": step.id,
                "step_name": step.name,
                "step_type": step.type,
                "started_at": datetime.utcnow().isoformat()
            })
            
            try:
                if step.type == WorkflowStepType.LLM_CALL:
                    await self._execute_llm_step(step, context)
                elif step.type == WorkflowStepType.CONDITION:
                    await self._execute_conditional_step(step, context)
                elif step.type == WorkflowStepType.TRANSFORM:
                    await self._execute_transform_step(step, context)
                elif step.type == WorkflowStepType.PARALLEL:
                    await self._execute_parallel_step(step, context)
                elif step.type == WorkflowStepType.DELAY:
                    await self._execute_delay_step(step, context)
                elif step.type == WorkflowStepType.CHATBOT:
                    await self._execute_chatbot_step(step, context)
                # Brand-AI inspired step types
                elif step.type == WorkflowStepType.AI_GENERATION:
                    await self._execute_ai_generation_step(step, context)
                elif step.type == WorkflowStepType.AGGREGATE:
                    await self._execute_aggregate_step(step, context)
                elif step.type == WorkflowStepType.FILTER:
                    await self._execute_filter_step(step, context)
                elif step.type == WorkflowStepType.MAP:
                    await self._execute_map_step(step, context)
                elif step.type == WorkflowStepType.REDUCE:
                    await self._execute_reduce_step(step, context)
                elif step.type == WorkflowStepType.OUTPUT:
                    await self._execute_output_step(step, context)
                elif step.type == WorkflowStepType.EMAIL:
                    await self._execute_email_step(step, context)
                elif step.type == WorkflowStepType.STATUS_UPDATE:
                    await self._execute_status_update_step(step, context)
                else:
                    raise ValueError(f"Unknown step type: {step.type}")
                    
            except Exception as e:
                if step.retry_count > 0:
                    logger.warning(f"Step {step.id} failed, retrying...")
                    step.retry_count -= 1
                    await self._execute_steps([step], context)
                else:
                    raise
    
    async def _execute_llm_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute an LLM call step"""
        llm_step = LLMCallStep(**step.dict())
        
        # Template message content with context variables
        messages = self._template_messages(llm_step.messages, context.variables)
        
        # Make LLM call
        response = await self.litellm_client.chat_completion(
            model=llm_step.model,
            messages=messages,
            **llm_step.parameters
        )
        
        # Store result
        result = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        context.variables[llm_step.output_variable] = result
        context.results[step.id] = result
        
        logger.info(f"LLM step {step.id} completed")
    
    async def _execute_conditional_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute a conditional step"""
        cond_step = ConditionalStep(**step.dict())
        
        condition_result = self._evaluate_expression(cond_step.condition, context.variables)
        
        if condition_result:
            await self._execute_steps(cond_step.true_steps, context)
        else:
            await self._execute_steps(cond_step.false_steps, context)
    
    async def _execute_transform_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute a data transformation step"""
        transform_step = TransformStep(**step.dict())
        
        input_value = context.variables.get(transform_step.input_variable)
        
        # Simple transformation evaluation (could be extended)
        if transform_step.transformation.startswith("json:"):
            # JSON path transformation
            result = self._apply_json_path(input_value, transform_step.transformation[5:])
        else:
            # Python expression evaluation (limited scope for security)
            result = self._evaluate_transform(transform_step.transformation, input_value)
        
        context.variables[transform_step.output_variable] = result
        context.results[step.id] = result
    
    async def _execute_parallel_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute steps in parallel"""
        parallel_step = ParallelStep(**step.dict())
        
        # Create tasks for parallel execution
        tasks = []
        for sub_step in parallel_step.steps:
            # Create a copy of context for each parallel branch
            parallel_context = WorkflowContext(
                workflow_id=context.workflow_id,
                execution_id=context.execution_id,
                variables=context.variables.copy(),
                results=context.results.copy(),
                metadata=context.metadata.copy(),
                step_history=context.step_history.copy()
            )
            
            task = asyncio.create_task(self._execute_steps([sub_step], parallel_context))
            tasks.append((task, parallel_context))
        
        # Wait for completion
        if parallel_step.wait_for_all:
            completed_contexts = []
            for task, parallel_context in tasks:
                await task
                completed_contexts.append(parallel_context)
            
            # Merge results back to main context
            for parallel_context in completed_contexts:
                context.variables.update(parallel_context.variables)
                context.results.update(parallel_context.results)
        else:
            # Wait for any to complete
            done, pending = await asyncio.wait([task for task, _ in tasks], 
                                              return_when=asyncio.FIRST_COMPLETED)
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
    
    async def _execute_delay_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute a delay step"""
        delay_seconds = step.config.get("seconds", 1)
        await asyncio.sleep(delay_seconds)
    
    async def _execute_chatbot_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute a chatbot interaction step"""
        chatbot_step = ChatbotStep(**step.dict())
        
        # Template the message with context variables
        message = self._template_string(chatbot_step.message_template, context.variables)
        
        try:
            # Use the injected chatbot service
            if not self.chatbot_service:
                raise ValueError("Chatbot service not available")
            
            # Prepare context variables for the chatbot
            chatbot_context = {}
            if chatbot_step.context_variables:
                for chatbot_var, workflow_var in chatbot_step.context_variables.items():
                    if workflow_var in context.variables:
                        chatbot_context[chatbot_var] = context.variables[workflow_var]
            
            # Prepare conversation ID
            conversation_id = chatbot_step.conversation_id
            if conversation_id and conversation_id in context.variables:
                conversation_id = context.variables[conversation_id]
            
            # Create a chat request object that matches the protocol
            from ..chatbot.main import ChatRequest
            chat_request = ChatRequest(
                message=message,
                chatbot_id=chatbot_step.chatbot_id,
                conversation_id=conversation_id if not chatbot_step.create_new_conversation else None,
                context=chatbot_context
            )
            
            # Make the chatbot call using the service protocol
            # NOTE: DB session dependency should be injected via WorkflowEngine constructor
            # for proper chatbot database operations (conversation persistence, etc.)
            response = await self.chatbot_service.chat_completion(
                request=chat_request,
                user_id="workflow_system",  # Identifier for workflow-initiated chats
                db=None  # Database session needed for conversation persistence
            )
            
            # Extract response data for compatibility
            response_data = {
                "response": response.response,
                "conversation_id": response.conversation_id,
                "message_id": response.message_id,
                "sources": response.sources,
                "metadata": response.metadata if hasattr(response, 'metadata') else {}
            }
            
            # Store the response in context variables
            context.variables[chatbot_step.output_variable] = response_data.get("response", "")
            
            # Save conversation ID if requested
            if chatbot_step.save_conversation_id and "conversation_id" in response_data:
                context.variables[chatbot_step.save_conversation_id] = response_data["conversation_id"]
            
            # Store complete result for step tracking
            context.results[step.id] = {
                "response": response_data.get("response", ""),
                "conversation_id": response_data.get("conversation_id"),
                "message_id": response_data.get("message_id"),
                "sources": response_data.get("sources", []),
                "metadata": response_data.get("metadata", {})
            }
            
            logger.info(f"Chatbot step {step.id} completed successfully")
            
        except Exception as e:
            error_msg = f"Chatbot step failed: {str(e)}"
            logger.error(error_msg)
            
            # Store error response and continue workflow
            context.variables[chatbot_step.output_variable] = f"Error: {error_msg}"
            context.results[step.id] = {
                "error": error_msg,
                "response": "",
                "conversation_id": None
            }
    
    def _template_messages(self, messages: List[Dict[str, str]], 
                          variables: Dict[str, Any]) -> List[Dict[str, str]]:
        """Template message content with variables"""
        templated = []
        for message in messages:
            templated_message = message.copy()
            for key, value in templated_message.items():
                if isinstance(value, str):
                    templated_message[key] = self._template_string(value, variables)
            templated.append(templated_message)
        return templated
    
    def _template_string(self, template: str, variables: Dict[str, Any]) -> str:
        """Simple string templating with variables"""
        try:
            return template.format(**variables)
        except KeyError as e:
            logger.warning(f"Template variable not found: {e}")
            return template
    
    def _evaluate_conditions(self, conditions: List[str], context: WorkflowContext) -> bool:
        """Evaluate a list of conditions (all must be true)"""
        for condition in conditions:
            if not self._evaluate_expression(condition, context.variables):
                return False
        return True
    
    def _evaluate_expression(self, expression: str, variables: Dict[str, Any]) -> bool:
        """Safely evaluate a boolean expression"""
        # Simple expression evaluation (could be enhanced with a proper parser)
        try:
            # Replace variable references
            for var_name, var_value in variables.items():
                if isinstance(var_value, str):
                    expression = expression.replace(f"${var_name}", f"'{var_value}'")
                else:
                    expression = expression.replace(f"${var_name}", str(var_value))
            
            # Evaluate using eval (limited scope for security)
            return bool(eval(expression, {"__builtins__": {}}, {}))
        except Exception as e:
            logger.error(f"Failed to evaluate expression '{expression}': {e}")
            return False
    
    def _evaluate_transform(self, transformation: str, input_value: Any) -> Any:
        """Evaluate a transformation expression"""
        try:
            # Simple transformations
            if transformation == "upper":
                return str(input_value).upper()
            elif transformation == "lower":
                return str(input_value).lower()
            elif transformation == "length":
                return len(input_value) if hasattr(input_value, "__len__") else 0
            elif transformation.startswith("extract:"):
                # Extract JSON field
                field = transformation[8:]
                if isinstance(input_value, dict):
                    return input_value.get(field)
            
            return input_value
        except Exception as e:
            logger.error(f"Transform failed: {e}")
            return input_value
    
    def _apply_json_path(self, data: Any, path: str) -> Any:
        """Apply a simple JSON path to extract data"""
        try:
            parts = path.split(".")
            result = data
            for part in parts:
                if isinstance(result, dict):
                    result = result.get(part)
                elif isinstance(result, list) and part.isdigit():
                    result = result[int(part)]
                else:
                    return None
            return result
        except Exception as e:
            logger.error(f"JSON path failed: {e}")
            return None
    
    # Brand-AI inspired step execution methods
    async def _execute_ai_generation_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute AI generation step for various operations"""
        ai_step = AIGenerationStep(**step.dict())
        
        # Prepare variables for templating
        variables = {**context.variables, **ai_step.variables}
        
        # Generate content based on operation type
        if ai_step.operation == "market_research":
            result = await self._generate_market_research(variables, ai_step)
        elif ai_step.operation == "brand_names":
            result = await self._generate_brand_names(variables, ai_step)
        elif ai_step.operation == "analysis":
            result = await self._generate_analysis(variables, ai_step)
        elif ai_step.operation == "custom_prompt":
            result = await self._generate_custom_prompt(variables, ai_step)
        else:
            raise ValueError(f"Unknown AI operation: {ai_step.operation}")
        
        # Store result
        context.variables[ai_step.output_key] = result
        context.results[step.id] = result
        logger.info(f"AI generation step {step.id} completed")
    
    async def _generate_market_research(self, variables: Dict[str, Any], step: AIGenerationStep) -> str:
        """Generate market research content"""
        prompt = step.prompt_template or f"""
        Conduct market research for the following business:
        Industry: {variables.get('industry', 'Not specified')}
        Target audience: {variables.get('target_audience', 'Not specified')}
        Competitors: {variables.get('competitors', 'Not specified')}
        
        Provide insights on market trends, opportunities, and competitive landscape.
        """
        
        messages = [{"role": "user", "content": self._template_string(prompt, variables)}]
        
        response = await self.litellm_client.create_chat_completion(
            model=step.model,
            messages=messages,
            user_id="workflow_system",
            api_key_id="workflow",
            temperature=step.temperature,
            max_tokens=step.max_tokens
        )
        
        return response.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    async def _generate_brand_names(self, variables: Dict[str, Any], step: AIGenerationStep) -> List[Dict[str, str]]:
        """Generate brand names for a specific category"""
        category = step.category or "general"
        prompt = step.prompt_template or f"""
        Generate 10 creative brand names for a {variables.get('industry', 'business')} company.
        Category: {category}
        Description: {variables.get('description', 'Not specified')}
        Target audience: {variables.get('target_audience', 'Not specified')}
        
        Return names in JSON format: {{"name1": "description1", "name2": "description2", ...}}
        """
        
        messages = [{"role": "user", "content": self._template_string(prompt, variables)}]
        
        response = await self.litellm_client.create_chat_completion(
            model=step.model,
            messages=messages,
            user_id="workflow_system",
            api_key_id="workflow",
            temperature=step.temperature,
            max_tokens=step.max_tokens
        )
        
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Parse JSON response
        try:
            import json
            names_dict = json.loads(content)
            return [{"name": name, "description": desc} for name, desc in names_dict.items()]
        except json.JSONDecodeError:
            logger.error(f"Failed to parse brand names JSON: {content}")
            return []
    
    async def _generate_analysis(self, variables: Dict[str, Any], step: AIGenerationStep) -> str:
        """Generate general analysis content"""
        prompt = step.prompt_template or f"""
        Analyze the following data:
        {json.dumps(variables, indent=2)}
        
        Provide detailed insights and recommendations.
        """
        
        messages = [{"role": "user", "content": self._template_string(prompt, variables)}]
        
        response = await self.litellm_client.create_chat_completion(
            model=step.model,
            messages=messages,
            user_id="workflow_system",
            api_key_id="workflow",
            temperature=step.temperature,
            max_tokens=step.max_tokens
        )
        
        return response.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    async def _generate_custom_prompt(self, variables: Dict[str, Any], step: AIGenerationStep) -> str:
        """Generate content using custom prompt template"""
        if not step.prompt_template:
            raise ValueError("Custom prompt step requires prompt_template")
        
        messages = [{"role": "user", "content": self._template_string(step.prompt_template, variables)}]
        
        response = await self.litellm_client.create_chat_completion(
            model=step.model,
            messages=messages,
            user_id="workflow_system",
            api_key_id="workflow",
            temperature=step.temperature,
            max_tokens=step.max_tokens
        )
        
        return response.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    async def _execute_aggregate_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute aggregate step to combine multiple inputs"""
        agg_step = AggregateStep(**step.dict())
        
        # Collect input values
        inputs = []
        for input_key in agg_step.input_keys:
            value = context.variables.get(input_key)
            if value is not None:
                inputs.append(value)
        
        # Apply aggregation strategy
        if agg_step.strategy == "merge":
            result = {}
            for inp in inputs:
                if isinstance(inp, dict):
                    result.update(inp)
        elif agg_step.strategy == "concat":
            result = []
            for inp in inputs:
                if isinstance(inp, list):
                    result.extend(inp)
                else:
                    result.append(inp)
        elif agg_step.strategy == "sum":
            result = sum(inp for inp in inputs if isinstance(inp, (int, float)))
        elif agg_step.strategy == "average":
            numeric_inputs = [inp for inp in inputs if isinstance(inp, (int, float))]
            result = sum(numeric_inputs) / len(numeric_inputs) if numeric_inputs else 0
        else:
            result = inputs
        
        context.variables[agg_step.output_key] = result
        context.results[step.id] = result
    
    async def _execute_filter_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute filter step to filter data based on conditions"""
        filter_step = FilterStep(**step.dict())
        
        input_data = context.variables.get(filter_step.input_key, [])
        
        if not isinstance(input_data, list):
            input_data = [input_data]
        
        filtered_data = []
        for item in input_data:
            # Create temporary context for evaluation
            temp_vars = {**context.variables, "item": item}
            if self._evaluate_expression(filter_step.filter_expression, temp_vars):
                filtered_data.append(item)
        
        result = filtered_data
        if filter_step.keep_original:
            result = {"original": input_data, "filtered": filtered_data}
        
        context.variables[filter_step.output_key] = result
        context.results[step.id] = result
    
    async def _execute_map_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute map step to transform each item in a collection"""
        map_step = MapStep(**step.dict())
        
        input_data = context.variables.get(map_step.input_key, [])
        
        if not isinstance(input_data, list):
            input_data = [input_data]
        
        if map_step.parallel:
            # Parallel execution for independent transformations
            tasks = []
            for item in input_data:
                task = self._transform_item(item, map_step.transform_expression, context.variables)
                tasks.append(task)
            transformed_data = await asyncio.gather(*tasks)
        else:
            # Sequential execution
            transformed_data = []
            for item in input_data:
                transformed_item = await self._transform_item(item, map_step.transform_expression, context.variables)
                transformed_data.append(transformed_item)
        
        context.variables[map_step.output_key] = transformed_data
        context.results[step.id] = transformed_data
    
    async def _transform_item(self, item: Any, expression: str, context_vars: Dict[str, Any]) -> Any:
        """Transform a single item using expression"""
        # Create temporary context for transformation
        temp_vars = {**context_vars, "item": item}
        return self._evaluate_transform(expression, item)
    
    async def _execute_reduce_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute reduce step to reduce collection to single value"""
        reduce_step = ReduceStep(**step.dict())
        
        input_data = context.variables.get(reduce_step.input_key, [])
        
        if not isinstance(input_data, list):
            input_data = [input_data]
        
        accumulator = reduce_step.initial_value
        
        for item in input_data:
            temp_vars = {**context.variables, "acc": accumulator, "item": item}
            # Simple reduction operations
            if reduce_step.reduce_expression == "sum":
                accumulator = (accumulator or 0) + (item if isinstance(item, (int, float)) else 0)
            elif reduce_step.reduce_expression == "count":
                accumulator = (accumulator or 0) + 1
            elif reduce_step.reduce_expression == "max":
                accumulator = max(accumulator or float('-inf'), item) if isinstance(item, (int, float)) else accumulator
            elif reduce_step.reduce_expression == "min":
                accumulator = min(accumulator or float('inf'), item) if isinstance(item, (int, float)) else accumulator
            else:
                # Custom expression evaluation could be added here
                accumulator = item
        
        context.variables[reduce_step.output_key] = accumulator
        context.results[step.id] = accumulator
    
    async def _execute_output_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute output step to save data"""
        output_step = OutputStep(**step.dict())
        
        data = context.variables.get(output_step.input_key)
        
        if output_step.destination == "database":
            # Save to database (placeholder - would need actual DB integration)
            logger.info(f"Saving data to database: {output_step.save_path}")
            context.results[f"{step.id}_saved"] = True
        elif output_step.destination == "file":
            # Save to file
            import json
            import os
            
            os.makedirs(os.path.dirname(output_step.save_path or "/tmp/workflow_output.json"), exist_ok=True)
            with open(output_step.save_path or "/tmp/workflow_output.json", "w") as f:
                if output_step.format == "json":
                    json.dump(data, f, indent=2)
                else:
                    f.write(str(data))
        elif output_step.destination == "api":
            # Send to API endpoint (placeholder)
            logger.info(f"Sending data to API: {output_step.save_path}")
        
        context.results[step.id] = {"saved": True, "destination": output_step.destination}
    
    async def _execute_email_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute email step to send notifications"""
        email_step = EmailStep(**step.dict())
        
        try:
            # Template email content
            variables = {**context.variables, **email_step.variables}
            subject = self._template_string(email_step.subject, variables)
            body = self._template_string(email_step.template, variables)
            
            # Email sending would be implemented here
            logger.info(f"Sending email to {email_step.recipient}: {subject}")
            
            context.results[step.id] = {"sent": True, "recipient": email_step.recipient}
        except Exception as e:
            if not email_step.continue_on_failure:
                raise
            logger.error(f"Email step failed but continuing: {e}")
            context.results[step.id] = {"sent": False, "error": str(e)}
    
    async def _execute_status_update_step(self, step: WorkflowStep, context: WorkflowContext):
        """Execute status update step"""
        status_step = StatusUpdateStep(**step.dict())
        
        if status_step.target == "workflow":
            context.variables[status_step.status_key] = status_step.status_value
        elif status_step.target == "external" and status_step.webhook_url:
            # Send webhook (placeholder)
            logger.info(f"Sending status update to webhook: {status_step.webhook_url}")
        
        context.results[step.id] = {"updated": True, "status": status_step.status_value}


class WorkflowModule:
    """Workflow module for Confidential Empire"""
    
    def __init__(self, chatbot_service: Optional[ChatbotServiceProtocol] = None):
        self.config = {}
        self.engine = None
        self.chatbot_service = chatbot_service
        self.router = APIRouter(prefix="/workflow", tags=["workflow"])
        self.initialized = False
        
        logger.info("Workflow module created")
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the workflow module"""
        if config:
            self.config = config
        
        # Initialize the workflow engine
        self.engine = WorkflowEngine(LiteLLMClient(), chatbot_service=self.chatbot_service)
        self.setup_routes()
        self.initialized = True
        
        logger.info("Workflow module initialized")
    
    def setup_routes(self):
        """Setup workflow API routes"""
        
        @self.router.post("/execute")
        async def execute_workflow(workflow_def: WorkflowDefinition, 
                                 input_data: Optional[Dict[str, Any]] = None):
            """Execute a workflow"""
            if not self.initialized or not self.engine:
                raise HTTPException(status_code=503, detail="Workflow module not initialized")
            
            try:
                execution = await self.engine.execute_workflow(workflow_def, input_data)
                return {
                    "execution_id": execution.id,
                    "status": execution.status,
                    "results": execution.results if execution.status == WorkflowStatus.COMPLETED else None,
                    "error": execution.error
                }
            except Exception as e:
                logger.error(f"Workflow execution failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/execution/{execution_id}")
        async def get_execution(execution_id: str):
            """Get workflow execution status"""
            if not self.initialized or not self.engine:
                raise HTTPException(status_code=503, detail="Workflow module not initialized")
            
            execution = self.engine.executions.get(execution_id)
            if not execution:
                raise HTTPException(status_code=404, detail="Execution not found")
            
            return {
                "execution_id": execution.id,
                "workflow_id": execution.workflow_id,
                "status": execution.status,
                "current_step": execution.current_step,
                "started_at": execution.started_at,
                "completed_at": execution.completed_at,
                "results": execution.results,
                "error": execution.error
            }
        
        @self.router.post("/validate")
        async def validate_workflow(workflow_def: WorkflowDefinition):
            """Validate a workflow definition"""
            try:
                # Basic validation
                errors = []
                
                if not workflow_def.steps:
                    errors.append("Workflow must have at least one step")
                
                # Validate step references
                step_ids = {step.id for step in workflow_def.steps}
                for step in workflow_def.steps:
                    if step.type == WorkflowStepType.CONDITION:
                        cond_step = ConditionalStep(**step.dict())
                        for sub_step in cond_step.true_steps + cond_step.false_steps:
                            if sub_step.id not in step_ids:
                                errors.append(f"Invalid step reference: {sub_step.id}")
                
                return {
                    "valid": len(errors) == 0,
                    "errors": errors
                }
            except Exception as e:
                return {
                    "valid": False,
                    "errors": [str(e)]
                }
        
        @self.router.get("/templates")
        async def get_workflow_templates():
            """Get predefined workflow templates"""
            # Load chatbot integration templates from file
            chatbot_templates = []
            try:
                import os
                template_file = os.path.join(os.path.dirname(__file__), "templates", "chatbot_integration_examples.json")
                if os.path.exists(template_file):
                    with open(template_file, 'r') as f:
                        chatbot_data = json.load(f)
                        for template in chatbot_data.get("templates", []):
                            chatbot_templates.append({
                                "id": template["id"],
                                "name": template["name"],
                                "description": template["description"],
                                "definition": template,
                                "category": "chatbot_integration"
                            })
            except Exception as e:
                logger.warning(f"Could not load chatbot templates: {e}")
            
            # Built-in templates
            templates = [
                {
                    "id": "simple_chat",
                    "name": "Simple Chat Workflow",
                    "description": "Basic LLM chat interaction",
                    "definition": {
                        "name": "Simple Chat",
                        "steps": [
                            {
                                "name": "Chat Response",
                                "type": "llm_call",
                                "model": "gpt-4",
                                "messages": [
                                    {"role": "user", "content": "{user_input}"}
                                ],
                                "output_variable": "response"
                            }
                        ],
                        "variables": {
                            "user_input": "Hello, how are you?"
                        }
                    }
                },
                {
                    "id": "sentiment_analysis",
                    "name": "Sentiment Analysis Workflow",
                    "description": "Analyze text sentiment with follow-up actions",
                    "definition": {
                        "name": "Sentiment Analysis",
                        "steps": [
                            {
                                "name": "Analyze Sentiment",
                                "type": "llm_call",
                                "model": "gpt-4",
                                "messages": [
                                    {
                                        "role": "system", 
                                        "content": "Analyze the sentiment of the following text and respond with only: positive, negative, or neutral"
                                    },
                                    {"role": "user", "content": "{text_to_analyze}"}
                                ],
                                "output_variable": "sentiment"
                            },
                            {
                                "name": "Conditional Response",
                                "type": "condition",
                                "condition": "$sentiment == 'negative'",
                                "true_steps": [
                                    {
                                        "name": "Generate Positive Response",
                                        "type": "llm_call",
                                        "model": "gpt-4",
                                        "messages": [
                                            {
                                                "role": "system",
                                                "content": "Generate a helpful and positive response to address the negative sentiment"
                                            },
                                            {"role": "user", "content": "{text_to_analyze}"}
                                        ],
                                        "output_variable": "response"
                                    }
                                ],
                                "false_steps": [
                                    {
                                        "name": "Generate Standard Response",
                                        "type": "llm_call",
                                        "model": "gpt-4",
                                        "messages": [
                                            {"role": "user", "content": "Thank you for your {sentiment} feedback!"}
                                        ],
                                        "output_variable": "response"
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
            
            # Combine built-in templates with chatbot templates
            all_templates = templates + chatbot_templates
            return {"templates": all_templates}
    
    async def intercept_llm_request(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Workflow module request interceptor"""
        # Skip interception if module not initialized
        if not self.initialized or not self.engine:
            return context
            
        request = context.get("request", {})
        
        # Check if this is a workflow execution request
        if request.get("workflow_execution"):
            workflow_id = request.get("workflow_id")
            if workflow_id in self.engine.workflows:
                # Execute workflow instead of direct LLM call
                workflow = self.engine.workflows[workflow_id]
                execution = await self.engine.execute_workflow(workflow, request.get("input_data", {}))
                
                # Return workflow results
                context["workflow_result"] = execution.results
                context["skip_llm_call"] = True
        
        return context
    
    async def intercept_llm_response(self, context: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        """Workflow module response interceptor"""
        if context.get("workflow_result"):
            # Return workflow results instead of LLM response
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(context["workflow_result"])
                        }
                    }
                ],
                "usage": {"total_tokens": 0},
                "workflow_execution": True
            }
        
        return response
    
    def get_interceptor_priority(self) -> int:
        """Workflow should run early in the chain"""
        return 15
    
    async def on_enable(self):
        """Called when module is enabled"""
        logger.info("Workflow module enabled")
    
    async def on_disable(self):
        """Called when module is disabled"""
        logger.info("Workflow module disabled")
    
    async def get_workflow_templates(self, request_data: Dict[str, Any] = None):
        """Get predefined workflow templates - for modules API"""
        # Load chatbot integration templates from file
        chatbot_templates = []
        try:
            import os
            template_file = os.path.join(os.path.dirname(__file__), "templates", "chatbot_integration_examples.json")
            if os.path.exists(template_file):
                with open(template_file, 'r') as f:
                    chatbot_data = json.load(f)
                    for template in chatbot_data.get("templates", []):
                        chatbot_templates.append({
                            "id": template["id"],
                            "name": template["name"],
                            "description": template["description"],
                            "definition": template,
                            "category": "chatbot_integration"
                        })
        except Exception as e:
            logger.warning(f"Could not load chatbot templates: {e}")
        
        # Built-in templates
        templates = [
            {
                "id": "simple_chat",
                "name": "Simple Chat Workflow",
                "description": "Basic LLM chat interaction",
                "definition": {
                    "name": "Simple Chat",
                    "steps": [
                        {
                            "name": "Chat Response",
                            "type": "llm_call",
                            "model": "gpt-4",
                            "messages": [
                                {"role": "user", "content": "{user_input}"}
                            ],
                            "output_variable": "response"
                        }
                    ],
                    "variables": {
                        "user_input": "Hello, how are you?"
                    }
                }
            },
            {
                "id": "sentiment_analysis",
                "name": "Sentiment Analysis Workflow",
                "description": "Analyze text sentiment with follow-up actions",
                "definition": {
                    "name": "Sentiment Analysis",
                    "steps": [
                        {
                            "name": "Analyze Sentiment",
                            "type": "llm_call",
                            "model": "gpt-4",
                            "messages": [
                                {"role": "system", "content": "Analyze the sentiment of the following text. Respond with only: positive, negative, or neutral."},
                                {"role": "user", "content": "{text_input}"}
                            ],
                            "output_variable": "sentiment"
                        }
                    ],
                    "variables": {
                        "text_input": "I love this product!"
                    }
                }
            }
        ]
        
        all_templates = chatbot_templates + templates
        return {"templates": all_templates}

    async def execute_workflow(self, request_data: Dict[str, Any]):
        """Execute a workflow - for modules API"""
        if not self.initialized or not self.engine:
            raise HTTPException(status_code=500, detail="Workflow engine not initialized")

        workflow_def = WorkflowDefinition(**request_data.get("workflow_def", {}))
        input_data = request_data.get("input_data", {})
        
        execution = await self.engine.execute_workflow(workflow_def, input_data)
        return {
            "execution_id": execution.id,
            "status": execution.status.value,
            "workflow_id": execution.workflow_id
        }

    async def validate_workflow(self, request_data: Dict[str, Any]):
        """Validate a workflow definition - for modules API"""
        try:
            # Basic validation
            workflow_def = request_data.get("workflow_def", {})
            errors = []
            
            if not workflow_def.get("name"):
                errors.append("Workflow must have a name")
            
            if not workflow_def.get("steps"):
                errors.append("Workflow must have at least one step")
            
            # Validate step references
            step_ids = {step["id"] for step in workflow_def.get("steps", []) if "id" in step}
            for step in workflow_def.get("steps", []):
                if step.get("type") == "condition":
                    cond_step = ConditionalStep(**step)
                    for sub_step in cond_step.true_steps + cond_step.false_steps:
                        if sub_step.id not in step_ids:
                            errors.append(f"Step '{step['name']}' references unknown step '{sub_step.id}'")
            
            return {
                "valid": len(errors) == 0,
                "errors": errors
            }
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"]
            }

    async def get_workflows(self, request_data: Dict[str, Any] = None):
        """Get all workflows - for modules API"""
        try:
            # Create database session
            db = SessionLocal()
            try:
                # Fetch workflows from database
                db_workflows = db.query(DBWorkflowDefinition).filter(
                    DBWorkflowDefinition.is_active == True
                ).all()
                
                # Convert to API format
                workflows = []
                for workflow in db_workflows:
                    workflows.append({
                        "id": workflow.id,
                        "name": workflow.name,
                        "description": workflow.description,
                        "version": workflow.version,
                        "steps": workflow.steps,
                        "variables": workflow.variables,
                        "metadata": workflow.workflow_metadata,
                        "timeout": workflow.timeout,
                        "created_at": workflow.created_at.isoformat() + "Z",
                        "updated_at": workflow.updated_at.isoformat() + "Z",
                        "is_active": workflow.is_active,
                        "created_by": workflow.created_by
                    })
                
                logger.info(f"Retrieved {len(workflows)} workflows from database")
                return {"workflows": workflows}
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error getting workflows: {e}")
            return {"error": str(e)}

    async def get_workflow(self, request_data: Dict[str, Any]):
        """Get a specific workflow - for modules API"""
        try:
            workflow_id = request_data.get("workflow_id")
            if not workflow_id:
                return {"error": "workflow_id is required"}
            
            # Create database session
            db = SessionLocal()
            try:
                # Fetch workflow from database
                db_workflow = db.query(DBWorkflowDefinition).filter(
                    DBWorkflowDefinition.id == workflow_id,
                    DBWorkflowDefinition.is_active == True
                ).first()
                
                if not db_workflow:
                    return {"error": f"Workflow {workflow_id} not found"}
                
                # Convert to API format
                workflow = {
                    "id": db_workflow.id,
                    "name": db_workflow.name,
                    "description": db_workflow.description,
                    "version": db_workflow.version,
                    "steps": db_workflow.steps,
                    "variables": db_workflow.variables,
                    "metadata": db_workflow.workflow_metadata,
                    "timeout": db_workflow.timeout,
                    "created_at": db_workflow.created_at.isoformat() + "Z",
                    "updated_at": db_workflow.updated_at.isoformat() + "Z",
                    "is_active": db_workflow.is_active,
                    "created_by": db_workflow.created_by
                }
                
                return {"workflow": workflow}
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error getting workflow: {e}")
            return {"error": str(e)}

    async def create_workflow(self, request_data: Dict[str, Any]):
        """Create a new workflow - for modules API"""
        try:
            workflow_def = request_data.get("workflow_def", {})
            
            # Generate ID if not provided
            if "id" not in workflow_def:
                workflow_def["id"] = f"wf-{uuid.uuid4().hex[:8]}"
            
            # Extract required fields
            name = workflow_def.get("name", "Untitled Workflow")
            description = workflow_def.get("description", "")
            version = workflow_def.get("version", "1.0.0")
            steps = workflow_def.get("steps", [])
            variables = workflow_def.get("variables", {})
            workflow_metadata = workflow_def.get("metadata", {})
            timeout = workflow_def.get("timeout")
            
            # Create database session
            db = SessionLocal()
            try:
                # Create database record
                db_workflow = DBWorkflowDefinition(
                    id=workflow_def["id"],
                    name=name,
                    description=description,
                    version=version,
                    steps=steps,
                    variables=variables,
                    workflow_metadata=workflow_metadata,
                    timeout=timeout,
                    created_by="system",  # TODO: Get from user context
                    is_active=True
                )
                
                db.add(db_workflow)
                db.commit()
                db.refresh(db_workflow)
                
                logger.info(f"Created workflow in database: {workflow_def['id']}")
                
                # Return workflow data
                return {
                    "workflow": {
                        "id": db_workflow.id,
                        "name": db_workflow.name,
                        "description": db_workflow.description,
                        "version": db_workflow.version,
                        "steps": db_workflow.steps,
                        "variables": db_workflow.variables,
                        "metadata": db_workflow.workflow_metadata,
                        "timeout": db_workflow.timeout,
                        "created_at": db_workflow.created_at.isoformat() + "Z",
                        "updated_at": db_workflow.updated_at.isoformat() + "Z",
                        "is_active": db_workflow.is_active
                    }
                }
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error creating workflow: {e}")
            return {"error": str(e)}

    async def update_workflow(self, request_data: Dict[str, Any]):
        """Update an existing workflow - for modules API"""
        try:
            workflow_id = request_data.get("workflow_id")
            workflow_def = request_data.get("workflow_def", {})
            
            if not workflow_id:
                return {"error": "workflow_id is required"}
            
            # Ensure ID matches
            workflow_def["id"] = workflow_id
            
            # Update timestamp
            import datetime
            workflow_def["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            
            # In a real implementation, this would update in the database
            logger.info(f"Updated workflow: {workflow_id}")
            
            return {"workflow": workflow_def}
        except Exception as e:
            logger.error(f"Error updating workflow: {e}")
            return {"error": str(e)}

    async def delete_workflow(self, request_data: Dict[str, Any]):
        """Delete a workflow - for modules API"""
        try:
            workflow_id = request_data.get("workflow_id")
            
            if not workflow_id:
                return {"error": "workflow_id is required"}
            
            # Create database session
            db = SessionLocal()
            try:
                # Fetch workflow from database
                db_workflow = db.query(DBWorkflowDefinition).filter(
                    DBWorkflowDefinition.id == workflow_id,
                    DBWorkflowDefinition.is_active == True
                ).first()
                
                if not db_workflow:
                    return {"error": f"Workflow {workflow_id} not found"}
                
                # Soft delete - mark as inactive instead of hard delete
                # This preserves execution history while making the workflow unavailable
                db_workflow.is_active = False
                db.commit()
                
                logger.info(f"Workflow {workflow_id} marked as deleted (soft delete)")
                
                return {"success": True, "message": f"Workflow {workflow_id} deleted successfully"}
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error deleting workflow: {e}")
            return {"error": str(e)}

    async def get_executions(self, request_data: Dict[str, Any] = None):
        """Get workflow executions - for modules API"""
        try:
            # For now, return sample execution data
            # In a real implementation, this would fetch from a database
            executions = [
                {
                    "id": "exec-1",
                    "workflow_id": "sample-customer-support",
                    "status": "completed",
                    "started_at": "2024-01-01T12:00:00Z",
                    "completed_at": "2024-01-01T12:05:00Z",
                    "results": {
                        "response": "Customer inquiry resolved successfully",
                        "steps_completed": 3,
                        "tokens_used": 250
                    }
                }
            ]
            
            return {"executions": executions}
        except Exception as e:
            logger.error(f"Error getting executions: {e}")
            return {"error": str(e)}

    async def cancel_execution(self, request_data: Dict[str, Any]):
        """Cancel a workflow execution - for modules API"""
        try:
            execution_id = request_data.get("execution_id")
            
            if not execution_id:
                return {"error": "execution_id is required"}
            
            # In a real implementation, this would cancel the running execution
            logger.info(f"Cancelled execution: {execution_id}")
            
            return {"success": True, "message": f"Execution {execution_id} cancelled successfully"}
        except Exception as e:
            logger.error(f"Error cancelling execution: {e}")
            return {"error": str(e)}

    def get_required_permissions(self) -> List[Permission]:
        """Return required permissions for this module"""
        return [
            Permission("workflows", "create", "Create workflows"),
            Permission("workflows", "execute", "Execute workflows"),
            Permission("workflows", "view", "View workflow status"),
            Permission("workflows", "manage", "Manage workflows"),
        ]


# Create module instance (chatbot service will be injected via factory)
workflow_module = WorkflowModule()