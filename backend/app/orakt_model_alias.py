"""Create and verify an exact lightweight local alias without production switch."""
import argparse,hashlib,json,re
from pathlib import Path
import httpx
from app.company_history_dossier import write_json
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.model_workload import local_model_workload_lock
from app.leader_report_batch import now

BASE='qwen3:14b-q4_K_M'
ALIAS='orakt-14b'


def storage(root):
    return {str(p.relative_to(root)):p.stat().st_size for folder in ('blobs','manifests') for p in (root/folder).rglob('*') if p.is_file()}


def parameter_values(value):
    result={}
    for line in value.splitlines():
        key,content=line.split(None,1);result.setdefault(key,[]).append(content.strip())
    return result


def run(output):
    if output.exists():raise ValueError('Preserve prior alias verification')
    settings=get_settings();url=str(settings.llm_base_url).rstrip('/')
    if not url.startswith(('http://127.0.0.1:','http://localhost:')):raise ValueError('Local Ollama only')
    with get_session_factory()() as session,local_model_workload_lock(session) as acquired,httpx.Client(base_url=url,timeout=120) as client:
        if not acquired:raise RuntimeError('Report worker owns the model; wait for safe boundary')
        def post(path,body):
            r=client.post(path,json=body);r.raise_for_status();return r.json() if r.content else {}
        original=post('/api/show',{'model':BASE})
        source_path=Path(re.search(r'^FROM (.+)$',original['modelfile'],re.M).group(1).strip())
        root=source_path.parent.parent
        if source_path.parent.name!='blobs' or not source_path.is_file():raise ValueError('Local blob path unavailable')
        before=storage(root)
        response=client.get('/api/tags');response.raise_for_status();tags=response.json()['models']
        existing=next((m for m in tags if m['name']==ALIAS+':latest'),None)
        base=next(m for m in tags if m['name']==BASE)
        if existing and existing['digest']!=base['digest']:raise ValueError('Existing alias has different weights/config; no overwrite')
        if not existing:post('/api/copy',{'source':BASE,'destination':ALIAS})
        alias=post('/api/show',{'model':ALIAS})
        fields=('details','template','license','model_info','system')
        if any(original.get(k)!=alias.get(k) for k in fields) or parameter_values(original.get('parameters',''))!=parameter_values(alias.get('parameters','')):
            raise ValueError('Alias configuration differs; do not switch production')
        outputs=[]
        for model in (BASE,ALIAS):
            r=post('/api/chat',{'model':model,'think':False,'stream':False,'keep_alive':'5m',
                'options':{'seed':42,'temperature':0,'num_ctx':2048,'num_predict':32},
                'messages':[{'role':'user','content':'Return only the exact uppercase word: READY'}]})
            outputs.append({'model':model,'content':r['message']['content'],'done':r.get('done'),'evalCount':r.get('eval_count')})
        after=storage(root);new={k:v for k,v in after.items() if k not in before}
        if any(k.startswith('blobs') for k in new):raise ValueError('Unexpected weight allocation; inspect before any production switch')
        result={'checkedAt':now(),'displayName':'Orakt 14B','productName':'Orakt','internalAlias':ALIAS,
            'baseModel':BASE,'baseDigest':base['digest'],'upstream':'https://huggingface.co/Qwen/Qwen3-14B',
            'license':'Apache-2.0','licenseSha256':hashlib.sha256(original['license'].encode()).hexdigest(),
            'details':original['details'],'configurationsEqual':True,'fixedInputChecks':outputs,
            'fixedInputEqual':outputs[0]['done'] and outputs[1]['done'] and outputs[0]['content']==outputs[1]['content'],
            'diskIncrementBytes':sum(after.values())-sum(before.values()),'newFiles':new,
            'aliasManifestBytes':sum(v for k,v in after.items() if ALIAS in Path(k).parts),
            'weightFilesCopied':0,'fineTuned':False,'productionModelUnchanged':settings.llm_model,
            'rollback':'Keep NEWSAPP_LLM_MODEL=qwen3:14b-q4_K_M. Optional alias-only removal: ollama rm orakt-14b (do not remove the base).',
            'description':'Orakt, based on Qwen3; customized report system, not independently pretrained or fine-tuned weights.'}
        write_json(output,result)
        return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.output)))
