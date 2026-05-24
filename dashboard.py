"""
GitHub Issue Triage Agent — Operational Dashboard.

Live operational view of an autonomous triage system powered by Devin.
Reads sessions from the Devin v3 API filtered by the `auto-triage` tag.

Run:
    source .venv/bin/activate
    set -a && source .env && set +a
    streamlit run dashboard.py
"""
from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["DEVIN_API_KEY"]
ORG_ID = os.environ["DEVIN_ORG_ID"]
BASE = f"https://api.devin.ai/v3/organizations/{ORG_ID}"
TRIAGE_TAG = "auto-triage"

USD_PER_ACU = 2.50
HOURS_SAVED_PER_FIX = 2.0

st.set_page_config(
    page_title="GitHub Issue Triage Agent",
    layout="wide",
)

# ─── Global styling ──────────────────────────────────────────────────
st.markdown(
    """
    <style>
      :root {
        --bg-card: #ffffff;
        --border: #e6e8eb;
        --muted: #6b7280;
        --accent: #2563eb;
        --success: #16a34a;
        --warning: #f59e0b;
        --danger: #dc2626;
      }

      .stApp {
        background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
      }

      .brand-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 24px 28px;
        margin-bottom: 18px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
      }
      .brand-row {
        display: flex;
        align-items: center;
        gap: 16px;
      }
      .brand-logo {
        width: 44px; height: 44px;
        border-radius: 10px;
        background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
        display: flex; align-items: center; justify-content: center;
        color: white; font-weight: 700; font-size: 20px;
        letter-spacing: 0.5px;
      }
      .brand-title { font-size: 24px; font-weight: 700; color: #0f172a; line-height: 1.1; }
      .brand-sub { font-size: 13px; color: var(--muted); margin-top: 4px; }

      .pill {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.3px;
      }
      .pill-success { background: #dcfce7; color: #166534; }
      .pill-warning { background: #fef3c7; color: #92400e; }
      .pill-danger  { background: #fee2e2; color: #991b1b; }
      .pill-muted   { background: #f1f5f9; color: #475569; }
      .pill-info    { background: #dbeafe; color: #1e40af; }

      section[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid var(--border);
      }

      div[data-testid="stMetric"] {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 12px 16px;
        box-shadow: 0 1px 1px rgba(0,0,0,0.02);
      }
      div[data-testid="stMetricLabel"] {
        font-size: 12px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      div[data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: 700;
      }

      h2, h3 {
        color: #0f172a;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─── Data fetch ───────────────────────────────────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def fetch_sessions() -> list[dict]:
    headers = {"Authorization": f"Bearer {API_KEY}"}
    all_items: list[dict] = []
    cursor: str | None = None

    while True:
        params: dict = {"first": 100}
        if cursor:
            params["after"] = cursor
        resp = requests.get(
            f"{BASE}/sessions", headers=headers, params=params, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        all_items.extend(data.get("items", []))
        if not data.get("has_next_page"):
            break
        cursor = data.get("end_cursor")
        if not cursor:
            break

    return [s for s in all_items if TRIAGE_TAG in (s.get("tags") or [])]


def build_sample_sessions() -> list[dict]:
    now = int(datetime.now(tz=timezone.utc).timestamp())
    template = [
        {"complexity": "low", "category": "docs", "action_taken": "pr_opened", "pr_state": "merged"},
        {"complexity": "low", "category": "type-hints", "action_taken": "pr_opened", "pr_state": "merged"},
        {"complexity": "low", "category": "lint", "action_taken": "pr_opened", "pr_state": "open"},
        {"complexity": "medium", "category": "test", "action_taken": "pr_opened", "pr_state": "merged"},
        {"complexity": "medium", "category": "refactor", "action_taken": "pr_opened", "pr_state": "open"},
        {"complexity": "low", "category": "docs", "action_taken": "pr_opened", "pr_state": "merged"},
        {"complexity": "low", "category": "type-hints", "action_taken": "pr_opened", "pr_state": "merged"},
        {"complexity": "high", "category": "bug", "action_taken": "skipped_unsafe", "pr_state": None},
        {"complexity": "high", "category": "refactor", "action_taken": "skipped_unsafe", "pr_state": None},
        {"complexity": "medium", "category": "test", "action_taken": "aborted_too_complex", "pr_state": None},
    ]
    sessions = []
    for i, t in enumerate(template):
        prs = [{"pr_url": f"https://github.com/torabata/superset/pull/{200 + i}", "pr_state": t["pr_state"]}] if t["pr_state"] else []
        created_at = now - (i * 3600 * 8)
        # Sample sessions span 10–25 minutes
        duration = 10 * 60 + (i % 5) * 3 * 60
        sessions.append({
            "session_id": f"sample-{i}",
            "url": f"https://app.devin.ai/sessions/sample-{i}",
            "title": f"Sample issue #{100 + i}",
            "status": "exit",
            "tags": [TRIAGE_TAG, "sample"],
            "acus_consumed": 0.4 + (i * 0.05),
            "created_at": created_at,
            "updated_at": created_at + duration,
            "pull_requests": prs,
            "structured_output": {
                "complexity": t["complexity"],
                "category": t["category"],
                "action_taken": t["action_taken"],
                "pr_url": prs[0]["pr_url"] if prs else "",
                "summary": "Synthetic sample - toggle off in sidebar to see live data only.",
                "reasoning": "Sample data for demo purposes.",
                "files_changed": [],
            },
        })
    return sessions


def fmt_ts(ts: int | None) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def status_pill(status: str) -> str:
    cls = {
        "running": "pill-info",
        "new": "pill-muted",
        "claimed": "pill-muted",
        "exit": "pill-success",
        "error": "pill-danger",
        "suspended": "pill-warning",
        "resuming": "pill-info",
    }.get(status, "pill-muted")
    text = {
        "new": "queued",
        "claimed": "queued",
        "running": "running",
        "exit": "done",
        "error": "error",
        "suspended": "paused",
        "resuming": "running",
    }.get(status, status or "—")
    return f'<span class="pill {cls}">{text}</span>'


def action_pill(action: str) -> str:
    cls = {
        "pr_opened": "pill-success",
        "skipped_unsafe": "pill-warning",
        "aborted_too_complex": "pill-danger",
    }.get(action, "pill-muted")
    label = {
        "pr_opened": "PR opened",
        "skipped_unsafe": "Skipped",
        "aborted_too_complex": "Aborted",
    }.get(action, action or "—")
    return f'<span class="pill {cls}">{label}</span>'


def pr_state_pill(pr_state: str) -> str:
    if not pr_state or pr_state == "—":
        return '<span class="pill pill-muted">—</span>'
    cls = {
        "merged": "pill-success",
        "open": "pill-info",
        "closed": "pill-muted",
    }.get(pr_state, "pill-muted")
    return f'<span class="pill {cls}">{pr_state}</span>'


# ─── Header card ──────────────────────────────────────────────────────
st.markdown(
    """
    <div class="brand-card">
      <div class="brand-row">
        <div class="brand-logo">DV</div>
        <div>
          <div class="brand-title">GitHub Issue Triage Agent</div>
          <div class="brand-sub">Powered by Devin · autonomous triage and remediation of GitHub issues</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ─── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Controls")
    if st.button("Refresh data", use_container_width=True):
        fetch_sessions.clear()
        st.rerun()

    st.markdown("---")
    show_samples = st.toggle(
        "Include sample data",
        value=False,
        help="Pads the dashboard with synthetic sessions so early-stage demos aren't empty.",
    )

    st.markdown("---")
    st.markdown("**Assumptions**")
    st.markdown(f"- Cost: `${USD_PER_ACU:.2f}` per ACU")
    st.markdown(f"- Time saved per fix: `{HOURS_SAVED_PER_FIX:.1f}` engineer-hours")

    st.markdown("---")
    st.caption(f"Tag filter: `{TRIAGE_TAG}`")
    st.caption(f"Org: `{ORG_ID[:24]}…`")


# ─── Load data ────────────────────────────────────────────────────────
with st.spinner("Loading sessions..."):
    sessions = fetch_sessions()

if show_samples:
    sessions = sessions + build_sample_sessions()

if not sessions:
    st.warning(f"No sessions found with tag `{TRIAGE_TAG}` yet. Toggle 'Include sample data' to preview the dashboard.")
    st.stop()

structured = [s.get("structured_output") or {} for s in sessions]
structured = [so for so in structured if so]

# ─── Calculate metrics ────────────────────────────────────────────────
total = len(sessions)
running = sum(1 for s in sessions if s.get("status") in ("running", "new", "claimed", "resuming"))
auto_fixed = sum(1 for so in structured if so.get("action_taken") == "pr_opened")
skipped = sum(1 for so in structured if so.get("action_taken") == "skipped_unsafe")
aborted = sum(1 for so in structured if so.get("action_taken") == "aborted_too_complex")

merged = 0
total_prs = 0
for s in sessions:
    for pr in s.get("pull_requests") or []:
        total_prs += 1
        if pr.get("pr_state") == "merged":
            merged += 1
merge_rate = (merged / total_prs * 100) if total_prs else 0

total_acu = sum(s.get("acus_consumed", 0) for s in sessions)
total_cost = total_acu * USD_PER_ACU
hours_saved = auto_fixed * HOURS_SAVED_PER_FIX
cost_per_fix = (total_cost / auto_fixed) if auto_fixed else 0

seven_days_ago = int((datetime.now(tz=timezone.utc) - timedelta(days=7)).timestamp())
weekly_count = sum(1 for s in sessions if s.get("created_at", 0) >= seven_days_ago)


# ─── Time-based metrics ──────────────────────────────────────────────
import statistics


def session_duration_seconds(s: dict) -> int | None:
    created = s.get("created_at")
    updated = s.get("updated_at")
    if created and updated and updated >= created:
        return int(updated - created)
    return None


# MTTR = median time from issue creation (= session creation) to PR creation,
# considering only sessions that successfully opened a PR.
mttr_durations = [
    d for s in sessions
    if (s.get("structured_output") or {}).get("action_taken") == "pr_opened"
    and (d := session_duration_seconds(s)) is not None
]
mttr_minutes = statistics.median(mttr_durations) / 60 if mttr_durations else None

# Median session duration across all completed sessions
all_durations = [
    d for s in sessions
    if s.get("status") == "exit"
    and (d := session_duration_seconds(s)) is not None
]
median_session_minutes = statistics.median(all_durations) / 60 if all_durations else None


def fmt_minutes(m: float | None) -> str:
    if m is None:
        return "—"
    if m < 1:
        return f"{m * 60:.0f} sec"
    if m < 60:
        return f"{m:.1f} min"
    return f"{m / 60:.1f} hr"

# ─── Business outcomes ────────────────────────────────────────────────
st.subheader("Business outcomes")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(
    "Engineer-hours saved",
    f"{hours_saved:.1f}",
    help=f"Engineer time freed up by Devin. Calculated as auto-fixed count × {HOURS_SAVED_PER_FIX} hours per fix (the assumed cost of a human triaging + implementing the same change).",
)
c2.metric(
    "Cost (USD)",
    f"${total_cost:,.2f}",
    help=f"Total Devin spend across all sessions. Calculated as ACUs consumed × ${USD_PER_ACU:.2f} per ACU.",
)
c3.metric(
    "Cost per fix",
    f"${cost_per_fix:,.2f}" if auto_fixed else "—",
    help="Average Devin spend per pull request opened. The unit economics number: how much does it cost us to ship one autonomous fix?",
)
c4.metric(
    "MTTR (median)",
    fmt_minutes(mttr_minutes),
    help="Mean Time To Resolution. Median elapsed time from issue creation (= session start) to pull-request creation, across sessions that opened a PR.",
)
c5.metric(
    "PR merge rate",
    f"{merge_rate:.0f}%" if total_prs else "—",
    help="Of the pull requests Devin opened, what fraction were merged by a human reviewer. The truest signal that the agent is producing usable work.",
)

# ─── Operational metrics ──────────────────────────────────────────────
st.subheader("Operational metrics")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(
    "Total processed",
    total,
    help="Total number of issues that have been dispatched to Devin (regardless of outcome).",
)
c2.metric(
    "Auto-fixed (PR)",
    auto_fixed,
    help="Sessions where Devin judged the change safe and successfully opened a pull request.",
)
c3.metric(
    "Skipped (unsafe)",
    skipped,
    help="Sessions where Devin consulted the Safe-Change Heuristics knowledge note and decided NOT to modify code (e.g., security, auth, or DB-migration territory).",
)
c4.metric(
    "Aborted",
    aborted,
    help="Sessions where Devin started the fix but stopped mid-way after realising the change was more complex than initial triage suggested.",
)
c5.metric(
    "Running now",
    running,
    help="Sessions currently in flight (status: new, claimed, running, or resuming).",
)

c1, c2, c3 = st.columns(3)
c1.metric(
    "Throughput (last 7 days)",
    weekly_count,
    help="Issues dispatched in the trailing 7-day window. Indicates current operating tempo.",
)
c2.metric(
    "Auto-fix rate",
    f"{(auto_fixed / max(len(structured), 1) * 100):.0f}%" if structured else "—",
    help="Auto-fixed sessions as a percentage of completed sessions. The agent's effective hit rate.",
)
c3.metric(
    "Median session duration",
    fmt_minutes(median_session_minutes),
    help="Median wall-clock time for one Devin session to finish (clone → fix → PR). Useful for capacity planning.",
)

# ─── Trend (last 14 days) ─────────────────────────────────────────────
st.subheader("Trend — sessions per day (last 14 days)")
from collections import defaultdict

daily_counts: dict = defaultdict(int)
for s in sessions:
    ts = s.get("created_at")
    if not ts:
        continue
    d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
    daily_counts[d] += 1

today = datetime.now(tz=timezone.utc).date()
days = [today - timedelta(days=i) for i in range(13, -1, -1)]
trend_df = pd.DataFrame(
    [{"date": d, "sessions": daily_counts.get(d, 0)} for d in days]
).set_index("date")

if trend_df["sessions"].sum() > 0:
    st.line_chart(trend_df, color="#2563eb", height=240)
else:
    st.info("Not enough history yet.")

# ─── Distributions ────────────────────────────────────────────────────
st.subheader("Distribution")
col_a, col_b = st.columns(2)

with col_a:
    st.markdown("**Complexity**")
    counts = Counter(so.get("complexity", "unknown") for so in structured)
    if counts:
        order = ["low", "medium", "high", "unknown"]
        df = pd.DataFrame(
            [(k, counts.get(k, 0)) for k in order if counts.get(k, 0) > 0],
            columns=["complexity", "count"],
        ).set_index("complexity")
        st.bar_chart(df, color="#2563eb")
    else:
        st.info("No completed sessions yet.")

with col_b:
    st.markdown("**Category**")
    counts = Counter(so.get("category", "unknown") for so in structured)
    if counts:
        df = pd.DataFrame(sorted(counts.items()), columns=["category", "count"]).set_index("category")
        st.bar_chart(df, color="#7c3aed")
    else:
        st.info("No completed sessions yet.")

# ─── Recent sessions table ────────────────────────────────────────────
st.subheader("Recent sessions")

sessions_sorted = sorted(sessions, key=lambda s: s.get("created_at", 0), reverse=True)

rows = []
for s in sessions_sorted[:20]:
    so = s.get("structured_output") or {}
    pr_url = so.get("pr_url") or ""
    pr_state = "—"
    if not pr_url and s.get("pull_requests"):
        pr_url = s["pull_requests"][0].get("pr_url", "")
        pr_state = s["pull_requests"][0].get("pr_state") or "—"
    elif s.get("pull_requests"):
        pr_state = s["pull_requests"][0].get("pr_state") or "—"

    status_text_map = {
        "new": "queued", "claimed": "queued", "running": "running",
        "exit": "done", "error": "error", "suspended": "paused", "resuming": "running",
    }
    action_text_map = {
        "pr_opened": "PR opened",
        "skipped_unsafe": "Skipped",
        "aborted_too_complex": "Aborted",
    }

    rows.append({
        "Status": status_text_map.get(s.get("status", ""), s.get("status", "—")),
        "Created": fmt_ts(s.get("created_at")),
        "Title": (s.get("title") or "—")[:50],
        "Complexity": so.get("complexity", "—"),
        "Category": so.get("category", "—"),
        "Action": action_text_map.get(so.get("action_taken", ""), so.get("action_taken", "—")),
        "PR state": pr_state,
        "ACU": float(s.get("acus_consumed", 0) or 0),
        "PR": pr_url or "",
        "Session": s.get("url", ""),
    })

df = pd.DataFrame(rows)


def color_action(val: str) -> str:
    return {
        "PR opened": "background-color: #dcfce7; color: #166534; font-weight: 600;",
        "Skipped":   "background-color: #fef3c7; color: #92400e; font-weight: 600;",
        "Aborted":   "background-color: #fee2e2; color: #991b1b; font-weight: 600;",
    }.get(val, "")


def color_pr_state(val: str) -> str:
    return {
        "merged": "background-color: #dcfce7; color: #166534; font-weight: 600;",
        "open":   "background-color: #dbeafe; color: #1e40af; font-weight: 600;",
        "closed": "background-color: #f1f5f9; color: #475569;",
    }.get(val, "")


def color_status(val: str) -> str:
    return {
        "running": "background-color: #dbeafe; color: #1e40af; font-weight: 600;",
        "done":    "background-color: #dcfce7; color: #166534; font-weight: 600;",
        "queued":  "background-color: #f1f5f9; color: #475569;",
        "error":   "background-color: #fee2e2; color: #991b1b; font-weight: 600;",
        "paused":  "background-color: #fef3c7; color: #92400e;",
    }.get(val, "")


styled = (
    df.style
      .map(color_status,   subset=["Status"])
      .map(color_action,   subset=["Action"])
      .map(color_pr_state, subset=["PR state"])
      .format({"ACU": "{:.2f}"})
)

st.dataframe(
    styled,
    column_config={
        "PR": st.column_config.LinkColumn("PR", display_text=r"#(\d+)$"),
        "Session": st.column_config.LinkColumn("Session", display_text="open"),
    },
    hide_index=True,
    use_container_width=True,
)

# ─── Latest reasoning ─────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("Latest reasoning")
latest_with_output = next((s for s in sessions_sorted if s.get("structured_output")), None)
if latest_with_output:
    so = latest_with_output["structured_output"]
    title = latest_with_output.get("title") or "—"
    with st.expander(title, expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Action:** {action_pill(so.get('action_taken', ''))}", unsafe_allow_html=True)
        c2.markdown(f"**Complexity:** `{so.get('complexity', '—')}`")
        c3.markdown(f"**Category:** `{so.get('category', '—')}`")
        st.markdown(f"**Summary:** {so.get('summary', '—')}")
        st.markdown(f"**Reasoning:** {so.get('reasoning', '—')}")
        files = so.get("files_changed") or []
        if files:
            st.markdown("**Files changed:**")
            for f in files:
                st.markdown(f"- `{f}`")
else:
    st.info("No completed sessions yet.")
