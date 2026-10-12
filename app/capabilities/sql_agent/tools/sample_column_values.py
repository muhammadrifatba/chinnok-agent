"""
Tool: sample_column_values
Allows the agent to look up distinct real values (value linking)
(e.g., exact genre names, country spellings) from an allowlist of non-PII columns.
"""

import json
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.capabilities.sql_agent.engine import execute_sql
from app.security.input_guard import wrap_untrusted_data

# Allowlist of low-cardinality, non-PII columns safe for distinct lookup
ALLOWED_VALUE_COLUMNS: dict[str, set[str]] = {
    "genre": {"name"},
    "media_type": {"name"},
    "artist": {"name"},
    "playlist": {"name"},
    "customer": {"country", "city", "state"},
    "invoice": {"billing_country", "billing_city", "billing_state"},
    "employee": {"title", "country"},
}
MAX_VALUES = 25


class SampleValuesInput(BaseModel):
    table: str = Field(description="Table name, e.g. 'genre' or 'customer'.")
    column: str = Field(description="Column name, e.g. 'name' or 'country'.")
    contains: str | None = Field(
        default=None,
        description="Optional case-insensitive substring filter, e.g. 'rock'.",
    )


@tool(args_schema=SampleValuesInput)
def sample_column_values(table: str, column: str, contains: str | None = None) -> str:
    """
    Returns up to 25 distinct values of a column to find exact spellings
    for WHERE clauses. Only low-cardinality, non-PII columns are permitted.
    """
    t = table.lower().strip()
    c = column.lower().strip()

    allowed = ALLOWED_VALUE_COLUMNS.get(t)
    if not allowed or c not in allowed:
        return json.dumps({
            "status": "validation_error",
            "message": f"Column '{t}.{c}' is not available for value lookup.",
            "allowed_lookup_columns": {tbl: sorted(cols) for tbl, cols in ALLOWED_VALUE_COLUMNS.items()},
        })

    # table and column are validated against the allowlist above
    sql = f"SELECT DISTINCT {c} AS value FROM {t} WHERE {c} IS NOT NULL"
    params: dict[str, str] = {}
    if contains:
        sql += f" AND {c} ILIKE :pat"
        params["pat"] = f"%{contains.strip()[:50]}%"
    sql += f" ORDER BY {c} LIMIT {MAX_VALUES}"

    try:
        _, rows, _, _ = execute_sql(sql, max_rows=MAX_VALUES, params=params)
    except Exception as e:
        return json.dumps({"status": "execution_error", "message": str(e).split("\n")[0]})

    payload = json.dumps(
        {
            "status": "success",
            "table": t,
            "column": c,
            "values": [r["value"] for r in rows],
        },
        default=str,
    )
    return wrap_untrusted_data(payload, source=f"postgres:{t}.{c}")