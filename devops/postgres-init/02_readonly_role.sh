#!/usr/bin/env bash
set -euo pipefail

: "${READONLY_DB_PASSWORD:?READONLY_DB_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- 1. Create chinook_reader role if not exists
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'chinook_reader') THEN
            CREATE ROLE chinook_reader LOGIN PASSWORD '${READONLY_DB_PASSWORD}';
        ELSE
            ALTER ROLE chinook_reader WITH PASSWORD '${READONLY_DB_PASSWORD}';
        END IF;
    END
    \$\$;

    -- 2. Restrict role operational parameters (Least Privilege + Safety)
    ALTER ROLE chinook_reader SET default_transaction_read_only = on;
    ALTER ROLE chinook_reader SET statement_timeout = '5s';
    ALTER ROLE chinook_reader SET idle_in_transaction_session_timeout = '5s';
    ALTER ROLE chinook_reader SET lock_timeout = '3s';
    ALTER ROLE chinook_reader CONNECTION LIMIT 10;

    -- 3. Manage schema & table privileges
    REVOKE ALL ON SCHEMA public FROM PUBLIC;
    GRANT USAGE ON SCHEMA public TO chinook_reader;

    -- Non-sensitive tables: grant full table SELECT
    GRANT SELECT ON TABLE album, artist, genre, invoice_line, media_type, playlist, playlist_track, track TO chinook_reader;

    -- Tables with PII: grant column-level SELECT only (excluding email, phone, fax, address, postal_code, birth_date)
    GRANT SELECT (customer_id, first_name, last_name, company, city, state, country, support_rep_id) ON customer TO chinook_reader;
    GRANT SELECT (employee_id, first_name, last_name, title, reports_to, hire_date, city, state, country) ON employee TO chinook_reader;
    GRANT SELECT (invoice_id, customer_id, invoice_date, billing_city, billing_state, billing_country, total) ON invoice TO chinook_reader;

    -- Create convenient Safe Views for RAG/Agent reporting
    CREATE OR REPLACE VIEW v_customer_safe AS
        SELECT customer_id, first_name, last_name, company, city, state, country, support_rep_id FROM customer;
    CREATE OR REPLACE VIEW v_employee_safe AS
        SELECT employee_id, first_name, last_name, title, reports_to, hire_date, city, state, country FROM employee;
    CREATE OR REPLACE VIEW v_invoice_safe AS
        SELECT invoice_id, customer_id, invoice_date, billing_city, billing_state, billing_country, total FROM invoice;

    GRANT SELECT ON v_customer_safe, v_employee_safe, v_invoice_safe TO chinook_reader;

    -- Ensure no write privileges ever exist
    REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public FROM chinook_reader;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM chinook_reader;

    -- 4. Dedicated Checkpoint Role for LangGraph multi-turn memory
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'chinook_checkpointer') THEN
            CREATE ROLE chinook_checkpointer LOGIN PASSWORD '${CHECKPOINT_DB_PASSWORD:-checkpoint_secret}';
        ELSE
            ALTER ROLE chinook_checkpointer WITH PASSWORD '${CHECKPOINT_DB_PASSWORD:-checkpoint_secret}';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO chinook_checkpointer;
    CREATE SCHEMA IF NOT EXISTS checkpoints AUTHORIZATION chinook_checkpointer;
    GRANT ALL ON SCHEMA checkpoints TO chinook_checkpointer;

    -- Strict isolation: chinook_reader MUST NOT inspect or modify conversation checkpoints
    REVOKE ALL ON SCHEMA checkpoints FROM chinook_reader;
    REVOKE ALL ON SCHEMA checkpoints FROM PUBLIC;
EOSQL