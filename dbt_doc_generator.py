"""
dbt Documentation Generator Agent
===================================
Portfolio project: Analytics Engineering + AI Automation
Agent 2 of 3

What it does:
- Takes a dbt model SQL file as input
- Uses Claude AI to analyze the business logic
- Returns a complete, valid schema.yml file:
    - Model-level description
    - Column descriptions with data types
    - Recommended dbt tests (unique, not_null, relationships, accepted_values)

Interview talking point:
"I built an agent that generates dbt schema.yml documentation from raw
SQL models. You paste in a model, it reads the business logic and returns
column descriptions and recommended tests — ready to drop into your dbt
project. Turns a 30-minute manual task into 30 seconds."
"""

import anthropic
import yaml
import re
import sys


# ── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior analytics engineer who writes exceptional
dbt documentation. When given a dbt model SQL file, you analyze the business
logic and generate a complete, valid schema.yml block for that model.

Rules you always follow:
1. Read the SQL carefully — column names, joins, and business logic tell you
   what each field means and what tests are appropriate
2. Write descriptions in plain business language, not technical jargon
3. Recommend tests based on what makes sense for each column:
   - Primary keys: unique + not_null
   - Foreign keys: not_null + relationships (note the ref model)
   - Status/type fields: accepted_values (infer likely values from CASE WHEN or WHERE clauses)
   - Metrics/amounts: not_null
4. Never invent column names — only document what is actually in the SELECT
5. Infer the model name from the SQL file content or context provided

Return ONLY valid YAML — no preamble, no explanation, no markdown code fences.
The output must be pasteable directly into a dbt project's schema.yml file.

Use this exact structure:

version: 2

models:
  - name: [model_name]
    description: "[one sentence describing what this model contains and its business purpose]"
    columns:
      - name: [column_name]
        description: "[plain English description of what this column represents]"
        tests:
          - [test_name]
"""


# ── Agent ─────────────────────────────────────────────────────────────────────

def generate_schema_yml(sql: str, model_name: str = None) -> dict:
    """
    Generate a schema.yml block for a dbt model.

    Args:
        sql:        The full SQL content of the dbt model file
        model_name: Optional — the model name (e.g. 'fct_orders').
                    If not provided, Claude will infer it from the SQL.

    Returns:
        dict with keys: yaml_output, model_name, is_valid, raw_response
    """
    client = anthropic.Anthropic()

    context = ""
    if model_name:
        context = f"The model name is: {model_name}\n\n"

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"{context}Generate schema.yml documentation for this dbt model:\n\n{sql}"
        }]
    )

    raw = message.content[0].text.strip()

    # Strip markdown fences if Claude adds them despite instructions
    clean = re.sub(r"^```ya?ml\s*", "", raw, flags=re.MULTILINE)
    clean = re.sub(r"```$", "", clean, flags=re.MULTILINE).strip()

    # Validate it's parseable YAML
    is_valid = False
    parsed = None
    try:
        parsed = yaml.safe_load(clean)
        is_valid = (
            isinstance(parsed, dict)
            and "models" in parsed
            and isinstance(parsed["models"], list)
        )
    except yaml.YAMLError:
        pass

    # Extract model name from parsed output
    detected_name = model_name
    if parsed and is_valid:
        try:
            detected_name = parsed["models"][0]["name"]
        except (KeyError, IndexError):
            pass

    return {
        "yaml_output":  clean,
        "model_name":   detected_name,
        "is_valid":     is_valid,
        "raw_response": raw,
    }


def print_report(result: dict) -> None:
    """Pretty-print the schema.yml output to console."""
    print(f"\n{'═' * 65}")
    print("  dbt Documentation Generator")
    print(f"{'═' * 65}\n")

    if result["model_name"]:
        print(f"Model: {result['model_name']}")

    status = "✅ Valid YAML — ready to paste into schema.yml" if result["is_valid"] \
             else "⚠️  YAML validation failed — review before using"
    print(f"Status: {status}\n")

    print("─" * 65)
    print("Generated schema.yml:")
    print("─" * 65)
    print(result["yaml_output"])
    print(f"\n{'═' * 65}\n")


def save_schema_yml(result: dict, output_path: str = None) -> str:
    """Save the generated schema.yml to a file."""
    if not output_path:
        name = result["model_name"] or "generated"
        output_path = f"{name}_schema.yml"

    with open(output_path, "w") as f:
        f.write(result["yaml_output"])

    print(f"Saved to: {output_path}")
    return output_path


# ── Example Models ────────────────────────────────────────────────────────────
# These use the thelook_ecommerce dataset from your learning plan

EXAMPLE_MODELS = {

    "fct_orders": {
        "name": "fct_orders",
        "sql": """
with orders as (
    select * from {{ ref('stg_orders') }}
),

users as (
    select * from {{ ref('stg_users') }}
),

order_items as (
    select
        order_id,
        sum(sale_price) as order_revenue,
        count(*) as num_items
    from {{ ref('stg_order_items') }}
    group by order_id
),

final as (
    select
        o.order_id,
        o.user_id,
        o.status,
        o.created_at,
        o.returned_at,
        o.shipped_at,
        o.delivered_at,
        u.country,
        u.age,
        u.gender,
        oi.order_revenue,
        oi.num_items,
        case
            when o.status in ('Complete', 'Shipped') then 'Active'
            when o.status in ('Cancelled', 'Returned') then 'Inactive'
            else 'In Progress'
        end as status_group
    from orders o
    left join users u on o.user_id = u.user_id
    left join order_items oi on o.order_id = oi.order_id
)

select * from final
"""
    },

    "stg_orders": {
        "name": "stg_orders",
        "sql": """
with source as (
    select * from {{ source('thelook', 'orders') }}
),

renamed as (
    select
        order_id,
        user_id,
        status,
        gender,
        created_at,
        returned_at,
        shipped_at,
        delivered_at,
        num_of_item
    from source
)

select * from renamed
"""
    },
}


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Pass a model name as argument to run a specific example
    # e.g.: python dbt_doc_generator.py stg_orders
    # Default: fct_orders

    model_key = sys.argv[1] if len(sys.argv) > 1 else "fct_orders"

    if model_key not in EXAMPLE_MODELS:
        print(f"Unknown model: {model_key}")
        print(f"Available: {', '.join(EXAMPLE_MODELS.keys())}")
        sys.exit(1)

    example = EXAMPLE_MODELS[model_key]
    print(f"\nGenerating schema.yml for: {example['name']}")
    print("This may take 10-20 seconds...\n")

    result = generate_schema_yml(
        sql=example["sql"],
        model_name=example["name"]
    )

    print_report(result)

    # Optionally save to file
    # save_schema_yml(result)
