import copy
import hashlib
import json
import pytest
from app.dossier_reviewed_synthesis import review_claims,synthesis_messages,bind_narrative_context,chapter_schema


def fixture():
    ps=[{'id':'PASSAGE:'+str(i)*16,'text':f'Original archived paragraph {i} with numerical value 100.'} for i in (1,2)]
    packet={'ticker':'TEST','chapter_passages':{'business':ps}}
    pair={'zh':'原文说明特定业务的表现。','en':'The source describes a specific business.'}
    review={'reviewer':'codex_assistant','state':'accepted_with_revisions','ticker':'TEST','chapter':'business','sourceFingerprint':'frozen',
        'claims':[{'passageId':p['id'],'quoteSha256':hashlib.sha256(p['text'].encode()).hexdigest(),'extract':{'disclosed_fact':pair,'not_established':pair},'revisionNote':'Scope corrected.'} for p in ps]}
    return packet,review


def test_only_reviewed_qualitative_claims_go_to_writer():
    packet,review=fixture();claims=review_claims(packet,'frozen',review)
    messages=synthesis_messages('TEST',claims)
    assert 'Original archived paragraph' not in messages[1]['content']
    assert 'numerical value 100' not in messages[1]['content']
    assert 'source describes' in messages[1]['content']
    assert len(json.loads(messages[1]['content'])['reviewedClaims'])==2


@pytest.mark.parametrize('mutation', ['quote','source','reviewer','duplicate','rationale'])
def test_tampered_or_unreviewed_inputs_are_rejected(mutation):
    packet,review=fixture();review=copy.deepcopy(review)
    if mutation=='quote':review['claims'][0]['quoteSha256']='changed'
    elif mutation=='source':review['sourceFingerprint']='changed'
    elif mutation=='reviewer':review['reviewer']='local_model'
    elif mutation=='duplicate':review['claims'][1]=review['claims'][0]
    else:review['claims'][0]['revisionNote']=''
    with pytest.raises(ValueError):review_claims(packet,'frozen',review)


def narrative():
    keys=('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan')
    d={k:{'support_ids':['PASSAGE:1111111111111111'],'zh':'该段原文需要核对。','en':'Check the source paragraph.'} for k in keys}
    d['mechanism'].update(zh='如果渠道变化持续，需要检验传导。',en='If channel changes persist, test the proposed transmission.')
    d['evidenceGaps'].update(zh='本次所选摘录缺少单独贡献分解。',en='The selected excerpts do not quantify separate contributions.')
    return d


def test_context_ids_bound_to_both_languages_without_claiming_causality():
    text,ids=bind_narrative_context(narrative(),{'PASSAGE:1111111111111111'})
    assert text['analysis']['zh'].endswith('[PASSAGE:1111111111111111]')
    assert text['analysis']['en'].endswith('[PASSAGE:1111111111111111]')
    assert ids['mechanism']==['PASSAGE:1111111111111111']


@pytest.mark.parametrize('bad',['unknown','duplicate','mechanism','scope','repeated'])
def test_narrative_quality_gates(bad):
    d=narrative()
    if bad=='unknown':d['analysis']['support_ids']=['unseen']
    elif bad=='duplicate':d['analysis']['support_ids']*=2
    elif bad=='mechanism':d['mechanism']['en']='The company improved its efficiency.'
    elif bad=='scope':d['evidenceGaps']['en']='The company never disclosed this data.'
    else:d['counterEvidence']=copy.deepcopy(d['evidenceGaps'])
    with pytest.raises(ValueError):bind_narrative_context(d,{'PASSAGE:1111111111111111'})


def test_schema_requires_each_paragraph_context():
    packet,review=fixture();schema=chapter_schema(review_claims(packet,'frozen',review))
    assert len(schema['properties'])==5
    for p in schema['properties'].values():assert 'support_ids' in p['required']


def test_factor_prompt_gets_coverage_boundaries_not_unreviewed_prices():
    packet,review=fixture();claims=review_claims(packet,'frozen',review)
    messages=synthesis_messages('TEST',claims,chapter='factors',readiness={
        'factorState':'hypothesis_only','series':[{'value':99999}],'eligibleForPredictiveBacktest':False})
    payload=json.loads(messages[1]['content'])
    assert 'series' not in payload['marketReadiness']
    assert payload['marketReadiness']['eligibleForPredictiveBacktest'] is False
    assert 'non-overlapping out-of-sample' in messages[0]['content']
