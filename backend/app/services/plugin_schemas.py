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


def get_signal_configuration_schema() -> Dict[str, Any]:
    """
    Returns the configuration schema for the Signal Bot plugin.
    Based on the existing Signal module implementation.
    """
    return {
        "type": "object",
        "title": "Signal Bot Configuration", 
        "description": "Configure AI-powered Signal messaging bot with role-based permissions",
        "properties": {
            # Basic Settings
            "enable_signal_bot": {
                "type": "boolean",
                "title": "Enable Signal Bot",
                "description": "Turn the Signal bot on/off",
                "default": False,
                "required": True
            },
            "signal_service_url": {
                "type": "url",
                "title": "Signal Service URL",
                "description": "Signal service endpoint (e.g., signal-cli-rest-api)",
                "required": True,
                "placeholder": "http://localhost:8080",
                "depends_on": {
                    "field": "enable_signal_bot", 
                    "value": True
                }
            },
            "bot_phone_number": {
                "type": "string",
                "title": "Bot Phone Number",
                "description": "Registered Signal phone number for the bot",
                "required": True,
                "placeholder": "+1234567890",
                "pattern": "^\\+[1-9]\\d{1,14}$",
                "depends_on": {
                    "field": "enable_signal_bot",
                    "value": True
                }
            },
            
            # AI Settings
            "model": {
                "type": "select",
                "title": "AI Model", 
                "description": "Choose the AI model for responses",
                "required": False,
                "default": "privatemode-llama-3-70b",
                "options": [],  # Will be populated from available models
                "depends_on": {
                    "field": "enable_signal_bot",
                    "value": True
                }
            },
            "temperature": {
                "type": "number",
                "title": "Response Creativity",
                "description": "Control response creativity (0.0-1.0)", 
                "required": False,
                "default": 0.7,
                "minimum": 0.0,
                "maximum": 1.0,
                "depends_on": {
                    "field": "enable_signal_bot",
                    "value": True
                }
            },
            "max_tokens": {
                "type": "integer",
                "title": "Max Response Length",
                "description": "Maximum tokens in AI responses",
                "required": False,
                "default": 500,
                "minimum": 50,
                "maximum": 2000,
                "depends_on": {
                    "field": "enable_signal_bot", 
                    "value": True
                }
            },
            "memory_length": {
                "type": "integer",
                "title": "Conversation Memory",
                "description": "Number of message pairs to remember per user",
                "required": False,
                "default": 10,
                "minimum": 1,
                "maximum": 50,
                "depends_on": {
                    "field": "enable_signal_bot",
                    "value": True
                }
            },
            
            # Permission Settings
            "default_role": {
                "type": "select", 
                "title": "Default User Role",
                "description": "Role assigned to new Signal users",
                "required": False,
                "default": "user",
                "options": [
                    {"value": "admin", "label": "Admin"},
                    {"value": "user", "label": "User"}, 
                    {"value": "disabled", "label": "Disabled"}
                ],
                "depends_on": {
                    "field": "enable_signal_bot",
                    "value": True
                }
            },
            "auto_register": {
                "type": "boolean",
                "title": "Auto-Register New Users", 
                "description": "Automatically register new Signal users",
                "default": True,
                "required": False,
                "depends_on": {
                    "field": "enable_signal_bot",
                    "value": True
                }
            },
            "admin_phone_numbers": {
                "type": "textarea",
                "title": "Admin Phone Numbers",
                "description": "Phone numbers with admin privileges (one per line)",
                "required": False,
                "placeholder": "+1234567890\n+0987654321",
                "rows": 3,
                "depends_on": {
                    "field": "enable_signal_bot",
                    "value": True
                }
            },
            
            # Bot Behavior
            "command_prefix": {
                "type": "string",
                "title": "Command Prefix", 
                "description": "Prefix for bot commands",
                "required": False,
                "default": "!",
                "placeholder": "!",
                "depends_on": {
                    "field": "enable_signal_bot",
                    "value": True
                }
            },
            "log_conversations": {
                "type": "boolean",
                "title": "Log Conversations",
                "description": "Enable conversation logging for analytics",
                "default": False,
                "required": False,
                "depends_on": {
                    "field": "enable_signal_bot", 
                    "value": True
                }
            }
        },
        "required": ["enable_signal_bot"],
        "field_groups": [
            {
                "title": "Basic Settings",
                "fields": ["enable_signal_bot", "signal_service_url", "bot_phone_number"]
            },
            {
                "title": "AI Configuration",
                "fields": ["model", "temperature", "max_tokens", "memory_length"]
            },
            {
                "title": "Permission Settings", 
                "fields": ["default_role", "auto_register", "admin_phone_numbers"]
            },
            {
                "title": "Bot Behavior",
                "fields": ["command_prefix", "log_conversations"]
            }
        ],
        "validation": {
            "signal_test": {
                "endpoint": "/api/v1/signal/test-connection",
                "method": "POST",
                "fields": ["signal_service_url", "bot_phone_number"],
                "success_message": "Signal service connection successful",
                "error_field": "Signal connection failed"
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
        "signal": get_signal_configuration_schema,
        "email-assistant": get_email_assistant_configuration_schema
    }
    
    schema_func = schemas.get(plugin_id)
    return schema_func() if schema_func else None


