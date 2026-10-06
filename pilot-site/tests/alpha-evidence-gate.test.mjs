import test from 'node:test';
import assert from 'node:assert/strict';
import {alphaEvidenceGate} from '../app/alpha-evidence-gate.mjs';
test('large sample counts or positive reported returns cannot establish Alpha',()=>{
 const r=alphaEvidenceGate({status:'out_of_sample_positive',test_observations:100000,excess_return:2});
 assert.equal(r.missing.length,8);assert.equal(r.validatedAlpha,false);
});
test('a complete protocol is only eligible for review and future-data leakage blocks it',()=>{
 const p={pointInTime:{status:'verified',inputManifestHash:'abc'},benchmarks:{market:{id:'SPY',status:'complete'},industry:{id:'SOXX',status:'complete'}},samples:{overlapExcluded:true,independentCount:20},confidenceInterval:{level:0.95,lower:-0.02,upper:0.03,method:'block_bootstrap'},costs:{status:'included',roundTripBps:25,slippageIncluded:true},multipleTesting:{status:'adjusted',trialCount:20},reproduction:{status:'matched',inputManifestHash:'abc'},forward:{status:'completed',preregistered:true,historicalReconstruction:false}};
 assert.equal(alphaEvidenceGate({validationProtocol:p}).status,'eligible_for_method_review');assert.equal(alphaEvidenceGate({validationProtocol:p}).validatedAlpha,false);
 p.forward.historicalReconstruction=true;assert.ok(alphaEvidenceGate({validationProtocol:p}).missing.includes('forward_validation'));
 p.confidenceInterval.lower=Infinity;assert.ok(alphaEvidenceGate({validationProtocol:p}).missing.includes('uncertainty'));
});
