"""Locked, issuer-grouped holdout and conservative eligibility assessment.

An evaluation result never enables production approval. Empty/adjusted/synthetic
holdouts cannot establish safety. All thresholds are fixed before evaluation.
"""
from collections import Counter
from app.report_usage import digest

POLICY = {'minimumIndependentReports': 300, 'maxSevereMissUpper95': 0.01,
          'maxFalseBlockRate': 0.05, 'maxRepairRegressionRate': 0.0,
          'requiredStrata': ['us_annual_historical', 'us_quarter_historical',
                             'us_annual_recent', 'us_quarter_recent',
                             'china_annual', 'china_quarter', 'news_chain']}


def split(issuer):
    # Group all years, amendments and revisions of an issuer into one split.
    return 'holdout' if int(digest(issuer.upper())[:8], 16) % 5 == 0 else 'development'


def evaluate(manifest, results):
    failures = []
    expected = {c['id']: c for c in manifest['cases'] if c['split'] == 'holdout'}
    if len(expected) != sum(c['split'] == 'holdout' for c in manifest['cases']):
        failures.append('duplicate_case_ids')
    if manifest.get('rulesFrozenBeforeHoldout') is not True:
        failures.append('holdout_not_locked_before_tuning')
    if not manifest.get('rulesetSha256'):
        failures.append('missing_ruleset_hash')
    training_groups = {c.get('groupId') for c in manifest['cases'] if c['split'] != 'holdout' or c.get('usedForTuning')}
    if training_groups & {c.get('groupId') for c in expected.values()}:
        failures.append('issuer_leakage_from_development')
    rows = {r['id']: r for r in results}
    if len(rows) != len(results) or set(rows) != set(expected):
        failures.append('missing_duplicate_or_unexpected_results')
    valid = []
    for key, case in expected.items():
        r = rows.get(key, {})
        if (case.get('labelStatus') != 'independently_adjudicated' or case.get('usedForTuning') is not False
                or case.get('synthetic') is not False or r.get('caseSha256') != digest(case)
                or r.get('rulesetSha256') != manifest.get('rulesetSha256')
                or not all(isinstance(r.get(k), bool) for k in ('severeErrorPresent', 'severeErrorDetected', 'correctContent', 'blocked', 'repairAttempted', 'repairIntroducedError'))):
            failures.append('unqualified_case:' + key); continue
        valid.append((case, r))
    unique = {c.get('groupId') for c, r in valid}
    if None in unique or len(unique) != len(valid):
        failures.append('non_independent_report_groups')
    strata = Counter(c['stratum'] for c, r in valid)
    if set(POLICY['requiredStrata']) - strata.keys():
        failures.append('coverage_missing')
    n = sum(r['severeErrorPresent'] for c, r in valid)
    misses = sum(r['severeErrorPresent'] and not r['severeErrorDetected'] for c, r in valid)
    # Exact one-sided binomial upper bound for zero misses. Any miss fails this
    # initial gate; do not pretend a zero observed rate proves zero real risk.
    upper = 1 - 0.05 ** (1 / n) if n and misses == 0 else None
    correct = sum(r['correctContent'] for c, r in valid)
    false_blocks = sum(r['correctContent'] and r['blocked'] for c, r in valid)
    repairs = sum(r['repairAttempted'] for c, r in valid)
    regressions = sum(r['repairAttempted'] and r['repairIntroducedError'] for c, r in valid)
    if len(valid) < POLICY['minimumIndependentReports'] or upper is None or upper > POLICY['maxSevereMissUpper95']:
        failures.append('severe_miss_evidence_insufficient')
    if not correct or false_blocks / correct > POLICY['maxFalseBlockRate']:
        failures.append('false_block_evidence_insufficient')
    if not repairs or regressions:
        failures.append('repair_safety_not_established')
    return {'policy': POLICY, 'independentCases': len(valid), 'strata': dict(strata),
            'severeCases': n, 'severeMisses': misses, 'severeMissUpper95': upper,
            'correctCases': correct, 'falseBlocks': false_blocks,
            'repairCases': repairs, 'repairRegressions': regressions,
            'eligibleForEnablementReview': not failures, 'failures': failures,
            'automaticApprovalEnabled': False,
            'note': 'Requires independent labels and separate explicit enablement review; does not approve reports.'}
