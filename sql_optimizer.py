"""
BigQuery SQL Optimization Agent
================================
Portfolio project: Analytics Engineering + AI Automation
Author: [Your Name]

What it does:
- Takes a BigQuery SQL query as input
- Uses Claude AI to analyze it for cost and performance issues
- Returns an optimized version with explanation and estimated savings

Interview talking point:
"I built an agent that audits BigQuery SQL for full table scans,
missing partition filters, and SELECT * anti-patterns. It rewrites
queries and estimates cost savings — something I now use in my
own dbt projects."
"""

import anthropic
import re


# ── Prompt ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior BigQuery optimization expert.
When given a SQL query, you analyze it for performance and cost issues,
then return an optimized version.

You always check for:
1. SELECT * (always replace with specific columns)
2. Missing partition filters on date/timestamp columns
3. Missing clustering column filters
4. Unnecessary JOINs or subqueries that could be CTEs
5. ORDER BY without LIMIT (extremely expensive in BigQuery)
6. COUNT(DISTINCT) alternatives using APPROX_COUNT_DISTINCT where precision isn't critical

Return your response in EXACTLY this format — no deviations:

ISSUES_FOUND:
- [issue 1]
- [issue 2]
(list every issue, or write "None" if the query is already optimal)

OPTIMIZED_QUERY:
```sql
[the full rewritten query]
```

EXPLANATION:
[2-3 sentences explaining the key changes and why they matter]

ESTIMATED_SAVINGS:
[e.g. "60-80% reduction in bytes processed by adding partition filter"]
(be specific — reference bytes, scan reduction, or cost if you can estimate)
"""


# ── Agent ────────────────────────────────────────────────────────────────────

def optimize_sql(query: str, context: str = "") -> dict:
    """
    Send a BigQuery SQL query to Claude for optimization analysis.

    Args:
        query:   The raw SQL query to optimize
        context: Optional context about the table (e.g. "orders table has
                 100M rows, partitioned on created_at, clustered on user_id")

    Returns:
        dict with keys: issues, optimized_query, explanation, estimated_savings
    """
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment

    user_message = f"Optimize this BigQuery SQL query:\n\n```sql\n{query}\n```"
    if context:
        user_message += f"\n\nTable context: {context}"

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    response_text = message.content[0].text
    return _parse_response(response_text)


def _parse_response(text: str) -> dict:
    """Parse Claude's structured response into a clean dict."""

    def extract(label: str) -> str:
        pattern = rf"{label}:\n(.*?)(?=\n[A-Z_]+:|$)"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ""

    # Pull out the SQL block separately (between ```sql and ```)
    sql_match = re.search(r"```sql\n(.*?)```", text, re.DOTALL)
    optimized_query = sql_match.group(1).strip() if sql_match else ""

    return {
        "issues":            extract("ISSUES_FOUND"),
        "optimized_query":   optimized_query,
        "explanation":       extract("EXPLANATION"),
        "estimated_savings": extract("ESTIMATED_SAVINGS"),
        "raw_response":      text,  # keep for debugging
    }


def print_report(result: dict, original_query: str) -> None:
    """Pretty-print the optimization report to console."""
    divider = "─" * 65

    print(f"\n{'═' * 65}")
    print("  BigQuery SQL Optimization Report")
    print(f"{'═' * 65}\n")

    print("ORIGINAL QUERY:")
    print(original_query.strip())

    print(f"\n{divider}")
    print("🔍  ISSUES FOUND:")
    print(result["issues"])

    print(f"\n{divider}")
    print("✅  OPTIMIZED QUERY:")
    print(result["optimized_query"])

    print(f"\n{divider}")
    print("💡  EXPLANATION:")
    print(result["explanation"])

    print(f"\n{divider}")
    print("💰  ESTIMATED SAVINGS:")
    print(result["estimated_savings"])
    print(f"\n{'═' * 65}\n")


# ── Example Queries ──────────────────────────────────────────────────────────
# These mirror the thelook_ecommerce dataset from your learning plan
# Run these against bigquery-public-data.thelook_ecommerce in your sandbox

EXAMPLE_QUERIES = {

    "bad_select_star": """
        SELECT *
        FROM `bigquery-public-data.thelook_ecommerce.orders`
        WHERE status = 'Complete'
    """,

    "missing_partition_filter": """
        SELECT
            u.id,
            u.country,
            COUNT(DISTINCT o.order_id) as num_orders,
            SUM(oi.sale_price) as total_spent
        FROM `bigquery-public-data.thelook_ecommerce.users` u
        LEFT JOIN `bigquery-public-data.thelook_ecommerce.orders` o
            ON u.id = o.user_id
        LEFT JOIN `bigquery-public-data.thelook_ecommerce.order_items` oi
            ON o.order_id = oi.order_id
        GROUP BY u.id, u.country
        ORDER BY total_spent DESC
    """,

    "order_by_no_limit": """
        SELECT
            order_id,
            user_id,
            sale_price,
            created_at
        FROM `bigquery-public-data.thelook_ecommerce.order_items`
        ORDER BY created_at DESC
    """,
}

TABLE_CONTEXTS = {
    "bad_select_star": (
        "orders table: ~125k rows, partitioned on created_at (DAY), "
        "clustered on user_id and status"
    ),
    "missing_partition_filter": (
        "orders: ~125k rows, partitioned on created_at (DAY), clustered on user_id. "
        "order_items: ~500k rows, partitioned on created_at (DAY), clustered on order_id. "
        "users: ~100k rows, no partitioning."
    ),
    "order_by_no_limit": (
        "order_items: ~500k rows, partitioned on created_at (DAY), "
        "clustered on order_id and product_id"
    ),
}


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # If a query name is passed as argument, run that specific example
    # e.g.: python sql_optimizer.py missing_partition_filter
    if len(sys.argv) > 1 and sys.argv[1] in EXAMPLE_QUERIES:
        name = sys.argv[1]
        print(f"\nRunning example: {name}")
        query = EXAMPLE_QUERIES[name]
        context = TABLE_CONTEXTS.get(name, "")
        result = optimize_sql(query, context)
        print_report(result, query)

    else:
        # Default: run the most illustrative example
        print("\nRunning default example: missing_partition_filter")
        print("(Pass a query name as argument to run others)")
        print("Available: " + ", ".join(EXAMPLE_QUERIES.keys()))

        query = EXAMPLE_QUERIES["missing_partition_filter"]
        context = TABLE_CONTEXTS["missing_partition_filter"]
        result = optimize_sql(query, context)
        print_report(result, query)
