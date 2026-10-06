"""Streaming progress and repetition guard for local-only dossier generation."""
import json,time
import httpx


def repeated_tail(text):
    return len(text)>1600 and len(text[-180:].strip())>100 and text.count(text[-180:])>=4


def generate(url,payload,progress,retain_partial):
    started=time.monotonic();last=0;content='';thinking='';terminal=None
    try:
        with httpx.Client(timeout=httpx.Timeout(180,connect=20),trust_env=False) as client:
            with client.stream('POST',url,json={**payload,'stream':True}) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:continue
                    part=json.loads(line)
                    if part.get('error'):raise ValueError('Local model stream error')
                    content+=part.get('message',{}).get('content','')
                    thinking+=part.get('message',{}).get('thinking','')
                    elapsed=time.monotonic()-started
                    if elapsed>3600:raise ValueError('Chapter exceeded one-hour hard deadline')
                    if elapsed-last>=10:
                        progress({'generatedCharacters':len(content),'reasoningCharacters':len(thinking),'elapsedSeconds':round(elapsed),'stage':'generating_chapter' if content else 'model_reasoning','progressPercent':None});last=elapsed
                        if repeated_tail(content) or repeated_tail(thinking):raise ValueError('Repetitive output detected; write distinct concise paragraphs, no repeated filler')
                    if part.get('done'):terminal=part;break
        if terminal is None:raise ValueError('Model stream ended without completion')
        return {**terminal,'message':{'role':'assistant','content':content,'thinking':thinking}}
    except BaseException:
        retain_partial({'message':{'content':content,'thinking':thinking},'complete':False,'elapsedSeconds':round(time.monotonic()-started)})
        raise
