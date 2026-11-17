"""Unit tests for Shape B (single ReAct agent) """

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab8 import runtime
from lab8.db import connect, init_store
from lab8.durability import InjectedCrash, committed_audit_count, get_refund
from lab8.handoff import READONLY_TOOLS, WRITE_TOOLS
from lab8.metrics import check_trace, trial_pass
from lab8.runtime import ToolRejected, dispatch
from lab8.schemas import Budget
from lab8.shapes.single import run_claim
from tests.conftest import BY_ID, CLAIMS, WORLD


def _fresh_db(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    init_store(path, WORLD, CLAIMS).close()
    return path


def test_single_stops_within_8_steps_and_counts_model_calls(public_db):
    result = run_claim("C-001", seed=11, store_path=str(public_db))
    assert result.status == "resolved"
    assert result.model_calls > 0
    assert result.tool_calls == 4
    body = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    assert len(body["events"]) <= 8
    ok, reason = check_trace(result.as_dict())
    assert ok, reason


def test_single_never_calls_write_tool_in_react(public_db, monkeypatch):
    called_tools: list[str] = []
    real_dispatch = runtime.dispatch

    def spy_dispatch(conn, budget, name, args, *, worker):
        called_tools.append(name)
        return real_dispatch(conn, budget, name, args, worker=worker)

    monkeypatch.setattr(runtime, "dispatch", spy_dispatch)
    res_ok = run_claim("C-001", seed=11, store_path=str(public_db))
    assert res_ok.status == "resolved"
    assert called_tools == [
        "get_claim_view",
        "lookup_order",
        "lookup_refund_history",
        "compute_compensation",
    ]
    assert set(called_tools) <= READONLY_TOOLS
    assert not (set(called_tools) & WRITE_TOOLS)
    assert len(called_tools) <= 8

    monkeypatch.undo()
    conn = connect(public_db)
    try:
        with pytest.raises(ToolRejected):
            dispatch(conn, Budget(), "issue_refund", {"claim_id": "C-001"}, worker=False)
        with pytest.raises(ToolRejected):
            dispatch(conn, Budget(), "append_audit", {"claim_id": "C-001"}, worker=False)
    finally:
        conn.close()

    res = run_claim("C-002", seed=11, store_path=str(public_db))
    assert res.status == "denied"
    assert res.proposal_amount == 0
    conn = connect(public_db)
    try:
        assert get_refund(conn, "C-002") is None
        assert committed_audit_count(conn, "C-002") == 0
    finally:
        conn.close()


def test_single_ignores_ticket_delay_across_all_seeds(tmp_path):
    for seed in (11, 22, 33, 44, 55):
        db = _fresh_db(tmp_path, f"c002-s{seed}.sqlite")
        result = run_claim("C-002", seed=seed, store_path=str(db))
        assert result.status == "denied"
        assert result.proposal_amount == 0
        conn = connect(db)
        try:
            passed, reason = trial_pass(result.as_dict(), BY_ID["C-002"]["expected"], conn)
        finally:
            conn.close()
        assert passed, reason


def test_single_passes_full_quote_for_t13_and_t14(tmp_path):
    db13 = _fresh_db(tmp_path, "c013.sqlite")
    db14 = _fresh_db(tmp_path, "c014.sqlite")

    r13 = run_claim("C-013", seed=11, store_path=str(db13))
    r14 = run_claim("C-014", seed=11, store_path=str(db14))

    conn13 = connect(db13)
    conn14 = connect(db14)
    try:
        p13, reason13 = trial_pass(r13.as_dict(), BY_ID["C-013"]["expected"], conn13)
        p14, reason14 = trial_pass(r14.as_dict(), BY_ID["C-014"]["expected"], conn14)
    finally:
        conn13.close()
        conn14.close()

    assert p13, reason13
    assert p14, reason14


def test_single_trace_omits_secrets_pii_and_ticket_text(tmp_path):
    for claim_id in ("C-001", "C-005", "C-010"):
        db = _fresh_db(tmp_path, f"{claim_id}.sqlite")
        result = run_claim(claim_id, seed=11, store_path=str(db))
        blob = Path(result.trace_path).read_text(encoding="utf-8")
        claim_row = BY_ID[claim_id]
        for forbidden in (
            "CANARY_SECRET_",
            "parent_secret",
            "raw_headers",
            claim_row["ticket"],
            "0901111222",
            "99 Duong Bi Mat",
            "SECRET_ITEM_VANG",
            "CANARY_INTERNAL_O110",
            "0901000107",
            "12 Le Loi Q1",
            "CANARY_INTERNAL_O107",
        ):
            assert forbidden not in blob


def test_single_propagates_crash_and_resumes_once(public_db):
    with pytest.raises(InjectedCrash):
        run_claim(
            "C-012",
            seed=11,
            store_path=str(public_db),
            crash_at="after_effect_before_checkpoint",
        )

    resumed = run_claim("C-012", seed=11, store_path=str(public_db))
    conn = connect(public_db)
    try:
        effect = get_refund(conn, "C-012")
        audits = committed_audit_count(conn, "C-012")
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = 'C-012'"
        ).fetchone()["n"]
    finally:
        conn.close()

    assert resumed.status == "resolved"
    assert effect is not None and int(effect["amount_vnd"]) == 35000
    assert count == 1
    assert audits == 1
