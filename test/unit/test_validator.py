import pytest
from app.capabilities.sql_agent.validator import (
    SQLValidationError,
    validate_readonly_sql,
    wrap_with_limit,
)


class TestSQLValidator:
    def test_valid_simple_select(self):
        query = "SELECT album_id, title FROM album WHERE artist_id = 1"
        res = validate_readonly_sql(query)
        assert "album" in res

    def test_valid_aggregate_query(self):
        query = """
        SELECT g.name AS genre, SUM(il.unit_price * il.quantity) AS total_revenue
        FROM track t
        JOIN genre g ON t.genre_id = g.genre_id
        JOIN invoice_line il ON il.track_id = t.track_id
        GROUP BY g.name
        """
        res = validate_readonly_sql(query)
        assert "SUM" in res or "sum" in res.lower()

    def test_reject_delete(self):
        with pytest.raises(SQLValidationError, match="Forbidden SQL operation"):
            validate_readonly_sql("DELETE FROM invoice WHERE invoice_id = 1")

    def test_reject_stacked_statements(self):
        with pytest.raises(SQLValidationError, match="Only single-statement"):
            validate_readonly_sql("SELECT * FROM album; DROP TABLE track;")

    def test_reject_write_smuggled_in_cte(self):
        query = "WITH bad AS (DELETE FROM customer RETURNING *) SELECT * FROM bad;"
        with pytest.raises(SQLValidationError, match="Forbidden SQL operation"):
            validate_readonly_sql(query)

    def test_reject_pg_sleep(self):
        with pytest.raises(SQLValidationError, match="not in the allowed function list"):
            validate_readonly_sql("SELECT pg_sleep(10)")

    def test_reject_pii_email(self):
        with pytest.raises(SQLValidationError, match="Direct access to sensitive PII column 'email'"):
            validate_readonly_sql("SELECT email FROM customer")

    def test_wrap_with_limit(self):
        wrapped = wrap_with_limit("SELECT title FROM album", max_rows=50)
        assert "LIMIT 50" in wrapped