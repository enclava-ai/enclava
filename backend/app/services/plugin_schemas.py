"""
Plugin Configuration Schemas
Defines the configuration schemas for different plugins in the system.
"""

from typing import Dict, Any, List, Optional


def get_zammad_configuration_schema() -> Dict[str, Any]:
    """
    Returns the configuration schema for the Zammad Integration plugin.
    Based on the existing Zammad module implementation from enclava-jo.
    """
    return {
        "type": "object",
        "title": "Zammad Integration Configuration",
        "description": "Configure AI-powered ticket summarization for Zammad ticketing system",
        "properties": {
            # Basic Settings
            "name": {
                "type": "string",
                "title": "Configuration Name",
                "description": "A descriptive name for this configuration",
                "required": True,
                "placeholder": "My Zammad Instance"
            },
            "description": {
                "type": "string", 
                "title": "Description",
                "description": "Optional description of this configuration",
                "required": False,
                "placeholder": "Production Zammad instance for customer support"
            },
            "is_default": {
                "type": "boolean",
                "title": "Default Configuration", 
                "description": "Set as the default configuration for processing",
                "default": False,
                "required": False
            },
            
            # Zammad Connection Settings
            "zammad_url": {
                "type": "url",
                "title": "Zammad URL",
                "description": "The base URL of your Zammad instance",
                "required": True,
                "placeholder": "https://your-zammad.example.com",
                "pattern": "^https?://.+"
            },
            "api_token": {
                "type": "password",
                "title": "API Token",
                "description": "Your Zammad API access token (will be encrypted)",
                "required": True,
                "placeholder": "Your Zammad API token"
            },
            
            # AI Integration
            "chatbot_id": {
                "type": "select",
                "title": "AI Chatbot",
                "description": "Select the chatbot to use for generating ticket summaries",
                "required": True,
                "options": [],  # Will be populated dynamically from available chatbots
                "placeholder": "Select a chatbot"
            },
            
            # Processing Settings
            "process_state": {
                "type": "select",
                "title": "Ticket State to Process",
                "description": "Which ticket state should be processed",
                "required": False,
                "default": "open",
                "options": [
                    {"value": "open", "label": "Open"},
                    {"value": "pending", "label": "Pending"}, 
                    {"value": "closed", "label": "Closed"},
                    {"value": "all", "label": "All States"}
                ]
            },
            "max_tickets": {
                "type": "integer",
                "title": "Max Tickets Per Run",
                "description": "Maximum number of tickets to process in a single batch",
                "required": False,
                "default": 10,
                "minimum": 1,
                "maximum": 100
            },
            "skip_existing": {
                "type": "boolean",
                "title": "Skip Already Processed",
                "description": "Skip tickets that already have AI summaries",
                "default": True,
                "required": False
            },
            
            # Automation Settings
            "auto_process": {
                "type": "boolean", 
                "title": "Enable Auto Processing",
                "description": "Automatically process new tickets at regular intervals",
                "default": False,
                "required": False
            },
            "process_interval": {
                "type": "integer",
                "title": "Processing Interval (minutes)",
                "description": "How often to automatically process tickets (only if auto-process is enabled)",
                "required": False,
                "default": 30,
                "minimum": 5,
                "maximum": 1440,
                "depends_on": {
                    "field": "auto_process",
                    "value": True
                }
            },
            
            # Customization
            "summary_template": {
                "type": "textarea",
                "title": "AI Summary Template",
                "description": "Custom template for generating AI summaries. Leave empty for default.",
                "required": False,
                "placeholder": "Generate a concise summary of this support ticket including key issues, customer concerns, and any actions taken.",
                "rows": 3
            }
        },
        "required": ["name", "zammad_url", "api_token", "chatbot_id"],
        "field_groups": [
            {
                "title": "Basic Information",
                "fields": ["name", "description", "is_default"]
            },
            {
                "title": "Zammad Connection", 
                "fields": ["zammad_url", "api_token"]
            },
            {
                "title": "AI Configuration",
                "fields": ["chatbot_id", "summary_template"] 
            },
            {
                "title": "Processing Settings",
                "fields": ["process_state", "max_tickets", "skip_existing"]
            },
            {
                "title": "Automation",
                "fields": ["auto_process", "process_interval"]
            }
        ],
        "validation": {
            "connection_test": {
                "endpoint": "/api/v1/zammad/test-connection",
                "method": "POST", 
                "fields": ["zammad_url", "api_token"],
                "success_message": "Connection to Zammad successful",
                "error_field": "Connection failed"
            }
        }
    }




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
                "required": True
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
                    {"value": "exchange", "label": "Exchange Server"}
                ],
                "depends_on": {
                    "field": "enable_email_assistant",
                    "value": True
                }
            },
            "email_address": {
                "type": "email",
                "title": "Email Address",
                "description": "Your email address for the assistant to monitor",
                "required": True,
                "placeholder": "your-email@example.com",
                "depends_on": {
                    "field": "enable_email_assistant",
                    "value": True
                }
            },
            
            # AI Configuration
            "auto_response_enabled": {
                "type": "boolean",
                "title": "Enable Auto-Response",
                "description": "Automatically respond to incoming emails",
                "default": False,
                "required": False,
                "depends_on": {
                    "field": "enable_email_assistant",
                    "value": True
                }
            },
            "response_template": {
                "type": "textarea",
                "title": "Auto-Response Template",
                "description": "Template for automatic responses",
                "required": False,
                "placeholder": "Thank you for your email. I'll respond within 24 hours.",
                "rows": 3,
                "depends_on": {
                    "field": "auto_response_enabled",
                    "value": True
                }
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
                "depends_on": {
                    "field": "enable_email_assistant",
                    "value": True
                }
            }
        },
        "required": ["enable_email_assistant"],
        "field_groups": [
            {
                "title": "Basic Settings",
                "fields": ["enable_email_assistant", "email_provider", "email_address"]
            },
            {
                "title": "Auto-Response",
                "fields": ["auto_response_enabled", "response_template"]
            },
            {
                "title": "Processing Settings",
                "fields": ["check_interval"]
            }
        ]
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
        "zammad": get_zammad_configuration_schema,
        "email-assistant": get_email_assistant_configuration_schema
    }
    
    schema_func = schemas.get(plugin_id)
    return schema_func() if schema_func else None


