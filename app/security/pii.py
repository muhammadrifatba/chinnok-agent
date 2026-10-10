"""
PII and Secret Detection & Redaction Utilities.
"""

import re
from typing import Tuple

# Common PII & Secret Patterns
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
API_KEY_REGEX = re.compile(r"(?:sk-[a-zA-Z0-9_-]{20,}|lsv2_[a-zA-Z0-9_-]{20,}|Bearer\s+[a-zA-Z0-9._-]+)", re.IGNORECASE)
DB_CONN_REGEX = re.compile(r"postgresql(?:\+[a-z]+)?://[^:]+:[^@]+@[^\s]+", re.IGNORECASE)


def scan_for_secrets(text: str) -> Tuple[bool, list[str]]:
    """
    Checks if text contains exposed API keys or DB connection passwords.
    """
    findings = []
    if API_KEY_REGEX.search(text):
        findings.append("Exposed API Key detected")
    if DB_CONN_REGEX.search(text):
        findings.append("Exposed Database Connection String with credentials detected")
    return len(findings) > 0, findings


def redact_pii_and_secrets(text: str) -> str:
    """
    Redacts sensitive emails, phones, API keys, and database passwords from text.
    """
    if not text:
        return text

    sanitized = API_KEY_REGEX.sub("[REDACTED_API_KEY]", text)
    sanitized = DB_CONN_REGEX.sub("[REDACTED_DB_URI]", sanitized)
    sanitized = EMAIL_REGEX.sub("[REDACTED_EMAIL]", sanitized)
    sanitized = PHONE_REGEX.sub("[REDACTED_PHONE]", sanitized)
    return sanitized
