"""
ItemMessageTranslator - Translation layer between Responses API Items and Chat Completions Messages

CRITICAL: Responses API uses item-based turns with typed objects.
ToolCallingService uses OpenAI Chat Completions message format.

This translator ensures consistency across:
- Item types vs message roles
- Tool call ID formats (call_id vs tool_call_id)
- Content format differences (typed content parts vs string/array)
"""

import json
import logging
from typing import List, Dict, Any, Union
from app.services.llm.models import ChatMessage, ToolCall

logger = logging.getLogger(__name__)


class ItemMessageTranslator:
    """Translates between Responses API Items and Chat Completions Messages"""

    @staticmethod
    def items_to_messages(items: List[Dict[str, Any]]) -> List[ChatMessage]:
        """Convert Responses API input items to Chat Completions messages.

        Translations:
        - MessageInputItem → ChatMessage with role
        - FunctionCallOutputItem → ChatMessage with role="tool"

        Args:
            items: List of input items from Responses API

        Returns:
            List of ChatMessage objects for ToolCallingService
        """
        messages = []

        for item in items:
            item_type = item.get("type")

            if item_type == "message":
                # Message input item
                role = item.get("role")
                content = item.get("content")

                # Convert content parts to string if needed
                if isinstance(content, list):
                    content_str = ItemMessageTranslator._content_parts_to_string(content)
                else:
                    content_str = content

                messages.append(
                    ChatMessage(
                        role=role,
                        content=content_str
                    )
                )

            elif item_type == "function_call_output":
                # Function call output item (tool result)
                call_id = item.get("call_id")
                output = item.get("output")

                # Translate call_id → tool_call_id
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=output if isinstance(output, str) else json.dumps(output),
                        tool_call_id=call_id
                    )
                )

            else:
                logger.warning(f"Unknown input item type: {item_type}")

        return messages

    @staticmethod
    def messages_to_output_items(messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """Convert Chat Completions messages to Responses API output items.

        Translations:
        - Assistant message with text → MessageOutputItem
        - Assistant message with tool_calls → FunctionCallItem(s)
        - Tool message → FunctionCallOutputItem

        Args:
            messages: List of ChatMessage objects from LLM response

        Returns:
            List of output items for Responses API
        """
        output_items = []
        message_id_counter = 1

        for message in messages:
            if message.role == "assistant":
                # Generate unique message/call IDs
                msg_id = f"msg_{message_id_counter:08d}"
                message_id_counter += 1

                # Check for tool calls
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    # Create function call items for each tool call
                    for tool_call in message.tool_calls:
                        output_items.append({
                            "type": "function_call",
                            "id": tool_call.id,
                            "call_id": tool_call.id,
                            "name": tool_call.function.get("name"),
                            "arguments": tool_call.function.get("arguments"),
                            "status": "completed"
                        })
                else:
                    # Regular assistant message with content
                    content = message.content

                    # Convert to output text content format
                    if isinstance(content, str):
                        content_formatted = [
                            {
                                "type": "output_text",
                                "text": content
                            }
                        ]
                    else:
                        content_formatted = content

                    output_items.append({
                        "type": "message",
                        "id": msg_id,
                        "role": "assistant",
                        "content": content_formatted,
                        "status": "completed"
                    })

            elif message.role == "tool":
                # Tool result message
                tool_call_id = getattr(message, 'tool_call_id', None)
                if tool_call_id:
                    output_items.append({
                        "type": "function_call_output",
                        "id": f"out_{message_id_counter:08d}",
                        "call_id": tool_call_id,
                        "output": message.content
                    })
                    message_id_counter += 1

        return output_items

    @staticmethod
    def _content_parts_to_string(content_parts: List[Dict[str, Any]]) -> str:
        """Convert content parts array to string.

        Args:
            content_parts: List of content part objects

        Returns:
            Combined string content
        """
        text_parts = []

        for part in content_parts:
            part_type = part.get("type")

            if part_type == "input_text":
                text_parts.append(part.get("text", ""))
            elif part_type == "text":
                text_parts.append(part.get("text", ""))
            # Handle other types (images, etc.) in the future

        return " ".join(text_parts)

    @staticmethod
    def tool_calls_to_function_call_items(tool_calls: List[ToolCall]) -> List[Dict[str, Any]]:
        """Convert ToolCall objects to function call items.

        Args:
            tool_calls: List of ToolCall objects from LLM

        Returns:
            List of function call items
        """
        items = []

        for tool_call in tool_calls:
            items.append({
                "type": "function_call",
                "id": tool_call.id,
                "call_id": tool_call.id,
                "name": tool_call.function.get("name"),
                "arguments": tool_call.function.get("arguments"),
                "status": "completed"
            })

        return items

    @staticmethod
    def extract_text_from_output_items(output_items: List[Dict[str, Any]]) -> str:
        """Extract text content from output items for convenience.

        Args:
            output_items: List of output items

        Returns:
            Combined text content from all message items
        """
        text_parts = []

        for item in output_items:
            if item.get("type") == "message":
                content = item.get("content")

                if isinstance(content, str):
                    text_parts.append(content)
                elif isinstance(content, list):
                    for part in content:
                        if part.get("type") == "output_text":
                            text_parts.append(part.get("text", ""))

        return " ".join(text_parts) if text_parts else None

    @staticmethod
    def normalize_input(input_data: Union[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Normalize input to items format.

        Args:
            input_data: Either a string or list of items

        Returns:
            List of input items
        """
        if isinstance(input_data, str):
            # Convert string to message item
            return [
                {
                    "type": "message",
                    "role": "user",
                    "content": input_data
                }
            ]
        else:
            # Already in items format
            return input_data

    @staticmethod
    def create_assistant_message_item(content: str, item_id: str = None) -> Dict[str, Any]:
        """Create an assistant message output item.

        Args:
            content: Text content
            item_id: Optional item ID

        Returns:
            Message output item
        """
        if not item_id:
            import time
            item_id = f"msg_{int(time.time() * 1000):016d}"

        return {
            "type": "message",
            "id": item_id,
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": content
                }
            ],
            "status": "completed"
        }

    @staticmethod
    def create_error_output(error_message: str, error_code: str = "internal_error") -> Dict[str, Any]:
        """Create error output structure.

        Args:
            error_message: Error description
            error_code: Error code

        Returns:
            Error object for response
        """
        return {
            "type": error_code,
            "code": error_code,
            "message": error_message
        }
