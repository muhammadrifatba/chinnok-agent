"""
Output Guardrail: Scans final agent synthesis for leaked secrets, sensitive data,
or unhandled internal stack traces.
"""

from dataclasses import dataclass
from typing import Optional
from app.security.pii import scan_for_secrets, redact_pii_and_secrets


@dataclass
class OutputGuardResult:
    is_safe: bool
    sanitized_output: str
    rejection_reason: Optional[str] = None


def validate_agent_output(output_text: str) -> OutputGuardResult:
    """
    Validates and sanitizes final synthesized response before sending to user.
    """
    if not output_text:
        return OutputGuardResult(is_safe=True, sanitized_output="")

    # 1. Check for exposed secrets (API keys, connection strings)
    has_secrets, findings = scan_for_secrets(output_text)
    if has_secrets:
        # Redact secrets immediately
        redacted = redact_pii_and_secrets(output_text)
        return OutputGuardResult(
            is_safe=True,
            sanitized_output=redacted,
            rejection_reason=f"Secrets detected and redacted: {', '.join(findings)}"
        )

    # 2. Check for raw unhandled DB / Python error traceback leaking
    if "Traceback (most recent call last):" in output_text or "psycopg.errors" in output_text:
        return OutputGuardResult(
            is_safe=False,
            sanitized_output="An internal error occurred while processing the request. Details have been logged securely.",
            rejection_reason="Internal stack trace leakage prevented."
        )

    return OutputGuardResult(
        is_safe=True,
        sanitized_output=output_text,
        rejection_reason=None
    )
