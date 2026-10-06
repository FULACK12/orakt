// Exported historical summaries must not inherit a validation badge from profit alone.
export function alphaEvidenceGate(record){
 const p=record?.validationProtocol||{};
 const checks=[
  ['point_in_time',p.pointInTime?.status==='verified'&&!!p.pointInTime?.inputManifestHash],
  ['dual_benchmarks',p.benchmarks?.market?.status==='complete'&&p.benchmarks?.industry?.status==='complete'&&!!p.benchmarks.market.id&&!!p.benchmarks.industry.id&&p.benchmarks.market.id!==p.benchmarks.industry.id],
  ['independent_samples',p.samples?.overlapExcluded===true&&Number.isInteger(p.samples?.independentCount)&&p.samples.independentCount>=20],
  ['uncertainty',p.confidenceInterval?.level===0.95&&Number.isFinite(p.confidenceInterval?.lower)&&Number.isFinite(p.confidenceInterval?.upper)&&p.confidenceInterval.lower<=p.confidenceInterval.upper&&!!p.confidenceInterval?.method],
  ['costs',p.costs?.status==='included'&&Number.isFinite(p.costs?.roundTripBps)&&p.costs.roundTripBps>=0&&p.costs?.slippageIncluded===true],
  ['multiple_tests',p.multipleTesting?.status==='adjusted'&&Number.isInteger(p.multipleTesting?.trialCount)&&p.multipleTesting.trialCount>0],
  ['reproduction',p.reproduction?.status==='matched'&&!!p.reproduction?.inputManifestHash],
  ['forward_validation',p.forward?.status==='completed'&&p.forward?.preregistered===true&&p.forward?.historicalReconstruction===false]
 ];
 const missing=checks.filter(([,ok])=>!ok).map(([key])=>key);
 return {version:'alpha-evidence-gate/v1',status:missing.length?'evidence_incomplete':'eligible_for_method_review',missing,checks:Object.fromEntries(checks),validatedAlpha:false,note:'Passing metadata requirements is not proof of profitability; inputs, estimators and economic interpretation still require review.'};
}
