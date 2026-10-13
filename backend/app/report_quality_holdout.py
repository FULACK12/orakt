"""Reserve unseen issuer candidates using metadata only, without reading prose."""
import argparse
import hashlib
import json
from pathlib import Path
from app.report_quality import rules_digest
from app.report_quality_evaluation import POLICY, split, evaluate
from app.report_usage import digest, save


def reserve(catalog, plans, output):
    if output.exists():
        raise ValueError('Preserve holdout selection')
    dev = json.loads((catalog/'evaluation-manifest.json').read_text(encoding='utf-8'))['cases']
    exposed = {c['groupId'] for c in dev}
    cases = []
    seen = set()
    for plan in plans:
        for item in json.loads(plan.read_text(encoding='utf-8')).get('items', []):
            issuer=item.get('ticker')
            if not issuer or issuer in exposed or issuer in seen or split(issuer)!='holdout':
                continue
            if item.get('state')!='ready_for_generation' or not item.get('sourcePath'):
                continue
            path=Path(item['sourcePath'])
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=item.get('sourceSha256'):
                continue
            form=item.get('form'); kind='annual' if form in ('10-K','20-F','40-F') else 'quarter' if form=='10-Q' else 'unknown'
            era='historical' if item.get('periodEnd','9999')<'2020-01-01' else 'recent'
            seen.add(issuer)
            cases.append({'id':issuer+'/'+item['accession'],'groupId':issuer,'split':'holdout',
                'stratum':'us_'+kind+'_'+era, 'sourcePath':str(path),'sourceSha256':item['sourceSha256'],
                'planPath':str(plan),'form':form,'periodEnd':item.get('periodEnd'),
                'usedForTuning':False,'synthetic':False,'labelStatus':'candidate_unseen_prose_not_adjudicated',
                'exposureCaveat':'Excluded current development issuers; prior unrelated threads cannot be proven unseen. Disqualify if later used for tuning.'})
    manifest={'rulesetSha256':rules_digest(),'rulesFrozenBeforeHoldout':True,
              'cases':dev+cases,'selection':'Issuer hash split, one filing per issuer; metadata and file hash only.',
              'missingStrata':sorted(set(POLICY['requiredStrata'])-{c['stratum'] for c in cases}),
              'automaticApprovalEnabled':False}
    save(output/'manifest.json',manifest)
    save(output/'evaluation-status.json',evaluate(manifest,[]))
    print(json.dumps({'reservedCandidates':len(cases),'missingStrata':manifest['missingStrata'],
                      'independentlyLabeled':0,'automaticApprovalEnabled':False}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--plans',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();reserve(a.catalog,a.plans,a.output)
