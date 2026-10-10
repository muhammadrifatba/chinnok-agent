"""
Tool: run_sql_query
Executes a read-only SQL query against the Chinook database after AST safety validation.
"""

import json
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.capabilities.sql_agent.engine import execute_sql
from app.capabilities.sql_agent.validator import (
    SQLValidationError,
    validate_readonly_sql,
    wrap_with_limit,
)
from app.config import get_settings


class RunSQLQueryInput(BaseModel):
    query: str = Field(
        description="The SQL SELECT query to execute. Must be valid PostgreSQL syntax and strictly read-only."
    )


@tool(args_schema=RunSQLQueryInput)
def run_sql_query(query: str) -> str:
    """
    Executes a read-only SQL query against the Chinook database and returns the result.
    The query is strictly validated via AST parser before execution to prevent any data modification
    or unauthorized function calls.
    """
    settings = get_settings()

    # 1. AST Validation
    try:
        validated_sql = validate_readonly_sql(query, dialect="postgres")
    except SQLValidationError as e:
        return json.dumps({
            "status": "validation_error",
            "error_type": "SecurityPolicyViolation",
            "message": str(e),
            "hint": "Ensure your query is a single read-only SELECT statement without forbidden functions, DDL/writes, or direct PII access."
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "validation_error",
            "error_type": "SyntaxOrParseError",
            "message": f"Failed to parse query: {str(e)}",
            "hint": "Check PostgreSQL syntax, quotation marks, and table/column names."
        }, indent=2)

    # 2. Wrap with safety row limit
    bounded_sql = wrap_with_limit(validated_sql, max_rows=settings.max_result_rows, dialect="postgres")

    # 3. Database Execution with Sanitized Error Handling
    try:
        columns, rows, row_count, truncated = execute_sql(bounded_sql, max_rows=settings.max_result_rows)
        return json.dumps({
            "status": "success",
            "columns": columns,
            "rows": rows,
            "row_count": row_count,
            "truncated": truncated,
            "max_rows_limit": settings.max_result_rows,
        }, indent=2, default=str)
    except Exception as e:
        # Sanitize internal Postgres / SQLAlchemy exceptions
        raw_error = str(e)
        sanitized_msg = raw_error.split("\n")[0]  # Avoid dumping driver stack trace
        return json.dumps({
            "status": "execution_error",
            "error_type": "DatabaseExecutionError",
            "message": f"Query execution failed: {sanitized_msg}",
            "hint": "Verify table and column names using get_schema before executing."
        }, indent=2)
