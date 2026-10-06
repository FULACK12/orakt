"""Bounded, restartable local ORAKT backfill. SQLite state lives on the cold disk.

Run plan before run; pause is cooperative (finish current report, stop before next).
No automatic publication or retry of failed content. No future-data backtest of
LLM historical reconstructions. All generated drafts require content review.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import ctypes
import shutil
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text

from app.core.config import get_settings
from app.db.models import CompanyFiling, CompanyProfile, MarketSeries
from app.db.session import get_session_factory
from app.historical_earnings_report import build_packet


def now():
    return datetime.now(UTC).isoformat()


def resource_gate():
    """Pre-task guards; no model is launched if host telemetry is unavailable."""
    if sys.platform == "win32":
        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        *[(n, ctypes.c_ulonglong) for n in ["total", "available", "total_page", "available_page", "total_virtual", "available_virtual", "extended"]]]
        memory = Memory()
        memory.length = ctypes.sizeof(memory)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            return "memory_sensor_unavailable"
        if memory.available < 2500 * 1024 * 1024:
            return "available_ram_below_2500_MiB"
    executable = shutil.which("nvidia-smi")
    if not executable:
        return "gpu_sensor_unavailable"
    try:
        result = subprocess.run([executable,"--query-gpu=temperature.gpu","--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=15,check=True)
        if max(int(v.strip()) for v in result.stdout.splitlines()) >= 85:
            return "gpu_temperature_at_or_above_85C"
    except (ValueError, subprocess.SubprocessError):
        return "gpu_sensor_unavailable"
    return None


def connect(root):
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "queue.sqlite3", timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS jobs (accession TEXT PRIMARY KEY, ticker TEXT NOT NULL, as_of TEXT NOT NULL, period_end TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued', started_at TEXT, finished_at TEXT, detail TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS coverage (ticker TEXT, market TEXT, name TEXT, indexed_from TEXT, indexed_count INTEGER, ready_count INTEGER, reason TEXT, PRIMARY KEY(ticker,market))")
    return db


def plan(root):
    settings = get_settings()
    with connect(root) as db, get_session_factory()() as session:
        for company in session.scalars(select(CompanyProfile).order_by(CompanyProfile.ticker)):
            filings = session.scalars(select(CompanyFiling).where(CompanyFiling.ticker == company.ticker, CompanyFiling.form.in_(["10-Q", "10-K"])).order_by(CompanyFiling.filed_at)).all()
            ready = 0
            for filing in filings:
                if not filing.primary_document:
                    continue
                base = (settings.cold_data_root / "raw/sec/company-filings" / company.ticker).resolve()
                path = (base / filing.accession_number.replace("-", "") / filing.primary_document).resolve()
                if not path.is_relative_to(base) or not path.is_file():
                    continue
                try:
                    packet = build_packet(session, ticker=company.ticker, cold_root=settings.cold_data_root, accession=filing.accession_number)
                except ValueError:
                    continue
                ready += 1
                db.execute("INSERT OR IGNORE INTO jobs(accession,ticker,as_of,period_end) VALUES(?,?,?,?)", (filing.accession_number, company.ticker, packet["as_of_date"], packet["period_end"]))
            reason = "partial_history_body_or_facts_missing" if ready < len(filings) else "available_history_ready"
            if not ready:
                reason = "no_complete_dated_body_and_same_filing_facts"
            db.execute("INSERT OR REPLACE INTO coverage VALUES(?,?,?,?,?,?,?)", (company.ticker, "us", company.name, str(filings[0].filed_at) if filings else None, len(filings), ready, reason))
        for series in session.scalars(select(MarketSeries).where(MarketSeries.region == "china", MarketSeries.category == "equity_price", MarketSeries.listing_status == "active", MarketSeries.series_id.like("CN:%"))):
            db.execute("INSERT OR REPLACE INTO coverage VALUES(?,?,?,?,?,?,?)", (series.series_id.split(":",1)[1], "china", series.name, None, None, 0, "dated_A_share_evidence_packet_adapter_required"))
    print(json.dumps(snapshot(root), ensure_ascii=False), flush=True)


def snapshot(root):
    with connect(root) as db:
        counts = {r[0]:r[1] for r in db.execute("SELECT state,count(*) FROM jobs GROUP BY state")}
        companies = [dict(r) for r in db.execute("SELECT * FROM coverage ORDER BY market,ticker")]
        active = [dict(r) for r in db.execute("SELECT ticker,as_of,state,started_at,detail FROM jobs WHERE state='running'")]
    heartbeat_file = root / "heartbeat.json"
    heartbeat = json.loads(heartbeat_file.read_text()) if heartbeat_file.exists() else {}
    return {"observedAt":now(),"counts":counts,"companies":companies,"active":active,"worker":heartbeat,"pauseRequested":(root/"pause").exists(),"policy":"serial_local_model_content_review_required"}


def run(root, limit, full=False):
    # Separate connection-scoped lock: one queue supervisor, child owns GPU lock.
    with get_session_factory()().get_bind().connect() as lock:
        if not lock.scalar(text("SELECT pg_try_advisory_lock(624730015811)")):
            raise RuntimeError("ORAKT history supervisor already running")
        try:
            _run_locked(root, limit, full)
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(624730015811)"))


def _run_locked(root, limit, full=False):
    with connect(root) as db:
        # An interrupted operation is not silently retried: possible saved output
        # must be reconciled before spending model time again.
        db.execute("UPDATE jobs SET state='interrupted',detail='Supervisor restarted; reconcile inquiry before retry' WHERE state='running'")
    failures = 0
    for _ in range(limit):
        if (root / "pause").exists():
            break
        reason = resource_gate()
        if reason:
            (root / "pause").write_text(reason, encoding="utf-8")
            print(json.dumps({"resource_pause":reason}),flush=True)
            break
        with connect(root) as db:
            row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY as_of,ticker LIMIT 1").fetchone()
            if not row:
                break
            db.execute("UPDATE jobs SET state='running',started_at=?,detail='Waiting for local model / generating / checking citations' WHERE accession=?", (now(),row["accession"]))
        log = root / f"{row['accession']}.log"
        env = {**os.environ,"PYTHONPATH":str(Path(__file__).resolve().parents[1]),"PYTHONIOENCODING":"utf-8"}
        with log.open("a", encoding="utf-8") as output:
            child = subprocess.Popen([sys.executable,"-m","app.company_history_dossier" if full else "app.historical_earnings_report","--ticker",row["ticker"],"--accession",row["accession"],"--output-dir",str(root / "reports")],stdout=output,stderr=output,env=env)
            started = time.monotonic()
            while child.poll() is None:
                elapsed = round(time.monotonic()-started)
                beat={"checkedAt":now(),"state":"running","ticker":row["ticker"],"elapsedSeconds":elapsed,"stage":"model_request_or_citation_validation","progressPercent":None}
                temp=root/"heartbeat.tmp"
                temp.write_text(json.dumps(beat),encoding="utf-8")
                temp.replace(root/"heartbeat.json")
                if elapsed > (36000 if full else 3900):
                    child.terminate()
                    child.wait(timeout=30)
                    break
                time.sleep(10)
        state = "content_review_pending" if child.returncode == 0 else "failed"
        with connect(root) as db:
            db.execute("UPDATE jobs SET state=?,finished_at=?,detail=? WHERE accession=?", (state,now(),"Saved locally; not automatically approved or published" if state=="content_review_pending" else "Generation/citation failure; retained locally for inspection",row["accession"]))
        print(json.dumps({"ticker":row["ticker"],"accession":row["accession"],"state":state}),flush=True)
        failures = failures+1 if state=="failed" else 0
        if failures >= 3:
            break
    (root/"heartbeat.json").write_text(json.dumps({"checkedAt":now(),"state":"paused" if (root/"pause").exists() else "stopped","reason":"bounded_batch_finished_or_failure_gate"}),encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["plan","run","status","pause","resume"])
    parser.add_argument("--root",type=Path,default=get_settings().cold_data_root / "orakt/history")
    parser.add_argument("--limit",type=int,default=8)
    parser.add_argument("--full",action="store_true",help="Generate checkpointed bilingual full dossiers; use a separate queue root")
    args=parser.parse_args()
    if args.action=="plan": plan(args.root)
    elif args.action=="run": run(args.root,max(1,min(250,args.limit)),args.full)
    elif args.action=="status": print(json.dumps(snapshot(args.root),ensure_ascii=False))
    elif args.action=="pause":
        args.root.mkdir(parents=True,exist_ok=True)
        (args.root/"pause").touch()
    elif args.action=="resume": (args.root/"pause").unlink(missing_ok=True)


if __name__=="__main__": main()
