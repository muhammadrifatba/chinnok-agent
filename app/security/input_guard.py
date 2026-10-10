"""
Input Guardrail: Validates length, checks for common prompt injection patterns,
and prevents bulk PII exfiltration attempts.
"""

import re
from dataclasses import dataclass
from typing import Optional

# Common prompt injection / jailbreak indicators
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?(?:system|developer)\s+prompts?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:DAN|unrestricted|in\s+developer\s+mode)", re.IGNORECASE),
    re.compile(r"reveal\s+(?:your\s+)?(?:system\s+prompt|internal\s+instructions)", re.IGNORECASE),
    re.compile(r"dump\s+(?:all\s+)?(?:tables|passwords|credentials|database)", re.IGNORECASE),
]

# Explicit bulk PII exfiltration requests
BULK_PII_PATTERNS = [
    re.compile(r"(?:list|show|give|dump|export|get)\s+(?:all\s+)?(?:customer\s+)?(?:emails?|passwords?|credit\s*cards?|phone\s*numbers?)", re.IGNORECASE),
]


@dataclass
class GuardResult:
    is_safe: bool
    sanitized_input: str
    rejection_reason: Optional[str] = None


def validate_user_input(
    user_input: str,
    max_chars: int = 4000
) -> GuardResult:
    """
    Validates user query before passing to supervisor router.
    """
    if not user_input or not user_input.strip():
        return GuardResult(
            is_safe=False,
            sanitized_input="",
            rejection_reason="Input question cannot be empty."
        )

    cleaned = user_input.strip()

    # 1. Length check
    if len(cleaned) > max_chars:
        return GuardResult(
            is_safe=False,
            sanitized_input=cleaned[:max_chars],
            rejection_reason=f"Question exceeds maximum allowed length of {max_chars} characters."
        )

    # 2. Prompt injection check
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(cleaned):
            return GuardResult(
                is_safe=False,
                sanitized_input=cleaned,
                rejection_reason="Potential prompt injection or security policy violation detected."
            )

    # 3. Bulk PII exfiltration check
    for pattern in BULK_PII_PATTERNS:
        if pattern.search(cleaned):
            return GuardResult(
                is_safe=False,
                sanitized_input=cleaned,
                rejection_reason="Request violates data privacy policy: bulk personal data (emails, phones) cannot be extracted."
            )

    return GuardResult(
        is_safe=True,
        sanitized_input=cleaned,
        rejection_reason=None
    )
