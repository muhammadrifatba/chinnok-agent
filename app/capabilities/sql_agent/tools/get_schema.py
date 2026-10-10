"""
Tool: get_schema
Provides cached, safe schema definitions and relationships for the Chinook database.
"""

from functools import lru_cache
from langchain_core.tools import tool

CHINOOK_SAFE_SCHEMA = """
Database: Chinook (Music Store)

Tables and Columns:
1. album (album_id PK, title, artist_id FK -> artist.artist_id)
2. artist (artist_id PK, name)
3. customer (customer_id PK, first_name, last_name, company, city, state, country, support_rep_id FK -> employee)
4. employee (employee_id PK, first_name, last_name, title, reports_to FK, hire_date, city, state, country)
5. genre (genre_id PK, name)
6. invoice (invoice_id PK, customer_id FK, invoice_date, billing_city, billing_state, billing_country, total)
7. invoice_line (invoice_line_id PK, invoice_id FK, track_id FK, unit_price, quantity)
8. media_type (media_type_id PK, name)
9. playlist (playlist_id PK, name)
10. playlist_track (playlist_id PK, track_id PK)
11. track (track_id PK, name, album_id FK, media_type_id FK, genre_id FK, composer, milliseconds, bytes, unit_price)

Business Rules:
- Revenue = SUM(invoice_line.unit_price * invoice_line.quantity)
- Join Chains:
  * track -> album -> artist
  * track -> genre
  * invoice_line -> invoice -> customer
"""

@lru_cache(maxsize=1)
def _get_cached_schema() -> str:
    return CHINOOK_SAFE_SCHEMA.strip()


@tool
def get_schema() -> str:
    """
    Returns the complete schema of the Chinook database including table names,
    column names, primary/foreign keys, and key join relationships.
    Call this before writing any SQL query.
    """
    return _get_cached_schema()