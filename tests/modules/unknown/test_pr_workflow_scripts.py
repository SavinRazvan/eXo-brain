"""
File: test_pr_workflow_scripts.py
Path: tests/modules/unknown/test_pr_workflow_scripts.py
Role: Verifies PR workflow scripts emit required actor attribution metadata.
Used By:
 - .github/workflows/architecture-fitness.yml
Depends On:
 - scripts/pr/review.py
 - scripts/pr/prepare.py
 - scripts/pr/merge.py
 - scripts/pr/verify_publish.py
Notes:
 - Uses temporary directories to avoid mutating repository-local artifacts.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts" / "pr"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_review_script_writes_actor_attribution(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("review_script", SCRIPTS_DIR / "review.py")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["review.py", "--pr", "123", "--actor", "Savin I. Razvan"])
    assert module.main() == 0

    content = (tmp_path / ".local" / "review.md").read_text(encoding="utf-8")
    assert "Action-By: Savin I. Razvan" in content
    assert "Reviewed-By: Savin I. Razvan" in content
    assert "GitHub-User: @SavinRazvan" in content


def test_prepare_script_writes_actor_attribution(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("prepare_script", SCRIPTS_DIR / "prepare.py")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "GATES", [["python", "-c", "print('ok')"]])
    monkeypatch.setattr(sys, "argv", ["prepare.py", "--pr", "123", "--actor", "Savin I. Razvan"])
    assert module.main() == 0

    content = (tmp_path / ".local" / "prep.md").read_text(encoding="utf-8")
    assert "Action-By: Savin I. Razvan" in content
    assert "Prepared-By: Savin I. Razvan" in content
    assert "GitHub-User: @SavinRazvan" in content


def test_merge_script_writes_actor_attribution(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("merge_script", SCRIPTS_DIR / "merge.py")

    local_dir = tmp_path / ".local"
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / "review.md").write_text("ready\n", encoding="utf-8")
    (local_dir / "prep.md").write_text("ready\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "_head_sha", lambda: "abc123")
    monkeypatch.setattr(sys, "argv", ["merge.py", "--pr", "123", "--actor", "Savin I. Razvan"])
    assert module.main() == 0

    content = (tmp_path / ".local" / "merge.md").read_text(encoding="utf-8")
    assert "Action-By: Savin I. Razvan" in content
    assert "Merged-By: Savin I. Razvan" in content
    assert "GitHub-User: @SavinRazvan" in content


def test_verify_publish_script_passes_when_upstream_and_remote_exist(monkeypatch) -> None:
    module = _load_module("verify_publish_script_ok", SCRIPTS_DIR / "verify_publish.py")

    def _fake_run(cmd: list[str]):
        if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "fix/test@{upstream}"]:
            return 0, "origin/fix/test"
        if cmd == ["git", "ls-remote", "--heads", "origin", "fix/test"]:
            return 0, "deadbeef\trefs/heads/fix/test"
        return 1, "unexpected command"

    monkeypatch.setattr(module, "_run", _fake_run)
    monkeypatch.setattr(
        sys, "argv", ["verify_publish.py", "--branch", "fix/test"]
    )
    assert module.main() == 0


def test_verify_publish_script_fails_when_upstream_missing(monkeypatch) -> None:
    module = _load_module("verify_publish_script_fail", SCRIPTS_DIR / "verify_publish.py")

    def _fake_run(cmd: list[str]):
        if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "fix/test@{upstream}"]:
            return 1, "fatal: no upstream configured"
        if cmd == ["git", "ls-remote", "--heads", "origin", "fix/test"]:
            return 0, "deadbeef\trefs/heads/fix/test"
        return 1, "unexpected command"

    monkeypatch.setattr(module, "_run", _fake_run)
    monkeypatch.setattr(
        sys, "argv", ["verify_publish.py", "--branch", "fix/test"]
    )
    assert module.main() == 1
