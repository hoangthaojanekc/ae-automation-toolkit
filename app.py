"""
AE Automation Toolkit — Web UI
================================
Local web interface for all three analytics engineering agents.
Run this file, open localhost:5000 in your browser.

Usage:
    pip install flask anthropic pyyaml
    python app.py
"""

from flask import Flask, request, jsonify
import anthropic
import re
import yaml
import json
from datetime import datetime

app = Flask(__name__)

# ── Shared Claude client ──────────────────────────────────────────────────────

def get_client():
    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment


# ── Agent logic (imported from your existing agents) ─────────────────────────

SQL_SYSTEM_PROMPT = """You are a senior BigQuery optimization expert.
When given a SQL query, you analyze it for performance and cost issues,
then return an optimized version.

You always check for:
1. SELECT * (always replace with specific columns)
2. Missing partition filters on date/timestamp columns
3. Missing clustering column filters
4. Unnecessary JOINs or subqueries that could be CTEs
5. ORDER BY without LIMIT (extremely expensive in BigQuery)
6. COUNT(DISTINCT) alternatives using APPROX_COUNT_DISTINCT where precision isn't critical

Return your response in EXACTLY this format:

ISSUES_FOUND:
- [issue 1]
- [issue 2]

OPTIMIZED_QUERY:
```sql
[the full rewritten query]
```

EXPLANATION:
[2-3 sentences explaining the key changes]

ESTIMATED_SAVINGS:
[specific savings estimate]
"""

DBT_SYSTEM_PROMPT = """You are a senior analytics engineer who writes exceptional
dbt documentation. When given a dbt model SQL file, generate a complete, valid schema.yml block.

Rules:
1. Read the SQL carefully — column names, joins, and business logic tell you what each field means
2. Write descriptions in plain business language
3. Recommend tests based on column semantics:
   - Primary keys: unique + not_null
   - Foreign keys: not_null + relationships
   - Status/type fields: accepted_values
   - Metrics/amounts: not_null
4. Never invent column names — only document what is in the SELECT
5. Return ONLY valid YAML — no preamble, no markdown fences

Use this exact structure:
version: 2
models:
  - name: [model_name]
    description: "[business purpose]"
    columns:
      - name: [column_name]
        description: "[plain English description]"
        tests:
          - [test_name]
"""

CAMPAIGN_SYSTEM_PROMPT = """You are a senior marketing analytics engineer.
When given campaign metrics, identify performance vs benchmarks, flag anomalies,
and write executive-ready analysis.

Industry benchmarks: email open rate 20-25%, CTR 2-5%, conversion 1-3%

Check for: conversion rates vs benchmarks, funnel drop-off, unsubscribe/spam spikes,
gaps between expected and actual send volumes, data quality signals.

Return in EXACTLY this format:

HEADLINE:
[One specific sentence with numbers — the most important thing leadership needs to know]

PERFORMANCE_SUMMARY:
[2-3 sentences on overall campaign health]

ANOMALIES:
- [anomaly — what it is, why surprising, urgency: LOW/MEDIUM/HIGH]

KEY_METRICS:
- [metric]: [value] — [interpretation]

RECOMMENDATION:
[One clear action with owner, action, and timeline]

WATCH_LIST:
[1-2 metrics to monitor next send with escalation thresholds]
"""


def run_sql_optimizer(query: str, context: str = "") -> dict:
    client = get_client()
    user_msg = f"Optimize this BigQuery SQL:\n\n```sql\n{query}\n```"
    if context:
        user_msg += f"\n\nTable context: {context}"

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SQL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}]
    )
    text = msg.content[0].text
    sql_match = re.search(r"```sql\n(.*?)```", text, re.DOTALL)

    def extract(label):
        m = re.search(rf"{label}:\n(.*?)(?=\n[A-Z_]+:|$)", text, re.DOTALL)
        return m.group(1).strip() if m else ""

    return {
        "issues": extract("ISSUES_FOUND"),
        "optimized_query": sql_match.group(1).strip() if sql_match else "",
        "explanation": extract("EXPLANATION"),
        "estimated_savings": extract("ESTIMATED_SAVINGS"),
    }


def run_dbt_doc_generator(sql: str, model_name: str = "") -> dict:
    client = get_client()
    context = f"Model name: {model_name}\n\n" if model_name else ""
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=DBT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"{context}Generate schema.yml for:\n\n{sql}"}]
    )
    raw = msg.content[0].text.strip()
    clean = re.sub(r"^```ya?ml\s*", "", raw, flags=re.MULTILINE)
    clean = re.sub(r"```$", "", clean, flags=re.MULTILINE).strip()

    is_valid = False
    try:
        parsed = yaml.safe_load(clean)
        is_valid = isinstance(parsed, dict) and "models" in parsed
    except Exception:
        pass

    return {"yaml_output": clean, "is_valid": is_valid}


def run_campaign_analyst(metrics: str, campaign_name: str = "Campaign") -> dict:
    client = get_client()
    context = f"Campaign: {campaign_name}\nDate: {datetime.now().strftime('%B %d, %Y')}\n"
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=CAMPAIGN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"{context}\nMetrics:\n\n{metrics}"}]
    )
    text = msg.content[0].text

    def extract(label):
        m = re.search(rf"{label}:\n(.*?)(?=\n[A-Z_]+:|$)", text, re.DOTALL)
        return m.group(1).strip() if m else ""

    return {
        "headline": extract("HEADLINE"),
        "performance_summary": extract("PERFORMANCE_SUMMARY"),
        "anomalies": extract("ANOMALIES"),
        "key_metrics": extract("KEY_METRICS"),
        "recommendation": extract("RECOMMENDATION"),
        "watch_list": extract("WATCH_LIST"),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    from flask import Response
    return Response(HTML, mimetype="text/html")

@app.route("/api/sql", methods=["POST"])
def api_sql():
    data = request.json
    result = run_sql_optimizer(data.get("query", ""), data.get("context", ""))
    return jsonify(result)

@app.route("/api/dbt", methods=["POST"])
def api_dbt():
    data = request.json
    result = run_dbt_doc_generator(data.get("sql", ""), data.get("model_name", ""))
    return jsonify(result)

@app.route("/api/campaign", methods=["POST"])
def api_campaign():
    data = request.json
    result = run_campaign_analyst(data.get("metrics", ""), data.get("campaign_name", "Campaign"))
    return jsonify(result)

@app.route("/api/upload", methods=["POST"])
def api_upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400
    try:
        content = file.read().decode("utf-8")
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ── HTML / CSS / JS (single file) ─────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AE Automation Toolkit</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0a0f;
    --surface: #111118;
    --surface2: #1a1a24;
    --border: #2a2a3a;
    --accent: #7b6ef6;
    --accent2: #4ecdc4;
    --accent3: #f7b731;
    --text: #e8e8f0;
    --text-dim: #6b6b8a;
    --success: #4ecdc4;
    --warning: #f7b731;
    --danger: #ff6b6b;
    --font-display: 'Syne', sans-serif;
    --font-mono: 'DM Mono', monospace;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-display);
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* Background grid */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(var(--border) 1px, transparent 1px),
      linear-gradient(90deg, var(--border) 1px, transparent 1px);
    background-size: 40px 40px;
    opacity: 0.3;
    pointer-events: none;
    z-index: 0;
  }

  .container {
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 24px;
    position: relative;
    z-index: 1;
  }

  /* Header */
  header {
    padding: 48px 0 40px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 48px;
  }

  .header-tag {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--accent);
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-bottom: 12px;
  }

  h1 {
    font-size: clamp(28px, 4vw, 44px);
    font-weight: 800;
    letter-spacing: -0.02em;
    line-height: 1.1;
    background: linear-gradient(135deg, var(--text) 0%, var(--accent) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .subtitle {
    margin-top: 10px;
    color: var(--text-dim);
    font-size: 15px;
    font-weight: 400;
  }

  /* Agent tabs */
  .tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 32px;
    background: var(--surface);
    padding: 4px;
    border-radius: 12px;
    border: 1px solid var(--border);
    width: fit-content;
  }

  .tab {
    padding: 10px 20px;
    border-radius: 8px;
    border: none;
    background: transparent;
    color: var(--text-dim);
    font-family: var(--font-display);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    letter-spacing: 0.01em;
  }

  .tab:hover { color: var(--text); }

  .tab.active {
    background: var(--surface2);
    color: var(--text);
    border: 1px solid var(--border);
  }

  .tab[data-agent="sql"].active { color: var(--accent); }
  .tab[data-agent="dbt"].active { color: var(--accent2); }
  .tab[data-agent="campaign"].active { color: var(--accent3); }

  /* Panels */
  .panel { display: none; }
  .panel.active { display: block; }

  /* Agent card */
  .agent-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
  }

  .agent-header {
    padding: 20px 24px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .agent-badge {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.1em;
    padding: 4px 10px;
    border-radius: 20px;
    font-weight: 500;
  }

  .badge-sql { background: rgba(123,110,246,0.15); color: var(--accent); border: 1px solid rgba(123,110,246,0.3); }
  .badge-dbt { background: rgba(78,205,196,0.15); color: var(--accent2); border: 1px solid rgba(78,205,196,0.3); }
  .badge-campaign { background: rgba(247,183,49,0.15); color: var(--accent3); border: 1px solid rgba(247,183,49,0.3); }

  .agent-title {
    font-size: 16px;
    font-weight: 700;
  }

  .agent-desc {
    margin-left: auto;
    font-size: 12px;
    color: var(--text-dim);
    font-family: var(--font-mono);
  }

  .agent-body {
    padding: 24px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }

  @media (max-width: 700px) {
    .agent-body { grid-template-columns: 1fr; }
    .tabs { flex-wrap: wrap; width: 100%; }
  }

  /* Input section */
  .input-section label {
    display: block;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 8px;
    font-family: var(--font-mono);
  }

  textarea {
    width: 100%;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text);
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.6;
    padding: 14px;
    resize: vertical;
    min-height: 200px;
    transition: border-color 0.2s;
    outline: none;
  }

  textarea:focus { border-color: var(--accent); }

  input[type="text"] {
    width: 100%;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text);
    font-family: var(--font-mono);
    font-size: 12px;
    padding: 10px 14px;
    outline: none;
    transition: border-color 0.2s;
    margin-bottom: 12px;
  }

  input[type="text"]:focus { border-color: var(--accent); }

  .run-btn {
    width: 100%;
    padding: 14px;
    border-radius: 10px;
    border: none;
    font-family: var(--font-display);
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
    margin-top: 12px;
    letter-spacing: 0.02em;
    position: relative;
    overflow: hidden;
  }

  .btn-sql { background: var(--accent); color: white; }
  .btn-dbt { background: var(--accent2); color: #0a0a0f; }
  .btn-campaign { background: var(--accent3); color: #0a0a0f; }

  .run-btn:hover { transform: translateY(-1px); filter: brightness(1.1); }
  .run-btn:active { transform: translateY(0); }
  .run-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

  /* Output section */
  .output-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .output-block {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }

  .output-block-header {
    padding: 8px 14px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-dim);
    font-family: var(--font-mono);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .output-block-body {
    padding: 14px;
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 280px;
    overflow-y: auto;
    color: var(--text);
  }

  .output-block-body::-webkit-scrollbar { width: 4px; }
  .output-block-body::-webkit-scrollbar-track { background: transparent; }
  .output-block-body::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  /* Status indicators */
  .dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
  .dot-green { background: var(--success); box-shadow: 0 0 6px var(--success); }
  .dot-yellow { background: var(--warning); box-shadow: 0 0 6px var(--warning); }
  .dot-red { background: var(--danger); box-shadow: 0 0 6px var(--danger); }

  /* Loading state */
  .loading {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 20px 14px;
    color: var(--text-dim);
    font-family: var(--font-mono);
    font-size: 12px;
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    flex-shrink: 0;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  /* Empty state */
  .empty-state {
    padding: 32px 14px;
    text-align: center;
    color: var(--text-dim);
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.8;
  }

  /* Copy button */
  .copy-btn {
    margin-left: auto;
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-family: var(--font-mono);
    font-size: 10px;
    padding: 3px 8px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .copy-btn:hover { color: var(--text); border-color: var(--text-dim); }

  /* Validity badge */
  .valid-badge {
    font-family: var(--font-mono);
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 4px;
    margin-left: auto;
  }

  .valid-yes { background: rgba(78,205,196,0.15); color: var(--accent2); }
  .valid-no  { background: rgba(255,107,107,0.15); color: var(--danger); }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="header-tag">Analytics Engineering Automation Toolkit</div>
    <h1>AE Agent Dashboard</h1>
    <p class="subtitle">Three AI agents. One interface. Built with Claude API.</p>
  </header>

  <div class="tabs">
    <button class="tab active" data-agent="sql" onclick="switchTab('sql')">SQL Optimizer</button>
    <button class="tab" data-agent="dbt" onclick="switchTab('dbt')">dbt Doc Generator</button>
    <button class="tab" data-agent="campaign" onclick="switchTab('campaign')">Campaign Analyst</button>
  </div>

  <!-- SQL OPTIMIZER -->
  <div class="panel active" id="panel-sql">
    <div class="agent-card">
      <div class="agent-header">
        <span class="agent-badge badge-sql">AGENT 01</span>
        <span class="agent-title">BigQuery SQL Optimizer</span>
        <span class="agent-desc">query → optimized query + savings</span>
      </div>
      <div class="agent-body">
        <div class="input-section">
          <label>BigQuery SQL Query</label>
          <textarea id="sql-input" placeholder="Paste your BigQuery SQL here...">SELECT
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
ORDER BY total_spent DESC</textarea>
          <label style="margin-top:12px">Table Context (optional)</label>
          <input type="text" id="sql-context" placeholder="e.g. orders: 100M rows, partitioned on created_at, clustered on user_id">
          <button class="run-btn btn-sql" onclick="runSQL()">Run SQL Optimizer</button>
        </div>
        <div class="output-section" id="sql-output">
          <div class="output-block">
            <div class="output-block-body">
              <div class="empty-state">Output will appear here.<br>Paste a query and click Run.</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- DBT DOC GENERATOR -->
  <div class="panel" id="panel-dbt">
    <div class="agent-card">
      <div class="agent-header">
        <span class="agent-badge badge-dbt">AGENT 02</span>
        <span class="agent-title">dbt Documentation Generator</span>
        <span class="agent-desc">model SQL → schema.yml</span>
      </div>
      <div class="agent-body">
        <div class="input-section">
          <label>Model Name</label>
          <input type="text" id="dbt-model-name" placeholder="e.g. fct_orders">
          <label>dbt Model SQL</label>
          <textarea id="dbt-input" placeholder="Paste your dbt model SQL here...">with orders as (
    select * from {% raw %}{{ ref('stg_orders') }}{% endraw %}
),
users as (
    select * from {% raw %}{{ ref('stg_users') }}{% endraw %}
),
final as (
    select
        o.order_id,
        o.user_id,
        o.status,
        o.created_at,
        u.country,
        case
            when o.status in ('Complete', 'Shipped') then 'Active'
            when o.status in ('Cancelled', 'Returned') then 'Inactive'
            else 'In Progress'
        end as status_group
    from orders o
    left join users u on o.user_id = u.user_id
)
select * from final</textarea>
          <button class="run-btn btn-dbt" onclick="runDBT()">Generate schema.yml</button>
        </div>
        <div class="output-section" id="dbt-output">
          <div class="output-block">
            <div class="output-block-body">
              <div class="empty-state">schema.yml will appear here.<br>Paste a model and click Generate.</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- CAMPAIGN ANALYST -->
  <div class="panel" id="panel-campaign">
    <div class="agent-card">
      <div class="agent-header">
        <span class="agent-badge badge-campaign">AGENT 03</span>
        <span class="agent-title">Campaign Performance Analyst</span>
        <span class="agent-desc">metrics → executive narrative</span>
      </div>
      <div class="agent-body">
        <div class="input-section">
          <label>Campaign Name</label>
          <input type="text" id="campaign-name" placeholder="e.g. May 2026 Re-engagement">
          <label>Upload CSV (optional)</label>
          <input type="file" id="csv-upload" accept=".csv,.txt"
                 onchange="handleFileUpload(this)"
                 style="width:100%; color:var(--text-dim); font-family:var(--font-mono);
                         font-size:12px; margin-bottom:12px; background:var(--surface2);
                         border:1px solid var(--border); border-radius:10px; padding:10px 14px;
                         cursor:pointer;">
          <label>Campaign Metrics</label>
          <textarea id="campaign-input" placeholder="Paste campaign metrics here — CSV, copied from a spreadsheet, or plain numbers...">Campaign: Product Migration Bootcamp
Send date: May 1, 2026

Total eligible users: 1,500
Emails sent: 1,500
Delivered: 1,487
Unique opens: 892
Unique clicks: 445
Opt-ins recorded: 900
Estimated target: 500-600
Users migrated (7 days): 810

Open rate: 60.0%
Opt-in rate: 60.0%
7-day migration rate: 90.0%
Prior benchmark open rate: 22%</textarea>
          <button class="run-btn btn-campaign" onclick="runCampaign()">Analyze Campaign</button>
        </div>
        <div class="output-section" id="campaign-output">
          <div class="output-block">
            <div class="output-block-body">
              <div class="empty-state">Analysis will appear here.<br>Paste metrics and click Analyze.</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

</div>

<script>
function switchTab(agent) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelector(`[data-agent="${agent}"]`).classList.add('active');
  document.getElementById(`panel-${agent}`).classList.add('active');
}

function setLoading(outputId) {
  document.getElementById(outputId).innerHTML = `
    <div class="output-block">
      <div class="output-block-body">
        <div class="loading">
          <div class="spinner"></div>
          Sending to Claude API — this takes 10-20 seconds...
        </div>
      </div>
    </div>`;
}

function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy', 1500);
  });
}

async function runSQL() {
  const query = document.getElementById('sql-input').value.trim();
  const context = document.getElementById('sql-context').value.trim();
  if (!query) return;

  setLoading('sql-output');
  const btn = document.querySelector('.btn-sql');
  btn.disabled = true;

  try {
    const res = await fetch('/api/sql', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query, context})
    });
    const data = await res.json();

    document.getElementById('sql-output').innerHTML = `
      <div class="output-block">
        <div class="output-block-header">
          <span class="dot dot-yellow"></span> Issues Found
        </div>
        <div class="output-block-body">${escHtml(data.issues)}</div>
      </div>
      <div class="output-block">
        <div class="output-block-header">
          <span class="dot dot-green"></span> Optimized Query
          <button class="copy-btn" onclick="copyText(${JSON.stringify(data.optimized_query)}, this)">Copy</button>
        </div>
        <div class="output-block-body">${escHtml(data.optimized_query)}</div>
      </div>
      <div class="output-block">
        <div class="output-block-header">
          <span class="dot dot-green"></span> Explanation
        </div>
        <div class="output-block-body">${escHtml(data.explanation)}</div>
      </div>
      <div class="output-block">
        <div class="output-block-header">
          <span class="dot dot-green"></span> Estimated Savings
        </div>
        <div class="output-block-body">${escHtml(data.estimated_savings)}</div>
      </div>`;
  } catch(e) {
    showError('sql-output', e);
  }
  btn.disabled = false;
}

async function runDBT() {
  const sql = document.getElementById('dbt-input').value.trim();
  const model_name = document.getElementById('dbt-model-name').value.trim();
  if (!sql) return;

  setLoading('dbt-output');
  const btn = document.querySelector('.btn-dbt');
  btn.disabled = true;

  try {
    const res = await fetch('/api/dbt', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sql, model_name})
    });
    const data = await res.json();
    const validClass = data.is_valid ? 'valid-yes' : 'valid-no';
    const validText = data.is_valid ? '✓ Valid YAML' : '⚠ Check YAML';

    document.getElementById('dbt-output').innerHTML = `
      <div class="output-block">
        <div class="output-block-header">
          <span class="dot dot-green"></span> Generated schema.yml
          <span class="valid-badge ${validClass}">${validText}</span>
          <button class="copy-btn" onclick="copyText(${JSON.stringify(data.yaml_output)}, this)">Copy</button>
        </div>
        <div class="output-block-body">${escHtml(data.yaml_output)}</div>
      </div>`;
  } catch(e) {
    showError('dbt-output', e);
  }
  btn.disabled = false;
}

async function runCampaign() {
  const metrics = document.getElementById('campaign-input').value.trim();
  const campaign_name = document.getElementById('campaign-name').value.trim() || 'Campaign';
  if (!metrics) return;

  setLoading('campaign-output');
  const btn = document.querySelector('.btn-campaign');
  btn.disabled = true;

  try {
    const res = await fetch('/api/campaign', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({metrics, campaign_name})
    });
    const data = await res.json();

    document.getElementById('campaign-output').innerHTML = `
      <div class="output-block">
        <div class="output-block-header"><span class="dot dot-yellow"></span> Headline</div>
        <div class="output-block-body">${escHtml(data.headline)}</div>
      </div>
      <div class="output-block">
        <div class="output-block-header"><span class="dot dot-green"></span> Performance Summary</div>
        <div class="output-block-body">${escHtml(data.performance_summary)}</div>
      </div>
      <div class="output-block">
        <div class="output-block-header"><span class="dot dot-red"></span> Anomalies</div>
        <div class="output-block-body">${escHtml(data.anomalies)}</div>
      </div>
      <div class="output-block">
        <div class="output-block-header"><span class="dot dot-green"></span> Key Metrics</div>
        <div class="output-block-body">${escHtml(data.key_metrics)}</div>
      </div>
      <div class="output-block">
        <div class="output-block-header"><span class="dot dot-green"></span> Recommendation</div>
        <div class="output-block-body">${escHtml(data.recommendation)}</div>
      </div>
      <div class="output-block">
        <div class="output-block-header"><span class="dot dot-yellow"></span> Watch List</div>
        <div class="output-block-body">${escHtml(data.watch_list)}</div>
      </div>`;
  } catch(e) {
    showError('campaign-output', e);
  }
  btn.disabled = false;
}

function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function handleFileUpload(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    document.getElementById('campaign-input').value = e.target.result;
    // Auto-fill campaign name from filename if empty
    const nameField = document.getElementById('campaign-name');
    if (!nameField.value) {
      nameField.value = file.name.replace(/\.csv|\.txt/gi, '').replace(/_/g, ' ');
    }
  };
  reader.readAsText(file);
}

function showError(outputId, err) {
  document.getElementById(outputId).innerHTML = `
    <div class="output-block">
      <div class="output-block-header"><span class="dot dot-red"></span> Error</div>
      <div class="output-block-body">Something went wrong: ${err.message}\n\nMake sure your ANTHROPIC_API_KEY is set and the server is running.</div>
    </div>`;
}
</script>
</body>
</html>"""


if __name__ == "__main__":
    print("\n" + "═" * 55)
    print("  AE Automation Toolkit — Web UI")
    print("═" * 55)
    print("  Open in browser: http://localhost:5000")
    print("  Stop server:     Ctrl+C")
    print("═" * 55 + "\n")
    app.run(debug=False, port=5000)
