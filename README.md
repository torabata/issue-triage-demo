# Devin Issue Triage Agent

> **autonomously triages and resolves GitHub issues using the Devin v3 API.
>
>
> Built for "FinServ Co" — issues piling up in different types, senior engineers focused on platform work, juniors slowed by triage. This system gets the stuck process moving — automatically.

---

## What it does

1. Engineer adds a `devin-triage` label to a GitHub issue
2. GitHub Actions fires `issues.labeled` and dispatches to Devin
3. Devin runs autonomously, configured with our team's Playbook + Knowledge Notes + Snapshot
4. Devin classifies each issue and takes the right action automatically:
   - 🟢 `pr_opened` — safe and easy to fix → Devin opens a PR
   - 🟡 `skipped_unsafe` — sensitive area → Devin escalates to a human via issue comment
5. Streamlit dashboard shows real-time metrics for executives, engineers, and project managers

**No human intervention** from issue label to PR.

> The Playbook also supports an `aborted_too_complex` outcome (for changes requiring design judgment), which Devin can return when an issue is structurally too large for safe automation. The Loom recording focuses on the two outcomes above to highlight the automation flow; `aborted_too_complex` remains in the system as a safety net.

---

## Architecture

```
[GitHub Issue + devin-triage label]
    ↓
[GitHub Actions: .github/workflows/devin-triage.yml]
    ↓ orchestrator.py is called
[Devin v3 API: POST /sessions]
  - playbook_id: Issue Auto-Fix
  - knowledge_ids: Coding Standards / PR Conventions / Safe-Change Heuristics
  - structured_output_schema: { can_auto_fix, action_taken, ... }
  - Snapshot Setup: pre-cloned repo
    ↓
[Devin Session — autonomous, fully on its own]
  ├─ Reads issue, applies playbook, references knowledge
  ├─ If safe → modifies code → opens PR
  └─ If sensitive → comments on the issue and escalates
    ↓
[Pull Request → Engineer review]
[Structured output → Streamlit Dashboard]
```

See `architecture.md` for detailed diagrams.

---

## Quick start

### 1. Clone and configure environment

```bash
git clone <this-repo>
cd <repo>
cp .env.example .env
# Edit .env with your DEVIN_API_KEY, DEVIN_ORG_ID, GITHUB_TOKEN
```

### 2. Provision Devin org resources (once per evaluator's Devin org)

The Playbook and Knowledge Notes are environment-specific — every evaluator
provisions their own in their Devin organization.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Loads DEVIN_API_KEY / DEVIN_ORG_ID from .env
set -a && source .env && set +a

# Creates the playbook + knowledge notes; writes playbook_ids.json / knowledge_ids.json
python3 scripts/create_playbooks.py
python3 scripts/create_knowledge.py
```

The orchestrator reads these JSON files automatically. (For CI use, the same
IDs can be passed via the `DEVIN_PLAYBOOK_ID` / `DEVIN_KNOWLEDGE_IDS` secrets
— see "Devin configuration" below.)

### 3. Run the dashboard

```bash
# Docker Compose
docker compose up dashboard       # dashboard at http://localhost:8501
docker compose run --rm tests     # run pytest suite

# Or directly:
streamlit run dashboard.py
```

---

## Live demo flow

After setup, trigger 3 demo issues:

```bash
# Load env first (the script uses GITHUB_TOKEN directly via the GitHub API)
set -a && source .env && set +a

./scripts/create_demo_issues.sh
```

This creates 3 issues of different kinds:
- A safe documentation change (cache.py docstrings) → expect `pr_opened`
- A safe annotation change (date_parser.py type hints) → expect `pr_opened`
- A sensitive change in `security/` (password hashing) → expect `skipped_unsafe`

Watch the GitHub Actions workflow fire, Devin sessions spin up, and the dashboard update in real time.

To clean up between demo runs:
```bash
./scripts/create_demo_issues.sh --reset      # Closes all open devin-triage issues
./scripts/create_demo_issues.sh --reset --create   # Reset + fresh run
```

---

## Repository structure

```
.
├── README.md                       # This file
├── architecture.md                 # System diagrams (4 levels of detail)
├── slides.html                     # Presentation slides (open in browser)
├── orchestrator.py                 # Main: GitHub event → Devin session
├── dashboard.py                    # Streamlit dashboard (3 audiences: exec/eng/PM)
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container image
├── docker-compose.yml              # dashboard / tests / cli profiles
├── .env.example                    # Environment variable template
├── .gitignore
├── .github/workflows/
│   └── devin-triage.yml            # GitHub Actions workflow (issues.labeled trigger)
├── scripts/
│   ├── create_playbooks.py         # Provisions the Issue Auto-Fix playbook
│   ├── create_knowledge.py         # Provisions 3 knowledge notes
│   ├── create_demo_issues.sh       # CLI helper to create 3 demo issues
│   └── demo-issues/                # Issue body templates
│       ├── issue-1-safe.md         # cache.py docstrings
│       ├── issue-2-safe.md         # date_parser type hints
│       └── issue-3-unsafe.md       # password hashing (sensitive)
└── tests/
    ├── test_orchestrator.py        # Unit tests (9 cases, all passing)
    └── test_dispatch.py            # Integration test (requires GITHUB_TOKEN)
```

---

## Devin configuration (org-level)

This system relies on three Devin resources that are configured **once per
Devin organization** and reused across all sessions. Run the bootstrap scripts
in [Quick start step 2](#2-provision-devin-org-resources-once-per-evaluators-devin-org)
to create them in your own org.

### 1. Playbook: "Issue Auto-Fix"
The triage procedure — what to do, in what order. Versioned on Devin's side.
Created by `scripts/create_playbooks.py`.

### 2. Knowledge Notes (×3)

| Note | Trigger | Purpose |
|---|---|---|
| Superset Coding Standards | Writing Python code | Apply project conventions |
| PR and Commit Conventions | Creating a PR | Conventional Commits, structure |
| Safe-Change Heuristics | Deciding to auto-fix | Refuse if security/auth/migration files |

Created by `scripts/create_knowledge.py`.

### 3. Snapshot Setup
Pre-cloned repository with Python environment. Sessions boot in seconds, no `git clone` overhead.
Configured manually in the Devin UI per repository.

### How the orchestrator finds these IDs

The IDs returned by the bootstrap scripts are written to `playbook_ids.json`
and `knowledge_ids.json` (gitignored — environment-specific). The orchestrator
resolves them in this order:

1. Environment variables `DEVIN_PLAYBOOK_ID` and `DEVIN_KNOWLEDGE_IDS`
   (comma-separated). Recommended for GitHub Actions secrets.
2. The JSON files above. Recommended for local runs.

### GitHub Actions secrets

For the workflow (`.github/workflows/devin-triage.yml`) to dispatch Devin from
issue events, set these secrets in your repository:

- `DEVIN_API_KEY`
- `DEVIN_ORG_ID`
- `DEVIN_PLAYBOOK_ID` — value from `playbook_ids.json["fix"]["playbook_id"]`
- `DEVIN_KNOWLEDGE_IDS` — comma-separated, e.g. `note-aaa...,note-bbb...,note-ccc...`

(`GITHUB_TOKEN` is auto-provided to Actions; no manual setup needed.)

---

## Tests

```bash
pytest -v tests/                    # Local
docker compose run --rm tests       # In Docker
```

- 9 unit tests in `test_orchestrator.py` — schema, dispatch logic, error handling
- Integration test in `test_dispatch.py` — requires `GITHUB_TOKEN` and `DEVIN_API_KEY`

---

## Observability

The Streamlit dashboard answers: **"How do I know it's working?"** for three audiences:

| Audience | What they see |
|---|---|
| **Executives** | Engineer-hours saved, total cost, MTTR, ROI |
| **Engineers** | Auto-fix rate, throughput, recent sessions, decision reasoning |
| **Project managers** | Trend over time, distribution by category/complexity |

Every session emits a structured JSON output with `action_taken`, `reasoning`, `files_changed`, etc. Every decision is auditable — there is no black box.

---

## Why this architecture

| Capability | Why |
|---|---|
| **Playbook** | Triage procedure is versioned and reusable across sessions, not duplicated per prompt |
| **Knowledge Notes** | Org rules apply automatically when triggers match — no prompt rewriting |
| **Snapshot Setup** | Sessions boot in seconds, not minutes |
| **structured_output_schema** | JSON-validated, auditable — every decision feeds the dashboard |
| **GitHub Actions trigger** | Native integration; no infrastructure to maintain |

The architecture is built for evolution: update the Playbook, every future session benefits. Add a Knowledge Note, Devin picks it up automatically. Pin a new Snapshot, sessions get the new environment.

---

## Roadmap proposal

| Phase | Duration | Goal |
|---|---|---|
| **1: Pilot** | 2 weeks | Run a few dozen real issues; measure auto-fix rate, merge rate, engineer time saved |
| **2: CI/CD integration** | 1 month | Wire Devin into existing CI/CD pipeline; trigger from CodeQL, flaky test failures, dependency updates |
| **3: Production deployment** | Ongoing | Devin becomes a permanent part of the engineering workflow |

---

## Author

[Tatsuya Nakamura](https://www.linkedin.com/in/tatsuya-nakamura-a31198186/).
