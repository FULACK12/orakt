"""Resume cold SEC imports without overwriting facts or collapsing quarter/YTD.

ZIPs remain the complete raw source. SQLite retains each selected core observation
including start date and value. Only unambiguous, previously absent facts enter
the legacy PostgreSQL table, whose unique key cannot represent period variants.
"""
import argparse
import hashlib
import json
import sqlite3
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from app.companies import (_company_fact_rows, _submission_rows,
    _submission_rows_from_columns, _historical_submission_files,
    _dialect_insert, COMPANY_FACT_KEY_FIELDS)
from app.db.models import CompanyProfile, CompanyFiling, CompanyFinancialFact
from app.db.session import get_session_factory
from app.company_history_dossier import write_json


def partition_variants(rows):
    grouped = {}
    for row in rows:
        key = tuple(row[k] for k in COMPANY_FACT_KEY_FIELDS)
        grouped.setdefault(key, {})[(row['period_start'], row['value'])] = row
    safe = [next(iter(v.values())) for v in grouped.values() if len(v) == 1]
    return safe, sum(len(v) for v in grouped.values() if len(v) > 1)


def read_member(archive, name):
    info = archive.getinfo(name)
    if info.file_size > 256 * 1024**2:
        raise ValueError('Oversized SEC member')
    # zipfile validates member CRC; never extracts paths from an archive.
    return json.loads(archive.read(info))


def insert_absent(session, model, rows):
    count = 0
    for start in range(0, len(rows), 500):
        result = session.execute(_dialect_insert(session, model).values(rows[start:start+500]).on_conflict_do_nothing())
        count += max(0, result.rowcount)
    return count


def run(root, limit):
    ledger = sqlite3.connect(root / 'import-ledger.sqlite3')
    ledger.execute('CREATE TABLE IF NOT EXISTS issuers(cik TEXT PRIMARY KEY, ticker TEXT, state TEXT, result TEXT)')
    ledger.execute('CREATE TABLE IF NOT EXISTS observations(hash TEXT PRIMARY KEY, ticker TEXT, period_start TEXT, period_end TEXT, filed_at TEXT, source_archive TEXT, payload TEXT)')
    ledger.execute('CREATE INDEX IF NOT EXISTS observations_ticker_date ON observations(ticker,filed_at)')
    identities = {}
    for name in ['submissions.zip', 'companyfacts.zip']:
        manifest = json.loads((root / (name + '.manifest.json')).read_text(encoding='utf-8'))
        with (root / name).open('rb') as handle:
            actual = hashlib.file_digest(handle, 'sha256').hexdigest()
        if actual != manifest['sha256']:
            raise ValueError('Archive SHA-256 mismatch: ' + name)
        identities[name] = actual
    summary = {'schema':'sec-bulk-import/v1','scope':'existing_company_profiles_only',
               'archives':identities,'companies':[], 'state':'running'}
    def progress():
        summary['checkedAt'] = datetime.now(UTC).isoformat()
        write_json(root / 'import-progress.json', summary)
    progress()
    with get_session_factory()() as session, zipfile.ZipFile(root/'submissions.zip') as submissions, zipfile.ZipFile(root/'companyfacts.zip') as facts:
        profiles = list(session.scalars(select(CompanyProfile).order_by(CompanyProfile.ticker)))
        for profile in profiles:
            prior = ledger.execute('SELECT state FROM issuers WHERE cik=?', (profile.cik,)).fetchone()
            if prior and prior[0] == 'complete':
                continue
            if len(summary['companies']) >= limit or (root / 'pause-import').exists():
                summary['state'] = 'bounded_batch_complete' if len(summary['companies']) >= limit else 'safely_paused'
                break
            result = {'ticker':profile.ticker, 'state':'importing'}
            summary['companies'].append(result); progress()
            try:
                payload = read_member(submissions, f'CIK{profile.cik}.json')
                filings = _submission_rows(profile, payload)
                for name in _historical_submission_files(payload):
                    filings.extend(_submission_rows_from_columns(profile, read_member(submissions, name)))
                observations = _company_fact_rows(profile, read_member(facts, f'CIK{profile.cik}.json'), retain_period_variants=True)
                for row in observations:
                    raw = json.dumps(row, sort_keys=True, default=str)
                    digest = hashlib.sha256(raw.encode()).hexdigest()
                    ledger.execute('INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?,?,?)',
                        (digest,profile.ticker,str(row['period_start'] or ''),str(row['period_end']),str(row['filed_at']),identities['companyfacts.zip'],raw))
                ledger.commit()
                safe, ambiguous = partition_variants(observations)
                result.update(rawCoreObservations=len(observations), ambiguousPeriodVariants=ambiguous,
                    newFilings=insert_absent(session, CompanyFiling, list({r['accession_number']:r for r in filings}.values())),
                    newUnambiguousFacts=insert_absent(session, CompanyFinancialFact, safe))
                session.commit()
                result['state']='complete'
            except Exception as exc:
                session.rollback(); result.update(state='failed', errorType=type(exc).__name__)
            ledger.execute('INSERT OR REPLACE INTO issuers VALUES(?,?,?,?)', (profile.cik,profile.ticker,result['state'],json.dumps(result)))
            ledger.commit(); progress()
            print(json.dumps(result), flush=True)
        else:
            summary['state']='known_universe_import_complete'
    summary['retainedCoreObservations'] = ledger.execute('SELECT count(*) FROM observations').fetchone()[0]
    summary['completedIssuers'] = ledger.execute("SELECT count(*) FROM issuers WHERE state='complete'").fetchone()[0]
    progress(); ledger.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--limit',type=int,default=10)
    args=parser.parse_args()
    if not 1 <= args.limit <= 200: parser.error('limit must be 1–200')
    run(args.root,args.limit)
