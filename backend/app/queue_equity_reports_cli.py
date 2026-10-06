"""Queue restart-safe company research batches without duplicating completed work."""

from __future__ import annotations

import argparse
import json
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CompanyProfile, MarketSeries, ResearchBatchItem
from app.db.session import get_session_factory
from app.research_batches import create_equity_research_batch
from app.schemas.research import ResearchBatchCreateRequest

MarketRegion = Literal["us", "china"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-queue-equity-reports")
    parser.add_argument(
        "--region",
        action="append",
        choices=("us", "china"),
        dest="regions",
    )
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--name-prefix", default="证据增强公司报告")
    parser.add_argument("--include-completed", action="store_true")
    return parser


def queue_missing_reports(
    session: Session,
    *,
    regions: list[MarketRegion],
    batch_size: int,
    name_prefix: str,
    include_completed: bool,
) -> dict[str, object]:
    if not 1 <= batch_size <= 200:
        raise ValueError("batch_size must be between 1 and 200")
    excluded_statuses = ("queued", "running")
    if not include_completed:
        excluded_statuses += ("completed",)
    excluded = {
        (region, ticker)
        for region, ticker in session.execute(
            select(ResearchBatchItem.market_region, ResearchBatchItem.ticker).where(
                ResearchBatchItem.status.in_(excluded_statuses)
            )
        )
    }
    catalogs: dict[MarketRegion, list[str]] = {
        "us": list(session.scalars(select(CompanyProfile.ticker).order_by(CompanyProfile.ticker))),
        "china": [
            series_id.split(":", 1)[1]
            for series_id in session.scalars(
                select(MarketSeries.series_id)
                .where(
                    MarketSeries.category == "equity_price",
                    MarketSeries.region == "china",
                    MarketSeries.listing_status == "active",
                    MarketSeries.series_id.like("CN:%"),
                )
                .order_by(MarketSeries.series_id)
            )
        ],
    }
    batches: list[dict[str, object]] = []
    for region in regions:
        pending = [ticker for ticker in catalogs[region] if (region, ticker) not in excluded]
        for index in range(0, len(pending), batch_size):
            tickers = pending[index : index + batch_size]
            sequence = index // batch_size + 1
            label = "美股" if region == "us" else "A股"
            view = create_equity_research_batch(
                session,
                request=ResearchBatchCreateRequest(
                    name=f"{name_prefix} · {label}第{sequence:02d}批",
                    regions=[region],
                    limit_per_region=len(tickers),
                    tickers=tickers,
                ),
            )
            batches.append(
                {
                    "id": view.id,
                    "name": view.name,
                    "market_region": region,
                    "target_count": view.target_count,
                    "first_ticker": tickers[0],
                    "last_ticker": tickers[-1],
                }
            )
    return {
        "regions": regions,
        "batch_size": batch_size,
        "batches_created": len(batches),
        "targets_queued": sum(int(item["target_count"]) for item in batches),
        "batches": batches,
    }


def main() -> None:
    args = build_parser().parse_args()
    regions = [cast(MarketRegion, item) for item in (args.regions or ["us", "china"])]
    with get_session_factory()() as session:
        result = queue_missing_reports(
            session,
            regions=regions,
            batch_size=args.batch_size,
            name_prefix=args.name_prefix,
            include_completed=args.include_completed,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
