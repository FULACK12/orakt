from types import SimpleNamespace as NS
import pytest
from app.dossier_compact_writer import check_source_scope


def section(zh='', en='', claim=None):
    return NS(analysis=NS(zh=zh,en=en),evidenceGaps=NS(zh='',en=''),validationPlan=NS(zh='',en=''),
              grounded_claims=[] if claim is None else [NS(passage_id='p',statement=NS(zh=claim,en=''))])


VIEW={'numbersRedacted':True,'passages':[{'id':'p','originalContainsQuantities':True,'qualitative_view':'Mac net sales increased due to higher net sales of laptops.'}]}


@pytest.mark.parametrize('zh,en',[('公司未披露具体金额。',''),('','The selected excerpts do not provide specific figures.')])
def test_masked_input_is_not_absent_disclosure(zh,en):
    with pytest.raises(ValueError,match='masking'):
        check_source_scope(section(zh,en),VIEW)


def test_sales_value_is_not_unit_volume():
    with pytest.raises(ValueError,match='unit volume'):
        check_source_scope(section(claim='笔记本电脑销量增长。'),VIEW)
    check_source_scope(section(claim='笔记本电脑销售额增长。'),VIEW)


def test_does_not_block_real_causal_uncertainty():
    check_source_scope(section('原文披露金额，但仍需独立渠道数据验证终端需求。','The original supplies quantities; independent channel evidence remains necessary.'),VIEW)


@pytest.mark.parametrize('field,zh,en',[
    ('analysis','关联方销售数据被遮蔽，仅提及区间。',''),
    ('counterEvidence','','Masked related-party sales amounts may conceal over-reliance.'),
    ('mechanism','','Related-party sales data is masked.'),
])
def test_prompt_masking_cannot_become_issuer_concealment(field,zh,en):
    s=section();setattr(s,field,NS(zh=zh,en=en))
    with pytest.raises(ValueError,match='masking'):
        check_source_scope(s,VIEW)


def test_claim_statements_are_checked_but_original_quotes_are_not_reinterpreted():
    with pytest.raises(ValueError,match='masking'):
        check_source_scope(section(claim='关联交易金额被隐藏。'),VIEW)
    check_source_scope(section('原文金额并非被遮蔽，仍需核对交易范围。',
        'Original amounts are not masked; transaction scope still needs verification.'),VIEW)


def test_concealment_regression_only_applies_to_masked_quantitative_input():
    check_source_scope(section('金额被遮蔽。',''),{**VIEW,'numbersRedacted':False})
