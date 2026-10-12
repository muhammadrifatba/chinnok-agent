"""
SQL Agent graph implementation using standard LangGraph.
Model-agnostic and database-agnostic.
"""

import time
import uuid
from typing import Any

from langgraph.prebuilt import create_react_agent

from app.capabilities.sql_agent.tools import SQL_TOOLS
from app.capabilities.sql_agent.tools.prompt import SQL_SYSTEM_PROMPT
from app.config import get_settings
from app.llm import get_llm, message_text
from app.security.input_guard import validate_user_input
from app.security.output_guard import validate_agent_output
from app.services.audit import log_audit_event


def build_sql_agent(provider: str | None = None, model: str | None = None):
    """
    Creates a standard LangGraph ReAct agent equipped ONLY with our 4 SQL tools.
    """
    llm = get_llm(provider=provider, model=model)

    return create_react_agent(
        model=llm,
        tools=SQL_TOOLS,
        prompt=SQL_SYSTEM_PROMPT,
        name="sql_agent",
    )


def ask_sql_agent(
    question: str,
    provider: str | None = None,
    model: str | None = None,
    agent=None,
) -> dict[str, Any]:
    """
    Guarded execution entrypoint:
    User Input Guard -> LangGraph Agent -> Output Guard -> Audit Logger
    """
    s = get_settings()
    request_id = uuid.uuid4().hex[:8]
    started = time.perf_counter()

    # 1. Perimeter Input Guardrail (Prompt Injection & Bulk PII check)
    guard = validate_user_input(question)
    if not guard.is_safe:
        log_audit_event(
            "sql_agent.rejected",
            request_id=request_id,
            route="sql",
            query=question,
            status="blocked",
            extra={"reason": guard.rejection_reason},
        )
        return {"answer": guard.rejection_reason, "tool_calls": [], "blocked": True}

    # 2. Invoke the standard LangGraph Agent
    agent = agent or build_sql_agent(provider=provider, model=model)
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": guard.sanitized_input}]},
            config={"recursion_limit": s.sql_agent_recursion_limit},
        )
    except Exception as e:
        log_audit_event(
            "sql_agent.error",
            request_id=request_id,
            route="sql",
            query=question,
            status="error",
            extra={"error": str(e)[:200]},
        )
        return {"answer": f"Execution error: {str(e)}", "tool_calls": [], "blocked": False}

    # 3. Extract tool calls & final answer
    messages = result["messages"]
    tool_calls = [
        tc["name"]
        for m in messages
        for tc in (getattr(m, "tool_calls", None) or [])
    ]
    raw_answer = message_text(messages[-1].content)

    # 4. Perimeter Output Guardrail (Secret Redaction & Error Masking)
    out = validate_agent_output(raw_answer)

    # 5. Log structured audit event
    log_audit_event(
        "sql_agent.answered",
        request_id=request_id,
        route="sql",
        query=question,
        status="success" if out.is_safe else "sanitized",
        latency_ms=(time.perf_counter() - started) * 1000,
        extra={"tool_calls": ",".join(tool_calls)},
    )

    return {
        "answer": out.sanitized_output,
        "tool_calls": tool_calls,
        "blocked": False,
    }