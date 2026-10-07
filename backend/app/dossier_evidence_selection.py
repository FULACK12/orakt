"""Diverse, source-only retrieval roles; selection is not semantic verification."""
import re

ROLES={
 'business':[
  ('operating_change',r'(?:revenue|sales).{0,60}(?:decreased|increased)|decrease was primarily'),
  ('product_scope',r'operating segments|comprised primarily|geforce|reportable segments'),
  ('attribution_boundary',r'initially billed|geographic region|location of customers'),
  ('customer_exposure',r'significant customers|sales are highly concentrated')],
 'financial':[
  ('realized_margin_drivers',r'improvement in gross margin|driven primarily|decrease in warranty charges'),
  ('expense_flexibility',r'operating expenses are relatively fixed|independent of revenue|cannot be reduced'),
  ('cost_definition',r'cost of revenue consists|gross profit consists'),
  ('reported_expenses',r'sales, general and administrative expenses were|cost reduction initiatives')],
 'supply':[
  ('named_dependency',r'tsmc|taiwan semiconductor|do not own or operate|depend on foundries'),
  ('realized_quality_event',r'recorded an additional net warranty charge|recorded a .{0,25}charge against'),
  ('capacity_mechanism',r'yield problems|decreases in manufacturing yields|limited access to wafer'),
  ('cost_basis',r'inventory cost is computed|inventory costs consist')]
}


def words(text):return set(re.findall(r'[a-z]{3,}',text.lower()))


def select(passages,key,limit=4):
    if len({p['id'] for p in passages})!=len(passages):raise ValueError('Duplicate retrieval identity')
    selected=[];trace=[]
    def diverse(p):
        a=words(p['text'])
        return all(len(a & words(q['text']))/max(1,len(a | words(q['text'])))<.72 for q in selected)
    for role,pattern in ROLES.get(key,[]):
        ranked=sorted(enumerate(passages),key=lambda ip:(-len(re.findall(pattern,ip[1]['text'],re.I|re.S)),ip[0]))
        for _,p in ranked:
            if p not in selected and diverse(p) and re.search(pattern,p['text'],re.I|re.S):
                selected.append(p);trace.append({'id':p['id'],'reason':role});break
        if len(selected)==limit:break
    for p in passages:
        if len(selected)==limit:break
        if p not in selected and diverse(p):selected.append(p);trace.append({'id':p['id'],'reason':'distinct_context'})
    # Small/overlapping packets must still supply two distinct quotations.
    if len(selected)<min(2,len(passages)):
        for p in passages:
            if p not in selected:selected.append(p);trace.append({'id':p['id'],'reason':'limited_source_fallback'})
            if len(selected)>=min(2,len(passages)):break
    return selected,trace
