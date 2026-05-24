"""
Create Devin Playbooks for the issue triage system.

Creates two playbooks:
  1. Issue Triage — reads an issue, classifies it (structured output)
  2. Issue Fix    — implements a fix and opens a PR (structured output)

Saves the resulting playbook_ids to `playbook_ids.json` so the
orchestrator can reference them.

Usage:
    source .venv/bin/activate
    set -a && source .env && set +a
    python3 scripts/create_playbooks.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["DEVIN_API_KEY"]
ORG_ID = os.environ["DEVIN_ORG_ID"]
BASE = f"https://api.devin.ai/v3/organizations/{ORG_ID}"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

OUTPUT_FILE = Path(__file__).parent.parent / "playbook_ids.json"


# ─── Playbook 1: Triage ──────────────────────────────────────────────
TRIAGE_PLAYBOOK = {
    "title": "GitHub Issue Triage v1",
    "body": """\
You are an autonomous triage agent for the repository specified in the prompt.

Your job is to read a GitHub issue and classify it. You do NOT write code in this phase.

# Steps

1. Clone or browse the repository to understand its structure.
2. Read the GitHub issue carefully (title, body, labels).
3. Identify what type of work is being requested.
4. Estimate complexity based on:
   - Number of files likely to change
   - Whether business logic is involved (high risk) or only docs/types/lint (low risk)
   - Whether external systems or production code paths are touched
5. Decide whether this issue is safe for an autonomous agent to fix without human review of the change scope.

# Decision rules

- "low" complexity = doc fixes, type hints, missing docstrings, simple lint fixes, dead code in tests
- "medium" complexity = small refactors, single-file logic changes, simple bug fixes
- "high" complexity = anything touching production code paths, security, data migrations, multi-file changes

# Output

You MUST end your turn by calling provide_structured_output with the schema fields:
- complexity: "low" | "medium" | "high"
- can_auto_fix: true if this is safe to delegate to an autonomous fixer; false otherwise
- category: one of "docs", "type-hints", "lint", "test", "refactor", "feature", "bug", "other"
- reasoning: 1-3 sentences explaining your decision
- estimated_files_changed: integer

Do NOT modify any code. Do NOT open a pull request. Triage only.
""",
    "macro": "!issue-triage",
}


# ─── Playbook 2: Fix ─────────────────────────────────────────────────
FIX_PLAYBOOK = {
    "title": "GitHub Issue Auto-Fix v1",
    "body": """\
You are an autonomous fixer agent. The triage stage has already classified this issue
as safe for automatic remediation. Your job is to implement the fix and open a pull request.

# Steps

1. Clone the repository specified in the prompt.
2. Read the GitHub issue carefully.
3. Make the smallest, most targeted change that addresses the issue.
4. Run any relevant local checks (lint, type check, tests) if the project supports them.
5. Commit on a new branch named `devin/fix-issue-{issue_number}`.
6. Open a pull request against the `master` branch.
7. The PR description must:
   - Reference the original issue (e.g., "Closes #123")
   - Briefly explain what changed and why
   - List the files changed

# Constraints

- Keep changes minimal — do not refactor unrelated code.
- Do not touch security-sensitive code, secrets, CI configuration, or production deployment scripts.
- If you find the issue is actually too complex once you start, stop and report it in structured output rather than producing a low-quality PR.

# Output

You MUST end your turn by calling provide_structured_output with the schema fields:
- pr_url: URL of the pull request you opened (empty string if you stopped)
- files_changed: array of file paths you modified
- tests_added: boolean — did you add or update tests?
- summary: 1-3 sentences describing the change
- aborted: boolean — true if you stopped without opening a PR
- abort_reason: string explaining why you stopped (empty if aborted=false)
""",
    "macro": "!issue-fix",
}


def create_playbook(spec: dict) -> dict:
    """Create one playbook. Returns the API response dict."""
    print(f"Creating playbook: {spec['title']}...")
    resp = requests.post(
        f"{BASE}/playbooks",
        headers=HEADERS,
        json=spec,
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        print(f"  HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        resp.raise_for_status()
    data = resp.json()
    print(f"  -> playbook_id: {data['playbook_id']}")
    return data


def main() -> None:
    triage = create_playbook(TRIAGE_PLAYBOOK)
    fix = create_playbook(FIX_PLAYBOOK)

    output = {
        "triage": {
            "playbook_id": triage["playbook_id"],
            "title": triage["title"],
            "macro": triage.get("macro"),
        },
        "fix": {
            "playbook_id": fix["playbook_id"],
            "title": fix["title"],
            "macro": fix.get("macro"),
        },
    }

    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"\nSaved to: {OUTPUT_FILE}")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
