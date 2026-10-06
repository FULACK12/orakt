"""Apply a checked, reproducible human review file to supply-chain candidates."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db.models import CompanySupplyChainEdge
from app.db.session import get_session_factory
from app.supply_chain import refresh_supply_chain_coverage
from app.supply_chain_sites import materialize_supply_chain_sites


class SupplyChainReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: int
    subject_ticker: str
    related_ticker: str | None
    relationship_type: str
    decision: Literal["verified", "rejected"]
    rationale: str = Field(min_length=20, max_length=1_000)


class SupplyChainReviewImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions_seen: int
    verified: int
    rejected: int
    subjects_refreshed: list[str]


def apply_supply_chain_review_decisions(
    session: Session,
    *,
    decisions: list[SupplyChainReviewDecision],
    reviewed_by: str,
) -> SupplyChainReviewImportResult:
    """Apply only decisions whose identity fields still match the candidate row."""
    if not reviewed_by.strip():
        raise ValueError("reviewed_by is required")
    if len({item.edge_id for item in decisions}) != len(decisions):
        raise ValueError("review file contains duplicate edge ids")
    now = datetime.now(UTC)
    verified = 0
    rejected = 0
    subjects: set[str] = set()
    for decision in decisions:
        edge = session.get(CompanySupplyChainEdge, decision.edge_id)
        if edge is None:
            raise ValueError(f"supply-chain edge {decision.edge_id} does not exist")
        actual_identity = (
            edge.subject_ticker,
            edge.related_ticker,
            edge.relationship_type,
        )
        expected_identity = (
            decision.subject_ticker.strip().upper(),
            decision.related_ticker.strip().upper() if decision.related_ticker else None,
            decision.relationship_type,
        )
        if actual_identity != expected_identity:
            raise ValueError(
                f"edge {decision.edge_id} identity changed: "
                f"expected {expected_identity}, found {actual_identity}"
            )
        if edge.review_status not in {"candidate", decision.decision}:
            raise ValueError(
                f"edge {decision.edge_id} already has incompatible status "
                f"{edge.review_status}"
            )
        edge.review_status = decision.decision
        edge.reviewed_at = now
        edge.reviewed_by = reviewed_by.strip()[:64]
        edge.review_note = decision.rationale
        subjects.add(edge.subject_ticker)
        verified += decision.decision == "verified"
        rejected += decision.decision == "rejected"
    session.flush()
    for ticker in sorted(subjects):
        refresh_supply_chain_coverage(session, ticker=ticker)
        materialize_supply_chain_sites(session, ticker=ticker)
    session.commit()
    return SupplyChainReviewImportResult(
        decisions_seen=len(decisions),
        verified=verified,
        rejected=rejected,
        subjects_refreshed=sorted(subjects),
    )


def load_review_file(path: Path) -> list[SupplyChainReviewDecision]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("decisions"), list):
        raise ValueError("review file must contain a decisions list")
    return [SupplyChainReviewDecision.model_validate(item) for item in payload["decisions"]]


def main() -> None:
    parser = argparse.ArgumentParser(prog="newsapp-supply-chain-review-import")
    parser.add_argument("path", type=Path)
    parser.add_argument("--reviewed-by", required=True)
    args = parser.parse_args()
    decisions = load_review_file(args.path)
    with get_session_factory()() as session:
        result = apply_supply_chain_review_decisions(
            session,
            decisions=decisions,
            reviewed_by=args.reviewed_by,
        )
    print(result.model_dump_json(indent=2), flush=True)


if __name__ == "__main__":
    main()
