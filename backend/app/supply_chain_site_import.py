"""Import reviewed exact supplier facilities without implying customer assignment."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CompanySupplyChainEdge, CompanySupplyChainSite
from app.db.session import get_session_factory


class ReviewedSupplyChainSite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_ticker: str
    related_ticker: str
    facility_name: str = Field(min_length=3, max_length=255)
    country_name: str
    country_iso2: str = Field(min_length=2, max_length=2)
    admin1_name: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    source_url: str
    source_excerpt: str = Field(min_length=20, max_length=2_000)
    observed_at: date
    available_at: date
    association_scope: Literal[
        "supplier_facility_not_customer_linked",
        "customer_linked_facility",
        "confirmed_production_line",
    ] = "supplier_facility_not_customer_linked"


class SupplyChainSiteImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sites_seen: int
    inserted: int
    updated: int
    subjects: list[str]


def import_reviewed_supply_chain_sites(
    session: Session,
    *,
    sites: list[ReviewedSupplyChainSite],
) -> SupplyChainSiteImportResult:
    """Attach reviewed facilities only to an already verified company relationship."""
    identities = {
        (item.subject_ticker.upper(), item.related_ticker.upper(), item.facility_name.casefold())
        for item in sites
    }
    if len(identities) != len(sites):
        raise ValueError("review file contains duplicate supply-chain facilities")
    inserted = 0
    updated = 0
    subjects: set[str] = set()
    for item in sites:
        subject = item.subject_ticker.strip().upper()
        related = item.related_ticker.strip().upper()
        edge = session.scalar(
            select(CompanySupplyChainEdge)
            .where(
                CompanySupplyChainEdge.subject_ticker == subject,
                CompanySupplyChainEdge.related_ticker == related,
                CompanySupplyChainEdge.review_status == "verified",
            )
            .order_by(CompanySupplyChainEdge.available_at.desc())
            .limit(1)
        )
        if edge is None:
            raise ValueError(f"missing verified relationship for {subject}->{related}")
        existing = session.scalar(
            select(CompanySupplyChainSite).where(
                CompanySupplyChainSite.edge_id == edge.id,
                CompanySupplyChainSite.site_kind == "facility",
                CompanySupplyChainSite.site_name == item.facility_name,
                CompanySupplyChainSite.country_iso2 == item.country_iso2.upper(),
            )
        )
        if existing is None:
            existing = CompanySupplyChainSite(
                edge_id=edge.id,
                subject_ticker=subject,
                related_company_name=edge.related_company_name,
                related_ticker=related,
                site_kind="facility",
                site_name=item.facility_name,
                country_name=item.country_name,
                country_iso2=item.country_iso2.upper(),
                admin1_name=item.admin1_name,
                latitude=item.latitude,
                longitude=item.longitude,
                coordinate_precision="exact_facility",
                verification_status="verified_exact",
                association_scope=item.association_scope,
                source_kind="supplier_facility_page",
                source_ref=f"facility:{related}:{item.facility_name}",
                source_url=item.source_url,
                source_excerpt=item.source_excerpt,
                observed_at=item.observed_at,
                available_at=item.available_at,
            )
            session.add(existing)
            inserted += 1
        else:
            existing.admin1_name = item.admin1_name
            existing.latitude = item.latitude
            existing.longitude = item.longitude
            existing.coordinate_precision = "exact_facility"
            existing.verification_status = "verified_exact"
            existing.association_scope = item.association_scope
            existing.source_kind = "supplier_facility_page"
            existing.source_url = item.source_url
            existing.source_excerpt = item.source_excerpt
            existing.observed_at = item.observed_at
            existing.available_at = item.available_at
            updated += 1
        subjects.add(subject)
    session.flush()
    return SupplyChainSiteImportResult(
        sites_seen=len(sites),
        inserted=inserted,
        updated=updated,
        subjects=sorted(subjects),
    )


def load_reviewed_sites(path: Path) -> list[ReviewedSupplyChainSite]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("sites"), list):
        raise ValueError("review file must contain a sites list")
    return [ReviewedSupplyChainSite.model_validate(item) for item in payload["sites"]]


def main() -> None:
    parser = argparse.ArgumentParser(prog="newsapp-supply-chain-site-import")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    sites = load_reviewed_sites(args.path)
    with get_session_factory()() as session:
        result = import_reviewed_supply_chain_sites(session, sites=sites)
        session.commit()
    print(result.model_dump_json(indent=2), flush=True)


if __name__ == "__main__":
    main()
