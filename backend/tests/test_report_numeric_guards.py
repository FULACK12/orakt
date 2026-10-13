from app.report_numeric_guards import check, money

PID='PASSAGE:0123456789abcdef'


def fixture(zh='',en='',source=''):
    return ({'chapter_passages':{'financial':[{'id':PID,'text':source}]}},
            [{'chapter':'financial','section':{'analysis':{'zh':zh+' ['+PID+']','en':en+' ['+PID+']'}}}])


def codes(args):return {f['code'] for f in check(*args)}


def test_bilingual_scale_normalization_and_false_positive_boundary():
    assert money('155.43亿美元','zh')[0][1]==money('$15.543 billion','en')[0][1]
    assert not check(*fixture('155.43亿美元','$15.543 billion'))
    assert 'bilingual_money_scale' in codes(fixture('155.43亿美元','$155.43 billion'))
    # Additional valid explanation in English alone is not a scale error.
    assert not check(*fixture('没有量化结论','$4 billion'))
    assert not check(*fixture('40亿美元和400亿美元','$4 billion and $40 billion'))


TABLE='Six Months Ended\nJune 30\n2026 2025\n(Millions of dollars)\nNet cash provided included cash payments:\nIncome taxes 4,539 4,136\n'


def test_cash_tax_arithmetic_exact_units_periods_and_cash_scope():
    text='The first half of 2026 had income tax payments of $4,539 million, up $393 million from 2025.'
    args=fixture('2026年上半年所得税支付4539百万美元，较2025年增加393百万美元。',text,TABLE)
    findings=check(*args)
    assert len(findings)==2 and {f['expected'] for f in findings}=={'403'}
    assert all(f['sourceIds']==[PID] for f in findings)
    assert not check(*fixture('',text.replace('393','403'),TABLE))
    assert not check(*fixture('',text,TABLE.replace('cash payments','tax expense')))
    assert not check(*fixture('',text,TABLE.replace('2026 2025','2025 2026')))
    assert not check(*fixture('',text,TABLE.replace('Millions of dollars','Billions of dollars')))
    assert not check(*fixture('',text.replace('first half','second quarter'),TABLE))
    assert not check(*fixture('',text,TABLE+'Income taxes 100 90\n'))


def test_negative_prepaid_row_does_not_reverse_direction():
    row='Decrease (increase) in prepaid expenses and other current assets ( 878 ) 214'
    assert 'working_capital_sign_direction' in codes(fixture('预付费用减少878百万美元','',row))
    assert not check(*fixture('预付费用增加878百万美元','',row))
    assert not check(*fixture('预付费用减少878百万美元','',row.replace('( 878 )','878')))


def test_rounded_expense_endpoints_not_used_for_exact_arithmetic():
    assert not check(*fixture('', 'Tax expense increased $2.8 billion from $1.6 billion to $4.5 billion.',TABLE))


def test_signed_cash_directions_not_outflow_magnitudes_or_hypotheses():
    source='Six Months Ended\nJune 30\n2026 2025\n(Millions of dollars)\nNet Cash Used for Investing Activities ( 7,266 ) ( 9,050 )\nNet Cash Provided by (Used for) Financing Activities ( 15,543 ) ( 7,649 )\n'
    p,d=fixture('投资活动现金流同比减少。融资活动现金流同比改善。',
                'Investing cash flow declined. Financing cash flow improved.',source)
    p['period_end']='2026-06-30'
    assert len(check(p,d))==4 and {f['code'] for f in check(p,d)}=={'signed_cash_flow_direction'}
    for zh,en in [('投资活动现金净流出减少。','Cash used in investing declined.'),
                  ('如果融资活动现金流改善，则进一步核查。','If financing cash flow improved, check funding.'),
                  ('投资活动现金流增加。融资活动现金流减少。','Investing cash flow increased. Financing cash flow decreased.')]:
        _,d=fixture(zh,en,source);assert not check(p,d)
    p['period_end']='2025-06-30';assert not check(p,d)
