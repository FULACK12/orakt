"""Narrow, source-aware regressions; passing is NOT semantic approval."""
import re


def known_semantic_errors(section, packet):
    source = ' '.join(p['text'] for ps in packet.get('chapter_passages', {}).values() for p in ps)
    authority_disclosed = bool(re.search(r'authorized.{0,200}repurchase.{0,120}additional amount of\s*\$', source, re.I | re.S))
    errors = []
    pairs = [(f, getattr(section, f)) for f in ('analysis', 'mechanism', 'counterEvidence', 'evidenceGaps', 'validationPlan')]
    pairs += [('claim', c.statement) for c in section.grounded_claims]
    for field, pair in pairs:
        for lang in ('zh', 'en'):
            # Contrast clauses can have different subjects: dilution offsets a
            # buyback, while stronger operations improve EPS. Do not merge them.
            for sentence in re.split(r'[。！？;；\n]|(?<=[.!?])\s+|,\s*(?:while|whereas|but)\b', getattr(pair, lang), flags=re.I):
                # Corrections discussing the old error are not endorsements.
                if re.search(r'不能|不应|并非|而非|错误|误称|误把|does not|cannot|must not|incorrect|wrongly|draft incorrectly', sentence, re.I):
                    continue
                if (re.search(r'(?:稀释|摊薄|分母增加).{0,35}(?:提高|提升|增加)每股收益', sentence)
                        or re.search(r'(?:dilution|dilutive shares|increased denominator).{0,65}(?:raises?|increases?|improves?|higher).{0,20}(?:EPS|earnings per share)', sentence, re.I)):
                    errors.append(f'{field}.{lang}: dilution is not EPS accretion; hold earnings constant')
                if authority_disclosed and (re.search(r'(?:剩余|剩下).{0,10}回购(?:授权|额度).{0,15}(?:未披露|未知|缺失|不明)', sentence)
                        or re.search(r'(?:remaining|unused) (?:repurchase|buyback) (?:authority|authorization|capacity).{0,25}(?:unknown|undisclosed|not disclosed|missing)', sentence, re.I)):
                    errors.append(f'{field}.{lang}: remaining repurchase authority is present in frozen passages')
                if re.search(r'非暂时性减值.{0,12}(?:就是|等于|意味着).{0,8}一次性损失', sentence) or re.search(r'other.than.temporary impairment.{0,25}(?:means|is equivalent to).{0,12}one.time loss', sentence, re.I):
                    errors.append(f'{field}.{lang}: other-than-temporary impairment is not a generic one-time loss')
    return errors


def guard_known_semantics(section, packet):
    errors = known_semantic_errors(section, packet)
    if errors:
        raise ValueError('Known semantic regression: ' + '; '.join(errors))
