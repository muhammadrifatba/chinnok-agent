"""
Audit Logging Service: Records executed queries, agent routing decisions,
and safety interventions in structured JSON format.
Automatically redacts sensitive credentials and PII before writing logs.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from app.security.pii import redact_pii_and_secrets

logger = logging.getLogger("chinook.audit")
logger.setLevel(logging.INFO)

# Console handler with JSON formatting if no handlers attached
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def log_audit_event(
    event_type: str,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    route: Optional[str] = None,
    query: Optional[str] = None,
    status: str = "success",
    latency_ms: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Logs an audit event in structured JSON format with automatic credential/PII sanitization.
    """
    payload: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "request_id": request_id or "unspecified",
        "user_id": user_id or "anonymous",
        "status": status,
    }

    if route:
        payload["route"] = route
    if query:
        # Sanitize query before logging to prevent PII or secret persistence in log sinks
        payload["query"] = redact_pii_and_secrets(query)
    if latency_ms is not None:
        payload["latency_ms"] = round(latency_ms, 2)
    if extra:
        sanitized_extra = {}
        for k, v in extra.items():
            if isinstance(v, str):
                sanitized_extra[k] = redact_pii_and_secrets(v)
            else:
                sanitized_extra[k] = v
        payload.update(sanitized_extra)

    logger.info(json.dumps(payload, default=str))

