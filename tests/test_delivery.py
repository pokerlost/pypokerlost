"""Check CI event coverage and the reviewed shared branch guard snapshot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_ci_covers_each_permanent_branch_push_without_cancellation() -> None:
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    for event in ("push", "pull_request"):
        assert workflow["on"][event] == {"branches": ["test", "dev", "main"]}
    assert workflow["concurrency"]["cancel-in-progress"] == (
        "${{ github.event_name == 'pull_request' }}"
    )
    assert "github.run_id" in workflow["concurrency"]["group"]
    assert workflow["permissions"] == {"contents": "read"}


def test_branch_guard_matches_reviewed_producer_identity() -> None:
    record = json.loads((ROOT / ".github/engineering-source.json").read_text())
    entry = record["files"][".github/workflows/contribution.yml"]
    assert entry["revision"] == "e75a3f51189f7f95c0123f6894fa57f18356c58e"
    assert entry["sha256"] == "9a92d2885189a911ebb2dafc1ee37fd8955490fffb8d080eb89ae41bf863f0fd"
    assert (
        hashlib.sha256((ROOT / ".github/workflows/contribution.yml").read_bytes()).hexdigest()
        == (entry["sha256"])
    )
