"""
Marketing Campaign Performance Analyst Agent
=============================================
Portfolio project: Analytics Engineering + AI Automation
Agent 3 of 3

What it does:
- Takes campaign performance metrics as input (CSV, pasted text, or dict)
- Uses Claude AI to analyze performance vs benchmarks
- Flags anomalies and unexpected patterns
- Returns an executive-ready narrative + structured recommendations

Interview talking point:
"I built a campaign analyst agent that takes raw performance metrics and
returns an executive narrative with anomaly detection. It flags when
numbers deviate significantly from benchmarks — the kind of catch I made
manually when I found 1,200 missing users in a critical email send.
This automates that vigilance."
"""

import anthropic
import csv
import json
import sys
import io
from datetime import datetime


# ── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior marketing analytics engineer who specializes
in campaign performance analysis. You combine deep data intuition with clear
business communication.

When given campaign metrics, you:
1. Identify what performed above or below expectation
2. Flag anomalies — numbers that are surprising, inconsistent, or warrant
   immediate investigation
3. Identify the single most important insight a business leader needs to act on
4. Write in clear, confident business language — no hedging, no jargon

You always check for:
- Conversion rates that deviate significantly from industry benchmarks
  (email open rate benchmark: 20-25%, CTR: 2-5%, conversion: 1-3%)
- Large gaps between sent/delivered/opened/converted (drop-off analysis)
- Metrics that improved dramatically — understand why before celebrating
- Metrics that declined — flag urgency level (monitor / investigate / escalate)
- Data quality signals: round numbers, impossible values, missing segments

Return your response in EXACTLY this format:

HEADLINE:
[One sentence. The single most important thing leadership needs to know.
Be specific — include numbers.]

PERFORMANCE_SUMMARY:
[2-3 sentences. Overall campaign health. What worked, what didn't.]

ANOMALIES:
- [anomaly 1 — what it is, why it's surprising, urgency: LOW/MEDIUM/HIGH]
- [anomaly 2]
(write "None detected" if everything looks clean)

KEY_METRICS:
- [metric name]: [value] — [one-line interpretation]
- [metric name]: [value] — [one-line interpretation]
(include 4-6 of the most meaningful metrics)

RECOMMENDATION:
[One clear action. Who should take it, what they should do, by when.]

WATCH_LIST:
[1-2 metrics to monitor in the next send or reporting period, and what
threshold should trigger escalation.]
"""


# ── Agent ─────────────────────────────────────────────────────────────────────

def analyze_campaign(metrics: str, campaign_name: str = "Campaign",
                     benchmarks: dict = None) -> dict:
    """
    Analyze campaign performance metrics and return executive narrative.

    Args:
        metrics:       Raw metrics as string — CSV, pasted text, or JSON
        campaign_name: Name of the campaign for context
        benchmarks:    Optional dict of expected values to compare against
                       e.g. {"open_rate": 0.22, "ctr": 0.03}

    Returns:
        dict with keys: headline, performance_summary, anomalies,
                        key_metrics, recommendation, watch_list, raw_response
    """
    client = anthropic.Anthropic()

    context = f"Campaign: {campaign_name}\n"
    context += f"Analysis date: {datetime.now().strftime('%B %d, %Y')}\n"

    if benchmarks:
        context += f"Expected benchmarks: {json.dumps(benchmarks, indent=2)}\n"

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"{context}\nCampaign metrics:\n\n{metrics}"
        }]
    )

    raw = message.content[0].text
    return _parse_response(raw)


def _parse_response(text: str) -> dict:
    """Parse Claude's structured response into a clean dict."""
    import re

    def extract(label: str) -> str:
        pattern = rf"{label}:\n(.*?)(?=\n[A-Z_]+:|$)"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ""

    return {
        "headline":            extract("HEADLINE"),
        "performance_summary": extract("PERFORMANCE_SUMMARY"),
        "anomalies":           extract("ANOMALIES"),
        "key_metrics":         extract("KEY_METRICS"),
        "recommendation":      extract("RECOMMENDATION"),
        "watch_list":          extract("WATCH_LIST"),
        "raw_response":        text,
    }


def print_report(result: dict, campaign_name: str = "Campaign") -> None:
    """Pretty-print the campaign analysis report."""
    print(f"\n{'═' * 65}")
    print(f"  Campaign Performance Analysis: {campaign_name}")
    print(f"{'═' * 65}\n")

    print("🎯  HEADLINE:")
    print(f"    {result['headline']}\n")

    print("─" * 65)
    print("📊  PERFORMANCE SUMMARY:")
    print(result["performance_summary"])

    print(f"\n{'─' * 65}")
    print("⚠️   ANOMALIES:")
    print(result["anomalies"])

    print(f"\n{'─' * 65}")
    print("📈  KEY METRICS:")
    print(result["key_metrics"])

    print(f"\n{'─' * 65}")
    print("✅  RECOMMENDATION:")
    print(result["recommendation"])

    print(f"\n{'─' * 65}")
    print("👀  WATCH LIST:")
    print(result["watch_list"])

    print(f"\n{'═' * 65}\n")


def analyze_from_csv(filepath: str, campaign_name: str = None) -> dict:
    """Load metrics from a CSV file and analyze."""
    with open(filepath, "r") as f:
        content = f.read()

    name = campaign_name or filepath.split("/")[-1].replace(".csv", "")
    return analyze_campaign(metrics=content, campaign_name=name)


# ── Example Campaigns ─────────────────────────────────────────────────────────
# These mirror real marketing analytics scenarios from your work stories

EXAMPLE_CAMPAIGNS = {

    # Mirrors your Story 2: bootcamp campaign (900 vs 600 estimate)
    "bootcamp_migration": {
        "name": "Product Migration Bootcamp — May 2026",
        "benchmarks": {"open_rate": 0.22, "ctr": 0.03, "conversion": 0.15},
        "metrics": """
Campaign: Product Migration Bootcamp
Send date: May 1, 2026
Segment: Lapsed users eligible for new product

Total eligible users: 1,500
Emails sent: 1,500
Delivered: 1,487
Bounced: 13
Unique opens: 892
Unique clicks: 445
Opt-ins recorded: 900
Estimated opt-in target: 500-600
Users migrated to new product within 7 days: 810
Total migrated (30-day window): 900

Open rate: 60.0%
Click-to-open rate: 49.9%
Opt-in rate: 60.0%
7-day migration rate: 90.0%

Prior campaign benchmark (open rate): 22%
Prior campaign benchmark (opt-in rate): 15%
"""
    },

    # Mirrors your Story 3: data quality catch (1,200 missing users)
    "migration_comms": {
        "name": "New Product Launch — Migration Communications",
        "benchmarks": {"delivery_rate": 0.98, "open_rate": 0.25},
        "metrics": """
Campaign: New Product Launch Migration Email
Send date: January 15, 2026
Segment: All active users eligible for migration

Total users in CRM: 12,000
Emails sent via Salesforce: 10,800
Delivered: 10,764
Bounced: 36
Unique opens: 2,800
Unique clicks: 980

Expected send volume: 12,000
Actual send volume: 10,800
Gap: 1,200 users (10% of total eligible base)

Open rate (of sent): 25.9%
Delivery rate: 99.7%
First-week migration rate (historical benchmark): 20%
Estimated revenue impact of delay (monthly subscription): $24,000/month
"""
    },

    # Generic underperforming campaign for contrast
    "q1_reengagement": {
        "name": "Q1 Re-engagement Campaign",
        "benchmarks": {"open_rate": 0.22, "ctr": 0.03, "conversion": 0.02},
        "metrics": """
Campaign: Q1 Re-engagement — Lapsed 90-day Users
Send date: March 10, 2026
Segment: Users with no activity in 90+ days

Total eligible: 8,500
Emails sent: 8,500
Delivered: 8,330
Bounced: 170
Unique opens: 1,250
Unique clicks: 87
Conversions (reactivated): 43

Open rate: 15.0%
CTR: 1.0%
Conversion rate: 0.5%
Unsubscribes: 340
Spam complaints: 28
"""
    },
}


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Pass a campaign name as argument to run a specific example
    # Or pass a .csv file path to analyze your own data
    # e.g.: python campaign_analyst.py bootcamp_migration
    #       python campaign_analyst.py my_campaign.csv

    arg = sys.argv[1] if len(sys.argv) > 1 else "bootcamp_migration"

    # Check if it's a CSV file
    if arg.endswith(".csv"):
        print(f"\nLoading campaign data from: {arg}")
        result = analyze_from_csv(arg)
        print_report(result, arg)

    elif arg in EXAMPLE_CAMPAIGNS:
        example = EXAMPLE_CAMPAIGNS[arg]
        print(f"\nAnalyzing: {example['name']}")
        print("This may take 10-20 seconds...\n")
        result = analyze_campaign(
            metrics=example["metrics"],
            campaign_name=example["name"],
            benchmarks=example.get("benchmarks")
        )
        print_report(result, example["name"])

    else:
        print(f"Not found: {arg}")
        print(f"Built-in examples: {', '.join(EXAMPLE_CAMPAIGNS.keys())}")
        print("Or pass a .csv file path to analyze your own data")
        sys.exit(1)
