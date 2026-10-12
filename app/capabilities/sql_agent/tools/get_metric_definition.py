"""
Tool: get_metric_definition
Deterministic Semantic Layer: Provides approved business formulas, join paths,
and calculation rules so the model doesn't guess metric calculations.
"""

import json
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# Pluggable metric dictionary (can easily be loaded from a YAML file in the future)
METRIC_CATALOG = {
    "revenue": {
        "definition": "Total sales revenue from music purchases",
        "formula": "SUM(invoice_line.unit_price * invoice_line.quantity)",
        "required_tables": ["invoice_line"],
        "critical_rule": "NEVER use SUM(invoice.total) when joining with invoice_line; it double-counts line items.",
    },
    "units_sold": {
        "definition": "Total number of track units purchased",
        "formula": "SUM(invoice_line.quantity)",
        "required_tables": ["invoice_line"],
    },
    "customer_sales": {
        "definition": "Sales aggregated per customer",
        "join_chain": "invoice_line -> invoice -> customer",
        "formula": "SUM(invoice_line.unit_price * invoice_line.quantity)",
        "group_by": "customer.customer_id",
    },
    "artist_sales": {
        "definition": "Sales aggregated per artist",
        "join_chain": "invoice_line -> track -> album -> artist",
        "formula": "SUM(invoice_line.unit_price * invoice_line.quantity)",
        "group_by": "artist.artist_id",
    },
    "genre_sales": {
        "definition": "Sales aggregated per genre",
        "join_chain": "invoice_line -> track -> genre",
        "formula": "SUM(invoice_line.unit_price * invoice_line.quantity)",
        "group_by": "genre.genre_id",
    },
}


class MetricQueryInput(BaseModel):
    metric_name: str | None = Field(
        default=None,
        description="Name of the metric or calculation (e.g. 'revenue', 'artist_sales'). Omit to list all available metrics."
    )


@tool(args_schema=MetricQueryInput)
def get_metric_definition(metric_name: str | None = None) -> str:
    """
    Returns official business calculation rules, formulas, and required join chains.
    Call this whenever answering questions involving revenue, sales, top sellers, or multi-table aggregations.
    """
    if not metric_name:
        return json.dumps({
            "status": "success",
            "available_metrics": list(METRIC_CATALOG.keys()),
            "hint": "Pass metric_name to get detailed calculation formulas and required joins."
        }, indent=2)

    name = metric_name.lower().strip()
    if name in METRIC_CATALOG:
        return json.dumps({
            "status": "success",
            "metric": name,
            **METRIC_CATALOG[name]
        }, indent=2)

    return json.dumps({
        "status": "not_found",
        "message": f"No metric defined for '{metric_name}'.",
        "available_metrics": list(METRIC_CATALOG.keys()),
    }, indent=2)