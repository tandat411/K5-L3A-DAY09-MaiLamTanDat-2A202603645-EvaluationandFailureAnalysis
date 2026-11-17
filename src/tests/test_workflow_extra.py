"""Extra test for Shape A (workflow) by Mai Lâm Tấn Đạt (2A202603645).

Verifies that the deterministic workflow ignores delay numbers written in the ticket
and strictly adheres to the database order record.

Specifically, for claim C-002 (T02):
The customer ticket claims 5 days delay, but the order row records 2 days (< 3 days required).
Swarm reference has an intentional weakness on seed % 5 == 0 where it erroneously pays 20,000 VND.
Workflow must strictly deny the refund across all seeds (11, 22, 33, 44, 55).
"""

from __future__ import annotations

from pathlib import Path
import pytest

from lab8.db import init_store
from lab8.shapes.workflow import run_claim
from tests.conftest import CLAIMS, WORLD


@pytest.mark.parametrize("seed", [11, 22, 33, 44, 55])
def test_workflow_ignores_ticket_delay_on_c002(tmp_path: Path, seed: int) -> None:
    store = tmp_path / f"wf-extra-c002-{seed}.sqlite"
    init_store(store, WORLD, CLAIMS).close()

    result = run_claim("C-002", seed=seed, store_path=str(store))

    # Must be denied with proposal 0, no ledger effect, no audit committed, and 0 model calls
    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert result.refund_effects == []
    assert result.committed_audit_count == 0
    assert result.model_calls == 0
    assert result.error_reason == "no_entitlement"
