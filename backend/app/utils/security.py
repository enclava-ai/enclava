"""
Security Utilities

Provides common security functions for input sanitization, output encoding, etc.
"""

import re
import urllib.parse
from typing import Optional


def sanitize_filename_for_header(filename: str, default: str = "download") -> str:
    """
    Sanitize filename for use in Content-Disposition header.

    Security mitigation #9: Prevent header injection via filenames.

    This function:
    - Removes CR/LF characters that could inject new headers
    - Removes path separators to prevent directory traversal
    - Encodes non-ASCII characters per RFC 5987
    - Falls back to a safe default if filename is empty/invalid

    Args:
        filename: The original filename
        default: Default filename to use if sanitization results in empty string

    Returns:
        Safe filename string suitable for Content-Disposition header
    """
    if not filename:
        return default

    # Remove any CR/LF characters (header injection prevention)
    filename = filename.replace("\r", "").replace("\n", "")

    # Remove path separators (directory traversal prevention)
    filename = filename.replace("/", "_").replace("\\", "_")

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Remove other control characters
    filename = re.sub(r"[\x00-\x1f\x7f]", "", filename)

    # Remove quotes that could break header parsing
    filename = filename.replace('"', "").replace("'", "")

    # Limit length to prevent header size issues
    if len(filename) > 255:
        # Keep extension if present
        if "." in filename:
            name, ext = filename.rsplit(".", 1)
            max_name_len = 255 - len(ext) - 1
            filename = f"{name[:max_name_len]}.{ext}"
        else:
            filename = filename[:255]

    # If filename is now empty, use default
    if not filename or filename.isspace():
        return default

    return filename


def encode_content_disposition(filename: str, disposition: str = "attachment") -> str:
    """
    Create a properly encoded Content-Disposition header value.

    Security mitigation #9: Properly encode filenames per RFC 5987.

    This handles:
    - ASCII filenames directly
    - Non-ASCII filenames with RFC 5987 encoding
    - Both 'filename' and 'filename*' parameters for compatibility

    Args:
        filename: The sanitized filename
        disposition: The disposition type ('attachment' or 'inline')

    Returns:
        Complete Content-Disposition header value
    """
    # First sanitize the filename
    safe_filename = sanitize_filename_for_header(filename)

    # Check if filename is pure ASCII
    try:
        safe_filename.encode("ascii")
        is_ascii = True
    except UnicodeEncodeError:
        is_ascii = False

    if is_ascii:
        # Simple case: ASCII filename
        # Quote the filename to handle spaces and special chars
        return f'{disposition}; filename="{safe_filename}"'
    else:
        # RFC 5987 encoding for non-ASCII
        # Use UTF-8 encoding with percent-encoding
        encoded = urllib.parse.quote(safe_filename, safe="")
        # Provide both for maximum compatibility
        # ASCII fallback (may be mangled) + RFC 5987 version
        ascii_fallback = "".join(c if ord(c) < 128 else "_" for c in safe_filename)
        return (
            f'{disposition}; filename="{ascii_fallback}"; '
            f"filename*=UTF-8''{encoded}"
        )


def is_safe_redirect_url(url: str, allowed_hosts: Optional[list] = None) -> bool:
    """
    Check if a URL is safe for redirecting.

    Prevents open redirect vulnerabilities.

    Args:
        url: The URL to check
        allowed_hosts: List of allowed host patterns (None = relative URLs only)

    Returns:
        True if the URL is safe for redirect
    """
    if not url:
        return False

    # Parse the URL
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False

    # Allow relative URLs (no scheme or netloc)
    if not parsed.scheme and not parsed.netloc:
        # Make sure it doesn't start with // (protocol-relative URL)
        if url.startswith("//"):
            return False
        return True

    # If scheme is present, must be http or https
    if parsed.scheme not in ("http", "https"):
        return False

    # If allowed_hosts is specified, check against it
    if allowed_hosts is not None:
        host = parsed.netloc.lower()
        for allowed in allowed_hosts:
            if allowed.startswith("*."):
                # Wildcard match
                suffix = allowed[1:]  # Remove *
                if host.endswith(suffix) or host == allowed[2:]:
                    return True
            elif host == allowed.lower():
                return True
        return False

    # No allowed hosts specified and URL is absolute - reject
    return False


def redact_sensitive_value(value: str, visible_chars: int = 4) -> str:
    """
    Redact a sensitive value for logging.

    Security mitigation #42: Redact API key prefixes and other sensitive values.

    Args:
        value: The value to redact
        visible_chars: Number of characters to keep visible at the end

    Returns:
        Redacted string like "***xyz"
    """
    if not value:
        return "[empty]"

    if len(value) <= visible_chars:
        return "*" * len(value)

    return "*" * (len(value) - visible_chars) + value[-visible_chars:]
