from typing import Set
import sqlglot
from sqlglot import exp

class SQLValidationError(Exception):
    """Raised when an SQL query fails safety or policy validation."""
    pass


SQLValidator = SQLValidationError

ALLOWED_STATEMENT_TYPES = (exp.Select, exp.Union, exp.Except, exp.Intersect)

# Explicit table allowlist: only Chinook tables and safe views
ALLOWED_TABLES: Set[str] = {
    "album",
    "artist",
    "customer",
    "employee",
    "genre",
    "invoice",
    "invoice_line",
    "media_type",
    "playlist",
    "playlist_track",
    "track",
    "v_customer_safe",
    "v_employee_safe",
    "v_invoice_safe",
}

# Strict function allowlist for analytical Text-to-SQL
ALLOWED_FUNCTIONS: Set[str] = {
    "count", "sum", "avg", "min", "max", "round", "coalesce", "nullif",
    "lower", "upper", "trim", "ltrim", "rtrim", "length", "substr",
    "substring", "concat", "replace", "date_trunc", "extract", "to_char",
    "to_date", "now", "current_date", "current_timestamp", "cast", "abs",
    "ceil", "floor", "greatest", "least", "row_number", "rank", "dense_rank", "ntile",
}

# Sensitive PII columns blocked at AST level
DENYLISTED_COLUMNS: Set[str] = {
    "email",
    "phone",
    "fax",
    "address",
    "postal_code",
    "birth_date",
}

FORBIDDEN_AST_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Into,          # SELECT ... INTO new_table
    exp.Lock,          # SELECT ... FOR UPDATE / FOR SHARE
    exp.Command,       # Generic DB administrative commands
    exp.Set,           # SET param = value
    exp.Pragma,        # PRAGMA commands
)

DENYLISTED_FUNCTIONS = {
    "pg_sleep",
    "pg_read_file",
    "pg_read_binary_file",
    "dblink",
    "dblink_connect",
    "lo_import",
    "lo_export",
}

def validate_readonly_sql(query: str, dialect: str = "postgres",  allow_pii_columns: bool = False,) -> str:
    """
    Validates that the SQL query is strictly read-only, references only allowed tables,
    uses only allowlisted functions, and contains no dangerous statements or PII leakage.
    """

    if not query or not query.strip():
        raise SQLValidator("Query cannot be empty.")
    
    cleaned_query = query.strip().rstrip(";")

    try:
        statements = sqlglot.parse(cleaned_query, read=dialect)
    except Exception as e:
        raise SQLValidator(f"Failed to parse SQL query: {e}") from e

    if len (statements) != 1:
        raise SQLValidator(f"Only single statement queries are allowed. Found {len(statements)} statements.")

    tree = statements[0]
    if tree is None:
        raise SQLValidator("Parsed statement AST is empty.")

    if not isinstance(tree, ALLOWED_STATEMENT_TYPES):
        stmt_type = type(tree).__name__
        raise SQLValidator(
            f"Disallowed query type: {stmt_type}. Only SELECT/UNION/EXCEPT/INTERSECT queries are permitted."
        )

    for node in tree.walk():
        node_obj = node[0] if isinstance(node, tuple) else node
        
        # Check forbidden statement/clause types (writes, DDL, SELECT INTO, FOR UPDATE)
        if isinstance(node_obj, FORBIDDEN_AST_NODES):
            raise SQLValidator(
                f"Forbidden SQL operation detected: {type(node_obj).__name__}"
            )

        if isinstance(node_obj, exp.Table):
            table_name = (node_obj.name or "").lower()
            schema_name = (node_obj.db or "").lower()
            if schema_name and schema_name not in ("public", ""):
                raise SQLValidator(
                    f"Access to schema '{schema_name}' is forbidden. Only public Chinook tables are allowed."
                )
            if table_name and table_name not in ALLOWED_TABLES:
                raise SQLValidator(
                    f"Access to table or relation '{table_name}' is forbidden."
                )
         # Check function calls against allowlist
        if isinstance(node_obj, exp.Func):
            fn_name = (node_obj.name or node_obj.key or "").lower()
            if fn_name and fn_name not in ALLOWED_FUNCTIONS:
                raise SQLValidator(
                    f"Function call '{fn_name}()' is not in the allowed function list."
                )

        if not allow_pii_columns and isinstance(node_obj, exp.Column):
            col_name = (node_obj.name or "").lower()
            if col_name in DENYLISTED_COLUMNS:
                raise SQLValidator(
                    f"Direct access to sensitive PII column '{col_name}' is forbidden."
                )
    return tree.sql(dialect=dialect)

def wrap_with_limit(
    query: str,
    max_rows: int = 100,
    dialect: str = "postgres"
) -> str:
    """
    Safely wraps any valid query inside a bounded subquery limit.
    """
    validated_sql = validate_readonly_sql(query, dialect=dialect)
    return f"SELECT * FROM ({validated_sql}) AS _subquery LIMIT {max_rows}"
