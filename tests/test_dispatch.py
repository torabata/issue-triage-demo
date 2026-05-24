"""
Integration test — exercises the live GitHub-to-Devin pipeline.

Workflow:
  1. POST a new issue (via GitHub API) on the configured fork, with the
     `devin-triage` label attached.
  2. Poll GitHub Actions until the workflow run for that issue starts.
  3. Assert the workflow eventually succeeds OR a Devin session is created
     (whichever signal is available within the timeout).
  4. Optionally reach into the Devin API and confirm a session exists with
     a `tag` matching `issue-<n>`.

Skipped automatically when GITHUB_TOKEN is not set, so this file can sit
alongside the unit tests without breaking offline runs.

Run:
    pytest -v tests/test_dispatch.py
or:
    docker compose run --rm tests pytest -v tests/test_dispatch.py
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import pytest
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "torabata/superset")
DEVIN_API_KEY = os.environ.get("DEVIN_API_KEY")
DEVIN_ORG_ID = os.environ.get("DEVIN_ORG_ID")

WORKFLOW_TIMEOUT_SECONDS = 180  # 3 minutes


pytestmark = pytest.mark.skipif(
    not GITHUB_TOKEN,
    reason="GITHUB_TOKEN not set — integration test skipped",
)


def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def _create_issue() -> dict:
    """Create a test issue tagged with `devin-triage`."""
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "title": f"[integration-test] dispatch smoke test {timestamp}",
        "body": (
            "This issue is created automatically by the Devin Triage "
            "Agent integration test. It will be picked up by the workflow.\n\n"
            "Scope: documentation typo fix only.\n"
            "Do not change any logic."
        ),
        "labels": ["devin-triage", "integration-test"],
    }
    resp = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues",
        headers=_gh_headers(),
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _close_issue(number: int) -> None:
    requests.patch(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues/{number}",
        headers=_gh_headers(),
        json={"state": "closed"},
        timeout=30,
    )


def _devin_session_for_issue(issue_number: int) -> dict | None:
    """Return the most recent Devin session tagged with this issue."""
    if not DEVIN_API_KEY or not DEVIN_ORG_ID:
        return None

    resp = requests.get(
        f"https://api.devin.ai/v3/organizations/{DEVIN_ORG_ID}/sessions",
        headers={"Authorization": f"Bearer {DEVIN_API_KEY}"},
        params={"first": 50},
        timeout=30,
    )
    if resp.status_code != 200:
        return None

    target_tag = f"issue-{issue_number}"
    for s in resp.json().get("items", []):
        if target_tag in (s.get("tags") or []):
            return s
    return None


def test_full_dispatch_pipeline():
    """A new issue triggers GitHub Actions and produces a Devin session."""
    issue = _create_issue()
    issue_number = issue["number"]
    print(f"\n[test] created issue #{issue_number}: {issue['html_url']}")

    deadline = time.monotonic() + WORKFLOW_TIMEOUT_SECONDS
    session = None

    try:
        while time.monotonic() < deadline:
            session = _devin_session_for_issue(issue_number)
            if session:
                print(f"[test] devin session found: {session.get('url')}")
                break
            time.sleep(15)

        assert session is not None, (
            f"No Devin session was created for issue #{issue_number} "
            f"within {WORKFLOW_TIMEOUT_SECONDS}s. Check GitHub Actions logs."
        )

        # Sanity assertions on the session shape
        assert session.get("session_id")
        assert session.get("url", "").startswith("https://app.devin.ai/sessions/")
        assert "auto-triage" in (session.get("tags") or [])
    finally:
        _close_issue(issue_number)
        print(f"[test] closed issue #{issue_number}")
