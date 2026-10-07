"""Carry reviewed legacy cash evidence into a new immutable writing packet."""
import copy
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from app.dossier_legacy_evidence import extract_table,reconcile,subtotal_checks
from app.historical_earnings_report import FilingText

ROW_LABELS={'opening':'期初现金及等价物','closing':'期末现金及等价物','netIncome':'净利润',
 'depreciation':'折旧、摊销及折溢价摊销','stockComp':'股票报酬费用','deferredTax':'递延所得税',
 'dispositionLoss':'资产处置损失','receivables':'应收账款变动','inventory':'存货变动',
 'currentAssets':'其他流动资产变动','otherAssets':'其他资产变动','payables':'应付账款变动',
 'deferredRevenue':'递延收入变动','otherLiabilities':'其他负债变动','operating':'经营现金净流量',
 'securityPurchases':'购买有价证券','securityMaturities':'有价证券到期回款','securitySales':'出售有价证券回款',
 'longInvestment':'购买其他长期投资','capex':'购置固定资产','intangibles':'购置无形资产',
 'otherInvesting':'其他投资活动','investing':'投资现金净流量','issuance':'发行普通股回款',
 'excessTax':'股票报酬相关超额税收利益','netShareSettle':'股权奖励净额结算支出',
 'financing':'融资现金净流量','netChange':'现金净变动','cashTaxes':'支付所得税净额'}


def render_cash_source(a):
    from html import escape
    from app.dossier_readable_bundle import bi
    periods=list(a['mapping']['columns'])
    parts=['<details><summary>'+bi('原始现金流完整分项及上年比较','Original cash-flow components and prior-period comparison')+'</summary><p>'+bi('以下为累计现金流，单位：百万美元。负值是原表现金流出或调节方向；没有独立汇率行不代表汇率影响为零。','Cumulative cash flows, USD millions. Negative values preserve original outflows or adjustments. No separate FX line does not mean zero currency effect.')+'</p><div class="table-wrap"><table><tr><th>'+bi('科目','Item')+'</th>'+''.join('<th>'+escape(p)+'</th>' for p in periods)+'</tr>']
    for key,values in a['facts'].items():
        label=next(iter(values.values()))['rawLabel']
        parts.append('<tr><td>'+bi(ROW_LABELS.get(key,label),label)+'</td>')
        for period in periods:
            f=values[period]
            parts.append('<td>'+format(Decimal(f['value'])/1000000,',.3f')+'<details><summary>'+bi('原表坐标','Source coordinates')+'</summary><code>'+escape(str(f['tableIndex'])+':'+str(f['rowIndex']))+'<br>'+escape(f['evidence_id'])+'</code></details></td>')
        parts.append('</tr>')
    return ''.join(parts)+'</table></div></details>'


def validate_attachment(packet,html):
    a=packet.get('verified_cash_source')
    if a is None:return None
    if a['ticker']!=packet['ticker'] or a['accession']!=packet['accession'] or a['sourceHash']!=packet['raw_sha256']:
        raise ValueError('Cash attachment identity mismatch')
    m=a['mapping'];p=FilingText();p.feed(html)
    if m['scaleEvidence'] not in p.clean():raise ValueError('Cash attachment unit context missing')
    facts=extract_table(html,packet['raw_sha256'],m)
    bridges={period:reconcile(facts,period,m.get('flowComponents',['operating','investing','financing','fx'])) for period in m['columns']}
    subtotals={period:subtotal_checks(facts,m['subtotalGroups'],period) for period in m['columns']}
    if facts!=a['facts'] or bridges!=a['cashReconciliations'] or subtotals!=a['subtotalChecks']:
        raise ValueError('Cash attachment does not reproduce original table')
    if any(x['state']!='matched' for x in bridges.values()) or any(x['state']!='matched' for cs in subtotals.values() for x in cs.values()):
        raise ValueError('Unreconciled cash attachment')
    if packet['period_end'] not in bridges or any(d>packet['period_end'] for d in bridges):
        raise ValueError('Cash attachment period mismatch')
    for period in bridges:
        values={Decimal(str(f['value'])) for f in packet['facts'] if f['concept']=='NetCashProvidedByUsedInOperatingActivities' and f['period_end']==period and f['unit']=='USD'}
        if values!={Decimal(facts['operating'][period]['value'])}:raise ValueError('Cash attachment conflicts with retained CFO')
    return a


def attach(source,supplement,cold_root,output):
    from app.company_history_dossier import write_json
    from app.review_frozen_dossier import load_frozen_packet
    from urllib.parse import urlsplit,unquote
    if output.exists():raise ValueError('Preserve existing source packet')
    original,raw=load_frozen_packet(source,cold_root)
    a_raw=supplement.read_bytes();a=json.loads(a_raw)
    if a['sourceFingerprint']!=original['fingerprint'] or a['reportGenerated'] is not False:
        raise ValueError('Prepared cash source parent mismatch')
    result=copy.deepcopy(original);packet=result['packet'];packet['verified_cash_source']=a
    base=(cold_root/'raw/sec/company-filings'/packet['ticker']).resolve()
    path=(base/packet['accession'].replace('-','')/unquote(urlsplit(packet['source_url']).path.rsplit('/',1)[-1])).resolve()
    if not path.is_relative_to(base):raise ValueError('Archive path escaped')
    validate_attachment(packet,path.read_bytes().decode('utf-8'))
    result['fingerprint']=hashlib.sha256(json.dumps({'version':result['version'],'packet':packet},sort_keys=True).encode()).hexdigest()
    result['continuation']={'parentSourceSha256':hashlib.sha256(raw).hexdigest(),'cashSourceSha256':hashlib.sha256(a_raw).hexdigest(),
                            'method':'same-filing original cash table; no new-date market observations'}
    write_json(output,result)
    return result
