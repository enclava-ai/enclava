"""
Smart reprocessing service.

Generates enhanced prompts based on validation errors and retries extraction.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ReprocessingService:
    """
    Handles smart retry logic for failed extractions.

    Analyzes validation errors and generates enhanced prompts with
    specific instructions to fix the issues.
    """

    def __init__(self):
        pass

    def generate_enhanced_prompt(
        self,
        original_prompt: str,
        validation_errors: list,
        validation_warnings: list,
    ) -> str:
        """
        Generate enhanced prompt based on validation errors.

        Args:
            original_prompt: Original extraction prompt
            validation_errors: List of validation errors from first attempt
            validation_warnings: List of validation warnings

        Returns:
            Enhanced prompt with specific instructions
        """
        enhancements = []

        # Analyze errors and add specific instructions
        error_text = " ".join(validation_errors + validation_warnings).lower()

        if "date" in error_text and "format" in error_text:
            enhancements.append(
                "CRITICAL: All dates MUST be in YYYY-MM-DD format. "
                "Convert any dates you see to this exact format."
            )

        if "address" in error_text:
            enhancements.append(
                "CRITICAL: Addresses must include street/number, city, "
                "postal code, and country, separated by commas. "
                "Format: 'Street Number, City PostalCode, Country'"
            )

        if "service_provider" in error_text or "missing" in error_text:
            enhancements.append(
                "CRITICAL: Ensure service_provider.name and "
                "service_provider.address are filled. The service provider "
                "is the company that issued the invoice (the seller/vendor)."
            )

        if "number" in error_text or "amount" in error_text:
            enhancements.append(
                "CRITICAL: All amount fields must be valid numbers (e.g., 123.45). "
                "Do not include currency symbols or commas."
            )

        if not enhancements:
            enhancements.append(
                "CRITICAL: Review the previous extraction and ensure all fields "
                "are properly formatted and complete."
            )

        # Build enhanced prompt
        enhancement_text = "\n\n".join(enhancements)
        enhanced_prompt = f"{original_prompt}\n\n{enhancement_text}"

        logger.debug(
            "Generated enhanced prompt with %d enhancements", len(enhancements)
        )
        return enhanced_prompt
