# Chinook Multi-Agent — Build Plan

Text-to-SQL + RAG-over-PDF multi-agent system: LangGraph (custom supervisor)
+ deepagents (used only for its skill system, not its subagent/`task` tool)
+ FastAPI + Postgres (Chinook) + Qdrant + LangSmith tracing, managed with uv.

Status key: `[x]` done, `[ ]` not started, `[~]` next up.

---

## Phase 1 — Environment & tooling
- [x] `uv` installed
- [x] `pyproject.toml` with langgraph, deepagents, fastapi, qdrant-client,
      sqlglot, psycopg3 (`psycopg[binary,pool]`, matches
      `langgraph-checkpoint-postgres`'s driver requirement)
- [x] `uv sync` resolving cleanly, no version conflicts
- [ ] LangSmith account + API key created (needed by Phase 7)

## Phase 2 — Infrastructure: Postgres + Qdrant
- [x] `devops/docker-compose.yml` running both services
- [x] Chinook Postgres dump downloaded, `DROP DATABASE`/`CREATE DATABASE`/`\c`
      lines stripped (conflicts with `POSTGRES_DB` auto-creating the DB)
- [x] `01_chinook_schema.sql` + `02_readonly_role.sh` mounted into
      `/docker-entrypoint-initdb.d/`, confirmed path is correct relative to
      `docker-compose.yml`'s own location
- [x] `chinook_reader` read-only role created, verified:
  - `SELECT` succeeds
  - `DELETE` is rejected (permission denied)
- [x] `docker compose down -v` used whenever init files change, to force
      Postgres to re-run them against an empty volume

## Phase 3 — SQL safety layer + tools
- [x] `app/graph/sql_agent/validator.py` — sqlglot AST-based read-only
      allowlist (not a regex/keyword blocklist)
  - Tested against: plain SELECT, DELETE, stacked statements
    (`SELECT ...; DROP ...;`), write-smuggled-in-CTE
    (`WITH x AS (DELETE ... RETURNING *) SELECT * FROM x`), denylisted
    functions (`pg_sleep`, etc.)
- [x] `app/graph/sql_agent/engine.py` — shared SQLAlchemy engine,
      connects as `chinook_reader` only (never the admin role)
- [x] Tools split one-per-file under `app/graph/sql_agent/tools/`, with a
      registry `__init__.py` exporting `SQL_TOOLS = [get_schema, run_sql_query]`
  - `get_schema.py` — full schema dump (tables, columns, FKs, sample rows);
    cached after first call since Chinook's schema is static
  - `run_sql_query.py` — validates via `validator.py`, executes, returns
    structured `{columns, rows, row_count}`, capped at `max_result_rows`
- [x] Tested directly (no LLM involved) — confirmed `DELETE` gets a
      `VALIDATION ERROR` before it ever reaches Postgres

## Phase 4 — SQL subagent (skill + deepagent) `[~ NEXT]`
- [ ] `app/skills/sql-conventions/SKILL.md` — business logic only, not a
      DB connection:
  - revenue = `SUM(InvoiceLine.UnitPrice * InvoiceLine.Quantity)`, not
    `Invoice.Total`
  - PII columns to avoid in aggregate queries (`Customer.Address`,
    `Email`, `Phone`, etc.) unless one named customer is asked about
  - FK join chains: `InvoiceLine → Invoice → Customer`,
    `InvoiceLine → Track → Album → Artist`, `Track → Genre`
- [ ] `app/graph/sql_agent/graph.py` —
      `create_deep_agent(tools=SQL_TOOLS, skills=["sql-conventions"])`
      with **no** `subagents=` param (deepagents' own `task` tool stays
      unused; multi-agent routing is owned by the supervisor, Phase 6)
- [ ] Standalone test: run real questions through the SQL subagent alone
      (e.g. "top 5 genres by revenue") — confirm it calls `get_schema`
      before writing SQL, and that a bad/ambiguous question gets a retry
      or a stated assumption rather than a hallucinated answer

## Phase 5 — RAG side: PDFs, ingestion, subagent
- [ ] Draft/source 4–6 short PDFs matching Chinook's data (artist bios,
      licensing docs, policy doc, quarterly report)
- [ ] `scripts/ingest_pdfs.py` — chunk (recursive text splitter) → embed
      (fastembed, local, no API key) → upsert to Qdrant with
      `{text, source, page}` payload for citations
- [ ] `app/graph/rag_agent/tools/search_documents.py` — embedder here
      **must match** the one used in `ingest_pdfs.py`, or similarity
      search is meaningless
- [ ] `app/skills/citation-format/SKILL.md` — `[source, page]` citation
      rules, disagreement handling, score threshold (reject < 0.5)
- [ ] `app/graph/rag_agent/graph.py` —
      `create_deep_agent(tools=[search_documents], skills=["citation-format"])`
- [ ] Standalone test: confirm citations appear, low-score matches get a
      "couldn't find this" response instead of a guess

## Phase 6 — Supervisor graph
- [ ] `app/graph/state.py` — shared `AgentState` TypedDict
- [ ] `app/graph/supervisor.py` — **plain LangGraph `StateGraph`**, not
      deepagents:
  - `router` node: classifies question as `sql` / `rag` / `both`
  - conditional edges to the Phase 4 and Phase 5 subagents
  - `synthesize` node: reconciles both answers when route is `both`
    (explicitly, not just concatenation)
- [ ] First point both subagents run together — test with questions
      deliberately designed to hit each route

## Phase 7 — FastAPI + LangSmith tracing
- [ ] `app/telemetry.py` — sets `LANGCHAIN_TRACING_V2` /
      `LANGCHAIN_API_KEY` / `LANGCHAIN_PROJECT` env vars **before** the
      graph/model is constructed (tracing only auto-instruments if these
      are set first)
- [ ] `app/main.py` — `POST /ask`, `GET /health`, wraps
      `supervisor_graph.invoke(...)`
- [ ] Confirm a trace actually appears in the LangSmith dashboard —
      router decision, which subagent ran, tool calls, retries, all
      visible as one trace tree

## Phase 8 — Eval harness + hardening
- [ ] `eval/dataset.yaml` — 15–20 (question, gold SQL) pairs across
      easy / medium / hard / adversarial (e.g. "delete all invoices",
      "list every customer's email" — should refuse)
- [ ] `scripts/run_eval.py` — grade by **execution accuracy**: run the
      agent's query and the gold query, compare result *sets*, not SQL
      text (a syntactically different but semantically equivalent query
      should still count as correct)
- [ ] Hard retry cap wired into the SQL subagent loop (state field
      `sql_retry_count` already reserved in `AgentState`)
- [ ] Multi-turn memory via `langgraph-checkpoint-postgres` (you already
      added this dependency — wire up a `PostgresSaver` checkpointer on
      the compiled supervisor graph)
- [ ] Basic auth on the FastAPI endpoints before deploying anywhere public
- [ ] Optional: `EXPLAIN`-based cost check before execution, only worth
      it if you later point this at a bigger DB than Chinook's 11 tables

---

## Key architectural decisions (for reference, don't relitigate these mid-build)

- **deepagents used only for skills, never for its own subagent spawning.**
  No `subagents=` param anywhere. Multi-agent orchestration is 100% a
  hand-written LangGraph `StateGraph` (Phase 6).
- **Skills ≠ data connections.** `SKILL.md` files are markdown judgment/
  convention text the agent reads. Tools (`tools/*.py`) are the only
  things that touch Postgres/Qdrant.
- **Defense in depth on writes**: `chinook_reader` Postgres role (no
  write grants, Phase 2) + sqlglot AST validator (Phase 3) are two
  independent layers — neither depends on the other being correct.
- **Full schema in context, no retrieval/filtering layer**, since
  Chinook is only 11 tables — this is a deliberate scale-appropriate
  choice, not an oversight. Revisit only if pointing this at a much
  larger database later.
