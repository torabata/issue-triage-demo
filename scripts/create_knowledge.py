"""
Create Devin Knowledge Notes for the Superset triage system.

Knowledge Notes provide implicit context that Devin auto-references when
triggers match. Unlike Playbooks (which are invoked explicitly), Notes act
as background expertise the agent applies to every relevant task.

Usage:
    source .venv/bin/activate
    set -a && source .env && set +a
    python3 scripts/create_knowledge.py
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

OUTPUT_FILE = Path(__file__).parent.parent / "knowledge_ids.json"


# ─── Note 1: Superset Coding Standards ────────────────────────────────
NOTE_CODING_STANDARDS = {
    "name": "Superset Coding Standards",
    "trigger": "When writing or modifying Python code in apache/superset or torabata/superset",
    "body": """\
Apache Superset is a Flask + SQLAlchemy data exploration platform with a TypeScript/React frontend.

Python code conventions:
- Follow PEP 8.
- Use type hints on public functions and methods. Prefer `from __future__ import annotations` for forward references.
- Add docstrings to all public functions and classes (Google style).
- Imports sorted by isort. Standard library, third-party, then local.
- Prefer dependency injection over module-level singletons.
- Database access goes through SQLAlchemy ORM, not raw SQL where possible.
- Logging via `logging.getLogger(__name__)`. Do not use `print()` in production code paths.

Test conventions:
- pytest is the test runner. Tests live under `tests/`.
- Use fixtures over setUp/tearDown.
- Mock external services with `unittest.mock` — never hit real network in tests.

When in doubt, look at the surrounding code and match its style. Consistency beats personal preference.
""",
}


# ─── Note 2: PR & Commit Conventions ─────────────────────────────────
NOTE_PR_CONVENTIONS = {
    "name": "PR and Commit Conventions",
    "trigger": "When opening a pull request or writing a commit message",
    "body": """\
Pull Request rules:

- Title format: `<type>(<scope>): <short description>` where type is one of:
  feat, fix, docs, style, refactor, perf, test, build, ci, chore.
  Example: `fix(utils): add type hints to date_parser`

- The PR description must include:
  1. A "Closes #<issue_number>" line so GitHub auto-links the issue.
  2. A brief "What changed" section (1-3 bullets).
  3. A "Why" section (motivation, linking back to the issue).
  4. A "Tested" section listing what verification was done.

- Keep PRs small. If a fix is touching more than ~10 files, stop and ask whether the scope is correct.

- Always create a branch named `devin/fix-issue-{number}` for traceability.

- Never push directly to master. Never force-push.
""",
}


# ─── Note 3: Safe-Change Heuristics ──────────────────────────────────
NOTE_SAFE_CHANGES = {
    "name": "Safe-Change Heuristics for Autonomous Fixes",
    "trigger": "When deciding whether to autonomously modify code in apache/superset or torabata/superset",
    "body": """\
This repository is run by an autonomous triage agent. Apply these heuristics to decide whether
a change is safe to ship without a human pre-approving the design.

SAFE for autonomous fix (low risk):
- Documentation: README, CONTRIBUTING, docs/, docstrings, code comments
- Type hint additions (no runtime behavior change)
- Lint/style fixes flagged by tools that already run in CI
- Removing genuinely dead code in test files (verify with grep)
- Adding missing tests that exercise existing behavior

NOT SAFE (escalate to human):
- Authentication, authorization, session, or permission code
- Database migrations or schema changes
- Security-sensitive code: password hashing, secrets, CSRF, XSS handling
- CI/CD configuration, Dockerfiles, deployment scripts
- API contracts (changing public function signatures, REST endpoints)
- Anything in `superset/security/`, `superset/cli/migrations/`
- Performance-critical hot paths where a wrong fix causes regressions

If a change touches both a safe and an unsafe area, treat the whole change as unsafe.

When unsafe, do NOT modify code. Instead, report it in structured output and let a human decide.
""",
}


def create_note(spec: dict) -> dict:
    print(f"Creating knowledge note: {spec['name']}...")
    resp = requests.post(
        f"{BASE}/knowledge/notes",
        headers=HEADERS,
        json=spec,
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        print(f"  HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        resp.raise_for_status()
    data = resp.json()
    note_id = data.get("note_id") or data.get("id") or "<unknown>"
    print(f"  -> note_id: {note_id}")
    return data


def main() -> None:
    notes = [
        ("coding_standards", NOTE_CODING_STANDARDS),
        ("pr_conventions", NOTE_PR_CONVENTIONS),
        ("safe_changes", NOTE_SAFE_CHANGES),
    ]

    output = {}
    for key, spec in notes:
        data = create_note(spec)
        output[key] = {
            "note_id": data.get("note_id") or data.get("id"),
            "name": spec["name"],
            "trigger": spec["trigger"],
        }

    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"\nSaved to: {OUTPUT_FILE}")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
