"""Shape C — orchestrator plus read-only investigators. Student work.

1. Build a handoff with `lab8.handoff.make_handoff`. Allowed tools are read-only.
   Never put parent_secret, raw headers, or the full claim row into facts.
2. `lab8.runtime.run_readonly_investigators` runs those tools.
3. The orchestrator quotes from the investigator's order view and calls
   `durability.issue_refund`. Investigators have no write registry.
   Pass the full quote; the host subtracts earlier refunds on the same order.
   `lookup_refund_history` is a read-only tool you may hand to an investigator.
4. Trace the sanitized handoff, not the parent context.

An LLM summary of the parent context is not a sanitizer. Use the allowlist.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.

Ranh giới trong shape này:

- Orchestrator (code) đọc claim qua `get_claim_view`, lập handoff bằng allowlist,
  nhận kết quả investigator, gọi `durability.issue_refund`. Chỉ orchestrator ghi.
- Investigator chỉ có tool đọc (`worker=True`), chỉ thấy handoff đã sanitize.
- Model (MockLLM) chỉ lập kế hoạch và soạn câu trả lời; không thấy ticket, không quyết tiền.
- Không có bước nào để chữ trong ticket đè dữ kiện order (khác swarm tham chiếu).
"""

from __future__ import annotations

import sqlite3

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.handoff import make_handoff
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, get_claim_view, tool_cost
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    run_id = make_run_id("orchestrator", claim_id, seed)
    trace = Trace(run_id)

    # Đọc claim
    budget.add_tool(tool_cost())
    claim_row = conn.execute(
        "SELECT claim_id, principal_id, order_id, ticket FROM claims WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()

    if claim_row is None:
        trace.add("error", {"reason": "unknown_claim"})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="unknown_claim",
        )

    if not claim_row["order_id"]:
        trace.add("decision", {"status": "needs_info"})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="needs_info",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="missing_order_id",
        )

    # Bước 1: Dựng handoff — chỉ allowlist fields, không truyền parent context
    handoff = make_handoff(
        request_id=f"REQ-{claim_id}",
        claim_id=claim_id,
        task="investigate_claim",
        facts={},
        allowed_tools=["lookup_order", "lookup_refund_history", "compute_compensation"],
    )
    # Bước 4: Trace handoff đã sanitize, không phải context gốc
    trace.add("handoff", safe_dump(handoff))

    # Bước 2: Chạy investigator (read-only)
    investigated = run_readonly_investigators(
        conn, budget, handoff, principal_id=claim_row["principal_id"]
    )

    order_view = investigated["tools"].get("lookup_order", {})
    trace.add("investigator", {
        "lookup_order": {"visible": order_view.get("visible")},
        "refund_history": investigated["tools"].get("lookup_refund_history"),
    })

    if not order_view.get("visible"):
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="escalated",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=order_view.get("reason"),
        )

    # Bước 3: Lấy quote từ investigator, orchestrator gọi issue_refund
    quote_payload = investigated["tools"].get("compute_compensation")
    if not quote_payload:
        # fallback nếu investigator chưa chạy compute_compensation
        order = order_view.get("order", {})
        budget.add_tool(tool_cost())
        quote_payload = compute_compensation(conn, order)

    trace.add("quote", quote_payload)
    proposal_amount = int(quote_payload.get("amount_vnd", 0))

    if proposal_amount <= 0:
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="denied",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=quote_payload.get("reason"),
        )

    # TODO CP3: truyền crash_at vào issue_refund, không bắt InjectedCrash
    outcome = issue_refund(conn, claim_id, proposal_amount, crash_at=crash_at)

    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal_amount,
            budget=budget,
            trace=trace,
            error_reason=outcome["reason"],
        )

    return finish(
        conn,
        shape="orchestrator",
        claim_id=claim_id,
        seed=seed,
        status="resolved",
        proposal_amount=proposal_amount,
        budget=budget,
        trace=trace,
        error_reason=None,
    )