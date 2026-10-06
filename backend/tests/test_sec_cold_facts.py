import json
import sqlite3
from app.sec_cold_facts import cold_facts_for_filing

def test_reads_variants_and_excludes_later_filings(tmp_path):
    root=tmp_path/'raw/sec/bulk/2026-10-06';root.mkdir(parents=True)
    with sqlite3.connect(root/'import-ledger.sqlite3') as db:
        db.execute('CREATE TABLE issuers(ticker TEXT,state TEXT)')
        db.execute("INSERT INTO issuers VALUES('A','complete')")
        db.execute('CREATE TABLE observations(hash TEXT,ticker TEXT,period_end TEXT,filed_at TEXT,source_archive TEXT,payload TEXT)')
        for i,(start,filed) in enumerate([('2020-01-01','2020-08-01'),('2020-04-01','2020-08-01'),('2020-01-01','2021-08-01')]):
            row=dict(accession_number='x',concept='Revenue',value=100,unit='USD',period_start=start,period_end='2020-06-30',filed_at=filed,source_url='https://www.sec.gov',taxonomy='us-gaap')
            db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?)',(str(i)*64,'A','2020-06-30',filed,'archive',json.dumps(row)))
    facts=cold_facts_for_filing(tmp_path,'A','x','2020-08-01','2020-06-30')
    assert len(facts)==2
    assert len({f['period_start'] for f in facts})==2
    assert all(f['evidence_id'].startswith('BULK:') for f in facts)
