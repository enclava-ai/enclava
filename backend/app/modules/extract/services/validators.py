"""
Extracted data validation.

Validates Extract output against expected formats and business rules.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of data validation."""

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


class DataValidator:
    """
    Validates extracted invoice/receipt data.

    Validation rules:
    - Addresses must be complete (street, city, country)
    - Amounts must be valid numbers
    - Dates must be YYYY-MM-DD format
    - Required fields must be present
    """

    DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    def validate(self, data: dict, template) -> ValidationResult:
        """
        Run all validations on extracted data.

        Args:
            data: Extracted data dictionary
            template: Template used (for output schema validation)

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult()

        if "_parse_error" in data:
            result.errors.append(f"JSON parse error: {data['_parse_error']}")
            return result

        # Validate service provider
        self._validate_service_provider(data.get("service_provider"), result)

        # Validate addresses
        if sp := data.get("service_provider"):
            self._validate_address(
                sp.get("address"), "service_provider.address", result
            )
        if buyer := data.get("buyer"):
            self._validate_address(buyer.get("address"), "buyer.address", result)

        # Validate dates
        for date_field in ["invoice_date", "due_date", "payment_date", "service_date"]:
            if date_value := data.get(date_field):
                self._validate_date(date_value, date_field, result)

        # Validate amounts
        for amount_field in ["amount", "subtotal", "tax_amount", "total_amount"]:
            if amount_value := data.get(amount_field):
                self._validate_amount(amount_value, amount_field, result)

        # Validate line items
        if line_items := data.get("line_items"):
            self._validate_line_items(line_items, result)

        return result

    def _validate_service_provider(
        self,
        provider: Optional[dict],
        result: ValidationResult,
    ):
        """Validate service provider structure."""
        if not provider:
            result.errors.append("service_provider is missing")
            return

        if not provider.get("name"):
            result.errors.append("service_provider.name is missing")

        if not provider.get("address"):
            result.errors.append("service_provider.address is missing")

    def _validate_address(
        self,
        address: Optional[str],
        field_name: str,
        result: ValidationResult,
    ):
        """
        Validate address completeness.

        A complete address should have at least:
        - Street/number
        - City
        - Country

        Heuristic: Minimum 2 commas separating components
        """
        if not address:
            return  # Missing addresses handled elsewhere

        if len(address) < 5:
            result.errors.append(f"{field_name} is too short")
            return

        comma_count = address.count(",")
        if comma_count < 2:
            result.warnings.append(
                f"{field_name} may be incomplete (expected: Street, City, Country)"
            )

    def _validate_date(
        self,
        date_value: str,
        field_name: str,
        result: ValidationResult,
    ):
        """Validate date format (YYYY-MM-DD)."""
        if not self.DATE_PATTERN.match(date_value):
            result.errors.append(
                f"{field_name} has invalid format: '{date_value}' (expected: YYYY-MM-DD)"
            )

    def _validate_amount(
        self,
        amount_value,
        field_name: str,
        result: ValidationResult,
    ):
        """Validate amount is a valid number."""
        try:
            float(amount_value)
        except (ValueError, TypeError):
            result.errors.append(
                f"{field_name} is not a valid number: '{amount_value}'"
            )

    def _validate_line_items(
        self,
        line_items: list,
        result: ValidationResult,
    ):
        """Validate line items structure."""
        if not isinstance(line_items, list):
            result.errors.append("line_items must be a list")
            return

        for i, item in enumerate(line_items):
            if not isinstance(item, dict):
                result.errors.append(f"line_items[{i}] is not an object")
                continue

            # Check required fields
            if not item.get("description"):
                result.warnings.append(f"line_items[{i}].description is missing")
