"""
Provider Registry

Central registry of all supported inference providers with their metadata
including native currency, sync capabilities, and display information.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ProviderMetadata:
    """Metadata for an inference provider"""

    id: str  # Internal identifier (e.g., 'privatemode', 'redpill')
    display_name: str  # Human-readable name
    currency: str  # Native currency code (ISO 4217: 'USD', 'EUR')
    supports_api_sync: bool  # Whether pricing can be synced from API
    description: str  # Brief description of the provider
    website: Optional[str] = None  # Provider website URL


# Registry of all supported providers
# Only confidential computing providers are included
PROVIDER_REGISTRY: Dict[str, ProviderMetadata] = {
    "privatemode": ProviderMetadata(
        id="privatemode",
        display_name="PrivateMode.ai",
        currency="EUR",  # PrivateMode uses Euro pricing
        supports_api_sync=False,  # No public pricing API
        description="Confidential AI inference with TEE protection via privatemode.ai",
        website="https://privatemode.ai",
    ),
    "redpill": ProviderMetadata(
        id="redpill",
        display_name="RedPill.ai",
        currency="USD",  # RedPill uses US Dollar pricing
        supports_api_sync=True,  # Has /v1/models with pricing
        description="TEE-protected inference with full attestation support",
        website="https://redpill.ai",
    ),
}


def get_provider_metadata(provider_id: str) -> Optional[ProviderMetadata]:
    """Get metadata for a provider by ID"""
    return PROVIDER_REGISTRY.get(provider_id.lower())


def get_provider_currency(provider_id: str) -> str:
    """Get the native currency for a provider, defaults to USD"""
    metadata = get_provider_metadata(provider_id)
    return metadata.currency if metadata else "USD"


def get_all_providers() -> List[ProviderMetadata]:
    """Get all registered providers"""
    return list(PROVIDER_REGISTRY.values())


def get_syncable_providers() -> List[str]:
    """Get IDs of providers that support API pricing sync"""
    return [p.id for p in PROVIDER_REGISTRY.values() if p.supports_api_sync]


def is_valid_provider(provider_id: str) -> bool:
    """Check if a provider ID is valid"""
    return provider_id.lower() in PROVIDER_REGISTRY


# Currency formatting helpers
CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}


def get_currency_symbol(currency_code: str) -> str:
    """Get the symbol for a currency code"""
    return CURRENCY_SYMBOLS.get(currency_code.upper(), currency_code)


def format_price_cents(cents: int, currency: str = "USD") -> str:
    """
    Format a price in cents to a display string.

    Args:
        cents: Price in cents (or euro cents)
        currency: ISO 4217 currency code

    Returns:
        Formatted string like "$1.50" or "€1,50"
    """
    symbol = get_currency_symbol(currency)
    dollars = cents / 100.0

    if currency == "EUR":
        # European format: €1,50
        return (
            f"{symbol}{dollars:,.2f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
    else:
        # US format: $1.50
        return f"{symbol}{dollars:,.2f}"
