"""
Abhinav Group AI Chatbot — Input Sanitization and Protection
Sanitizes user input to prevent XSS, HTML injection, null-byte attacks, and control-character exploitation.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional


# Pattern for stripping non-printable control characters (keeping \n, \r, \t)
CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Pattern for stripping HTML tags in plain text fields
HTML_TAG_REGEX = re.compile(r"<[^>]+>")

# Pattern for stripping script tags and their content
SCRIPT_TAG_REGEX = re.compile(r"<script.*?>.*?</script>", flags=re.IGNORECASE | re.DOTALL)


def sanitize_text(text: Optional[str], max_length: int = 2000, strip_html: bool = True) -> str:
    """
    Sanitize a text input string:
    - Strips null bytes and malicious control characters
    - Strips dangerous script tags and HTML tags (if strip_html is True)
    - Normalizes excessive whitespace
    - Enforces maximum length
    """
    if not text:
        return ""

    s = str(text)

    # 1. Strip script tags with content
    s = SCRIPT_TAG_REGEX.sub("", s)

    # 2. Strip HTML tags if required
    if strip_html:
        s = HTML_TAG_REGEX.sub("", s)

    # 3. Strip control characters and null bytes
    s = CONTROL_CHAR_REGEX.sub("", s)

    # 4. Truncate to maximum length
    if len(s) > max_length:
        s = s[:max_length]

    return s.strip()


def sanitize_lead_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize all user-provided fields in a lead submission payload before processing.
    """
    cleaned = dict(data)

    if cleaned.get("name"):
        # Names must be plain text without HTML or control characters
        cleaned["name"] = sanitize_text(cleaned["name"], max_length=100, strip_html=True)

    if cleaned.get("email"):
        # Strip whitespace and dangerous characters from email
        raw_email = sanitize_text(cleaned["email"], max_length=150, strip_html=True)
        # Email format normalization
        cleaned["email"] = raw_email.strip().lower() if "@" in raw_email else None

    if cleaned.get("enquiry_summary"):
        cleaned["enquiry_summary"] = sanitize_text(
            cleaned["enquiry_summary"], max_length=1000, strip_html=True
        )

    if cleaned.get("preferred_location"):
        cleaned["preferred_location"] = sanitize_text(
            cleaned["preferred_location"], max_length=100, strip_html=True
        )

    if cleaned.get("preferred_config"):
        cleaned["preferred_config"] = sanitize_text(
            cleaned["preferred_config"], max_length=50, strip_html=True
        )

    if cleaned.get("interested_project"):
        cleaned["interested_project"] = sanitize_text(
            cleaned["interested_project"], max_length=100, strip_html=True
        )

    if cleaned.get("source_page"):
        cleaned["source_page"] = sanitize_text(
            cleaned["source_page"], max_length=500, strip_html=True
        )

    return cleaned
