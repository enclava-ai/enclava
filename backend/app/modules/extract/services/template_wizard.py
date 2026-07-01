"""
Template Wizard service.

Analyzes sample documents and generates appropriate extraction templates.
"""

import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm.models import ChatRequest
from app.services.llm.service import llm_service

logger = logging.getLogger(__name__)


WIZARD_SYSTEM_PROMPT = """You are an expert at analyzing documents and creating data extraction templates.

Your task is to:
1. Analyze the provided document image
2. Identify the document type (invoice, receipt, contract, form, report, etc.)
3. Identify all relevant fields that should be extracted
4. Generate a comprehensive extraction template

Return ONLY valid JSON with no additional text."""

WIZARD_USER_PROMPT = """Analyze this document and create an extraction template.

Identify:
1. Document type (e.g., invoice, receipt, contract, expense_report, purchase_order, etc.)
2. All fields visible in the document that should be extracted
3. Appropriate field types and validation rules

Return JSON with this structure:
{
  "document_type": "invoice|receipt|contract|form|report|other",
  "suggested_template_id": "descriptive_id_with_underscores",
  "description": "Brief description of what this template extracts",
  "fields": [
    {"name": "field_name", "type": "string|number|date|array|object", "required": true|false, "description": "what this field contains"}
  ],
  "system_prompt": "System instructions for extraction AI - be specific about format, validation rules",
  "user_prompt": "User prompt with exact JSON structure to extract - include all identified fields"
}

Make the prompts comprehensive and specific. Include:
- Date format requirements (YYYY-MM-DD)
- Validation rules (addresses must include city, postal code, country)
- Field types (ISO currency codes, decimal tax rates)
- Handling of missing/unclear fields (use null)
- Complete JSON schema in user_prompt showing expected output structure"""


class TemplateWizardService:
    """Service for generating templates from sample documents."""

    async def analyze_document(
        self,
        image_b64: str,
        model_name: str = "gpt-4o",
        db: Optional[AsyncSession] = None,
        user_id: Optional[int] = None,
        api_key_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a document image and generate a template.

        Args:
            image_b64: Base64-encoded document image
            model_name: Vision model to use
            db: Database session for usage recording
            user_id: User ID for attribution
            api_key_id: API key ID for attribution (None for JWT auth)

        Returns:
            Dictionary with template suggestions
        """
        # Build messages with image
        messages = [
            {"role": "system", "content": WIZARD_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                            "detail": "high",
                        },
                    },
                    {"type": "text", "text": WIZARD_USER_PROMPT},
                ],
            },
        ]

        # Call LLM service with usage tracking
        llm_request = ChatRequest(
            model=model_name,
            messages=messages,
            response_format={"type": "json_object"},
            user_id=str(user_id) if user_id else "system",
            api_key_id=api_key_id,
        )

        logger.info("Analyzing document with template wizard")
        response = await llm_service.create_chat_completion(
            llm_request,
            db=db,
            user_id=user_id,
            api_key_id=api_key_id,
            endpoint="extract/templates/wizard",
        )

        # Parse response
        content = response.choices[0].message.content
        try:
            template_data = json.loads(content)
            logger.info(
                "Template wizard analysis complete: %s",
                template_data.get("document_type"),
            )
            return template_data
        except json.JSONDecodeError as e:
            logger.error("Failed to parse wizard response: %s", e)
            # Return a fallback template
            return {
                "document_type": "unknown",
                "suggested_template_id": "custom_document",
                "description": "Custom document extraction",
                "fields": [],
                "system_prompt": "Extract data from this document. Return valid JSON only.",
                "user_prompt": "Extract all visible information from this document and return as JSON.",
                "error": "Failed to parse AI response",
                "raw_response": content,
            }

    def validate_template(self, template_data: Dict[str, Any]) -> bool:
        """
        Validate that wizard-generated template has required fields.

        Args:
            template_data: Template data from wizard

        Returns:
            True if valid
        """
        required_fields = [
            "suggested_template_id",
            "description",
            "system_prompt",
            "user_prompt",
        ]

        for field in required_fields:
            if field not in template_data or not template_data[field]:
                logger.warning("Template missing required field: %s", field)
                return False

        return True

    def format_template_for_creation(
        self, template_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format wizard output into template creation schema.

        Args:
            template_data: Raw wizard output

        Returns:
            Template creation payload
        """
        return {
            "id": template_data.get("suggested_template_id", "custom_template"),
            "description": template_data.get("description", "AI-generated template"),
            "system_prompt": template_data.get("system_prompt"),
            "user_prompt": template_data.get("user_prompt"),
            "output_schema": None,  # Could be populated from fields
        }
