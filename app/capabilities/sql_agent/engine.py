"""
Database engine and execution layer for the SQL capability.
Connects strictly using read-only credentials and enforces execution timeouts.
"""

from typing import Any, Dict, List, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from app.config import get_settings

_engine: Engine | None = None

def get_sql_engine() -> Engine:
    """
    Returns the singleton SQLAlchemy engine configured for read-only access.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.database_url.get_secret_value() if settings.database_url else ""
        if not db_url:
            raise RuntimeError("DATABASE_URL is not configured in settings.")
        _engine = create_engine(
            db_url,
            pool_size=settings.postgres_pool_max_size,
            max_overflow=2,
            pool_timeout=settings.postgres_timeout_seconds,
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": settings.postgres_timeout_seconds,
                "options": f"-c statement_timeout={settings.postgres_timeout_seconds * 1000}",
            },
        )
    return _engine


def execute_sql(query:str, max_rows:int | None = None, params: Dict[str, Any] | None = None) -> Tuple[List[str], List[Dict[str, Any]], int, bool]:
     """
    Executes a validated read-only SQL query and returns structured results.
    """

     settings = get_settings()
     cap = max_rows or settings.max_result_rows
     engine= get_sql_engine()

     with engine.connect() as conn:
         conn.execution_options(read_only=True)
         result = conn.execute(text(query), params or {})
         columns = list(result.keys())

         raw_rows = result.fetchmany(cap + 1)
         truncated = len (raw_rows) > cap
         final_rows = raw_rows[:cap]

         rows = [dict(zip(columns, row)) for row in final_rows]
         return columns, rows, len(rows), truncated