"""Tests for the reconciliation + imports service wrappers.

A fake client records the path/params/json each helper sends and returns a
canned payload, so these lock the exact engine contract the desktop relies
on (the hyphen-vs-underscore and list-vs-envelope shapes that broke the web
import picker).
"""
from __future__ import annotations

from typing import Any

from saebooks_desktop.services import imports as imp
from saebooks_desktop.services import reconciliation as rec


class _FakeClient:
    def __init__(self, get_result: Any = None, post_result: Any = None) -> None:
        self._get_result = get_result
        self._post_result = post_result
        self.get_calls: list[tuple[str, dict | None]] = []
        self.post_calls: list[tuple[str, Any]] = []

    def get(self, path: str, params: dict | None = None) -> Any:
        self.get_calls.append((path, params))
        return self._get_result

    def post(self, path: str, json: Any = None, headers: Any = None) -> Any:
        self.post_calls.append((path, json))
        return self._post_result


# --- reconciliation ---------------------------------------------------------


def test_list_reconcilable_accounts_uses_recon_endpoint_and_bare_list() -> None:
    c = _FakeClient(get_result=[{"id": "a", "code": "1-1180", "name": "Undeposited"}])
    out = rec.list_reconcilable_accounts(c)
    assert c.get_calls == [("/api/v1/reconciliation/accounts", None)]
    assert out[0]["id"] == "a"


def test_list_unmatched_passes_account_id() -> None:
    c = _FakeClient(get_result=[{"id": "bsl-1"}])
    rec.list_unmatched(c, "acct-9")
    assert c.get_calls == [("/api/v1/reconciliation/unmatched", {"account_id": "acct-9"})]


def test_suggest_matches_path() -> None:
    c = _FakeClient(get_result=[])
    rec.suggest_matches(c, "bsl-7")
    assert c.get_calls == [("/api/v1/reconciliation/suggest/bsl-7", None)]


def test_match_posts_body() -> None:
    c = _FakeClient(post_result={"id": "bsl-1", "status": "MATCHED"})
    rec.match(c, "bsl-1", "je-1")
    assert c.post_calls == [("/api/v1/reconciliation/match", {"bsl_id": "bsl-1", "entry_id": "je-1"})]


def test_unmatch_path() -> None:
    c = _FakeClient(post_result={"id": "bsl-1", "status": "UNMATCHED"})
    rec.unmatch(c, "bsl-1")
    assert c.post_calls == [("/api/v1/reconciliation/unmatch/bsl-1", None)]


def test_auto_match_query_param() -> None:
    c = _FakeClient(post_result={"matched": 2})
    rec.auto_match(c, "acct-1")
    assert c.post_calls[0][0] == "/api/v1/reconciliation/auto_match?account_id=acct-1"


# --- imports ----------------------------------------------------------------


def test_start_bank_import_returns_wizard_id() -> None:
    c = _FakeClient(post_result={"wizard_id": "wz-1", "step": 0, "state": {}})
    wid = imp.start_bank_import(c, "acct-1")
    assert wid == "wz-1"
    path, body = c.post_calls[0]
    assert path == "/api/v1/imports/wizards"
    assert body == {"kind": "bank_csv", "initial": {"account_id": "acct-1"}}


def test_run_bank_import_chains_start_step_commit() -> None:
    # start -> {wizard_id}, step -> {}, commit -> {inserted,total}
    results = iter([
        {"wizard_id": "wz-1", "step": 0, "state": {}},
        {"step": 1, "state": {}, "completed": True},
        {"inserted": 3, "total": 3},
    ])

    class _Seq(_FakeClient):
        def post(self, path: str, json: Any = None, headers: Any = None) -> Any:
            self.post_calls.append((path, json))
            return next(results)

    c = _Seq()
    out = imp.run_bank_import(c, "acct-1", "Date,Amount\n2026-06-01,10.00")
    assert out == {"inserted": 3, "total": 3}
    paths = [p for p, _ in c.post_calls]
    assert paths == [
        "/api/v1/imports/wizards",
        "/api/v1/imports/wizards/wz-1/step",
        "/api/v1/imports/wizards/wz-1/commit",
    ]
