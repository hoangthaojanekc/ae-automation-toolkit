# Analytics Engineering Automation Toolkit

A collection of AI agents that automate the most painful parts of analytics engineering work — built with the Claude API and Python.

---

## Agent 1: BigQuery SQL Optimizer

Paste in a BigQuery SQL query and get back a full optimization report: issues found, a rewritten query, explanation of changes, and estimated cost savings.

### What it analyzes

- Missing partition filters (most expensive anti-pattern in BigQuery)
- SELECT * on wide tables
- ORDER BY without LIMIT (forces full distributed sort)
- Row multiplication from unoptimized multi-table JOINs
- COUNT(DISTINCT) alternatives using APPROX_COUNT_DISTINCT
- Missing clustering column filters

### Example output

```
═══════════════════════════════════════════════════════════════════
  BigQuery SQL Optimization Report
═══════════════════════════════════════════════════════════════════

ISSUES FOUND:
- Missing partition filter on orders.created_at — full table scan
- Double LEFT JOIN causes row multiplication before aggregation
- ORDER BY total_spent DESC has no LIMIT clause

OPTIMIZED QUERY:
WITH order_summary AS (
    SELECT
        o.user_id,
        COUNT(DISTINCT o.order_id) AS num_orders,
        SUM(oi.sale_price)         AS total_spent
    FROM `bigquery-public-data.thelook_ecommerce.orders` o
    LEFT JOIN `bigquery-public-data.thelook_ecommerce.order_items` oi
        ON  oi.order_id    = o.order_id
        AND oi.created_at >= TIMESTAMP '2022-01-01'
        AND oi.created_at  < TIMESTAMP '2024-01-01'
    WHERE o.created_at >= TIMESTAMP '2022-01-01'
      AND o.created_at  < TIMESTAMP '2024-01-01'
    GROUP BY o.user_id
)
SELECT
    u.id,
    u.country,
    COALESCE(os.num_orders, 0)  AS num_orders,
    COALESCE(os.total_spent, 0) AS total_spent
FROM `bigquery-public-data.thelook_ecommerce.users` u
LEFT JOIN order_summary os ON os.user_id = u.id
ORDER BY total_spent DESC
LIMIT 1000

EXPLANATION:
Pre-aggregating orders and order_items in a CTE before joining to users
prevents row multiplication. Partition filters convert full-table scans
into targeted reads — the highest-impact change on partitioned tables.

ESTIMATED SAVINGS:
50–70% reduction in bytes processed and slot time vs. the original query.
```

---

## Setup

**Requirements**
- Python 3.11+
- Anthropic API key (get one at console.anthropic.com)

**Install**
```bash
git clone https://github.com/yourusername/analytics-toolkit
cd analytics-toolkit
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac
pip install anthropic
```

**Configure**
```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY="your-key-here"

# Mac
export ANTHROPIC_API_KEY="your-key-here"
```

**Run**
```bash
# Default example (missing partition filter)
python sql_optimizer.py

# Run a specific example
python sql_optimizer.py bad_select_star
python sql_optimizer.py order_by_no_limit
python sql_optimizer.py missing_partition_filter
```

---

## Project structure

```
analytics-toolkit/
├── sql_optimizer.py      # Agent 1: BigQuery SQL optimizer
├── requirements.txt      # Python dependencies
└── README.md
```

---

## Built with

- [Claude API](https://console.anthropic.com) — claude-sonnet-4-6
- [thelook_ecommerce](https://console.cloud.google.com/bigquery?p=bigquery-public-data&d=thelook_ecommerce) — BigQuery public dataset used for examples

---

## Roadmap

- [ ] Agent 2: dbt model documentation generator (SQL → schema.yml)
- [ ] Agent 3: Marketing campaign performance analyst (metrics → executive narrative)
