from datetime import date
from app.sec_bulk_import import partition_variants

def row(start, value):
    return dict(ticker='TEST',taxonomy='us-gaap',concept='Revenues',unit='USD',period_end=date(2020,6,30),filed_at=date(2020,8,1),accession_number='test',period_start=start,value=value)

def test_quarter_ytd_never_collapse():
    safe, ambiguous=partition_variants([row(date(2020,1,1),20),row(date(2020,4,1),12)])
    assert safe == [] and ambiguous == 2

def test_exact_duplicates_and_conflicting_values():
    assert len(partition_variants([row(None,20),row(None,20)])[0]) == 1
    assert partition_variants([row(None,20),row(None,21)])[0] == []
