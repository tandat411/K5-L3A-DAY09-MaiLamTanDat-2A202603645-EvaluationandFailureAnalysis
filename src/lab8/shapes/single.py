"""Shape B — one ReAct agent. Student work.

Use `lab8.runtime.run_react` with max_steps=8. `decide` may pick a read tool.
It must not call `issue_refund`. After the loop, the host validates the quote
and is the only writer.

A decide() that trusts ticket text over the order row will fail hidden claims
where the customer overstates the delay or cites a superseded clause.

Per-order cap: an order may already have been refunded by an earlier claim.
The read tool `lookup_refund_history` shows how much. The host still enforces
the cap, so pass the full quote to `durability.issue_refund`, not a net amount.

Caps: stop at 8 steps. Count model calls in the Budget so cost stays comparable.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.

Ranh giới code / model trong shape này:

- Model (MockLLM, gọi trong `decide`) chỉ chọn tool ĐỌC tiếp theo, hoặc dừng.
  Model không thấy ticket, không trả số tiền, không có tool ghi.
- Số tiền là `amount_vnd` do `compute_compensation` tính từ dòng order.
- Sau vòng lặp, code của shape gọi `durability.issue_refund` với quote đầy đủ.
- Trace chỉ ghi kết quả tool đã qua allowlist; không ghi ticket, claim row hay order row thô.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8 import durability
from lab8.db import connect
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.trace import Trace

SHAPE = "single"


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    """Run bounded single-agent ReAct loop (max_steps=8) and commit via host."""
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    seed: int,
    crash_at: str | None,
) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))
    state: dict[str, Any] = {}

    def done(status: str, amount: int = 0, reason: str | None = None) -> RunResult:
        trace.add("decision", {"status": status, "proposal_amount": amount, "reason": reason})
        return finish(
            conn,
            shape=SHAPE,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=amount,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    def decide(obs: dict[str, Any]) -> dict[str, Any]:
        last_tool = obs.get("last_tool")
        last_result = obs.get("last_result") or {}
        complete(
            budget,
            seed=seed,
            purpose="react",
            prompt=f"step={budget.model_calls}|last={last_tool}",
        )

        if last_tool is None:
            return {"tool": "get_claim_view", "args": {"claim_id": claim_id}}

        if last_tool == "get_claim_view":
            state["claim_view"] = last_result
            if not last_result.get("found"):
                return {"final": {"status": "failed", "reason": "unknown_claim"}}
            trace.add(
                "claim",
                {"claim_id": claim_id, "has_order_id": bool(last_result.get("order_id"))},
            )
            if not last_result.get("order_id"):
                return {"final": {"status": "needs_info", "reason": "missing_order_id"}}
            return {
                "tool": "lookup_order",
                "args": {
                    "order_id": last_result["order_id"],
                    "principal_id": last_result["principal_id"],
                },
            }

        if last_tool == "lookup_order":
            state["order_view"] = last_result
            if not last_result.get("visible"):
                trace.add(
                    "lookup_order",
                    {"visible": False, "reason": last_result.get("reason")},
                )
                return {"final": {"status": "escalated", "reason": last_result.get("reason")}}
            trace.add(
                "lookup_order",
                {"visible": True, "order": safe_dump(last_result["order"])},
            )
            claim_view = state["claim_view"]
            return {
                "tool": "lookup_refund_history",
                "args": {
                    "order_id": claim_view["order_id"],
                    "principal_id": claim_view["principal_id"],
                },
            }

        if last_tool == "lookup_refund_history":
            state["refund_history"] = last_result
            trace.add("lookup_refund_history", safe_dump(last_result))
            return {
                "tool": "compute_compensation",
                "args": {"order": state["order_view"]["order"]},
            }

        if last_tool == "compute_compensation":
            state["quote"] = last_result
            trace.add("quote", safe_dump(last_result))
            return {"final": {"status": "ready"}}

        return {"final": {"status": "failed", "reason": f"unexpected_tool:{last_tool}"}}

    loop = run_react(
        conn,
        budget,
        observation={"claim_id": claim_id},
        decide=decide,
        max_steps=8,
        worker=False,
    )
    if loop["stopped"] == "step_cap":
        return done("failed", 0, "step_cap")

    final = loop["final"]
    if final.get("status") in ("failed", "needs_info", "escalated"):
        complete(budget, seed=seed, purpose="draft", prompt=f"status={final['status']}")
        return done(str(final["status"]), 0, final.get("reason"))

    q = state["quote"]
    proposal = int(q["amount_vnd"])
    if proposal <= 0:
        complete(budget, seed=seed, purpose="draft", prompt="proposal=0")
        return done("denied", 0, q.get("reason"))

    try:
        outcome = durability.issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except durability.InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise

    trace.add("issue_refund", {"ok": outcome["ok"], "reason": outcome["reason"]})
    complete(budget, seed=seed, purpose="draft", prompt=f"outcome={outcome['reason']}")

    if not outcome["ok"]:
        return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
    return done("resolved", proposal)
