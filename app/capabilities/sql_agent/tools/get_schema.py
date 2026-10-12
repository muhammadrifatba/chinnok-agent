"""
Tool: get_schema
Dynamically inspects tables, columns, primary keys, and foreign keys
from any connected relational database using SQLAlchemy.
"""

from functools import lru_cache
from langchain_core.tools import tool
from sqlalchemy import inspect
from app.capabilities.sql_agent.engine import get_sql_engine


@lru_cache(maxsize=1)
def _inspect_database_schema() -> str:
    engine = get_sql_engine()
    inspector = inspect(engine)

    table_names = sorted(inspector.get_table_names() + inspector.get_view_names())
    lines = [f"Connected Database Schema ({len(table_names)} tables/views found):\n"]

    for table in table_names:
        cols = inspector.get_columns(table)
        pk_constraint = inspector.get_pk_constraint(table)
        pks = set(pk_constraint.get("constrained_columns", []))
        fks = inspector.get_foreign_keys(table)

        fk_map = {}
        for fk in fks:
            for constrained, referred in zip(fk.get("constrained_columns", []), fk.get("referred_columns", [])):
                fk_map[constrained] = f"{fk.get('referred_table')}.{referred}"

        col_defs = []
        for c in cols:
            name = c["name"]
            type_str = str(c["type"])
            flags = []
            if name in pks:
                flags.append("PK")
            if name in fk_map:
                flags.append(f"FK -> {fk_map[name]}")
            suffix = f" [{', '.join(flags)}]" if flags else ""
            col_defs.append(f"{name} ({type_str}){suffix}")

        lines.append(f"Table: {table}")
        lines.append(f"  Columns: {', '.join(col_defs)}\n")

    return "\n".join(lines).strip()


@tool
def get_schema() -> str:
    """
    Returns the dynamic schema of the connected database, including table names,
    columns, data types, primary keys, and foreign key relationships.
    Always call this tool before generating any SQL query.
    """
    return _inspect_database_schema()