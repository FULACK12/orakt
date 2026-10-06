import pytest
from app.report_translation_batch import protect_numbers, restore_numbers, check_translation


def test_protected_values_roundtrip_and_order():
    original = "营收940.36亿美元，2025-08-01；FACT:8003。"
    masked, values = protect_numbers(original)
    assert "940.36" not in masked
    translated = "Revenue __ORAKT_N0__ hundred million USD; __ORAKT_N1__-__ORAKT_N2__-__ORAKT_N3__; FACT:__ORAKT_N4__."
    restored = restore_numbers(translated, values)
    check_translation(original, restored)
    assert "940.36 hundred million USD" in restored


def test_missing_duplicated_or_reinterpreted_values_fail():
    with pytest.raises(ValueError):
        restore_numbers("__ORAKT_N0__ __ORAKT_N0__", ["10"])
    with pytest.raises(ValueError):
        check_translation("金额940.36亿美元", "USD 94.036 billion")
    with pytest.raises(ValueError):
        check_translation("中文", "中文")


def test_company_name_never_guessed_by_translation_model():
    masked,values=protect_numbers('沪电股份（002463）营收上升',['沪电股份'])
    assert '沪电股份' not in masked and '002463' not in masked
    target=restore_numbers('__ORAKT_N0__ (__ORAKT_N1__) revenue increased',values)
    check_translation('沪电股份（002463）营收上升',target,['沪电股份'])
    with pytest.raises(ValueError,match='identity'):
        check_translation('沪电股份（002463）营收上升','Shanghai Electric (002463) revenue increased',['沪电股份'])
