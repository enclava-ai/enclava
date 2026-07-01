"""
Plugin Configuration Schemas
Defines the configuration schemas for different plugins in the system.
"""

from typing import Any, Dict, Optional


def get_email_assistant_configuration_schema() -> Dict[str, Any]:
    """
    Returns the configuration schema for the Email Assistant plugin.
    """
    return {
        "type": "object",
        "title": "Email Assistant Configuration",
        "description": "Configure AI-powered email management and auto-response system",
        "properties": {
            # Basic Settings
            "enable_email_assistant": {
                "type": "boolean",
                "title": "Enable Email Assistant",
                "description": "Turn the email assistant on/off",
                "default": False,
                "required": True,
            },
            "email_provider": {
                "type": "select",
                "title": "Email Provider",
                "description": "Select your email service provider",
                "required": True,
                "options": [
                    {"value": "gmail", "label": "Gmail"},
                    {"value": "outlook", "label": "Outlook/Hotmail"},
                    {"value": "imap", "label": "Generic IMAP"},
                    {"value": "exchange", "label": "Exchange Server"},
                ],
                "depends_on": {"field": "enable_email_assistant", "value": True},
            },
            "email_address": {
                "type": "email",
                "title": "Email Address",
                "description": "Your email address for the assistant to monitor",
                "required": True,
                "placeholder": "your-email@example.com",
                "depends_on": {"field": "enable_email_assistant", "value": True},
            },
            # AI Configuration
            "auto_response_enabled": {
                "type": "boolean",
                "title": "Enable Auto-Response",
                "description": "Automatically respond to incoming emails",
                "default": False,
                "required": False,
                "depends_on": {"field": "enable_email_assistant", "value": True},
            },
            "response_template": {
                "type": "textarea",
                "title": "Auto-Response Template",
                "description": "Template for automatic responses",
                "required": False,
                "placeholder": "Thank you for your email. I'll respond within 24 hours.",
                "rows": 3,
                "depends_on": {"field": "auto_response_enabled", "value": True},
            },
            # Processing Settings
            "check_interval": {
                "type": "integer",
                "title": "Check Interval (minutes)",
                "description": "How often to check for new emails",
                "required": False,
                "default": 15,
                "minimum": 1,
                "maximum": 1440,
                "depends_on": {"field": "enable_email_assistant", "value": True},
            },
        },
        "required": ["enable_email_assistant"],
        "field_groups": [
            {
                "title": "Basic Settings",
                "fields": ["enable_email_assistant", "email_provider", "email_address"],
            },
            {
                "title": "Auto-Response",
                "fields": ["auto_response_enabled", "response_template"],
            },
            {"title": "Processing Settings", "fields": ["check_interval"]},
        ],
    }


def get_plugin_configuration_schema(plugin_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the configuration schema for a specific plugin.

    Args:
        plugin_id: The ID of the plugin

    Returns:
        The configuration schema dictionary or None if not found
    """
    schemas = {
        "email-assistant": get_email_assistant_configuration_schema,
    }

    schema_func = schemas.get(plugin_id)
    return schema_func() if schema_func else None
