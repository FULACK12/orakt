"""Narrow Inline XBRL monetary parser; unsupported transforms fail closed.

Extracts original context periods/dimensions, scale and sign rather than guessing
column positions from flattened filing prose. This is not a full XBRL processor.
"""
from html.parser import HTMLParser
from decimal import Decimal, InvalidOperation
import re


class InlineFacts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.contexts={};self.units={};self.facts=[];self.ctx=None;self.unit=None
        self.capture=None;self.active=[];self.exclude=0

    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='xbrli:context':self.ctx={'id':a.get('id'),'dimensions':{}}
        elif tag=='xbrli:unit':self.unit={'id':a.get('id'),'measures':[]}
        elif tag=='xbrldi:typedmember' and self.ctx is not None:self.ctx['unsupported']=True
        elif tag in {'xbrli:startdate','xbrli:enddate','xbrli:instant','xbrldi:explicitmember','xbrli:measure'}:
            self.capture=(tag,a,[])
        elif tag=='ix:nonfraction':self.active.append((a,[]))
        elif tag=='ix:exclude':self.exclude+=1

    def handle_data(self,data):
        if self.capture:self.capture[2].append(data)
        if not self.exclude:
            for _,text in self.active:text.append(data)

    def handle_endtag(self,tag):
        if self.capture and tag==self.capture[0]:
            _,attrs,parts=self.capture;value=''.join(parts).strip();self.capture=None
            if tag=='xbrli:measure' and self.unit is not None:self.unit['measures'].append(value)
            elif self.ctx is not None:
                if tag=='xbrldi:explicitmember':self.ctx['dimensions'][attrs.get('dimension','')]=value
                else:self.ctx[tag.split(':')[1]]=value
        if tag=='xbrli:context' and self.ctx is not None:self.contexts[self.ctx['id']]=self.ctx;self.ctx=None
        elif tag=='xbrli:unit' and self.unit is not None:self.units[self.unit['id']]=self.unit;self.unit=None
        elif tag=='ix:nonfraction' and self.active:self.facts.append(self.active.pop())
        elif tag=='ix:exclude':self.exclude=max(0,self.exclude-1)


def monetary_facts(html,*,filed_at,source_url):
    p=InlineFacts();p.feed(html);result=[];skipped=0
    for a,parts in p.facts:
        ctx=p.contexts.get(a.get('contextref'));unit=p.units.get(a.get('unitref'))
        if not ctx or ctx.get('unsupported') or not unit or unit['measures']!=['iso4217:USD'] or a.get('xsi:nil') in {'true','1'}:
            skipped+=1;continue
        transform=a.get('format','').split(':')[-1]
        raw=''.join(parts).strip().replace('\u00a0','')
        if transform in {'zerodash','fixed-zero'} and raw in {'—','–','-'}:raw='0'
        elif transform in {'num-dot-decimal','numdotdecimal',''}:raw=raw.replace(',','').replace(' ','')
        else:skipped+=1;continue
        if not re.fullmatch(r'\d+(?:\.\d+)?',raw):skipped+=1;continue
        try:
            scale=int(a.get('scale','0'))
            if abs(scale)>20 or a.get('sign','') not in {'','-'}:raise ValueError('Unsupported scale/sign')
            value=Decimal(raw)*(Decimal(10)**scale)*(-1 if a.get('sign')=='-' else 1)
        except (InvalidOperation,ValueError):skipped+=1;continue
        identifier=a.get('id','')
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*',identifier):skipped+=1;continue
        concept=a.get('name','').split(':')[-1]
        # Keep dimensional totals distinct from the consolidated concept.
        dimension=';'.join(f'{k}={v}' for k,v in sorted(ctx['dimensions'].items()))
        result.append({'evidence_id':f'IX:{identifier}','concept':concept+(f' [{dimension}]' if dimension else ''),'base_concept':concept,'dimensions':ctx['dimensions'],
                       'value':str(value),'unit':'USD','period_start':ctx.get('startdate'),'period_end':ctx.get('enddate') or ctx.get('instant'),
                       'filed_at':filed_at,'source_url':source_url+'#'+identifier})
    return result,{'monetaryFacts':len(result),'unsupportedOrNonMonetaryFacts':skipped,'scope':'USD monetary nonFraction facts with supported transformations only'}
