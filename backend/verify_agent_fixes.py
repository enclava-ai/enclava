#!/usr/bin/env python3
"""
Verification script for agent & tool calling fixes.

This script can be run in a development environment to verify:
1. Agent chatbot instance exists in database
2. Built-in tools are properly registered
3. Tool validation works for built-in and MCP tools

Usage:
    python verify_agent_fixes.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))


async def verify_agent_chatbot_instance():
    """Verify the special agent chatbot instance exists in database."""
    print("\n=== P1: Verifying Agent Chatbot Instance ===")

    try:
        from app.services.agent_init import AGENT_CHATBOT_ID
        from app.db.database import async_session_factory
        from app.models.chatbot import ChatbotInstance
        from sqlalchemy import select

        print(f"✓ AGENT_CHATBOT_ID constant defined: '{AGENT_CHATBOT_ID}'")

        async with async_session_factory() as db:
            stmt = select(ChatbotInstance).where(ChatbotInstance.id == AGENT_CHATBOT_ID)
            result = await db.execute(stmt)
            agent_instance = result.scalar_one_or_none()

            if agent_instance:
                print(f"✓ Agent chatbot instance exists in database")
                print(f"  - ID: {agent_instance.id}")
                print(f"  - Name: {agent_instance.name}")
                print(f"  - Created by: {agent_instance.created_by}")
                print(f"  - Active: {agent_instance.is_active}")
                return True
            else:
                print("✗ Agent chatbot instance NOT found in database")
                print("  Run the application to create it automatically")
                return False

    except Exception as e:
        print(f"✗ Error verifying agent chatbot instance: {e}")
        return False


def verify_builtin_tools():
    """Verify built-in tools are registered."""
    print("\n=== P2a: Verifying Built-in Tools Registration ===")

    try:
        from app.services.builtin_tools.registry import BuiltinToolRegistry
        from app.services.builtin_tools import register_builtin_tools

        # Clear and re-register
        BuiltinToolRegistry.clear()
        register_builtin_tools()

        all_tools = BuiltinToolRegistry.get_all()
        print(f"✓ Built-in tools registered: {len(all_tools)} tools")

        expected_tools = ["rag_search", "web_search", "code_execution"]
        for tool_name in expected_tools:
            if BuiltinToolRegistry.is_builtin(tool_name):
                tool = BuiltinToolRegistry.get(tool_name)
                print(f"  ✓ {tool_name}: {tool.display_name}")
            else:
                print(f"  ✗ {tool_name}: NOT FOUND")
                return False

        return True

    except Exception as e:
        print(f"✗ Error verifying built-in tools: {e}")
        return False


def verify_mcp_configuration():
    """Verify MCP server configuration detection."""
    print("\n=== P2b: Verifying MCP Configuration ===")

    try:
        from app.services.tool_calling_service import ToolCallingService
        from unittest.mock import AsyncMock

        mock_db = AsyncMock()
        service = ToolCallingService(mock_db)

        # Check for any configured MCP servers
        test_servers = ["order-api", "customer-api", "test-server"]
        found_servers = []

        for server in test_servers:
            config = service._get_mcp_config(server)
            if config:
                found_servers.append((server, config))

        if found_servers:
            print(f"✓ Found {len(found_servers)} configured MCP server(s):")
            for server, config in found_servers:
                print(f"  - {server}: {config.get('url')}")
        else:
            print("ℹ No MCP servers configured (this is optional)")
            print("  To configure MCP servers, set environment variables:")
            print("  - MCP_<SERVER_NAME>_URL")
            print("  - MCP_<SERVER_NAME>_KEY (optional)")

        return True

    except Exception as e:
        print(f"✗ Error verifying MCP configuration: {e}")
        return False


async def verify_tool_validation():
    """Verify tool validation works correctly."""
    print("\n=== P2c: Verifying Tool Validation Logic ===")

    try:
        from app.services.tool_calling_service import ToolCallingService
        from app.services.builtin_tools import register_builtin_tools
        from unittest.mock import AsyncMock, MagicMock

        # Register built-in tools
        register_builtin_tools()

        # Create service
        mock_db = AsyncMock()
        service = ToolCallingService(mock_db)

        # Mock tool management to return no custom tools
        mock_tool_mgmt = MagicMock()
        mock_tool_mgmt.get_tool_by_name_and_user = AsyncMock(return_value=None)
        mock_tool_mgmt.get_tools = AsyncMock(return_value=[])
        service.tool_mgmt = mock_tool_mgmt

        # Mock user
        mock_user = {"id": 1, "email": "test@example.com"}

        # Test validation
        result = await service.validate_tool_availability(
            ["rag_search", "web_search", "code_execution", "nonexistent_tool"],
            mock_user
        )

        print("✓ Tool validation results:")
        for tool_name, available in result.items():
            status = "✓" if available else "✗"
            print(f"  {status} {tool_name}: {available}")

        # Verify built-in tools are available
        if result["rag_search"] and result["web_search"] and result["code_execution"]:
            print("✓ All built-in tools correctly validated as available")
            return True
        else:
            print("✗ Built-in tools not correctly validated")
            return False

    except Exception as e:
        print(f"✗ Error verifying tool validation: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all verification checks."""
    print("=" * 60)
    print("Agent & Tool Calling Fixes Verification")
    print("=" * 60)

    results = {
        "Agent Chatbot Instance": await verify_agent_chatbot_instance(),
        "Built-in Tools": verify_builtin_tools(),
        "MCP Configuration": verify_mcp_configuration(),
        "Tool Validation": await verify_tool_validation(),
    }

    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)

    all_passed = True
    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✓ All verification checks passed!")
        return 0
    else:
        print("\n✗ Some verification checks failed")
        print("Please review the output above for details")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nVerification cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
