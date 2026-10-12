"""
CLI to test the SQL Agent directly.
Usage:
  uv run python -m scripts.ask_sql "What are the top 5 genres by revenue?"
  uv run python -m scripts.ask_sql --provider anthropic "Top artists by sales?"
"""

import argparse
from app.capabilities.sql_agent.graph import ask_sql_agent


def main():
    parser = argparse.ArgumentParser(description="Ask SQL Agent")
    parser.add_argument("question", nargs="*", help="Natural language question")
    parser.add_argument("--provider", default=None, help="Override provider (google_genai, anthropic, openai)")
    parser.add_argument("--model", default=None, help="Override model ID")
    args = parser.parse_args()

    q = " ".join(args.question) or "What are the top 5 genres by revenue?"
    print(f"\nQuestion: {q}\n")

    res = ask_sql_agent(q, provider=args.provider, model=args.model)

    print("TOOL CALLS :", res["tool_calls"])
    print("-" * 50)
    print("ANSWER:\n", res["answer"])


if __name__ == "__main__":
    main()