from app.dossier_market_readiness import market_readiness


def packet(observations=None):
    return {'ticker':'TEST','as_of_date':'2026-10-02', 'market_evidence':[
        {'id':'MARKET:EQ:TEST','observations':observations or [{'date':'2026-09-22','value':10}]},
        {'id':'MARKET:TD:SPY','observations':[{'date':'2026-09-22','value':20}]}]}


def test_stale_stock_never_becomes_current_price_or_alpha():
    r=market_readiness(packet())
    assert r['equityPriceState']=='stale'
    assert r['series'][0]['calendarLagDays']==10
    assert r['broadBenchmarkPresent'] is True
    assert r['sectorBenchmarkState']=='not_attested'
    assert r['eligibleForPredictiveBacktest'] is False
    assert r['valuationState']=='framework_only'


def test_recent_price_is_not_point_in_time_or_total_return_attestation():
    r=market_readiness(packet([{'date':'2026-10-02','value':10}]))
    assert r['equityPriceState']=='recent_observation_only'
    assert not r['series'][0]['pointInTimeVerified']
    assert not r['priceBasisComparable']
    assert not r['eligibleForPredictiveBacktest']


def test_invalid_future_and_duplicate_rows_are_explicit():
    r=market_readiness(packet([
        {'date':'2026-10-01','value':10}, {'date':'2026-10-01','value':11},
        {'date':'2026-10-03','value':20}, {'date':'bad','value':4},
        {'date':'2026-09-30','value':float('nan')}, {'date':'2026-09-30','value':True}]))
    s=r['series'][0]
    assert (s['count'],s['duplicateDates'],s['futureRowsExcluded'],s['invalidRows'])==(1,1,1,3)
    assert s['lastDate']=='2026-10-01'


def test_empty_and_unsorted_series():
    p=packet();p['market_evidence']=[]
    assert market_readiness(p)['equityPriceState']=='missing'
    r=market_readiness(packet([{'date':'2026-10-02','value':20},{'date':'2026-09-21','value':10}]))
    assert r['series'][0]['firstDate']=='2026-09-21'

