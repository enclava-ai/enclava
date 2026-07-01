"""
Default extraction templates.

These templates are seeded on first run and can be edited/deleted
by users. The reset_defaults() function restores them.
"""

DETAILED_INVOICE_SYSTEM_PROMPT = """You are an expert invoice data extraction AI. Extract structured data from invoice images with high accuracy.

CRITICAL RULES:
1. Return ONLY valid JSON with no additional text or markdown formatting
2. Dates MUST be in YYYY-MM-DD format
3. For ambiguous dates like 01/02/2024, prefer DD/MM/YYYY interpretation (European format)
4. Addresses MUST include: street/number, city, postal code, and country
5. Currency codes should be ISO 4217 (EUR, USD, GBP, etc.)
6. Tax rates should be decimal (0.22 for 22%, not 22)
7. Payment methods: creditcard, banktransfer, cash, other
8. If a field is not visible or unclear, use null

IMPORTANT: The service_provider is the company that issued the invoice (seller/vendor).
The buyer is the recipient of the invoice (customer/client)."""

DETAILED_INVOICE_USER_PROMPT = """Extract all invoice information from this image.
{buyer_context}

Return JSON with this exact structure:
{
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "payment_date": "YYYY-MM-DD or null",
  "service_date": "YYYY-MM-DD or null",
  "service_provider": {
    "name": "Company name or null",
    "address": "Street Number, City PostalCode, Country or null",
    "tax_id": "VAT/Tax ID or null",
    "phone": "Phone number or null",
    "email": "Email or null",
    "website": "Website URL or null"
  },
  "buyer": {
    "name": "Buyer/customer name or null",
    "address": "Full address or null",
    "tax_id": "VAT/Tax ID or null",
    "phone": "Phone or null",
    "email": "Email or null"
  },
  "amount": 0.00,
  "currency": "EUR",
  "description": "Brief description of goods/services or null",
  "payment_method": "creditcard|banktransfer|cash|other or null",
  "line_items": [
    {
      "description": "Item description",
      "quantity": 1.0,
      "unit_price": 0.00,
      "total": 0.00,
      "tax_rate": 0.22
    }
  ],
  "subtotal": 0.00,
  "tax_amount": 0.00,
  "tax_rate": 0.22,
  "total_amount": 0.00
}"""

SIMPLE_RECEIPT_SYSTEM_PROMPT = """You are a receipt data extraction AI. Extract key information from receipt images.
Return ONLY valid JSON with no additional text."""

SIMPLE_RECEIPT_USER_PROMPT = """Extract receipt information from this image.

Return JSON:
{
  "merchant_name": "Store/merchant name or null",
  "merchant_address": "Address or null",
  "date": "YYYY-MM-DD or null",
  "time": "HH:MM or null",
  "items": [
    {"name": "Item name", "price": 0.00}
  ],
  "subtotal": 0.00,
  "tax": 0.00,
  "total": 0.00,
  "payment_method": "card|cash|other or null"
}"""

EXPENSE_REPORT_SYSTEM_PROMPT = """You are an expense extraction AI. Extract expense-relevant information from receipts and invoices.
Return ONLY valid JSON with no additional text."""

EXPENSE_REPORT_USER_PROMPT = """Extract expense information from this document.
{buyer_context}

Return JSON:
{
  "vendor": "Vendor/merchant name",
  "date": "YYYY-MM-DD",
  "amount": 0.00,
  "currency": "EUR",
  "category": "travel|meals|supplies|software|other",
  "description": "Brief description",
  "payment_method": "corporate_card|personal|cash|other",
  "tax_amount": 0.00,
  "is_reimbursable": true
}"""


DEFAULT_TEMPLATES = [
    {
        "id": "detailed_invoice",
        "description": "Comprehensive extraction for invoices with line items, addresses, and tax details",
        "system_prompt": DETAILED_INVOICE_SYSTEM_PROMPT,
        "user_prompt": DETAILED_INVOICE_USER_PROMPT,
        "output_schema": None,  # Could add JSON schema for validation
        "context_schema": {
            "company_name": {
                "type": "string",
                "label": "Your Company Name",
                "description": "The name of your company to help identify the buyer in invoices",
                "required": False,
                "placeholder": "Acme Corporation",
            },
            "currency": {
                "type": "string",
                "label": "Expected Currency",
                "description": "The expected currency for amounts (e.g., USD, EUR, GBP)",
                "required": False,
                "placeholder": "USD",
            },
        },
        "is_default": True,
        "is_active": True,
    },
    {
        "id": "simple_receipt",
        "description": "Basic extraction for retail receipts",
        "system_prompt": SIMPLE_RECEIPT_SYSTEM_PROMPT,
        "user_prompt": SIMPLE_RECEIPT_USER_PROMPT,
        "output_schema": None,
        "context_schema": None,  # No context needed for simple receipts
        "is_default": True,
        "is_active": True,
    },
    {
        "id": "expense_report",
        "description": "Expense-focused extraction with category classification",
        "system_prompt": EXPENSE_REPORT_SYSTEM_PROMPT,
        "user_prompt": EXPENSE_REPORT_USER_PROMPT,
        "output_schema": None,
        "context_schema": {
            "employee_name": {
                "type": "string",
                "label": "Employee Name",
                "description": "Name of the employee submitting the expense",
                "required": False,
                "placeholder": "John Doe",
            },
            "department": {
                "type": "string",
                "label": "Department",
                "description": "Employee's department",
                "required": False,
                "placeholder": "Engineering",
            },
        },
        "is_default": True,
        "is_active": True,
    },
]
