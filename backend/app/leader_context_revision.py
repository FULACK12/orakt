"""Explicitly refresh same-filing retrieval for a failed, chapter-free pilot.

No successful chapter is discarded. Prior attempts remain in their own queue.
"""
import argparse,copy,hashlib,json
from pathlib import Path
from app.company_history_dossier import write_json
from app.core.config import get_settings
from app.dossier_passages import add_passages
from app.leader_history_batch import sha,summarize
from app.leader_report_batch import now
from app.review_frozen_dossier import load_frozen_packet


def prepare(parent,accession,output):
    if output.exists():raise ValueError('Preserve revision directory')
    old=json.loads((parent/'plan.json').read_text(encoding='utf-8'))
    progress=json.loads((parent/'generation-progress.json').read_text(encoding='utf-8'))
    job=progress['jobs'][accession]
    if job['chapters'] or job['state']!='repair_required':raise ValueError('Only a failed chapter-free pilot may be re-planned')
    item=copy.deepcopy(next(i for i in old['items'] if i['accession']==accession))
    source=Path(item['sourcePath']);doc,raw=load_frozen_packet(source,get_settings().cold_data_root)
    doc=copy.deepcopy(doc);doc['packet']=add_passages(doc['packet'],get_settings().cold_data_root)
    doc['fingerprint']=hashlib.sha256(json.dumps({'version':doc['version'],'packet':doc['packet']},sort_keys=True).encode()).hexdigest()
    doc['continuation']={'parentSourceSha256':hashlib.sha256(raw).hexdigest(),'parentSourcePath':str(source),
        'method':'Same original and financial ledger; added paired accounting transition source context after substantive audit'}
    target=output/'packets'/item['ticker']/accession/'source.json';write_json(target,doc)
    load_frozen_packet(target,get_settings().cold_data_root)
    item.update(sourcePath=str(target),sourceSha256=sha(target))
    prior=[{'path':str(p),'sha256':sha(p)} for p in (parent/'drafts'/item['ticker']/accession).rglob('attempt-*.json')]
    plan={**old,'createdAt':now(),'checkedAt':now(),'items':[item],'summary':summarize([item]),
        'continuation':{'parentPlanSha256':sha(parent/'plan.json'),'retainedAttempts':prior,'contentApproved':False},
        'stage':'plan_ready'}
    write_json(output/'plan.json',plan)
    return {'ticker':item['ticker'],'accession':accession,'source':str(target),'originalChanged':False,'successfulChaptersRegenerated':0}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--parent',type=Path,required=True);p.add_argument('--accession',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.parent,a.accession,a.output)))
