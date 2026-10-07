"""Read full period variants from the latest retained, completed SEC cold import."""
import json
import sqlite3

def cold_facts_for_filing(cold_root, ticker, accession, filed_at, period_end):
    candidates=list((cold_root/'raw/sec/live').glob('*/import-ledger.sqlite3'))+list((cold_root/'raw/sec/bulk').glob('*/import-ledger.sqlite3'))
    candidates.sort(key=lambda p:p.stat().st_mtime,reverse=True)
    for path in candidates:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
            done=db.execute("SELECT state FROM issuers WHERE ticker=?",(ticker,)).fetchone()
            if not done or done[0]!='complete':continue
            result=[]
            for digest,archive,raw in db.execute('SELECT hash,source_archive,payload FROM observations WHERE ticker=? AND filed_at<=? AND period_end<=?',(ticker,str(filed_at),str(period_end))):
                row=json.loads(raw)
                if row['accession_number']!=accession:continue
                result.append({'evidence_id':'BULK:'+digest,'concept':row['concept'],'value':row['value'],'unit':row['unit'],
                    'period_start':row['period_start'],'period_end':row['period_end'],'filed_at':row['filed_at'],
                    'source_url':row['source_url'],'taxonomy':row['taxonomy'],'archive_sha256':archive})
            if result:return result
    return []
