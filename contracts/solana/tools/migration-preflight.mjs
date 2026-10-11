// Offline rehearsal only. No DB, RPC, keys, transactions, or production flags.
import {createHash} from 'node:crypto';
const plans = ['signal', 'research'];
const grants = ['free', 'manual_paid', 'complimentary', 'onchain_paid'];
const keys = ['status','plan','grantKind','expiresAt','walletBound','unresolvedOrders','trialClaimedAt','trialExpiresAt','chain'];
const stamp = n => Number.isSafeInteger(n) && n >= 0 && n < 13569465600000;
function check(ok, reason) { if (!ok) throw Error(reason); }
function exact(o, allowed) { return o && typeof o === 'object' && !Array.isArray(o) && Object.keys(o).length === allowed.length && allowed.every(k => Object.hasOwn(o,k)); }

export function migrationPreflight(input, now) {
  check(stamp(now), 'invalid_now');
  check(exact(input,['schema','network','observedAt','accounts']) && input.schema === 'orakt-migration-rehearsal-v1' && input.network === 'solana:devnet', 'rehearsal_only');
  check(stamp(input.observedAt) && input.observedAt <= now && now-input.observedAt <= 60000, 'stale_snapshot');
  check(Array.isArray(input.accounts) && input.accounts.length <= 1000, 'invalid_batch');
  const rows = input.accounts.map((a,index) => {
    check(exact(a,keys), 'invalid_account_shape');
    check(['active','suspended'].includes(a.status) && ['explorer',...plans].includes(a.plan) && grants.includes(a.grantKind), 'invalid_account');
    check(typeof a.walletBound === 'boolean' && Number.isSafeInteger(a.unresolvedOrders) && a.unresolvedOrders >= 0, 'invalid_account');
    check(a.plan === 'explorer' ? a.grantKind === 'free' && a.expiresAt === null : a.grantKind !== 'free' && stamp(a.expiresAt), 'invalid_term');
    check((a.trialClaimedAt === null && a.trialExpiresAt === null) || (stamp(a.trialClaimedAt) && stamp(a.trialExpiresAt) && a.trialClaimedAt <= now && a.trialExpiresAt-a.trialClaimedAt === 86400000), 'invalid_trial');
    check(exact(a.chain,['signal','research']) && plans.every(p=>stamp(a.chain[p])), 'invalid_chain_snapshot');
    const paidUntil = plans.includes(a.plan) && a.expiresAt > now ? a.expiresAt : 0;
    const trialUntil = a.trialExpiresAt > now ? a.trialExpiresAt : 0;
    const preserveUntil = Math.max(paidUntil,trialUntil);
    const reasons=[];
    if(a.status !== 'active') reasons.push('account_suspended');
    if(a.unresolvedOrders) reasons.push('reconcile_existing_orders_first');
    if(!a.walletBound) reasons.push('explicit_wallet_binding_required');
    if(trialUntil) reasons.push('preserve_wallet_free_trial');
    if(paidUntil && a.chain[a.plan] < paidUntil) reasons.push('preserve_legacy_term_no_overlapping_charge');
    if(plans.some(p=>a.chain[p]>now && (p!==a.plan || a.chain[p]>paidUntil))) reasons.push('verify_and_reconcile_chain_entitlement_first');
    return {row:index+1, reasons, classification:reasons.length?'blocked':'candidate_for_fresh_verification', preserveUntil:preserveUntil||null, remainingMs:Math.max(0,preserveUntil-now), rightsChanged:false, chargingAllowed:false};
  });
  return {schema:'orakt-migration-preflight-v1', mode:'offline_devnet_rehearsal', observedAt:input.observedAt, checkedAt:now,
    inputSha256:createHash('sha256').update(JSON.stringify(input)).digest('hex'),
    inputTrust:'Caller-supplied anonymized rehearsal snapshot; not chain verification or an account authorization',
    productionReady:false, changesApplied:0, total:rows.length, blocked:rows.filter(r=>r.classification==='blocked').length, rows};
}
