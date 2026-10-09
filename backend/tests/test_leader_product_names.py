from app.dossier_accounting_checks import disclosed_product_terms


def test_source_attested_microsoft_names_not_numeric_claims():
    names=disclosed_product_terms([{'text':'Microsoft 365 and Office 365; Dynamics 365. E5 adoption increased in 2026 by 17%.'}])
    assert set(names)=={'Microsoft 365','Office 365','Dynamics 365','E5'}
    assert '2026' not in names and '17' not in names


def test_no_names_imported_into_older_filings():
    assert disclosed_product_terms([{'text':'Microsoft Windows products; net income in 1994.'}])==[]
    assert disclosed_product_terms([{'text':'Section E5 and footnote 365.'}])==[]
