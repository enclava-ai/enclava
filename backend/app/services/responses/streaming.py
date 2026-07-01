"""
Streaming support for Responses API

Server-sent events for real-time response generation with tool execution support.
"""

import json
import logging
import time
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Union,
)

from app.services.llm.models import ChatMessage, ChatRequest, ToolCall
from app.services.llm.service import llm_service
from app.services.llm.streaming_tracker import StreamingTokenTracker, StreamingUsage

if TYPE_CHECKING:
    from app.models.user import User
    from app.services.tool_calling_service import ToolCallingService

logger = logging.getLogger(__name__)


# Callback type for usage recording
UsageRecordingCallback = Callable[[StreamingUsage, str, bool], Awaitable[None]]


class ResponseStreamEventType:
    """Event types for response streaming"""

    RESPONSE_CREATED = "response.created"
    OUTPUT_ITEM_ADDED = "response.output_item.added"
    OUTPUT_TEXT_DELTA = "response.output_text.delta"
    FUNCTION_CALL_DELTA = "response.function_call_arguments.delta"
    COMPLETED = "response.completed"
    FAILED = "response.failed"


class ResponseStreamEvent:
    """Streaming event wrapper"""

    def __init__(self, event_type: str, data: Dict[str, Any]):
        self.event_type = event_type
        self.data = data

    def to_sse(self) -> str:
        """Convert to Server-Sent Event format.

        Returns:
            SSE formatted string
        """
        return f"event: {self.event_type}\ndata: {json.dumps(self.data)}\n\n"


async def stream_response_events_with_tracking(
    response_id: str,
    model: str,
    chat_request: ChatRequest,
    tool_calling_service: "ToolCallingService",
    user: Union["User", Dict[str, Any]],
    tool_resources: Optional[Dict[str, Any]] = None,
    max_tool_calls: int = 5,
    estimated_input_tokens: int = 0,
    on_complete: Optional[UsageRecordingCallback] = None,
) -> AsyncGenerator[str, None]:
    """Stream response events with token tracking and usage recording callback.

    Wraps stream_response_events_with_tools with StreamingTokenTracker to
    accumulate token usage and call the recording callback when streaming completes.

    Args:
        response_id: Response ID for event correlation
        model: Model name
        chat_request: Chat request to send to LLM
        tool_calling_service: Tool calling service for tool resolution and execution
        user: User making the request
        tool_resources: Tool resources (e.g., file_search.vector_store_ids for RAG)
        max_tool_calls: Maximum number of tool call iterations
        estimated_input_tokens: Estimated input tokens for accurate tracking
        on_complete: Async callback to record usage when streaming completes

    Yields:
        SSE formatted event strings
    """
    # Initialize token tracker
    tracker = StreamingTokenTracker(
        model=model, estimated_input_tokens=estimated_input_tokens
    )
    stream_status = "success"
    error_occurred = False

    try:
        # Stream events and track tokens
        async for event in stream_response_events_with_tools(
            response_id=response_id,
            model=model,
            chat_request=chat_request,
            tool_calling_service=tool_calling_service,
            user=user,
            tool_resources=tool_resources,
            max_tool_calls=max_tool_calls,
        ):
            # Try to extract token data from event for tracking
            try:
                # Parse the SSE event to extract data
                if event.startswith("event:"):
                    lines = event.strip().split("\n")
                    if len(lines) >= 2 and lines[1].startswith("data:"):
                        data_str = lines[1][5:].strip()  # Remove "data:" prefix
                        data = json.loads(data_str)

                        # Track chunks from output_text.delta events
                        if "delta" in data and isinstance(data.get("delta"), str):
                            # Create a fake chunk for tracker
                            fake_chunk = {
                                "choices": [{"delta": {"content": data["delta"]}}]
                            }
                            tracker.process_chunk(fake_chunk)

                        # Check for completion or failure events
                        event_type = lines[0].replace("event:", "").strip()
                        if event_type == ResponseStreamEventType.COMPLETED:
                            pass  # Normal completion
                        elif event_type == ResponseStreamEventType.FAILED:
                            stream_status = "error"
                            error_occurred = True
            except Exception as parse_error:
                # Don't fail streaming if parsing fails
                logger.debug(
                    f"Failed to parse streaming event for tracking: {parse_error}"
                )

            yield event

    except Exception as e:
        logger.error(f"Error in tracked streaming response: {e}", exc_info=True)
        stream_status = "error"
        error_occurred = True

        # Yield error event
        failed_event = ResponseStreamEvent(
            ResponseStreamEventType.FAILED,
            {
                "id": response_id,
                "object": "response",
                "status": "failed",
                "error": {
                    "type": "internal_error",
                    "code": "internal_error",
                    "message": str(e),
                },
            },
        )
        yield failed_event.to_sse()

    finally:
        # Finalize tracking and record usage
        if on_complete:
            try:
                usage = tracker.finalize()
                await on_complete(usage, stream_status, error_occurred)
            except Exception as callback_error:
                logger.error(f"Failed to record streaming usage: {callback_error}")


async def stream_response_events(
    response_id: str, model: str, llm_stream: AsyncGenerator[Dict[str, Any], None]
) -> AsyncGenerator[str, None]:
    """Stream response events from LLM chunks.

    Converts LLM streaming chunks to Response API events.

    Args:
        response_id: Response ID
        model: Model name
        llm_stream: LLM streaming generator

    Yields:
        SSE formatted event strings
    """
    try:
        # Send response.created event
        created_event = ResponseStreamEvent(
            ResponseStreamEventType.RESPONSE_CREATED,
            {
                "id": response_id,
                "object": "response",
                "created_at": int(time.time()),
                "model": model,
                "status": "in_progress",
            },
        )
        yield created_event.to_sse()

        # Track state for event generation
        message_id = f"msg_{int(time.time() * 1000):016d}"
        current_text = []
        current_tool_calls = {}

        # Process LLM chunks
        async for chunk in llm_stream:
            # Extract delta from chunk
            delta = chunk.get("choices", [{}])[0].get("delta", {})

            # Handle text content
            if "content" in delta and delta["content"]:
                text_delta = delta["content"]
                current_text.append(text_delta)

                # Send text delta event
                text_event = ResponseStreamEvent(
                    ResponseStreamEventType.OUTPUT_TEXT_DELTA,
                    {
                        "response_id": response_id,
                        "item_id": message_id,
                        "delta": text_delta,
                        "type": "output_text",
                    },
                )
                yield text_event.to_sse()

            # Handle tool calls
            if "tool_calls" in delta and delta["tool_calls"]:
                for tool_call_delta in delta["tool_calls"]:
                    index = tool_call_delta.get("index", 0)
                    call_id = tool_call_delta.get("id")

                    # Initialize tool call tracking
                    if index not in current_tool_calls:
                        current_tool_calls[index] = {
                            "id": call_id or f"fc_{int(time.time() * 1000)}_{index}",
                            "name": "",
                            "arguments": "",
                        }

                    # Update tool call data
                    if "function" in tool_call_delta:
                        func = tool_call_delta["function"]
                        if "name" in func:
                            current_tool_calls[index]["name"] = func["name"]
                        if "arguments" in func:
                            current_tool_calls[index]["arguments"] += func["arguments"]

                            # Send function call delta event
                            func_event = ResponseStreamEvent(
                                ResponseStreamEventType.FUNCTION_CALL_DELTA,
                                {
                                    "response_id": response_id,
                                    "call_id": current_tool_calls[index]["id"],
                                    "delta": func["arguments"],
                                    "type": "function_call_arguments",
                                },
                            )
                            yield func_event.to_sse()

        # Send final output items
        output_items = []

        # Add message item if text was generated
        if current_text:
            message_item = {
                "type": "message",
                "id": message_id,
                "role": "assistant",
                "content": [{"type": "output_text", "text": "".join(current_text)}],
                "status": "completed",
            }
            output_items.append(message_item)

            # Send item added event
            item_event = ResponseStreamEvent(
                ResponseStreamEventType.OUTPUT_ITEM_ADDED,
                {"response_id": response_id, "item": message_item},
            )
            yield item_event.to_sse()

        # Add tool call items
        for tool_call in current_tool_calls.values():
            if tool_call["name"]:  # Only add if we have a function name
                tool_item = {
                    "type": "function_call",
                    "id": tool_call["id"],
                    "call_id": tool_call["id"],
                    "name": tool_call["name"],
                    "arguments": tool_call["arguments"],
                    "status": "completed",
                }
                output_items.append(tool_item)

                # Send item added event
                item_event = ResponseStreamEvent(
                    ResponseStreamEventType.OUTPUT_ITEM_ADDED,
                    {"response_id": response_id, "item": tool_item},
                )
                yield item_event.to_sse()

        # Send completed event
        completed_event = ResponseStreamEvent(
            ResponseStreamEventType.COMPLETED,
            {
                "id": response_id,
                "object": "response",
                "status": "completed",
                "output": output_items,
                "output_text": "".join(current_text) if current_text else None,
            },
        )
        yield completed_event.to_sse()

    except Exception as e:
        logger.error(f"Error in streaming response: {e}", exc_info=True)

        # Send failed event
        failed_event = ResponseStreamEvent(
            ResponseStreamEventType.FAILED,
            {
                "id": response_id,
                "object": "response",
                "status": "failed",
                "error": {
                    "type": "internal_error",
                    "code": "internal_error",
                    "message": str(e),
                },
            },
        )
        yield failed_event.to_sse()


async def stream_tool_execution_events(
    response_id: str, tool_calls: list, tool_results: list
) -> AsyncGenerator[str, None]:
    """Stream events for tool execution.

    Args:
        response_id: Response ID
        tool_calls: List of tool calls
        tool_results: List of tool results

    Yields:
        SSE formatted event strings
    """
    for i, (tool_call, result) in enumerate(zip(tool_calls, tool_results)):
        # Send tool result as output item
        result_item = {
            "type": "function_call_output",
            "id": f"out_{i}",
            "call_id": tool_call.id,
            "output": json.dumps(result),
        }

        item_event = ResponseStreamEvent(
            ResponseStreamEventType.OUTPUT_ITEM_ADDED,
            {"response_id": response_id, "item": result_item},
        )
        yield item_event.to_sse()


async def stream_response_events_with_tools(
    response_id: str,
    model: str,
    chat_request: ChatRequest,
    tool_calling_service: "ToolCallingService",
    user: Union["User", Dict[str, Any]],
    tool_resources: Optional[Dict[str, Any]] = None,
    max_tool_calls: int = 5,
) -> AsyncGenerator[str, None]:
    """Stream response events with full tool execution support.

    This function handles the complete streaming flow:
    1. Adds tool definitions to the request
    2. Streams LLM response chunks
    3. Detects and executes tool calls
    4. Streams tool results
    5. Continues with additional LLM calls if needed

    Args:
        response_id: Response ID for event correlation
        model: Model name
        chat_request: Chat request to send to LLM
        tool_calling_service: Tool calling service for tool resolution and execution
        user: User making the request
        tool_resources: Tool resources (e.g., file_search.vector_store_ids for RAG)
        max_tool_calls: Maximum number of tool call iterations

    Yields:
        SSE formatted event strings
    """
    try:
        # Store tool_resources in the service for use during tool execution
        tool_calling_service._tool_resources = tool_resources

        # Get available tools and add to request
        available_tools = await tool_calling_service._get_available_tools_for_user(user)
        if available_tools and not chat_request.tools:
            chat_request.tools = (
                await tool_calling_service._convert_tools_to_openai_format(
                    available_tools
                )
            )

        # Send response.created event
        created_event = ResponseStreamEvent(
            ResponseStreamEventType.RESPONSE_CREATED,
            {
                "id": response_id,
                "object": "response",
                "created_at": int(time.time()),
                "model": model,
                "status": "in_progress",
            },
        )
        yield created_event.to_sse()

        messages = chat_request.messages.copy()
        tool_call_iteration = 0
        all_output_items = []

        while tool_call_iteration < max_tool_calls:
            # Track state for this iteration
            message_id = f"msg_{int(time.time() * 1000):016d}_{tool_call_iteration}"
            current_text = []
            current_tool_calls = {}

            # Stream LLM response with usage tracking
            user_id = tool_calling_service._get_user_id(user)
            llm_stream = llm_service.create_chat_completion_stream(
                chat_request,
                db=tool_calling_service.db,
                user_id=user_id,
                api_key_id=None,  # Responses API uses JWT auth
                endpoint="responses/stream",
            )

            async for chunk in llm_stream:
                delta = chunk.get("choices", [{}])[0].get("delta", {})

                # Handle text content
                if "content" in delta and delta["content"]:
                    text_delta = delta["content"]
                    current_text.append(text_delta)

                    text_event = ResponseStreamEvent(
                        ResponseStreamEventType.OUTPUT_TEXT_DELTA,
                        {
                            "response_id": response_id,
                            "item_id": message_id,
                            "delta": text_delta,
                            "type": "output_text",
                        },
                    )
                    yield text_event.to_sse()

                # Handle tool calls
                if "tool_calls" in delta and delta["tool_calls"]:
                    for tool_call_delta in delta["tool_calls"]:
                        index = tool_call_delta.get("index", 0)
                        call_id = tool_call_delta.get("id")

                        if index not in current_tool_calls:
                            current_tool_calls[index] = {
                                "id": call_id
                                or f"fc_{int(time.time() * 1000)}_{index}",
                                "name": "",
                                "arguments": "",
                            }

                        if "function" in tool_call_delta:
                            func = tool_call_delta["function"]
                            if "name" in func:
                                current_tool_calls[index]["name"] = func["name"]
                            if "arguments" in func:
                                current_tool_calls[index]["arguments"] += func[
                                    "arguments"
                                ]

                                func_event = ResponseStreamEvent(
                                    ResponseStreamEventType.FUNCTION_CALL_DELTA,
                                    {
                                        "response_id": response_id,
                                        "call_id": current_tool_calls[index]["id"],
                                        "delta": func["arguments"],
                                        "type": "function_call_arguments",
                                    },
                                )
                                yield func_event.to_sse()

            # Process completed message
            if current_text:
                message_item = {
                    "type": "message",
                    "id": message_id,
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "".join(current_text)}],
                    "status": "completed",
                }
                all_output_items.append(message_item)

                item_event = ResponseStreamEvent(
                    ResponseStreamEventType.OUTPUT_ITEM_ADDED,
                    {"response_id": response_id, "item": message_item},
                )
                yield item_event.to_sse()

            # Process tool calls
            if current_tool_calls:
                # Build assistant message with tool calls for conversation
                tool_calls_for_message = []
                for idx, tc in sorted(current_tool_calls.items()):
                    if tc["name"]:
                        tool_call_obj = ToolCall(
                            id=tc["id"],
                            type="function",
                            function={"name": tc["name"], "arguments": tc["arguments"]},
                        )
                        tool_calls_for_message.append(tool_call_obj)

                        # Emit tool call item
                        tool_item = {
                            "type": "function_call",
                            "id": tc["id"],
                            "call_id": tc["id"],
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                            "status": "in_progress",
                        }
                        all_output_items.append(tool_item)

                        item_event = ResponseStreamEvent(
                            ResponseStreamEventType.OUTPUT_ITEM_ADDED,
                            {"response_id": response_id, "item": tool_item},
                        )
                        yield item_event.to_sse()

                # Add assistant message to conversation
                assistant_msg = ChatMessage(
                    role="assistant",
                    content="".join(current_text) if current_text else None,
                    tool_calls=tool_calls_for_message,
                )
                messages.append(assistant_msg)

                # Execute each tool call and stream results
                for tool_call in tool_calls_for_message:
                    try:
                        result = await tool_calling_service._execute_tool_call(
                            tool_call, user
                        )

                        # Add tool result to conversation
                        tool_msg = ChatMessage(
                            role="tool",
                            content=json.dumps(result.get("output", result)),
                            tool_call_id=tool_call.id,
                        )
                        messages.append(tool_msg)

                        # Stream tool result event
                        result_item = {
                            "type": "function_call_output",
                            "id": f"out_{tool_call.id}",
                            "call_id": tool_call.id,
                            "output": json.dumps(result.get("output", result)),
                            "status": "completed",
                        }
                        all_output_items.append(result_item)

                        item_event = ResponseStreamEvent(
                            ResponseStreamEventType.OUTPUT_ITEM_ADDED,
                            {"response_id": response_id, "item": result_item},
                        )
                        yield item_event.to_sse()

                    except Exception as e:
                        logger.error(
                            f"Tool execution failed for {tool_call.function.get('name')}: {e}"
                        )

                        # Add error result to conversation
                        error_result = {"error": str(e)}
                        tool_msg = ChatMessage(
                            role="tool",
                            content=json.dumps(error_result),
                            tool_call_id=tool_call.id,
                        )
                        messages.append(tool_msg)

                        # Stream error event
                        error_item = {
                            "type": "function_call_output",
                            "id": f"out_{tool_call.id}",
                            "call_id": tool_call.id,
                            "output": json.dumps(error_result),
                            "status": "failed",
                        }
                        all_output_items.append(error_item)

                        item_event = ResponseStreamEvent(
                            ResponseStreamEventType.OUTPUT_ITEM_ADDED,
                            {"response_id": response_id, "item": error_item},
                        )
                        yield item_event.to_sse()

                # Update request with new messages and continue loop
                chat_request.messages = messages
                tool_call_iteration += 1

            else:
                # No tool calls, we're done
                break

        # Send completed event
        final_text = None
        for item in all_output_items:
            if item.get("type") == "message" and item.get("content"):
                for content in item["content"]:
                    if content.get("type") == "output_text":
                        final_text = content.get("text")

        completed_event = ResponseStreamEvent(
            ResponseStreamEventType.COMPLETED,
            {
                "id": response_id,
                "object": "response",
                "status": "completed",
                "output": all_output_items,
                "output_text": final_text,
            },
        )
        yield completed_event.to_sse()

    except Exception as e:
        logger.error(f"Error in streaming response with tools: {e}", exc_info=True)

        failed_event = ResponseStreamEvent(
            ResponseStreamEventType.FAILED,
            {
                "id": response_id,
                "object": "response",
                "status": "failed",
                "error": {
                    "type": "internal_error",
                    "code": "internal_error",
                    "message": str(e),
                },
            },
        )
        yield failed_event.to_sse()
