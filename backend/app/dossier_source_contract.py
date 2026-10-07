"""Source-attested scope hints and narrow bilingual guards, not semantic proof."""
import re
from datetime import date

TERMS = [
    ('Net revenue', '净营收', 'Revenue, not net income or profit.'),
    ('shipping below consumption', '出货低于终端消耗', 'Channel inventory adjustment; consumption is not total market demand.'),
    ('Corporate revenues', '总部／未分配项收入', 'A reporting category, NOT total company revenue.'),
    ('Converse other revenues', 'Converse 其他收入', 'Only other revenues, NOT all Converse revenue.'),
    ('Global Brand Divisions', '全球品牌部门', 'Not consolidated company revenue.'),
    ('Deferred revenue', '递延收入', 'Not yet recognized revenue; do not call it profit, cash flow or sales already earned.'),
    ('currency-neutral', '剔除汇率影响', 'Do not attribute a currency-neutral increase to currency gains.'),
    ('ASP', '平均售价', 'Not average profit, and not total revenue.'),
    ('North America', '北美', 'Do not generalize this region to the whole company.'),
    ('Greater China', '大中华区', 'Not APAC, Asia-Pacific or all international business.'),
    ('EMEA', '欧洲、中东及非洲', 'Not Europe alone.'),
    ('Business Professionals & Consumers', '商业专业人士与消费者', 'A customer group, not all company customers.'),
    ('Creative & Marketing Professionals', '创意与营销专业人士', 'A customer group, not all company customers.'),
    ('AI inferencing costs', '人工智能推理成本', 'Subscription service delivery cost, not necessarily model training cost.'),
    ('AI training costs', '人工智能训练成本', 'Development cost; do not combine with inference cost without consistent accounting scope.'),
    ('fair value of long-term debt', '长期债务公允价值', 'Not principal outstanding or cash repayment; changes do not alone prove deleveraging.'),
]


def source_contract(passage, packet=None):
    text=passage['text'];packet=packet or {}
    terms=[{'sourceTerm':en,'chinese':zh,'scope':scope} for en,zh,scope in TERMS if re.search(re.escape(en),text,re.I)]
    periods=re.findall(r'(?:FIRST|SECOND|THIRD|FOURTH) QUARTER OF FISCAL \d{4}(?: COMPARED TO (?:FIRST|SECOND|THIRD|FOURTH) QUARTER OF FISCAL \d{4})?',text,re.I)
    periods+=re.findall(r'(?:first|second|third|fourth) quarter of fiscal \d{4}',text,re.I)
    return {'passageId':passage.get('id'),'filingDate':packet.get('as_of_date'),
            'filingPeriodEnd':packet.get('period_end'),
            'explicitFiscalLabels':list(dict.fromkeys(periods)),
            'terms':terms,'eventTiming':event_timing(text,packet),
            'scopeRule':'Only explicit paragraph scope is known. Filing date is not fiscal quarter. Do not infer omitted geographic/segment context from nearby paragraphs.'}


def event_timing(text,packet):
    """Keep month precision. Never invent a day or backdate a later plan."""
    months={name.lower():i for i,name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
    result=[]
    for m in re.finditer(r'\bIn ('+'|'.join(months)+r') (\d{4}),.{0,80}\b(?:announced|approved|entered|reapproved)\b',text,re.I):
        month=f'{int(m[2]):04d}-{months[m[1].lower()]:02d}'
        period=packet.get('period_end','')[:7];filing=packet.get('as_of_date','')[:7]
        result.append({'eventMonth':month,'precision':'month','afterPeriodEnd':bool(period and month>period),
            'afterFilingMonth':bool(filing and month>filing),'rule':'Announcement/authorization is not measured operating performance. Exact event day is unverified.'})
    return result


def guard_extracted_scope(parsed, passage):
    """Block known regressions; passing still requires independent content review."""
    source=passage['text'].lower();zh=parsed.disclosed_fact.zh;en=parsed.disclosed_fact.en
    if 'shipping below consumption' in source and re.search(r'发货量?低于需求|出货量?低于需求',zh):
        raise ValueError('Preserve channel consumption, not generalized demand')
    if 'corporate revenues' in source:
        if re.search(r'公司(?:整体|总体|总)?收入(?:主要|由|包括|包含|来自)',zh):
            raise ValueError('Corporate revenues is a reporting category: use 总部／未分配项收入, not company revenue')
        if re.search(r'(?:total|overall) company revenue',en,re.I):
            raise ValueError('Do not broaden Corporate revenues to total company revenue')
    if 'converse other revenues' in source:
        if re.search(r'(?:Converse|匡威)(?:的)?(?:主要|整体|全部)?收入',zh,re.I):
            raise ValueError('Preserve Converse OTHER revenues scope')
    if 'deferred revenue' in source:
        if '递延收入' not in zh or re.search(r'递延收入(?:已|均已|就是|即是)(?:确认|实现|营业收入|利润)',zh):
            raise ValueError('Preserve deferred revenue recognition distinction')
    regions=[('north america',r'北美|North America'),('greater china',r'大中华|Greater China'),('emea',r'EMEA|欧洲、中东及非洲'),('asia pacific',r'亚太|APAC|Asia.Pacific')]
    for original,pattern in regions:
        if original not in source and re.search(pattern,zh+' '+en,re.I):
            raise ValueError('Geographic scope not in supplied paragraph: '+original)
    if 'currency-neutral' in source and re.search(r'currency.neutral.*(?:driven by|due to) (?:foreign exchange|currency) gains',en,re.I):
        raise ValueError('Currency-neutral growth cannot be explained by currency gains')
    if re.search(r'convert.{0,25}fixed interest rates.{0,45}floating interest rates',source):
        if re.search(r'浮动.{0,12}(?:转为|转换为|变为)固定',zh) or re.search(r'convert.{0,20}floating.{0,30}(?:to|into) fixed',en,re.I):
            raise ValueError('Interest swap direction reversed: source says fixed to floating')


def qualitative_schema(schema):
    # Runtime validation remains authoritative; the schema deliberately uses
    # only grammar primitives already supported by the installed local model.
    schema['description']='Qualitative bilingual extraction. Original numbers remain in the source quote. Do not generate numerical claims.'
    return schema
