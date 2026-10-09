"""Exact reviewer-selected original spans, never new facts or model approval."""
import hashlib


def validate_context(packet,text):
    ids=packet.get('review_context_ids',[])
    if len(set(ids))!=len(ids):raise ValueError('Duplicate review context')
    for pid in ids:
        records=[p for rows in packet['chapter_passages'].values() for p in rows if p['id']==pid]
        if not records:raise ValueError('Missing review context')
        for p in records:
            digest=hashlib.sha256((packet['raw_sha256']+':'+str(p['start'])+':'+p['text']).encode()).hexdigest()
            if (not p['text'] or not 0<=p['start']<p['end']<=len(text)
                or p['sourceHash']!=packet['raw_sha256'] or text[p['start']:p['end']]!=p['text']
                or pid!='PASSAGE:'+digest[:16]):
                raise ValueError('Review context differs from original')
