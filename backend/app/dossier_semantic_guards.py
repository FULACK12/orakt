"""Narrow, source-aware regressions; passing is NOT semantic approval."""
import re


def known_semantic_errors(section, packet):
    source = ' '.join(p['text'] for ps in packet.get('chapter_passages', {}).values() for p in ps)
    authority_disclosed = bool(re.search(r'authorized.{0,200}repurchase.{0,120}additional amount of\s*\$', source, re.I | re.S))
    immediate_hardware_recognition=bool(re.search(r'new accounting principles\s+result in the recognition of substantially all',source,re.I))
    errors = []
    pairs = [(f, getattr(section, f)) for f in ('analysis', 'mechanism', 'counterEvidence', 'evidenceGaps', 'validationPlan')]
    pairs += [('claim', c.statement) for c in section.grounded_claims]
    for field, pair in pairs:
        for lang in ('zh', 'en'):
            if re.search(r'\[(?:quantity|amount|数量|数值|value in source table)\]', getattr(pair, lang), re.I):
                errors.append(f'{field}.{lang}: prompt placeholders are not report content; recover original context')
            # Contrast clauses can have different subjects: dilution offsets a
            # buyback, while stronger operations improve EPS. Do not merge them.
            for sentence in re.split(r'[。！？;；\n]|(?<=[.!?])\s+|,\s*(?:while|whereas|but)\b', getattr(pair, lang), flags=re.I):
                # Corrections discussing the old error are not endorsements.
                if re.search(r'不能|不应|并非|而非|错误|误称|误把|does not|cannot|must not|incorrect|wrongly|draft incorrectly', sentence, re.I):
                    continue
                asset_proceeds_in_investing=bool(re.search(r'Investing Activities(?:(?!Financing Activities).){0,1400}Proceeds and deposits related to asset sales',source,re.I|re.S))
                if asset_proceeds_in_investing and (
                    re.search(r'经营(?:活动)?现金流.{0,45}(?:源于|来自|由).{0,35}资产(?:出售|销售)(?:收益|款|收入)',sentence)
                    or re.search(r'operating cash flow.{0,65}(?:driven by|from|due to).{0,60}asset sale proceeds',sentence,re.I)):
                    errors.append(f'{field}.{lang}: asset-sale proceeds are investing cash flows in this source, not a direct operating cash inflow')
                dilution_denial = bool(re.search(r'(?:稀释|摊薄|分母增加)(?:本身)?不等于(?:提高|提升|增加)每股收益', sentence))
                if (not dilution_denial and re.search(r'(?:稀释|摊薄|分母增加).{0,35}(?:提高|提升|增加)每股收益', sentence)
                        or re.search(r'(?:dilution|dilutive shares|increased denominator).{0,65}(?:raises?|increases?|improves?|higher).{0,20}(?:EPS|earnings per share)', sentence, re.I)):
                    errors.append(f'{field}.{lang}: dilution is not EPS accretion; hold earnings constant')
                if authority_disclosed and (re.search(r'(?:剩余|剩下).{0,10}回购(?:授权|额度).{0,15}(?:未披露|未知|缺失|不明)', sentence)
                        or re.search(r'(?:remaining|unused) (?:repurchase|buyback) (?:authority|authorization|capacity).{0,25}(?:unknown|undisclosed|not disclosed|missing)', sentence, re.I)):
                    errors.append(f'{field}.{lang}: remaining repurchase authority is present in frozen passages')
                if re.search(r'非暂时性减值.{0,12}(?:就是|等于|意味着).{0,8}一次性损失', sentence) or re.search(r'other.than.temporary impairment.{0,25}(?:means|is equivalent to).{0,12}one.time loss', sentence, re.I):
                    errors.append(f'{field}.{lang}: other-than-temporary impairment is not a generic one-time loss')
                if immediate_hardware_recognition and (
                    re.search(r'(?:新(?:的)?会计(?:政策|原则)|会计政策变更).{0,80}(?:要求|导致|引入).{0,50}(?:递延|延迟|订阅会计)',sentence)
                    or re.search(r'(?:new accounting (?:principles|policy)|accounting policy change).{0,80}(?:required|introduced|deferred).{0,50}(?:subscription|deferred revenue|revenue recognition)',sentence,re.I)):
                    if not re.search(r'software upgrade rights|软件升级权|does not|并非|而非',sentence,re.I):
                        errors.append(f'{field}.{lang}: old subscription deferral is not the new hardware recognition rule; retain the original policy transition')
    return errors


def guard_known_semantics(section, packet):
    errors = known_semantic_errors(section, packet)
    if errors:
        raise ValueError('Known semantic regression: ' + '; '.join(errors))
