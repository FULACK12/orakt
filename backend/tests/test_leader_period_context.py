from app.dossier_compact_writer import period_hints


def test_masking_keeps_source_period_metadata():
    h=period_hints('Net sales during 2008 increased 35% from 2007.',{'period_end':'2009-09-26','as_of_date':'2009-10-27'})
    assert h['sourceYears']==['2007','2008']
    assert h['explicitOpeningPeriod']=='Net sales during 2008'
    assert h['reportPeriodEnd']=='2009-09-26'


def test_fiscal_year_not_inferred_from_calendar_end():
    h=period_hints('In fiscal 2027, revenue increased.',{'period_end':'2026-07-26','as_of_date':'2026-08-28'})
    assert h['sourceYears']==['2027']
    assert 'Calendar year alone' in h['rule']
