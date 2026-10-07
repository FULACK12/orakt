"""Reproducible retrospective accounting-factor diagnostic, not validated alpha.

The event is SEC filing acceptance (NOT first earnings news). Exact-accession
facts avoid silently injecting later restated values into an older signal.
All prices share an explicitly split-only basis; distributions are excluded.
"""
import argparse
import bisect
import hashlib
import json
import math
import random
import zipfile
from datetime import date,datetime
from html import escape
from pathlib import Path
from statistics import fmean
from zoneinfo import ZoneInfo
from app.company_history_dossier import write_json
from app.dossier_study_evidence import CIKS,BENCHMARKS

REVENUE=('Revenues','SalesRevenueNet','RevenueFromContractWithCustomerExcludingAssessedTax')
POLICY={'version':'filing-gross-margin-pilot/v1','signal':'long only when same-quarter gross margin improved year over year; otherwise no entry',
        'threshold':0,'holdingObservedSessions':20,'roundTripCostBps':25,
        'trainingEnd':'2023-12-31','evaluationStart':'2024-01-01',
        'entry':'first SPY-observed session strictly AFTER SEC acceptance New York date; enter at close',
        'returnBasis':'split-adjusted PRICE return, excluding dividends and cash interest',
        'calendar':'SPY observation dates, not independently attested exchange calendar',
        'statistic':'unlevered long price return less assumed round-trip cost; compare separately to SPY and sector proxy price returns',
        'uncertainty':'circular event-block bootstrap, block length two, fixed seed, percentile interval; no interval below eight independent trades',
        'selection':'per company, evaluation trades cannot overlap; all excluded events retained',
        'scope':'Retrospective exploratory diagnostic; not a preregistered historical prediction or proof of causal alpha',
        'adbeProxy':'Consolidated gross margin, NOT subscription margin or isolated AI inference cost',
        'notTested':['inventory interaction','deferred revenue interaction','multivariate factor weights','total-return profitability','outcome-independent external replication']}


def margin_feature(facts,event):
    gaap=facts.get('facts',{}).get('us-gaap',{})
    end=date.fromisoformat(event['periodEnd'])
    def values(tags):
        grouped={}
        for tag in tags:
            for r in gaap.get(tag,{}).get('units',{}).get('USD',[]):
                if r.get('accn')!=event['accession'] or r.get('filed','9999')>event['filedAt']:continue
                try:
                    lo=date.fromisoformat(r['start']);hi=date.fromisoformat(r['end']);v=float(r['val'])
                except (KeyError,ValueError,TypeError):continue
                if not 70 <= (hi-lo).days <= 105 or not math.isfinite(v):continue
                if hi!=end and not 350 <= (end-hi).days <= 380:continue
                grouped.setdefault((lo,hi),[]).append((v,tag,r))
        return grouped
    rev=values(REVENUE);gross=values(('GrossProfit',))
    periods=[]
    for key in sorted(set(rev)&set(gross)):
        rv={x[0] for x in rev[key]};gv={x[0] for x in gross[key]}
        if len(rv)!=1 or len(gv)!=1 or next(iter(rv))<=0:continue
        periods.append({'start':str(key[0]),'end':str(key[1]),'revenue':next(iter(rv)),
                        'grossProfit':next(iter(gv)),
                        'margin':next(iter(gv))/next(iter(rv)),
                        'references':[{'concept':t,**r} for _,t,r in rev[key]+gross[key]]})
    now=[p for p in periods if p['end']==event['periodEnd']]
    before=[p for p in periods if p['end']!=event['periodEnd']]
    if len(now)!=1 or len(before)!=1:
        return {'state':'missing_or_ambiguous_same_accession_quarter_pair'}
    delta=now[0]['margin']-before[0]['margin']
    return {'state':'available','delta':delta,'positive':delta>0,'current':now[0],'prior':before[0]}


def evaluate_event(event,feature,prices,horizon=20,cost_bps=25,sessions=None):
    if horizon<1 or cost_bps<0:raise ValueError('Invalid experiment parameters')
    base={'accession':event['accession'],'acceptedAt':event.get('acceptedAt'),'filedAt':event['filedAt'],
          'periodEnd':event['periodEnd'],'feature':feature}
    if feature['state']!='available':return {**base,'state':'feature_gap'}
    raw=event.get('acceptedAt')
    if not raw:return {**base,'state':'release_time_missing'}
    stamp=datetime.fromisoformat(raw)
    if stamp.tzinfo is None:return {**base,'state':'release_time_missing'}
    signal_day=stamp.astimezone(ZoneInfo('America/New_York')).date().isoformat()
    days=sorted(prices['SPY']) if sessions is None else sessions
    if days!=sorted(set(days)):raise ValueError('Calendar sessions must be sorted and unique')
    idx=bisect.bisect_right(days,signal_day)
    if idx+horizon>=len(days):return {**base,'state':'forward_window_not_mature'}
    window=days[idx:idx+horizon+1];ticker=event['ticker'];sector=BENCHMARKS[ticker]['symbol']
    for symbol in (ticker,'SPY',sector):
        if any(d not in prices[symbol] or not math.isfinite(prices[symbol][d]) or prices[symbol][d]<=0 for d in window):
            return {**base,'state':'price_window_gap','missingSymbol':symbol}
    def ret(s):return prices[s][window[-1]]/prices[s][window[0]]-1
    raw_return=ret(ticker);net=raw_return-cost_bps/10000
    return {**base,'state':'observed','entry':window[0],'exit':window[-1],
            'grossPriceReturn':raw_return,'netPriceReturn':net,'marketPriceReturn':ret('SPY'),
            'sectorPriceReturn':ret(sector),'marketExcess':net-ret('SPY'),
            'sectorExcess':net-ret(sector),'signalDayNY':signal_day}


def independent_trades(events,evaluation_start):
    kept=[];exclusions=[];last_exit=''
    for e in sorted(events,key=lambda e:(e.get('entry',''),e['accession'])):
        if e['state']!='observed':continue
        if e['entry']<evaluation_start:continue
        if not e['feature']['positive']:continue
        if e['entry']<=last_exit:
            exclusions.append({'accession':e['accession'],'reason':'overlapping_holding_window'});continue
        kept.append(e);last_exit=e['exit']
    return kept,exclusions


def interval(values):
    if len(values)<8:return None
    rng=random.Random(1729);means=[];n=len(values)
    for _ in range(2000):
        draw=[]
        while len(draw)<n:
            start=rng.randrange(n);draw.extend((values[start],values[(start+1)%n]))
        means.append(fmean(draw[:n]))
    means.sort()
    return [means[49],means[1949]]


def summarize(trades):
    output={'independentTrades':len(trades),'eligibleForPredictiveBacktest':False,'validatedAlpha':False}
    for key in ('netPriceReturn','marketExcess','sectorExcess'):
        vals=[e[key] for e in trades]
        output[key]={'mean':fmean(vals) if vals else None,'positiveFraction':sum(v>0 for v in vals)/len(vals) if vals else None,
                     'interval95':interval(vals)}
    return output


def render(result):
    def pct(v):return '—' if v is None else f'{v*100:.2f}%'
    sections=['<section><h2>行情覆盖 / Price coverage</h2><p>请求范围与实际返回范围分开列示；已存档不等于完整覆盖。新数据为单独补充版本，原报告冻结证据未被覆盖。<br>Requested and observed coverage are distinct. Retention is not completeness; original report snapshots are unchanged.</p><table><tr><th>标的 / Symbol</th><th>实际开始 / First</th><th>实际截止 / Last</th><th>请求截止 / Requested end</th><th>条数 / Rows</th></tr>']
    for symbol,c in result['priceCoverage'].items():
        sections.append('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in [symbol,c['first'],c['last'],c['requestedEnd'],c['count']])+'</tr>')
    sections.append('</table></section>')
    for ticker,d in result['companies'].items():
        s=d['summary'];sections.append('<section><h2>'+ticker+'</h2><p>独立入场样本 / Independent entries: '+str(s['independentTrades'])+'</p><table><tr><th>指标 / Metric</th><th>事件均值 / Event mean</th><th>区块区间 / Block interval</th></tr>')
        for key,name in [('netPriceReturn','扣假设成本价格收益 / Net price return'),('marketExcess','相对 SPY / Excess vs SPY'),('sectorExcess','相对 '+BENCHMARKS[ticker]['symbol']+' / Sector excess')]:
            v=s[key];ci=v['interval95'];sections.append('<tr><td>'+name+'</td><td>'+pct(v['mean'])+'</td><td>'+('样本不足 / Insufficient sample' if ci is None else ' — '.join(pct(x) for x in ci))+'</td></tr>')
        sections.append('</table><p>行业基准 / Sector proxy: <a href="'+escape(BENCHMARKS[ticker]['source'],quote=True)+'">'+BENCHMARKS[ticker]['symbol']+'</a></p><details><summary>逐条事件和剔除原因 / Event audit</summary><table><tr><th>申报 / Filing</th><th>状态 / Status</th><th>样本用途 / Selection</th><th>入场 / Entry</th><th>退出 / Exit</th><th>毛利率同比差 / Margin delta</th></tr>')
        for e in d['events']:
            sections.append('<tr>'+''.join('<td>'+escape(str(x))+'</td>' for x in [e['accession'],e['state'],e['sampleStatus'],e.get('entry','—'),e.get('exit','—'),pct(e['feature'].get('delta'))])+'</tr>')
        sections.append('</table></details></section>')
    return '''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ORAKT · Factor experiment audit</title><style>body{background:#101921;color:#eaf0f4;font:16px/1.8 system-ui;margin:0}main{max-width:1080px;margin:auto;padding:24px}h1{font-size:32px}h2,a{color:#a4eac8}.notice{padding:18px;border-left:3px solid #d9b85c;background:#26313e}section{padding:24px 0;border-bottom:1px solid #52697b}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:10px;border-bottom:1px solid #334652;text-align:left}details{overflow:auto}code{overflow-wrap:anywhere}</style><main><h1>ORAKT 因子实测审计<br>Retrospective factor diagnostic</h1><p class="notice">实际行情计算，不是历史预测记录，也不是已验证 Alpha。仅使用拆股复权价格收益，不含股息；扣除的费用为假设而非实际成交。当前只检验合并毛利率信号，不代表完整多因子系统。<br>Observed-price calculation, not an ex-ante prediction or validated alpha. Split-only price returns exclude dividends; costs are assumed, not executed. Consolidated gross-margin signal only, not the complete multifactor design.</p><p>2020—2023 为开发区间，2024 起为按时间隔离的回顾检验；规则是在今天制定，不声称当时已登记。SEC 接收时间不是首次财报新闻时间，采用其后下一观测交易日收盘入场，持有二十个 SPY 观测交易日；行业与大盘分别比较。成本假设每次往返二十五个基点。交易日历尚未独立核验。<br>Development: 2020–2023; retrospective chronological evaluation: 2024 onward. This rule was defined today, not preregistered historically. Entry is the close of the next observed session after SEC acceptance, not first earnings news; holding period is twenty SPY-observed sessions. Assumed round-trip cost: twenty-five basis points. Exchange calendar is not independently verified.</p><p>下方为每次事件平均收益，不是年化收益或连续组合净值；样本不足时不显示置信区间。区间未控制所有研究尝试，不足以宣称统计显著的盈利能力。<br>Metrics are mean event returns, not annualized returns or continuous portfolio NAV. Small samples receive no confidence interval. Intervals do not adjust for all research trials and do not establish significant profitability.</p>'''+''.join(sections)+'<footer><p>ADBE 使用合并毛利率代理，并非订阅毛利率或纯 AI 因子。缺失数据和后续窗口不足均保留，不填造数据。<br>ADBE uses consolidated gross margin, not subscription margin or a pure AI factor. Missing and immature observations are retained as gaps.</p></footer></main></html>'


def run(study,bulk,output):
    if output.exists():raise ValueError('Preserve prior experiment output')
    output.mkdir(parents=True)
    # Freeze policy before reading outcomes, without falsely calling it historical preregistration.
    write_json(output/'policy.json',POLICY)
    events=json.loads((study/'filing-events.json').read_text(encoding='utf-8'))['events']
    prices={};hashes={};coverage={};scope=None
    for symbol in ('NKE','ADBE','SPY','XLY','IGV'):
        p=study/'prices'/f'{symbol}.json';raw=p.read_bytes();doc=json.loads(raw)
        if doc['scope']['adjustment']!='splits':raise ValueError('Return-basis mismatch')
        if scope is not None and scope!=doc['scope']:raise ValueError('Price request scopes differ')
        scope=doc['scope']
        from app.dossier_study_evidence import validate_prices
        clean=validate_prices(doc['response'],symbol,date.fromisoformat(scope['start']),date.fromisoformat(scope['end']))
        prices[symbol]={r['date']:r['close'] for r in clean}
        coverage[symbol]={'first':clean[0]['date'],'last':clean[-1]['date'],'requestedEnd':scope['end'],'count':len(clean)}
        hashes[str(p)]=hashlib.sha256(raw).hexdigest()
    result={'policy':POLICY,'priceSourceHashes':hashes,'priceCoverage':coverage,
            'filingEventsSha256':hashlib.sha256((study/'filing-events.json').read_bytes()).hexdigest(),'companies':{},'published':False}
    with zipfile.ZipFile(bulk/'companyfacts.zip') as z:
        for ticker,cik in CIKS.items():
            raw=z.read('CIK'+cik+'.json');facts=json.loads(raw)
            write_json(output/f'{ticker}-companyfacts.json',facts)
            selected=[e for e in events if e['ticker']==ticker and e['form']=='10-Q']
            outcomes=[evaluate_event(e,margin_feature(facts,e),prices) for e in selected]
            trades,exclusions=independent_trades(outcomes,POLICY['evaluationStart'])
            taken={e['accession'] for e in trades};overlap={e['accession'] for e in exclusions}
            for e in outcomes:
                e['sampleStatus']=('included_evaluation_trade' if e['accession'] in taken else
                    'excluded_overlap' if e['accession'] in overlap else e['state'] if e['state']!='observed' else
                    'development_window' if e['entry']<POLICY['evaluationStart'] else 'no_long_signal')
            result['companies'][ticker]={'sourceMemberSha256':hashlib.sha256(raw).hexdigest(),
                'events':outcomes,'independentTrades':[e['accession'] for e in trades],
                'exclusions':exclusions,'summary':summarize(trades)}
    write_json(output/'result.json',result)
    (output/'readable.html').write_text(render(result),encoding='utf-8')
    print(json.dumps({t:d['summary'] for t,d in result['companies'].items()}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('study','bulk','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();run(a.study,a.bulk,a.output)
