"""Freeze local failure/revision references; never promote or train a model.

This is an inventory of candidate assets, not a ready training corpus. Exact
source checks establish provenance, not truth of every economic interpretation.
"""
import argparse,hashlib,json,shutil
from pathlib import Path
from app.company_history_dossier import write_json
from app.core.config import get_settings
from app.dossier_consolidation import validate_chapters
from app.leader_report_batch import now
from app.review_frozen_dossier import load_frozen_packet


def digest(raw):return hashlib.sha256(raw).hexdigest()


def reference(path):
    return {'path':str(path),'sha256':digest(path.read_bytes())}


def export(roots,reviewed,output):
    if output.exists():raise ValueError('Preserve frozen training inventory')
    if shutil.disk_usage(output.parent).free<30*1024**3:raise ValueError('Cold reserve below 30 GiB')
    records=[];blobs={};failed=set();pairs=[]
    def retain(path):
        raw=path.read_bytes();h=digest(raw)
        target=output/'blobs'/f'{h}.json'
        if h not in blobs:
            target.parent.mkdir(parents=True,exist_ok=True)
            # Exclusive content-addressed objects. Originals remain untouched.
            with target.open('xb') as f:f.write(raw)
            blobs[h]=len(raw)
        return {'path':str(path),'sha256':h,'retainedBlob':str(target)}
    for root in roots:
        for path in sorted(root.rglob('attempt-*.json')):
            if not path.stem.removeprefix('attempt-').isdigit():continue
            parent=path.parent;progress=parent/'progress.json';request=parent/path.name.replace('attempt-','request-')
            p=json.loads(progress.read_text(encoding='utf-8')) if progress.exists() else {}
            raw=retain(path);r=json.loads(path.read_text(encoding='utf-8'))
            case=p.get('stage') in {'repair_required','failed'}
            if case:failed.add(raw['sha256'])
            records.append({'schema':'orakt-training-asset/v1','kind':'model_attempt','id':raw['sha256'],
                'rawOutput':raw,'state':'pending_review','negativeOnly':case,'error':p.get('error') if case else None,
                'errorScope':'revision_last_error; per-attempt classification pending','model':r.get('model'),
                'request':retain(request) if request.exists() else None,
                'requestGap':None if request.exists() else 'Exact historical request/options/code hash were not retained; do not infer them from current code.',
                'writerView':retain(parent/'writer-view.json') if (parent/'writer-view.json').exists() else None,
                'goldEligible':False,'split':'unassigned_quarantine'})
    for folder in reviewed:
        source=folder/'source.json';dossier=folder/'dossier.json'
        original,_=load_frozen_packet(source,get_settings().cold_data_root)
        d=json.loads(dossier.read_text(encoding='utf-8'));m=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        if digest(dossier.read_bytes())!=m['dossierSha256'] or d['review']['state']!='assistant_reviewed_research_only':raise ValueError('Reviewed artifact changed')
        validate_chapters(original,d['chapters']);p=original['packet']
        for c in d['chapters']:
            record={'schema':'orakt-training-asset/v1','kind':'source_checked_correction_candidate',
                'id':digest((d['ticker']+d['accession']+c['chapter']+c['review']['reviewSha256']).encode()),
                'company':d['ticker'],'periodEnd':d['periodEnd'],'asOf':d['asOf'],'groupKey':d['ticker']+':'+d['periodEnd'],
                'chapter':c['chapter'],'source':reference(source),'originalSource':{'url':p['source_url'],'sha256':p['raw_sha256']},
                'originalDraftSha256':c['review']['parentSha256'],'correctedReport':retain(dossier),
                'correctionJsonPointer':'/chapters/'+str(d['chapters'].index(c))+'/section',
                'errors':c['review']['findings'],'review':c['review'],
                'sourceVerification':{'documentHash':'matched','ledger':'reproduced','quotes':'exact_binding','semanticReview':'explicit_codex_review_not_independent_truth'},
                'state':'awaiting_dataset_eligibility_review','goldEligible':False,'split':'unassigned_quarantine',
                'exclusions':['License and source rights review pending','Independent held-out split not assigned','Publication readability closure not attested in this dataset',
                    'Pretrained-model future knowledge cannot be eliminated by retrieval cutoff alone']}
            records.append(record);pairs.append(record)
    # JSONL plus schema: technical dataset artifact, not an automatic promotion.
    output.mkdir(parents=True,exist_ok=True)
    data=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records)
    with (output/'assets.jsonl').open('x',encoding='utf-8') as f:f.write(data)
    manifest={'schema':'orakt-training-inventory/v1','createdAt':now(),
        'state':'training_start_blocked_until_108_leaders_complete','trainingStarted':False,'productionModelChanged':False,
        'scopeRoots':[str(r) for r in roots],'reviewedRoots':[str(r) for r in reviewed],
        'counts':{'retainedOriginalAttempts':len({r['id'] for r in records if r['kind']=='model_attempt'}),
            'attemptsInFailedRevisions':len(failed),'sourceCheckedChapterCorrectionCandidates':len(pairs),
            'companyPeriodGroups':len({p['groupKey'] for p in pairs}),'formalGoldPairs':0,'independentTestSamples':0},
        'blobCount':len(blobs),'blobBytes':sum(blobs.values()),'assetsSha256':digest(data.encode()),
        'splitPolicy':'No split assigned yet. Group by company+financial period and near-duplicate source spans; original/amended versions never cross sets. Hold out unseen issuers and later periods; baseline and test frozen before any training.',
        'startGate':'Finish all 108 US leaders in the frozen scope; obtain new user decision; then require source/license-reviewed representative corrections and independently reviewed holdouts. No auto-start.',
        'provisionalEvidenceGate':{'minimumReviewedCorrections':500,'minimumIssuers':20,'minimumPeriodGroups':60,
            'minimumIndependentTestCases':100,'note':'Engineering acceptance target, not a scientific guarantee. Test cases excluded from tuning and selection; severe errors block deployment.'},
        'knownGaps':['Historical requests often not stored; new requests now persisted without credentials.',
            'Correction candidates are not automatically training gold; source attribution and Codex review are insufficient alone.',
            'No model training libraries installed in current backend venv; no download or installation performed.']}
    write_json(output/'manifest.json',manifest)
    write_json(output/'schema.json',{'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object',
        'required':['schema','kind','id','state','goldEligible','split'],
        'properties':{'schema':{'const':'orakt-training-asset/v1'},'id':{'type':'string','pattern':'^[a-f0-9]{64}$'},
            'kind':{'enum':['model_attempt','source_checked_correction_candidate']},'goldEligible':{'const':False},'split':{'const':'unassigned_quarantine'}},
        'additionalProperties':True})
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--roots',nargs='+',type=Path,required=True);p.add_argument('--reviewed',nargs='+',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=export(a.roots,a.reviewed,a.output);print(json.dumps({'state':r['state'],'counts':r['counts'],'bytes':r['blobBytes']}))
