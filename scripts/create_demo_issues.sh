#!/bin/bash
#
# Create three demo issues for the Devin Triage Agent Loom recording.
#
# Uses the GitHub REST API directly (via curl) so it doesn't depend on
# the gh CLI's auth state. Only requires a GITHUB_TOKEN with `repo` scope.
#
# Usage:
#   ./scripts/create_demo_issues.sh             # Create 3 issues
#   ./scripts/create_demo_issues.sh --dry-run   # Preview without creating
#   ./scripts/create_demo_issues.sh --reset     # Close all open `devin-triage` issues
#   ./scripts/create_demo_issues.sh --reset --create   # Reset + create (clean run)
#
# Requirements:
#   - GITHUB_TOKEN environment variable (with `repo` scope)
#   - GITHUB_REPO (defaults to torabata/superset)
#
# Each issue triggers a GitHub Actions workflow that dispatches to Devin.

set -euo pipefail

REPO="${GITHUB_REPO:-torabata/superset}"
GITHUB_TOKEN="${GITHUB_TOKEN:?GITHUB_TOKEN is required (load from .env or set in shell)}"
API="https://api.github.com/repos/$REPO"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/demo-issues"

DRY_RUN=false
RESET=false
CREATE=true

for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=true ;;
    --reset)
      RESET=true
      CREATE=false  # default: --reset alone only resets
      ;;
    --create) CREATE=true ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Usage: $0 [--dry-run] [--reset] [--create]" >&2
      exit 1
      ;;
  esac
done

# ---------- Helpers ----------

api_call() {
  # Args: METHOD PATH [JSON_BODY]
  local method="$1" path="$2" body="${3:-}"
  if [[ -n "$body" ]]; then
    curl -sS -X "$method" \
      -H "Authorization: token $GITHUB_TOKEN" \
      -H "Accept: application/vnd.github+json" \
      -H "Content-Type: application/json" \
      "$API$path" -d "$body"
  else
    curl -sS -X "$method" \
      -H "Authorization: token $GITHUB_TOKEN" \
      -H "Accept: application/vnd.github+json" \
      "$API$path"
  fi
}

build_issue_payload() {
  # Args: TITLE BODY_FILE
  local title="$1" body_file="$2"
  python3 -c "
import json, sys
with open('$body_file') as f:
    body = f.read()
print(json.dumps({'title': '''$title''', 'body': body, 'labels': ['devin-triage']}))
"
}

# ---------- Reset: Close all open devin-triage issues ----------

if [[ "$RESET" == true ]]; then
  echo ""
  echo "Resetting open 'devin-triage' issues in $REPO..."
  echo ""

  open_issues=$(api_call GET "/issues?labels=devin-triage&state=open" \
    | python3 -c "import json,sys; print(' '.join(str(i['number']) for i in json.load(sys.stdin)))")

  if [[ -z "$open_issues" ]]; then
    echo "No open 'devin-triage' issues found. Nothing to reset."
  else
    for num in $open_issues; do
      if [[ "$DRY_RUN" == true ]]; then
        echo "[DRY-RUN] Would close issue #${num}"
      else
        api_call PATCH "/issues/$num" '{"state":"closed"}' >/dev/null
        echo "Closed issue #${num}"
      fi
    done
  fi
  echo ""
fi

# ---------- Create issues ----------

if [[ "$CREATE" != true ]]; then
  exit 0
fi

# Verify body files exist
for f in issue-1-safe.md issue-2-safe.md issue-3-unsafe.md; do
  if [[ ! -f "$DEMO_DIR/$f" ]]; then
    echo "Error: $DEMO_DIR/$f not found." >&2
    exit 1
  fi
done

if [[ "$DRY_RUN" == true ]]; then
  echo "[DRY-RUN MODE] No issues will be created."
  echo ""
fi

ISSUES=(
  "Add docstrings to public functions in superset/utils/cache.py|issue-1-safe.md"
  "Add type hints to superset/utils/date_parser.py|issue-2-safe.md"
  "Strengthen password hashing in superset/security/manager.py|issue-3-unsafe.md"
)

echo "Creating three demo issues in $REPO..."
echo ""

for issue_def in "${ISSUES[@]}"; do
  TITLE="${issue_def%%|*}"
  BODY_FILE="$DEMO_DIR/${issue_def##*|}"

  if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY-RUN] Would create: $TITLE"
    echo "          body: $BODY_FILE"
    echo ""
    continue
  fi

  payload=$(build_issue_payload "$TITLE" "$BODY_FILE")
  resp=$(api_call POST "/issues" "$payload")

  issue_num=$(echo "$resp" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('number') or sys.exit('Error: '+str(d)))")

  echo "Created issue #${issue_num}: $TITLE"
  echo "  https://github.com/$REPO/issues/${issue_num}"
  echo ""
done

if [[ "$DRY_RUN" == false ]]; then
  echo "All three issues created and labeled with 'devin-triage'."
  echo "Workflows triggered. Check GitHub Actions:"
  echo "  https://github.com/$REPO/actions"
fi
