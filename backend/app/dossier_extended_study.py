"""Calendar-aware historical extension and fixed-rule operating-factor audit.

Price returns only until corporate actions have been independently reconciled.
Calendar metadata is reproducible, not a claim of official exchange certification.
"""
import argparse,copy,hashlib,json,zipfile
from datetime import date,datetime,timedelta
from html import escape
from pathlib import Path
from app.company_history_dossier import write_json
from app.dossier_study_evidence import SYMBOLS,CIKS,validate_prices
from app.dossier_factor_pilot import (POLICY,margin_feature,evaluate_event,independent_trades,summarize)


def calendar_sessions(start,end):
    import exchange_calendars as xc
    # Requested edges may be holidays. Pad construction so range parsing does
    # not reject New Year's Day before the calendar's first actual session.
    c=xc.get_calendar('XNYS',start=str(date.fromisoformat(start)-timedelta(days=7)),end=str(date.fromisoformat(end)+timedelta(days=7)))
    return c.sessions_in_range(start,end).strftime('%Y-%m-%d').tolist(),{
        'library':'exchange_calendars','version':xc.__version__,'calendar':'XNYS',
        'scope':'Regular US equity-session proxy; not a trading-halt calendar or official certification',
        'reference':'https://www.nyse.com/markets/hours-calendars',
        'librarySource':'https://github.com/gerrymanoim/exchange_calendars'}


def inventory_feature(facts,event,margin):
    if margin.get('state')!='available':return {'state':'revenue_pair_missing'}
    gaap=facts.get('facts',{}).get('us-gaap',{});candidates=[]
    # Never silently splice total inventory and finished-goods inventory.
    for tag in ('InventoryNet','InventoryFinishedGoodsNetOfReserves'):
        rows=gaap.get(tag,{}).get('units',{}).get('USD',[])
        current=[r for r in rows if r.get('accn')==event['accession'] and r.get('end')==event['periodEnd'] and not r.get('start') and r.get('filed','9999')<=event['filedAt']]
        previous=[r for r in rows if r.get('end')==margin['prior']['end'] and not r.get('start') and r.get('filed','9999')<=event['filedAt']]
        # Choose latest available filing vintage BEFORE the signal, not today's latest restatement.
        if previous:
            last=max(r['filed'] for r in previous);previous=[r for r in previous if r['filed']==last]
        try:
            cv={float(r['val']) for r in current};pv={float(r['val']) for r in previous}
        except (ValueError,TypeError):continue
        import math
        if len(cv)!=1 or len(pv)!=1 or not all(math.isfinite(v) and v>0 for v in cv|pv):continue
        growth=next(iter(cv))/next(iter(pv))-1
        revenue_growth=margin['current']['revenue']/margin['prior']['revenue']-1
        candidates.append({'concept':tag,'inventoryGrowth':growth,'revenueGrowth':revenue_growth,
                           'pressure':growth-revenue_growth,'currentReferences':current,'priorReferences':previous})
    if not candidates:return {'state':'same_concept_inventory_pair_missing'}
    if len({(x['inventoryGrowth'],x['pressure']) for x in candidates})!=1:
        return {'state':'conflicting_inventory_concepts'}
    return {'state':'available',**candidates[0]}


def subscription_feature(facts,event):
    # Construct a paired gross-profit amount ONLY from identical subscription
    # revenue/cost periods and the same original accession. No broad-company proxy.
    gaap=facts.get('facts',{}).get('us-gaap',{})
    def group(tag):
        out={}
        for r in gaap.get(tag,{}).get('units',{}).get('USD',[]):
            if r.get('accn')!=event['accession'] or r.get('filed','9999')>event['filedAt']:continue
            if not r.get('start') or not r.get('end'):continue
            out.setdefault((r['start'],r['end']),[]).append(r)
        return out
    rev=group('SubscriptionRevenue');cost=group('CostOfGoodsSoldSubscription');profit=[];refs=[]
    for key in sorted(set(rev)&set(cost)):
        rv={float(r['val']) for r in rev[key]};cv={float(r['val']) for r in cost[key]}
        if len(rv)!=1 or len(cv)!=1:continue
        profit.append({**rev[key][0],'val':next(iter(rv))-next(iter(cv))})
        refs.extend([{'concept':'SubscriptionRevenue',**r} for r in rev[key]])
        refs.extend([{'concept':'CostOfGoodsSoldSubscription',**r} for r in cost[key]])
    adapted={'facts':{'us-gaap':{
        'Revenues':gaap.get('SubscriptionRevenue',{}),'GrossProfit':{'units':{'USD':profit}}}}}
    result=margin_feature(adapted,event)
    if result['state']=='available':
        result['derivation']='Subscription gross profit = SubscriptionRevenue - CostOfGoodsSoldSubscription, identical period/accession'
        result['sourceReferences']=refs
        # Remove synthetic GrossProfit references: the true source tags are above.
        for k in ('current','prior'):result[k]['references']=[r for r in refs if r['start']==result[k]['start'] and r['end']==result[k]['end']]
    return result


def merge_studies(paths):
    prices={s:{} for s in SYMBOLS};events={};hashes={};starts=[];ends=[]
    for root in paths:
        f=root/'filing-events.json';raw=f.read_bytes();doc=json.loads(raw);hashes[str(f)]=hashlib.sha256(raw).hexdigest()
        for e in doc['events']:
            prior=events.get(e['accession'])
            if prior and prior!=e:raise ValueError('Conflicting filing identity')
            events[e['accession']]=e
        for symbol in SYMBOLS:
            p=root/'prices'/f'{symbol}.json';raw=p.read_bytes();d=json.loads(raw);scope=d['scope']
            if scope['adjustment']!='splits':raise ValueError('Price basis mismatch')
            starts.append(scope['start']);ends.append(scope['end'])
            rows=validate_prices(d['response'],symbol,date.fromisoformat(scope['start']),date.fromisoformat(scope['end']))
            for r in rows:
                old=prices[symbol].get(r['date'])
                if old is not None and old!=r['close']:raise ValueError('Conflicting historical price vintages')
                prices[symbol][r['date']]=r['close']
            hashes[str(p)]=hashlib.sha256(raw).hexdigest()
    return prices,list(events.values()),hashes,min(starts),max(ends)


def cohort(outcomes,lo,hi):
    subset=[e for e in outcomes if e.get('entry','')>=lo and e.get('exit','')<=hi]
    trades,excluded=independent_trades(subset,lo)
    return {'summary':summarize(trades),'accessions':[e['accession'] for e in trades],'overlapExclusions':excluded,
            'start':lo,'end':hi,'interpretation':'retrospective exploratory cohort, not independent confirmation after seeing prior results'}


def render(result):
    def pct(v):return '—' if v is None else f'{100*v:.2f}%'
    out=['<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ORAKT · Historical factor audit</title><style>body{margin:0;background:#101921;color:#edf2f5;font:16px/1.8 system-ui}main{max-width:1100px;margin:auto;padding:24px}section{padding:24px 0;border-bottom:1px solid #344652}.notice{background:#26313e;border-left:3px solid #d9b85c;padding:16px}h2,a{color:#a4eac8}.scroll{overflow:auto}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #344652;font-size:14px}code{overflow-wrap:anywhere}</style><main><h1>ORAKT 历史因子扩展核验<br>Historical factor extension audit</h1><p class="notice">固定规则，未调参；真实价格回顾计算，不是当年已作出的预测。仅拆股复权价格收益，不含股息，费用是假设。新增经营变量仍属待验证候选，不证明因果或可交易 Alpha。<br>Fixed rules, no optimization. Retrospective price calculations, not forecasts made historically. Split-adjusted price returns exclude dividends; costs are assumed. New operating features remain candidates, not causal or tradable alpha.</p><section><h2>交易日覆盖 / Calendar coverage</h2><p>按 XNYS 常规交易日历逐日比较，缺失不会用后面的日期补位。库版本与日历源已留档，不含个股停牌判断。<br>Every scheduled XNYS session is checked; missing dates cannot compress a holding window. Library version/source retained; security-specific halts are not modeled.</p><div class="scroll"><table><tr><th>标的</th><th>实际范围</th><th>缺失交易日</th><th>非交易日记录</th></tr>']
    for s,c in result['calendarCoverage'].items():
        out.append('<tr><td>'+s+'</td><td>'+c['first']+' — '+c['last']+'</td><td>'+str(len(c['missing']))+'</td><td>'+str(len(c['offCalendar']))+'</td></tr>')
    out.append('</table></div><details><summary>查看缺失日期 / Missing dates</summary><pre>'+escape(json.dumps(result['calendarCoverage'],ensure_ascii=False,indent=2))+'</pre></details></section>')
    labels={'margin':'原合并毛利率 / Consolidated margin','margin_inventory':'毛利率＋库存约束 / Margin + inventory','subscription':'订阅毛利率 / Subscription margin'}
    for ticker,company in result['companies'].items():
        out.append('<section><h2>'+ticker+'</h2><p>财报事件 '+str(company['filingEvents'])+'；每条特征引用及缺口保留在结果文件。<br>Filing events and feature provenance retained.</p><div class="scroll"><table><tr><th>规则</th><th>区间</th><th>独立样本</th><th>事件均值（扣成本）</th><th>相对大盘</th><th>相对行业</th><th>大盘超额区间</th></tr>')
        for rule,study in company['rules'].items():
            for name,c in study['cohorts'].items():
                s=c['summary'];ci=s['marketExcess']['interval95']
                out.append('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in [labels[rule],name,s['independentTrades'],pct(s['netPriceReturn']['mean']),pct(s['marketExcess']['mean']),pct(s['sectorExcess']['mean']),'样本不足 / Small sample' if ci is None else ' — '.join(pct(x) for x in ci)])+'</tr>')
        out.append('</table></div><details><summary>特征与证据缺口 / Feature evidence audit</summary>')
        from collections import Counter
        for rule,study in company['rules'].items():
            counts=dict(Counter(e['state'] for e in study['events']))
            out.append('<h3>'+labels[rule]+'</h3><p>'+escape(json.dumps(counts,ensure_ascii=False))+'</p>')
            gaps=[{'accession':e['accession'],'state':e['state'],'feature':e.get('feature')} for e in study['events'] if e['state']=='feature_gap']
            if gaps:out.append('<pre style="white-space:pre-wrap">'+escape(json.dumps(gaps,ensure_ascii=False,indent=2))+'</pre>')
        out.append('</details></section>')
    out.append('<section><h2>使用限制 / Limitations</h2><p>持有二十个日历交易日，披露后的下一交易日收盘入场，往返成本二十五个基点；事件均值不是年化收益。旧历史区间为扩展诊断，不能因结果较好便与近期合并成“高胜率”。样本至少八个才展示区块重采样区间，尚未做多重检验调整。<br>Twenty scheduled-session hold, next-session close after disclosure, assumed twenty-five basis-point round-trip cost. Event means are not annualized. Earlier data is a retrospective diagnostic, not a way to manufacture a better recent hit rate. Block intervals require at least eight trades and are not multiple-testing adjusted.</p><p>同一公司多条规则复用事件，彼此不独立；库存标签不跨口径拼接；订阅毛利率不等同于纯人工智能推理收益。<br>Rules reuse events and are not independent replications. Inventory concepts are not spliced; subscription margins are not pure AI inference returns.</p></section></main></html>')
    return ''.join(out)


def run(studies,bulk,output,subscription=None,patches=None):
    if output.exists():raise ValueError('Preserve prior output')
    output.mkdir(parents=True)
    policy={**POLICY,'version':'calendar-extension/v1','calendar':'XNYS exchange_calendars pinned library',
            'addedRules':{'NKE':'positive consolidated margin AND same-concept inventory YoY growth <= revenue YoY growth',
                          'ADBE':'positive same-period subscription gross-margin YoY change'},
            'cohorts':{'earlier_2010_2019':['2010-01-01','2019-12-31'],'reference_2020_2023':['2020-01-01','2023-12-31'],'recent_2024_onward':['2024-01-01','2026-10-05']},
            'preregisteredHistorically':False,'validatedAlpha':False}
    write_json(output/'policy.json',policy)
    prices,events,hashes,start,end=merge_studies(studies)
    if patches:
        raw=patches.read_bytes();p=json.loads(raw);hashes[str(patches)]=hashlib.sha256(raw).hexdigest()
        if p['adjustment']!='splits':raise ValueError('Patch basis mismatch')
        from app.dossier_price_gap_repair import select_missing
        for symbol,rows in p['prices'].items():
            if symbol not in prices:raise ValueError('Unknown patch symbol')
            for day,row in rows.items():
                body=Path(row['archivePath']).read_bytes()
                if hashlib.sha256(body).hexdigest()!=row['archiveSha256']:raise ValueError('Patch archive changed')
                clean=select_missing(json.loads(body)['response'],symbol,day)
                if clean['close']!=row['close'] or not start<=day<=end:raise ValueError('Patch value/date mismatch')
                if day in prices[symbol] and prices[symbol][day]!=row['close']:raise ValueError('Patch conflicts with existing observation')
                prices[symbol][day]=row['close']
    originals={}
    if subscription:
        raw=subscription.read_bytes();originals=json.loads(raw)['filings'];hashes[str(subscription)]=hashlib.sha256(raw).hexdigest()
        for d in originals.values():
            if d['state']=='extracted' and hashlib.sha256(Path(d['sourcePath']).read_bytes()).hexdigest()!=d['sourceSha256']:
                raise ValueError('Original subscription filing changed')
    sessions,meta=calendar_sessions(start,end)
    result={'policy':policy,'inputHashes':hashes,'calendar':meta,'calendarCoverage':{},'companies':{},'published':False}
    write_json(output/'sessions.json',{'metadata':meta,'sessions':sessions})
    for s,rows in prices.items():result['calendarCoverage'][s]={'first':min(rows),'last':max(rows),'count':len(rows),'missing':sorted(set(sessions)-set(rows)),'offCalendar':sorted(set(rows)-set(sessions))}
    with zipfile.ZipFile(bulk/'companyfacts.zip') as z:
        for ticker,cik in CIKS.items():
            raw=z.read('CIK'+cik+'.json');facts=json.loads(raw);write_json(output/f'{ticker}-facts.json',facts)
            selected=sorted([e for e in events if e['ticker']==ticker and e['form']=='10-Q'],key=lambda e:e['filedAt'])
            rules={'margin':[],('margin_inventory' if ticker=='NKE' else 'subscription'):[]}
            for e in selected:
                f=margin_feature(facts,e)
                rules['margin'].append(evaluate_event(e,f,prices,sessions=sessions))
                if ticker=='NKE':
                    inv=inventory_feature(facts,e,f)
                    extra={**f,'inventory':inv}
                    if inv['state']!='available':extra['state']='inventory_pair_missing'
                    else:extra['positive']=f['positive'] and inv['pressure']<=0
                    name='margin_inventory'
                else:
                    extra=subscription_feature(facts,e);name='subscription'
                    original=originals.get(e['accession'])
                    if extra['state']!='available' and original and original['state']=='extracted':
                        adapted={'facts':{'us-gaap':{tag:{'units':{'USD':[r for r in original['rows'] if r['concept']==tag]}} for tag in ('SubscriptionRevenue','CostOfGoodsSoldSubscription')}}}
                        extra=subscription_feature(adapted,e)
                        extra['inlineSourceSha256']=original['sourceSha256']
                        extra['inlineSourcePath']=original['sourcePath']
                rules[name].append(evaluate_event(e,extra,prices,sessions=sessions))
            result['companies'][ticker]={'sourceMemberSha256':hashlib.sha256(raw).hexdigest(),'filingEvents':len(selected),'rules':{
                k:{'events':v,'cohorts':{label:cohort(v,*bounds) for label,bounds in policy['cohorts'].items()}} for k,v in rules.items()}}
    write_json(output/'result.json',result)
    (output/'readable.html').write_text(render(result),encoding='utf-8')
    print(json.dumps({t:{k:{c:st['summary']['independentTrades'] for c,st in v['cohorts'].items()} for k,v in d['rules'].items()} for t,d in result['companies'].items()}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--studies',type=Path,nargs='+',required=True)
    p.add_argument('--bulk',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--subscription',type=Path);p.add_argument('--patches',type=Path)
    a=p.parse_args();run(a.studies,a.bulk,a.output,a.subscription,a.patches)
