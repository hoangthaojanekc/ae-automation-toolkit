# Analytics Engineering Automation Toolkit

Three AI agents that automate the most painful parts of analytics engineering work — built with the Claude API and Python.

| Agent | Input | Output |
|---|---|---|
| SQL Optimizer | BigQuery SQL query | Optimized query + cost savings report |
| dbt Doc Generator | dbt model SQL | Ready-to-use schema.yml |
| Campaign Analyst | Campaign metrics (CSV or text) | Executive narrative + anomaly flags |

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

### Run it

```bash
# Default example (missing partition filter)
python sql_optimizer.py

# Specific examples
python sql_optimizer.py bad_select_star
python sql_optimizer.py order_by_no_limit
python sql_optimizer.py missing_partition_filter
```

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

## Agent 2: dbt Documentation Generator

Paste in a dbt model SQL file and get back a complete, valid `schema.yml` — model description, column descriptions, and recommended tests. Ready to drop directly into your dbt project.

### What it generates

- Model-level description in plain business language
- Column descriptions inferred from business logic (not just column names)
- Recommended dbt tests: `unique`, `not_null`, `relationships`, `accepted_values`
- Valid YAML — verified parseable before output

### Run it

```bash
# Built-in examples (thelook_ecommerce dataset)
python dbt_doc_generator.py fct_orders
python dbt_doc_generator.py stg_orders

# Your own model
python dbt_doc_generator.py path/to/your_model.sql
```

### Example output

```yaml
version: 2

models:
  - name: fct_orders
    description: "Fact table combining order, customer, and order item data
      to provide a complete view of each order's status, revenue, and
      associated customer attributes."
    columns:
      - name: order_id
        description: "Unique identifier for each order — primary key."
        tests:
          - unique
          - not_null
      - name: status_group
        description: "Simplified grouping of order status. Complete/Shipped
          = Active, Cancelled/Returned = Inactive, all others = In Progress."
        tests:
          - not_null
          - accepted_values:
              values: ['Active', 'Inactive', 'In Progress']
```

---

## Agent 3: Marketing Campaign Performance Analyst

Paste in campaign metrics — CSV, spreadsheet copy-paste, or plain numbers — and get back an executive-ready analysis: performance summary, anomaly detection, key metrics interpretation, and a clear recommendation.

### What it analyzes

- Performance vs industry benchmarks (open rate, CTR, conversion)
- Funnel drop-off at each stage (sent → delivered → opened → clicked → converted)
- Anomalies: unsubscribe spikes, spam complaint rates, deliverability risks
- Data quality signals: gaps between expected and actual send volumes

### Run it

```bash
# Built-in examples
python campaign_analyst.py bootcamp_migration    # high performer
python campaign_analyst.py migration_comms       # data quality catch
python campaign_analyst.py q1_reengagement       # underperforming campaign

# Your own CSV
python campaign_analyst.py my_campaign.csv
```

### Example output

```
🎯  HEADLINE:
    The Q1 Re-engagement Campaign critically underperformed across every
    metric, with a 0.5% conversion rate — 75% below benchmark — while a
    4% unsubscribe rate signals list health damage threatening future
    deliverability.

⚠️  ANOMALIES:
    - Spam complaint rate 0.34% — 4x above ESP danger threshold of 0.08%;
      sender reputation damage likely already in progress. Urgency: HIGH
    - Unsubscribe rate 4.07% — 8x above safe threshold. Urgency: HIGH

✅  RECOMMENDATION:
    Pause follow-up sends to this segment immediately and submit a
    deliverability audit to your ESP within 48 hours.
```

---

## Setup

**Requirements**
- Python 3.11+
- Anthropic API key — get one at [console.anthropic.com](https://console.anthropic.com)

**Install**
```bash
git clone https://github.com/hoangthaojanekc/ae-automation-toolkit
cd ae-automation-toolkit
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac
pip install anthropic pyyaml
```

**Configure API key**
```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY="your-key-here"

# Mac
export ANTHROPIC_API_KEY="your-key-here"
```

---

## Project structure

```
ae-automation-toolkit/
├── sql_optimizer.py        # Agent 1: BigQuery SQL optimizer
├── dbt_doc_generator.py    # Agent 2: dbt schema.yml generator
├── campaign_analyst.py     # Agent 3: Campaign performance analyst
├── .gitignore
└── README.md
```

---

## Built with

- [Claude API](https://console.anthropic.com) — claude-sonnet-4-6
- [thelook_ecommerce](https://console.cloud.google.com/bigquery?p=bigquery-public-data&d=thelook_ecommerce) — BigQuery public dataset used for examples

---

## Roadmap

- [ ] Web UI — wrap all three agents in a local browser interface for live demos

