"""Development replay only. This cannot measure semantic error detection."""
import argparse
import json
from pathlib import Path
from collections import Counter
from app.report_quality import check, rules_digest
from app.report_usage import save


def replay(root, output):
    if output.exists():
        raise ValueError('Preserve prior replay')
    records = json.loads((root/'error-catalog.json').read_text(encoding='utf-8'))['records']
    results = []
    for record in records:
        r = json.loads((root/'errors'/f"{record['id']}.json").read_text(encoding='utf-8'))
        packet = json.loads(Path(r['sourcePath']).read_text(encoding='utf-8'))['packet']
        old = json.loads(Path(r['parentPath']).read_text(encoding='utf-8'))
        new = json.loads(Path(r['correctedPath']).read_text(encoding='utf-8'))
        before, after = check(packet,[old]), check(packet,[new])
        results.append({'id':r['id'],'ticker':r['ticker'],'chapter':r['chapter'],
                        'before':before,'after':after,
                        'interpretation':'Mechanical findings only. No finding is not a semantic pass; prior review is not independent gold labeling.'})
    summary = {'rulesetSha256':rules_digest(),'chapters':len(results),
        'beforeFindings':dict(Counter(f['code'] for r in results for f in r['before']['findings'])),
        'afterFindings':dict(Counter(f['code'] for r in results for f in r['after']['findings'])),
        'semanticMissRate':None,'independentFalseBlockRate':None,'repairRegressionRate':None,
        'automaticApprovalEnabled':False,'results':results}
    save(output,summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='results'}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();replay(a.catalog,a.output)
