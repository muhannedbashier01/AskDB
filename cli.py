#!/usr/bin/env python3
"""CLI demo for the AskDB SQL Agent."""

import sys

import structlog
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure structlog for CLI output
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(structlog.get_logger().level or 20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def print_banner():
    """Print welcome banner."""
    print("\n" + "=" * 60)
    print("  AskDB - Natural Language SQL Agent")
    print("  Type your question in plain English")
    print("  Type 'exit' or 'quit' to exit")
    print("  Type 'schema' to see database schema")
    print("  Type 'history' to see query history")
    print("=" * 60 + "\n")


def print_result(result: dict):
    """Print query result in a formatted way."""
    print("\n" + "-" * 50)

    if result.get("success"):
        print(f"✓ SQL Query (attempt {result.get('attempts', 1)}):")
        print(f"  {result.get('sql_query', '')}\n")

        if result.get("message"):
            print(f"  {result['message']}\n")

        if result.get("columns"):
            # Print as table
            columns = result["columns"]
            rows = result.get("rows", [])

            # Calculate column widths
            widths = {col: len(col) for col in columns}
            for row in rows[:20]:  # Limit for display
                for col in columns:
                    val = str(row.get(col, ""))[:50]  # Truncate long values
                    widths[col] = max(widths[col], len(val))

            # Print header
            header = " | ".join(col.ljust(widths[col]) for col in columns)
            print(f"  {header}")
            print(f"  {'-' * len(header)}")

            # Print rows
            for row in rows[:20]:
                row_str = " | ".join(
                    str(row.get(col, ""))[:50].ljust(widths[col]) for col in columns
                )
                print(f"  {row_str}")

            if len(rows) > 20:
                print(f"\n  ... and {len(rows) - 20} more rows")

            print(f"\n  Total: {result.get('row_count', 0)} rows")
    else:
        print(f"✗ Query failed after {result.get('attempts', 1)} attempts")
        print(f"  SQL: {result.get('sql_query', 'N/A')}")
        print(f"  Error: {result.get('error', 'Unknown error')}")

    print("-" * 50 + "\n")


def check_connection():
    """Check database and LLM connections."""
    from app.services.db_service import get_db_service

    print("Checking connections...")

    # Check database
    db = get_db_service()
    success, msg = db.test_connection()
    if success:
        print("  ✓ Database connection OK")
    else:
        print(f"  ✗ Database connection failed: {msg}")
        return False

    # Check LLM (basic check)
    from app.core.config import get_settings

    settings = get_settings()
    print(f"  ✓ LLM endpoint configured: {settings.llm_base_url}")

    return True


def show_schema():
    """Display database schema."""
    from app.services.db_service import get_db_service

    db = get_db_service()
    schema = db.get_schema()
    print("\nDatabase Schema:")
    print("-" * 40)
    print(schema)
    print("-" * 40 + "\n")


def show_history():
    """Display query history."""
    from app.services.db_service import get_history

    history = get_history(limit=10)
    if not history:
        print("\nNo query history yet.\n")
        return

    print("\nQuery History (last 10):")
    print("-" * 40)
    for entry in history:
        status = "✓" if entry["success"] else "✗"
        print(f"{status} [{entry['timestamp'][:19]}]")
        print(f"   Q: {entry['user_query'][:60]}...")
        print(f"   SQL: {entry['sql_query'][:60]}...")
        if entry.get("error"):
            print(f"   Error: {entry['error'][:60]}...")
        print()
    print("-" * 40 + "\n")


def main():
    """Main CLI loop."""
    print_banner()

    if not check_connection():
        print("\n⚠️  Please check your .env configuration and try again.")
        sys.exit(1)

    print("\nReady! Enter your query:\n")

    from app.core.agent.graph import run_agent_sync

    while True:
        try:
            user_input = input("askdb> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            if user_input.lower() == "schema":
                show_schema()
                continue

            if user_input.lower() == "history":
                show_history()
                continue

            # Run the agent
            print("\nProcessing...")
            result = run_agent_sync(user_input)
            print_result(result)

        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            logger.exception("Error processing query")
            print(f"\n✗ Error: {e}\n")


if __name__ == "__main__":
    main()
