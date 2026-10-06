"""Merge reviewed historical reports, provenance and coverage into ORAKT.

Does not export raw full text, credentials, unreviewed model drafts, or overwrite
unrelated map snapshots. Run the existing full export before this merge if needed.
"""
from __future__ import annotations
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from sqlalchemy import select, text

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/"backend"))
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.db.models import ResearchInquiry
from app.orakt_history_queue import snapshot as queue_snapshot
from app.provenance import prepare, view
from export_local_snapshot import _research_report_index_item


def historical_report(row, stamp):
    snap=row.evidence_snapshot or {}
    packet=snap.get("historical_reconstruction")
    audit=snap.get("report_audit") or {}
    if not packet or audit.get("reviewer")!="codex_assistant" or not audit.get("corrections") or row.status!="completed":
        return None
    result=row.result
    paper=result["paper_report"]
    hypothesis=result["hypotheses"][0]
    return {"id":f"local-{row.id}","localInquiryId":row.id,"origin":"local_ollama","ticker":packet["ticker"],"companyName":packet["ticker"],"marketRegion":"us","sector":"","analysisMode":"news_first",
        "question":row.question,"thesis":result["summary"],"verdict":"助手复审后发布；非人工接受，非当时预测", "confidence":round(hypothesis["confidence"]*100),
        "createdAt":row.created_at.isoformat(),"updatedAt":row.updated_at.isoformat(),"syncedAt":stamp,"model":row.local_model,"dataCutoff":packet["as_of_date"],
        "historical":{"asOf":packet["as_of_date"],"periodEnd":packet["period_end"],"mode":"historical_reconstruction","precision":"day","reviewer":"codex_assistant","corrections":audit["corrections"],"eligibleForPredictiveBacktest":False},
        "audit":{"version":"assistant_historical_review_v1","status":"assistant_revised","recommendation":"research_only","openaiUsed":False,"citedReferences":len(paper.get("evidence_refs",[])),"missingReferences":0,"headlineOnlyReferences":0,"futureDatedReferences":0,"foreignSubjects":0,"repairsApplied":len(audit["corrections"])},
        "newsReport":{"headline":paper["title"],"narrative":paper["abstract"],"facts":paper["findings"],"uncertainties":paper["limitations"],"documentsReviewed":1,"fullContentReviewed":1,"headlineOnlyExcluded":0},
        "chain":[{"title":s["label"],"claim":s["label"],"status":{"verified":"verified","partially_supported":"partial"}.get(s["status"],"missing"),"confidence":round(s["confidence"]*100),"evidenceCount":len(s["evidence_refs"])} for s in hypothesis["steps"]],
        "evidence":[{"title":f['concept'],"publisher":"SEC XBRL","url":f["source_url"],"observedAt":f["filed_at"],"claim":f"{f['evidence_id']}: {f['value']} {f['unit']} · {f['period_start'] or 'instant'} → {f['period_end']}","supports":"support","reliability":None} for f in packet["facts"] if f["evidence_id"] in paper.get("evidence_refs",[])]+[{"title":packet["filing_ref"],"publisher":"SEC","url":packet["source_url"],"observedAt":packet["as_of_date"],"claim":"Official filing; bounded excerpts used, not the entire document in the model context.","supports":"support","reliability":None}],
        "alternatives":paper.get("alternative_explanations",[]),"limitations":paper["limitations"],"nextData":hypothesis.get("evidence_gaps",[]),"scores":[],"tradingScenario":None,"canslim":None,"competitorComparison":None}


def main():
    stamp=datetime.now(UTC).isoformat()
    folder=ROOT/"snapshot"
    index=json.loads((folder/"research-report-index.json").read_text(encoding="utf-8"))
    by_id={r["id"]:r for r in index["reports"]}
    provenance=[]
    with get_session_factory()() as session:
        rows=session.scalars(select(ResearchInquiry).where(ResearchInquiry.status=="completed")).all()
        for row in rows:
            report=historical_report(row,stamp)
            if not report: continue
            (ROOT/"private-data/research-reports"/f"{report['id']}.json").write_text(json.dumps({"report":report},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
            by_id[report["id"]]={**_research_report_index_item(report),"historical":report["historical"],"dataCutoff":report["dataCutoff"]}
            record=prepare(session,kind="report",object_id=row.id,namespace="orakt-local-v1")
            provenance.append({"reportId":report["id"],"revision":record.revision,"payloadHash":record.payload_hash,"sourceHash":record.source_set_hash,"status":record.status,"network":"solana:devnet","signature":record.signature,"memo":record.memo})
        session.commit()
        alpha=[]
        for row in rows:
            if f"local-{row.id}" not in by_id: continue
            result=row.result or {}
            research=result.get("factor_research") or {}
            vals=research.get("profit_validations") or []
            ctx=row.evidence_snapshot.get("equity_research_context") or row.evidence_snapshot.get("equity_context") or {}
            if not vals and not result.get("factor_candidates"): continue
            alpha.append({"reportId":f"local-{row.id}","ticker":ctx.get("ticker"),"market":ctx.get("market_region"),"generatedAt":row.created_at.isoformat(),"candidateCount":len(research.get("factors") or result.get("factor_candidates") or []),"validations":[{k:v.get(k) for k in ["target_series_id","start_date","end_date","train_end_date","test_observations","forecast_horizon_days","transaction_cost_bps","excess_return","status","limitations","replication"]} for v in vals]})
        future={s:n for s,n in session.execute(text("SELECT status,count(*) FROM factor_experiments GROUP BY status"))}
    index.update(generatedAt=stamp,total=len(by_id),reports=sorted(by_id.values(),key=lambda r:r["createdAt"],reverse=True))
    (folder/"research-report-index.json").write_text(json.dumps(index,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    catalog=json.loads((folder/"equity-report-catalog.json").read_text(encoding="utf-8"))
    for c in catalog["companies"]:
        c["reportIds"]=[r["id"] for r in index["reports"] if r.get("marketRegion")==c["marketRegion"] and r.get("ticker")==c["ticker"]]
    (folder/"equity-report-catalog.json").write_text(json.dumps(catalog,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    queue=queue_snapshot(get_settings().cold_data_root/"orakt/history")
    payload={"generatedAt":stamp,"publicationMode":"reviewed_snapshot_not_live","publishedReports":len(by_id),"publishedHistoricalReports":len(provenance),"history":queue,"alpha":{"reports":alpha,"futureExperiments":future,"validatedAlphaCount":None,"validationStatus":"not_established","note":"单一回测正收益或超额收益不等于稳健 Alpha；未完成双基准、独立样本、置信区间和未来验证时不计入已验证。历史重建报告不用于预测回测。"},"provenance":provenance}
    (folder/"orakt-research-ops.json").write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(json.dumps({"publishedReports":len(by_id),"historicalReports":len(provenance),"alphaReports":len(alpha),"queue":queue["counts"]}))


if __name__=="__main__": main()
