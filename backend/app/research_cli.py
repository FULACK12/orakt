"""Run bounded autonomous local research from the command line."""

from __future__ import annotations

import argparse
import time

from sqlalchemy import select

from app.core.config import get_settings
from app.db.enums import ClusterJobStatus
from app.db.models import ClusterJob
from app.db.session import get_session_factory
from app.logic_chains import refresh_recent_logic_hypotheses
from app.model_workload import local_model_workload_lock
from app.research import (
    ResearchProviderError,
    backfill_factor_research,
    refresh_research_forecasts,
    run_research,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newsapp-research")
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        choices=range(1, 8),
        metavar="1-7",
        help="Number of rotating finance-focused questions to investigate",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        help="Repeat the batch on this interval; minimum 3600 seconds",
    )
    return parser


def run_batch(*, count: int) -> bool:
    """Generate one batch while retaining both successes and failed attempts."""
    settings = get_settings()
    session_factory = get_session_factory()
    with session_factory() as session:
        active_job_id = session.scalar(
            select(ClusterJob.id)
            .where(
                ClusterJob.status.in_(
                    [ClusterJobStatus.QUEUED, ClusterJobStatus.RUNNING]
                )
            )
            .order_by(ClusterJob.id)
            .limit(1)
        )
        if active_job_id is not None:
            print(
                f"research_deferred=active_cluster_job:{active_job_id}",
                flush=True,
            )
            return False
        with local_model_workload_lock(session) as acquired:
            if not acquired:
                print("research_deferred=local_model_busy", flush=True)
                return False
            logic = refresh_recent_logic_hypotheses(
                session,
                settings=settings,
                limit=2,
            )
            session.commit()
            print(
                f"logic_refresh={logic['jobs_completed']}/{logic['jobs_attempted']} "
                f"failed={logic['jobs_failed']} generated={logic['hypotheses_generated']} "
                f"validated={logic['hypotheses_validated']} jobs={logic['job_ids']}",
                flush=True,
            )
            factors = backfill_factor_research(session, settings=settings)
            session.commit()
            print(
                f"factor_backfill={factors['factor_reports_updated']}/"
                f"{factors['scanned_reports']} cold={factors['cold_artifacts_stored']}",
                flush=True,
            )
            try:
                refresh = refresh_research_forecasts(session, settings=settings)
                session.commit()
                print(
                    f"forecast_refresh={refresh['forecasts_updated']}/"
                    f"{refresh['forecasts_checked']}",
                    flush=True,
                )
            except ResearchProviderError as exc:
                session.rollback()
                print(f"forecast_refresh=failed error={exc}", flush=True)
            for _ in range(count):
                try:
                    result = run_research(
                        session,
                        question=None,
                        mode="autonomous",
                        settings=settings,
                    )
                    session.commit()
                    print(
                        f"id={result.id} status={result.status} "
                        f"hypotheses={len(result.result.hypotheses) if result.result else 0} "
                        f"question={result.question}",
                        flush=True,
                    )
                except ResearchProviderError as exc:
                    session.commit()
                    print(f"status=failed error={exc}", flush=True)
    return True


def main() -> None:
    """Generate independent audit records once or on a bounded schedule."""
    args = build_parser().parse_args()
    if args.poll_seconds is not None and args.poll_seconds < 3_600:
        raise ValueError("poll_seconds must be at least 3600")
    while True:
        completed = run_batch(count=args.count)
        if args.poll_seconds is None:
            return
        time.sleep(
            args.poll_seconds
            if completed
            else min(args.poll_seconds, 300)
        )


if __name__ == "__main__":
    main()
