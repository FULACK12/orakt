"""Deterministic, same-filing comparisons. No model arithmetic or future data."""
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256


def period_type(fact):
    if not fact.get("period_start"):
        return "instant"
    days=(date.fromisoformat(fact["period_end"])-date.fromisoformat(fact["period_start"])).days+1
    for lower,upper,label in [(70,110,"quarter"),(165,200,"six_month_cumulative"),(250,295,"nine_month_cumulative"),(345,385,"annual")]:
        if lower<=days<=upper:return label
    return "other_duration"


def _number(v):
    value=Decimal(str(v))
    if not value.is_finite():raise ValueError("Nonfinite financial value")
    return value


def comparison(key,current,previous,basis):
    a,b=_number(current["value"]),_number(previous["value"])
    stable_key=key+'|'+current['unit']+'|'+str(current.get('period_start'))+'|'+current['period_end']
    return {"id":'CMP:'+sha256(stable_key.encode()).hexdigest()[:12],"concept":current["concept"],"unit":current["unit"],"periodType":period_type(current),"comparisonBasis":basis,
            "current":current,"previous":previous,"change":str(a-b),
            "changePercent":str((a/b-1)*100) if b>0 else None,
            "direction":"increase" if a>b else "decrease" if a<b else "unchanged",
            "evidence_refs":list(dict.fromkeys([*previous.get("evidence_refs",[previous["evidence_id"]]),*current.get("evidence_refs",[current["evidence_id"]])]))}


def build_ledger(packet):
    cutoff=packet["as_of_date"];end=packet["period_end"]
    grouped=defaultdict(list);problems=[]
    for fact in packet["facts"]:
        if fact.get("filed_at",cutoff)>cutoff or fact["period_end"]>end:
            problems.append({"id":fact["evidence_id"],"reason":"after_cutoff"});continue
        try:
            _number(fact["value"]);kind=period_type(fact)
        except (InvalidOperation,ValueError,TypeError,KeyError):
            problems.append({"id":fact.get("evidence_id"),"reason":"invalid_value_or_period"});continue
        grouped[(fact["concept"],fact["unit"],fact.get("period_start"),fact["period_end"])].append(fact)
    clean=[]
    for rows in grouped.values():
        if len({_number(r["value"]) for r in rows})>1:
            problems.append({"ids":[r["evidence_id"] for r in rows],"reason":"conflicting_same_period_values"});continue
        clean.append(rows[0])
    result=[]
    for current in sorted(clean,key=lambda f:(f["concept"],f.get("period_start") or "")):
        if current["period_end"]!=end:continue
        kind=period_type(current)
        if kind=="other_duration":continue
        peers=[r for r in clean if r["concept"]==current["concept"] and r["unit"]==current["unit"] and r["period_end"]<end and period_type(r)==kind]
        if kind!="instant":
            # A prior quarter is not a YoY comparator. Match both boundaries,
            # allowing fiscal week calendars, but not quarter-vs-YTD mixing.
            peers=[r for r in peers if 350<=(date.fromisoformat(end)-date.fromisoformat(r["period_end"])).days<=380 and 350<=(date.fromisoformat(current["period_start"])-date.fromisoformat(r["period_start"])).days<=380 and abs((date.fromisoformat(current["period_end"])-date.fromisoformat(current["period_start"])).days-(date.fromisoformat(r["period_end"])-date.fromisoformat(r["period_start"])).days)<=14]
        if not peers:continue
        previous=max(peers,key=lambda f:f["period_end"])
        result.append(comparison(f"CMP:{current['concept']}:{kind}",current,previous,"prior_reported_balance" if kind=="instant" else "same_duration_year_over_year"))
    # Simplified FCF is a derived analyst measure, not a company non-GAAP metric.
    cfo=[r for r in result if r["concept"]=="NetCashProvidedByUsedInOperatingActivities"]
    for cash in cfo:
        cap=next((r for r in result if r["concept"]=="PaymentsToAcquirePropertyPlantAndEquipment" and r["unit"]==cash["unit"] and all(r[k].get("period_start")==cash[k].get("period_start") and r[k]["period_end"]==cash[k]["period_end"] for k in ["current","previous"])),None)
        if not cap:continue
        legs=[]
        for k in ["current","previous"]:
            legs.append({**cash[k],"concept":"SimplifiedFreeCashFlow","value":str(_number(cash[k]["value"])-_number(cap[k]["value"])),"evidence_refs":[cash[k]["evidence_id"],cap[k]["evidence_id"]]})
        derived=comparison(f"CMP:SimplifiedFreeCashFlow:{cash['periodType']}",*legs,cash["comparisonBasis"])
        derived["formula"]="Operating cash flow minus payments to acquire property, plant and equipment; matching periods only."
        result.append(derived)
    return {"version":"financial-period-ledger/v1","comparisons":result,"excluded":problems,
            "accountingRules":["Cash flow duration is cumulative when the source period exceeds a quarter; do not call it quarterly cash flow.","Capital expenditure is an investing cash outflow; it does not directly reduce operating cash flow.","A positive balance change or increasing expenditure does not by itself mean operating improvement.","Statements of causation require a cash-flow bridge or separate evidence; these comparisons establish arithmetic only."]}
