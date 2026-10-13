"""Replay retained development outputs through the writer without model calls.

Refuses holdout/tuning-unknown issuers, preserves drafts and source bytes, and
reports acceptance only as mechanical routing (never semantic correctness).
"""
import argparse,json,re
from pathlib import Path
from datetime import UTC,datetime
from app.dossier_compact_writer import bind,prompt_view,scoped_prompt_view
from app.report_quality import FIELDS,REF,rules_digest
from app.report_quality_evaluation import evaluate
from app.report_quality_holdout_audit import file_hash
from app.report_usage import save
from app.review_frozen_dossier import load_frozen_packet


def replay(root,corrected,manifest_path,cold_root,output):
    if output.exists():raise ValueError('Preserve previous replay')
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    manifest=read(manifest_path)
    # Hash-only preflight before opening any source prose. Reserved sources
    # cannot be pulled into development just by relabeling the output report.
    source_hash=file_hash(root/'source.json')
    cases=[c for c in manifest['cases'] if c.get('sourceSha256')==source_hash]
    if (len(cases)!=1 or cases[0]['split']!='development' or cases[0].get('usedForTuning') is not True
            or any(c['groupId'].upper()==cases[0]['groupId'].upper() and c['split']=='holdout' for c in manifest['cases'])):
        raise ValueError('Only explicitly exposed development examples may be replayed')
    original,_=load_frozen_packet(root/'source.json',cold_root)
    packet=original['packet'];identity=packet['ticker']+'/'+packet['accession']
    if cases[0]['id']!=identity:raise ValueError('Development source identity changed')
    fixed=read(corrected)
    if fixed['ticker']!=packet['ticker'] or fixed['accession']!=packet['accession']:
        raise ValueError('Mismatched revision')
    rows=[]
    for doc in fixed['chapters']:
        key=doc['chapter'];directory=root/'drafts'/key/'revision-1'
        request=read(directory/'request-1.json');raw=read(directory/'attempt-1.json')
        if request['sourcePacketSha256']!=file_hash(root/'source.json'):
            raise ValueError('Model request evidence changed')
        if raw.get('done') is not True or raw.get('done_reason')=='length':
            raise ValueError('Incomplete model output')
        view=read(directory/'writer-view.json')
        body={}
        for field in FIELDS:
            pair=doc['section'][field]
            refs={lang:set(REF.findall(pair[lang])) for lang in ('zh','en')}
            if refs['zh']!=refs['en']:raise ValueError('Bilingual references differ')
            body[field]={lang:re.sub(r'\s*\[PASSAGE:[^]]+\]','',pair[lang]) for lang in refs}
            body[field]['support_ids']=sorted(refs['en'])
        body['claims']=[{k:c[k] for k in ('passage_id','statement')} for c in doc['section']['grounded_claims']]
        row={'chapter':key,'originalResponseSha256':file_hash(directory/'attempt-1.json'),
             'writerViewSha256':file_hash(directory/'writer-view.json')}
        for label,candidate in [('initial',json.loads(raw['message']['content'])),('authorCorrected',body)]:
            try:
                bind(candidate,packet,key,view)
                row[label]={'checksAccepted':True,'semanticApproval':False}
            except ValueError as exc:
                row[label]={'checksAccepted':False,'error':str(exc),'semanticApproval':False}
        measure=lambda x:len(json.dumps(x,ensure_ascii=False,separators=(',',':')))
        row['promptEvidenceCharacters']={'before':measure(prompt_view(view)),'after':measure(scoped_prompt_view(view)),
                                         'tokens':None,'note':'Characters only; not measured model tokens or quality improvement.'}
        rows.append(row)
    assessment=evaluate(manifest,[])
    result={'state':'development_replay_only','createdAt':datetime.now(UTC).isoformat(),
       'sourceSha256':file_hash(root/'source.json'),'correctedSha256':file_hash(corrected),
       'writerSha256':file_hash(Path(__file__).resolve().parents[1]/'backend/app/dossier_compact_writer.py'),
       'rulesetSha256':rules_digest(),'rows':rows,
       'initialAccepted':sum(r['initial']['checksAccepted'] for r in rows),
       'correctedAccepted':sum(r['authorCorrected']['checksAccepted'] for r in rows),
       'independentEvidence':assessment,'batchSamplingReady':False,
       'allowedMode':'development_drafts_with_full_substantive_review',
       'localModelCalls':0,'localModelTokens':0,'codexTokens':None,'published':False,
       'note':'Replay tests routing, not the effect of the changed prompt. The accepted initial drafts can still contain semantic errors. No independent labels supplied; no false-positive or miss-rate estimate.'}
    save(output,result)
    return {k:v for k,v in result.items() if k not in ('rows','independentEvidence')}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--corrected',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--cold-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(replay(a.root,a.corrected,a.manifest,a.cold_root,a.output)))
