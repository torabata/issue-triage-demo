"""
Unit tests for orchestrator.py.

These tests don't touch the network. They exercise:
  - structured-output schema validity (JSON Schema Draft 7-style fields)
  - prompt construction
  - issue payload extraction from a synthetic GitHub event file
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Ensure required env vars are set so `import orchestrator` succeeds.
os.environ.setdefault("DEVIN_API_KEY", "cog_test_dummy")
os.environ.setdefault("DEVIN_ORG_ID", "org-test-dummy")
os.environ.setdefault("GITHUB_REPO", "torabata/superset")

import orchestrator  # noqa: E402


# ─── Schema sanity ───────────────────────────────────────────────────
def test_structured_output_schema_has_required_fields():
    schema = orchestrator.STRUCTURED_OUTPUT_SCHEMA
    required = set(schema.get("required", []))
    expected = {
        "can_auto_fix",
        "action_taken",
        "complexity",
        "category",
        "pr_url",
        "summary",
        "reasoning",
    }
    assert expected.issubset(required), f"missing required fields: {expected - required}"


def test_structured_output_schema_action_enum():
    props = orchestrator.STRUCTURED_OUTPUT_SCHEMA["properties"]
    enum = set(props["action_taken"]["enum"])
    assert enum == {"pr_opened", "skipped_unsafe", "aborted_too_complex"}


def test_structured_output_schema_complexity_enum():
    props = orchestrator.STRUCTURED_OUTPUT_SCHEMA["properties"]
    enum = set(props["complexity"]["enum"])
    assert enum == {"low", "medium", "high"}


# ─── Knowledge / Playbook IDs ────────────────────────────────────────
def test_playbook_id_set():
    assert orchestrator.PLAYBOOK_ID
    assert orchestrator.PLAYBOOK_ID.startswith("playbook-")


def test_three_knowledge_notes_attached():
    assert len(orchestrator.KNOWLEDGE_IDS) == 3
    for nid in orchestrator.KNOWLEDGE_IDS:
        assert nid.startswith("note-")


# ─── Event payload parsing ───────────────────────────────────────────
def test_load_issue_from_event(tmp_path, monkeypatch):
    payload = {
        "action": "labeled",
        "label": {"name": "devin-triage"},
        "issue": {
            "number": 42,
            "title": "Test issue",
            "body": "Body text",
            "html_url": "https://example.com/issues/42",
        },
        "repository": {"full_name": "torabata/superset"},
    }
    event_file = tmp_path / "event.json"
    event_file.write_text(json.dumps(payload))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))

    issue = orchestrator.load_issue_from_event()
    assert issue["number"] == 42
    assert issue["title"] == "Test issue"


def test_load_issue_from_event_missing_path(monkeypatch):
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    with pytest.raises(SystemExit):
        orchestrator.load_issue_from_event()


def test_load_issue_from_event_no_issue(tmp_path, monkeypatch):
    event_file = tmp_path / "event.json"
    event_file.write_text(json.dumps({"action": "ping"}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))
    with pytest.raises(SystemExit):
        orchestrator.load_issue_from_event()


# ─── dispatch_to_devin builds correct request ────────────────────────
def test_dispatch_to_devin_request_shape(monkeypatch):
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self): ...

        def json(self):
            return {"session_id": "sess-1", "url": "https://app.devin.ai/sessions/sess-1", "status": "new"}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(orchestrator.requests, "post", fake_post)

    issue = {"number": 99, "title": "Test", "body": "Test body"}
    result = orchestrator.dispatch_to_devin(issue)

    assert result["session_id"] == "sess-1"
    assert "/sessions" in captured["url"]
    assert captured["headers"]["Authorization"].startswith("Bearer ")

    body = captured["json"]
    assert body["playbook_id"] == orchestrator.PLAYBOOK_ID
    assert body["knowledge_ids"] == orchestrator.KNOWLEDGE_IDS
    assert body["repos"] == [orchestrator.GITHUB_REPO]
    assert body["structured_output_required"] is True
    assert body["structured_output_schema"] == orchestrator.STRUCTURED_OUTPUT_SCHEMA
    assert "max_acu_limit" in body
    assert "Issue #99" in body["prompt"]
    assert "Test body" in body["prompt"]
