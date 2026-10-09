import copy
import pytest
from app.dossier_earnings_context import add_context, extract_contexts, validate_context, earnings_observations
from app.dossier_evidence_selection import select

TEXT='''Notes before this section.
Other Income (Expense), Net
Components of OI&E were as follows (in millions):
Three Months Ended Six Months Ended
June 30, June 30,
2025 2026 2025 2026
Gain (loss) on equity securities, net 12 99 20 130
Other income (expense), net 10 98 21 132
Note 8. Acquisitions
Do not include this unrelated section.
In November 2024, the FASB issued Accounting Standards Update (ASU) 2024-03 to improve expense disclosures. Upon adoption, more expense details are required. The standard is effective for our 2027 annual period, and interim periods beginning in 2028, with early adoption permitted. We are assessing adoption timing.
In September 2025, a separate standard is discussed.
'''


def test_exact_earnings_table_and_effective_dates_are_preserved():
    rows=extract_contexts(TEXT,'hash')
    assert len(rows)==2
    assert '2025 2026 2025 2026' in rows[0]['text']
    assert 'Gain (loss) on equity' in rows[0]['text']
    assert 'Acquisitions' not in rows[0]['text']
    assert '2027 annual' in rows[1]['text'] and '2028' in rows[1]['text']
    assert 'assessing adoption timing' in rows[1]['text']
    assert 'separate standard' not in rows[1]['text']
    assert all(TEXT[p['start']:p['end']]==p['text'] for p in rows)


def test_selection_keeps_material_non_operating_context_and_rejects_tampering():
    packet={'raw_sha256':'hash','chapter_passages':{'financial':[{'id':'old','text':'Sales commissions are expensed.'}]}}
    add_context(packet,TEXT);validate_context(packet,TEXT)
    selected,trace=select(packet['chapter_passages']['financial'],'financial')
    assert selected[0]['contextRole']=='non_operating_earnings_bridge'
    assert trace[0]['reason']=='non_operating_earnings_bridge'
    assert selected[1]['contextRole']=='accounting_effective_date'
    assert '2027 annual' in selected[1]['text']
    bad=copy.deepcopy(packet);bad['chapter_passages']['financial'][1]['text']+=' invented'
    with pytest.raises(ValueError,match='differs'):validate_context(bad,TEXT)


def test_idempotence_and_unrelated_text():
    packet={'raw_sha256':'hash','chapter_passages':{}}
    add_context(packet,TEXT);before=copy.deepcopy(packet);add_context(packet,TEXT)
    assert packet==before
    assert extract_contexts('Revenue increased. No such section.','hash')==[]


def test_earnings_columns_keep_quarter_and_half_year_separate():
    packet={'raw_sha256':'hash','period_end':'2026-06-30','chapter_passages':{}}
    add_context(packet,TEXT.replace('12 99 20 130','12 9 20 130'))
    rows=earnings_observations(packet)
    assert len(rows)==4
    assert rows[0]['periodType']=='quarter' and rows[0]['direction']=='decrease'
    assert rows[1]['periodType']=='half_year' and rows[1]['direction']=='increase'
    assert rows[0]['concept']=='equity_security_gains'
    assert rows[2]['concept']=='other_income_net'


@pytest.mark.parametrize('old,new',[
    ('2025 2026 2025 2026','2026 2025 2026 2025'),
    ('June 30, June 30,','June 30, December 31,'),
    ('Three Months Ended Six Months Ended','Six Months Ended Three Months Ended')])
def test_unknown_earnings_headers_never_guessed(old,new):
    packet={'raw_sha256':'hash','period_end':'2026-06-30','chapter_passages':{}}
    add_context(packet,TEXT.replace(old,new))
    assert earnings_observations(packet)==[]
