// Public evidence export: explicit allowlist, never keys, signed transaction bytes,
// private member identities, or unfinalized attempts.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const workspace=fileURLToPath(new URL('../../../',import.meta.url));
const read=name=>JSON.parse(readFileSync(resolve(workspace,'.tmp/orakt-devnet-v145',name)));
const manifest=read('manifest.json'),smoke=read('smoke-audit.json'),deploy=read('deployment-cli.json');
assert.equal(manifest.status,'deployed_finalized');assert.equal(smoke.status,'passed');assert.equal(smoke.programId,manifest.programId);
assert.ok(smoke.checks.includes('guardian recovery and rotation completed; payments remain off'));
const txs=Object.entries(smoke.steps).map(([label,step])=>{assert.equal(step.status,'finalized');assert.match(step.signature,/^[1-9A-HJ-NP-Za-km-z]{64,88}$/);return {label,signature:step.signature,explorer:'https://explorer.solana.com/tx/'+step.signature+'?cluster=devnet'};});
const output={schema:'orakt-devnet-acceptance-v2',network:'solana:devnet',status:'deployed_and_smoke_tested',testOnly:true,productionEntitlements:false,independentSecurityAudit:false,
 programId:manifest.programId,programData:manifest.programData,config:smoke.config,governance:smoke.governance,guardian:smoke.guardian,paymentsEnabled:false,deploySlot:manifest.deploySlot,upgradeAuthority:manifest.upgradeAuthority,
 authorityNotice:'Disposable isolated test operator, not Phantom or production governance. All test actors are controlled by the same test operator; different-wallet review is not independent assurance.',
 sourceSha256:manifest.sourceSha256,binarySha256:manifest.binarySha256,binaryBytes:manifest.binaryBytes,mints:manifest.mints,
 tokenNotice:'TEST_USDC and TEST_USDT are synthetic Devnet mints, NOT issuer USDC/USDT, not redeemable, and not accepted for production memberships.',
 programExplorer:'https://explorer.solana.com/address/'+manifest.programId+'?cluster=devnet',
 deployment:deploy,verifiedAt:manifest.verifiedAt,smokeCompletedAt:smoke.completedAt,checks:smoke.checks,
 evidence:smoke.evidence,records:Object.fromEntries(Object.entries(smoke).filter(([key])=>/^(record_|receipt_|subscription_)|^(review|retraction|trial)$/.test(key))),transactions:txs,
 remainingGates:['Independent security review','Mainnet deployment budget and owner signatures','Production governance and deployment pins','Production feature activation after separate acceptance']};
writeFileSync(resolve(workspace,'contracts/solana/devnet-deployment-v145.json'),JSON.stringify(output,null,2));
console.log(JSON.stringify({publicArtifact:'contracts/solana/devnet-deployment-v145.json',programId:output.programId,transactions:txs.length,checks:output.checks.length}));
