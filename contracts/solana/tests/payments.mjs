// Real program/CPI execution on synthetic local genesis; never public-chain money.
import assert from 'node:assert/strict';
import {web3, buyer, authority, stranger, testKey, program, token, merchant, usdc, usdt, unsupported, accounts, digest} from './payment-fixtures.mjs';
const {Connection, PublicKey, SystemProgram, Transaction, TransactionInstruction, sendAndConfirmTransaction} = web3;
const rpc = new Connection('http://127.0.0.1:8899', 'confirmed');
const pda = (...seeds) => PublicKey.findProgramAddressSync(seeds.map(s => typeof s === 'string' ? Buffer.from(s) : s instanceof PublicKey ? s.toBuffer() : s), program)[0];
const meta = (pubkey, isSigner = false, isWritable = false) => ({pubkey: pubkey.publicKey ?? pubkey, isSigner, isWritable});
const config = pda('config', authority.publicKey);
const governance = pda('governance', config);
const sub = plan => pda('subscription', config, buyer.publicKey, Buffer.from([plan]));
const receipt = invoice => pda('receipt', config, buyer.publicKey, invoice);
const integer = n => {const b = Buffer.alloc(8); b.writeBigInt64LE(BigInt(n)); return b;};
const ix = (name, keys, ...args) => new TransactionInstruction({programId: program, keys, data: Buffer.concat([digest('global:' + name).subarray(0, 8), ...args])});
const quoteSigner = testKey('payment-quote');
const send = (instruction, signers = [buyer, quoteSigner]) => sendAndConfirmTransaction(rpc, new Transaction().add(instruction), signers, {commitment: 'confirmed'});
const read = async key => (await rpc.getAccountInfo(key))?.data ?? null;
const balance = async key => (await read(key)).readBigUInt64LE(64);
let count = 0;
let quoteNonce = 0n;
const check = label => {count++; console.log('PASS payment: ' + label);};
const chainTime = async () => (await read(new PublicKey('SysvarC1ock11111111111111111111111111111111'))).readBigInt64LE(32);
const deadline = async () => await chainTime() + 300n + quoteNonce++;
async function purchase(o = {}) {
  const plan = o.plan ?? 2, invoice = o.invoice ?? digest('invoice:' + o.label);
  const gov = await read(governance), current = await read(sub(plan));
  return {plan, invoice, instruction: ix('purchase', [meta(buyer, true, true), meta(config), meta(o.mint ?? usdc),
    meta(o.source ?? accounts.source.address, false, true), meta(o.treasury ?? accounts.treasury.address, false, true),
    meta(o.subscription ?? sub(plan), false, true), meta(o.receipt ?? receipt(invoice), false, true),
    meta(o.tokenProgram ?? token), meta(SystemProgram.programId),meta(governance),meta(o.quoteSigner ?? quoteSigner, o.quoteIsSigner ?? true)], Buffer.from([plan]), invoice, Buffer.from([o.months ?? 1]),
    integer(o.amount ?? 79_000_000n), integer(o.deadline), integer(o.epoch ?? gov.readBigUInt64LE(138)), integer(o.expectedExpiry ?? current?.readBigInt64LE(73) ?? 0n))};
}
async function state(p) {
  return Promise.all([...Object.values(accounts).map(a => a.address), sub(1), sub(2), receipt(p.invoice)].map(read));
}
async function rejected(label, options = {}, {execute = false, code, signers} = {}) {
  const p = await purchase({label, deadline: await deadline(), ...options}), before = await state(p);
  if (execute) {
    // Bypass simulation only inside this hardcoded loopback validator, so rollback
    // is verified after an ACTUAL failed transaction, not merely a preflight rejection.
    const block = await rpc.getLatestBlockhash();
    const tx = new Transaction({feePayer: buyer.publicKey, ...block}).add(p.instruction); tx.sign(buyer, quoteSigner);
    const signature = await rpc.sendRawTransaction(tx.serialize(), {skipPreflight: true});
    const confirmation = await rpc.confirmTransaction({signature, ...block}, 'confirmed');
    assert.deepEqual(confirmation.value.err, {InstructionError: [0, {Custom: code}]}, label);
    let landed;
    for (let attempt = 0; attempt < 10; attempt++) {
      landed = await rpc.getTransaction(signature, {commitment: 'confirmed', maxSupportedTransactionVersion: 0});
      if (landed) break;
      await new Promise(resolve => setTimeout(resolve, 300));
    }
    assert.deepEqual(landed?.meta?.err, confirmation.value.err);
  } else {
    const expected = code === undefined ? /custom program error/i : new RegExp('custom program error: 0x' + code.toString(16) + '\\b', 'i');
    await assert.rejects(() => send(p.instruction, signers), e => expected.test(String(e)), label);
  }
  assert.deepEqual(await state(p), before, label + ': balances and entitlement unchanged');
  check(label);
}
function monthEnd(timestamp, months) {
  const date = new Date(Number(timestamp) * 1000);
  for (let i = 0; i < months; i++) {
    const day = date.getUTCDate(); date.setUTCDate(1); date.setUTCMonth(date.getUTCMonth() + 1);
    const last = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate();
    date.setUTCDate(Math.min(day, last));
  }
  return BigInt(date.getTime() / 1000);
}
async function accepted(label, options = {}) {
  const p = await purchase({label, deadline: await deadline(), ...options});
  const source = options.source ?? accounts.source.address, treasury = options.treasury ?? accounts.treasury.address;
  const beforeFrom = await balance(source), beforeTo = await balance(treasury), previous = await read(sub(p.plan));
  await send(p.instruction);
  const r = await read(receipt(p.invoice)), s = await read(sub(p.plan));
  assert.equal(r.length, 163); assert.equal(s.length, 82);
  assert.deepEqual(r.subarray(0, 8), digest('account:Receipt').subarray(0, 8));
  assert.deepEqual(r.subarray(8, 40), config.toBuffer()); assert.deepEqual(r.subarray(40, 72), buyer.publicKey.toBuffer());
  assert.deepEqual(r.subarray(72, 104), p.invoice); assert.deepEqual(r.subarray(104, 136), (options.mint ?? usdc).toBuffer());
  const amount = options.amount ?? 79_000_000n;
  assert.equal(beforeFrom - await balance(source), amount); assert.equal(await balance(treasury) - beforeTo, amount);
  assert.equal(r.readBigUInt64LE(136), amount); assert.equal(r[144], p.plan); assert.equal(r[145], options.months ?? 1);
  const paidAt = r.readBigInt64LE(146), oldEnd = previous?.readBigInt64LE(73) ?? 0n;
  const end = monthEnd(oldEnd > paidAt ? oldEnd : paidAt, options.months ?? 1);
  assert.equal(r.readBigInt64LE(154), end); assert.equal(s.readBigInt64LE(73), end); assert.equal(s[72], p.plan);
  check(label); return p;
}

assert.ok((await rpc.getAccountInfo(program))?.executable);
// Reject accidental use against a non-fixture ledger before signing anything.
for (const a of Object.values(accounts)) {
  const info = await rpc.getAccountInfo(a.address);
  assert.ok(info?.owner.equals(token)); assert.equal(info.data.readBigUInt64LE(64), a.amount);
}
for (const pair of [buyer, authority, quoteSigner]) {
  const signature = await rpc.requestAirdrop(pair.publicKey, 2_000_000_000); await rpc.confirmTransaction(signature, 'confirmed');
}
await send(ix('initialize', [meta(authority, true, true), meta(config, false, true), meta(governance,false,true), meta(SystemProgram.programId)],buyer.publicKey.toBuffer()), [authority]);
const adminKeys = [meta(authority,true),meta(config,false,true),meta(governance,false,true)];
const configureSigner = signer => send(ix('set_quote_signer',adminKeys,signer.publicKey.toBuffer()),[authority]);
const enable = () => send(ix('set_payments_enabled',adminKeys,Buffer.from([1])),[authority]);
for (const forbidden of [authority,buyer,{publicKey:merchant}]) {
  await assert.rejects(() => configureSigner(forbidden),/custom program error: 0x1770/i);
}
check('quote signer cannot be authority, guardian or merchant');
await configureSigner(quoteSigner);
assert.equal((await read(governance)).length,178); // Candidate only; live v145 remains 138.
await rejected('payments default off', {}, {code:6010});
await send(ix('set_payments_enabled',[meta(authority,true),meta(config,false,true),meta(governance,false,true)],Buffer.from([1])),[authority]);
await rejected('buyer alone cannot bypass quote signature', {quoteIsSigner:false}, {code:3010,signers:[buyer]});
await rejected('stranger cannot authorize quote', {quoteSigner:stranger}, {code:6001,signers:[buyer,stranger]});
await rejected('buyer cannot self-authorize', {quoteSigner:buyer}, {code:6001,signers:[buyer]});
await rejected('stale epoch', {epoch:0n}, {code:6012});
await rejected('incorrect subscription baseline', {expectedExpiry:1n}, {execute:true,code:6013});
const unsignedLegacy = await purchase({label:'legacy-wire',deadline:await deadline()});
const legacyBefore=await state(unsignedLegacy);
unsignedLegacy.instruction.keys.pop(); unsignedLegacy.instruction.data=unsignedLegacy.instruction.data.subarray(0,58);
await assert.rejects(() => send(unsignedLegacy.instruction,[buyer]),/custom program error/i);
assert.deepEqual(await state(unsignedLegacy),legacyBefore);
check('old unsigned purchase format fails closed');
const signed = await purchase({label:'signature-tamper',deadline:await deadline()});
const signedTx = new Transaction({feePayer:buyer.publicKey,...await rpc.getLatestBlockhash()}).add(signed.instruction);
signedTx.partialSign(quoteSigner); signedTx.partialSign(buyer);
assert.equal(signedTx.verifySignatures(),true);
signedTx.instructions[0].data[9]^=1; // Change invoice after authorization.
assert.equal(signedTx.verifySignatures(),false);
assert.throws(() => signedTx.serialize(),/Signature verification failed/i);
await assert.rejects(() => rpc.sendRawTransaction(signedTx.serialize({verifySignatures:false}),{skipPreflight:false}),/signature verification fail|did not pass signature verification/i);
assert.equal(await read(receipt(signed.invoice)),null);
check('changing signed invoice invalidates both signatures');
const govBefore = await read(governance);
await assert.rejects(() => send(ix('set_quote_signer',[meta(quoteSigner,true),meta(config,false,true),meta(governance,false,true)],stranger.publicKey.toBuffer()),[quoteSigner]),/custom program error/i);
assert.deepEqual(await read(governance),govBefore);
check('quote signer has no administrator privilege');
await rejected('underpayment', {amount: 78_000_000n}, {code: 6008});
await rejected('overpayment quote mismatch', {amount: 80_000_000n}, {code: 6008});
await rejected('expired quote', {deadline: await chainTime() - 1n}, {code: 6007});
await rejected('quote too far in future', {deadline: await chainTime() + 3600n}, {code: 6007});
await rejected('empty invoice', {invoice: Buffer.alloc(32)}, {code: 6007});
await rejected('zero-month term', {months: 0}, {code: 6000});
await rejected('term exceeds limit', {months: 13}, {code: 6000});
await rejected('unknown plan', {plan: 3}, {code: 6000});
await rejected('wrong recipient', {treasury: accounts.wrongTreasury.address}, {code: 6001});
await rejected('wrong source owner', {source: accounts.wrongSource.address});
await rejected('wrong source mint', {source: accounts.sourceUsdt.address});
await rejected('wrong treasury mint', {treasury: accounts.treasuryUsdt.address});
await rejected('unsupported mint', {mint: unsupported, source: accounts.unsupportedSource.address, treasury: accounts.unsupportedTreasury.address}, {code: 6006});
await rejected('wrong token program', {tokenProgram: SystemProgram.programId});
await rejected('substituted subscription PDA', {subscription: sub(1)});
await rejected('substituted invoice PDA', {receipt: receipt(digest('other invoice'))});
await rejected('insufficient funds: landed transaction rolls back', {source: accounts.empty.address}, {execute: true, code: 1});
await rejected('frozen source: landed transaction rolls back', {source: accounts.frozen.address}, {execute: true, code: 17});
const concurrent = await purchase({label:'concurrent-quote',deadline:await deadline()});
const first = await accepted('USDC Research purchase');
const concurrentBefore=await state(concurrent);
await assert.rejects(() => send(concurrent.instruction),/custom program error: 0x177d/i);
assert.deepEqual(await state(concurrent),concurrentBefore);
check('second quote on old subscription baseline cannot double-renew');
await rejected('invoice replay rejected without second charge', {invoice: first.invoice});
await accepted('USDC Research renewal preserves unexpired term', {months: 2, amount: 158_000_000n});
const research = await read(sub(2));
await accepted('USDT Signal purchase', {plan: 1, mint: usdt, source: accounts.sourceUsdt.address, treasury: accounts.treasuryUsdt.address, amount: 19_000_000n});
assert.deepEqual(await read(sub(2)), research); check('lower plan cannot erase Research entitlement');
await accepted('USDT Research 12-month renewal', {mint: usdt, source: accounts.sourceUsdt.address, treasury: accounts.treasuryUsdt.address, months: 12, amount: 948_000_000n});
const oldEpoch=(await read(governance)).readBigUInt64LE(138);
await send(ix('set_payments_enabled',[meta(authority,true),meta(config,false,true),meta(governance,false,true)],Buffer.from([0])),[authority]);
await rejected('payments independently disabled', {}, {code:6010});
await send(ix('set_payments_enabled',[meta(authority,true),meta(config,false,true),meta(governance,false,true)],Buffer.from([1])),[authority]);
await rejected('off/on cannot resurrect old quotes',{epoch:oldEpoch},{code:6012});
const beforeRotation=(await read(governance)).readBigUInt64LE(138);
await configureSigner(stranger); await configureSigner(quoteSigner); await enable();
await rejected('A to B to A signer rotation cannot resurrect quotes',{epoch:beforeRotation},{code:6012});
const beforePause=(await read(governance)).readBigUInt64LE(138);
await send(ix('set_paused', [meta(authority, true), meta(config, false, true),meta(governance,false,true)], Buffer.from([1])), [authority]);
await rejected('paused configuration cannot charge', {}, {code: 6002});
await send(ix('set_paused',adminKeys,Buffer.from([0])),[authority]);
await rejected('unpause cannot resurrect quotes',{epoch:beforePause},{code:6012});
const beforeRecovery=(await read(governance)).readBigUInt64LE(138);
await send(ix('propose_authority',[meta(authority,true),meta(config),meta(governance,false,true)],stranger.publicKey.toBuffer()),[authority]);
await assert.rejects(() => configureSigner(quoteSigner),/custom program error: 0x177b/i);
check('quote key cannot rotate during recovery');
await send(ix('cancel_authority',adminKeys),[authority]); await enable();
await rejected('cancelled recovery cannot resurrect quotes',{epoch:beforeRecovery},{code:6012});
await accepted('fresh co-signed quote after revocation succeeds');
await send(ix('propose_authority',[meta(authority,true),meta(config),meta(governance,false,true)],stranger.publicKey.toBuffer()),[authority]);
// Local-only successor gets fee SOL; never a public-chain wallet.
const fund=await rpc.requestAirdrop(stranger.publicKey,1_000_000_000);await rpc.confirmTransaction(fund,'confirmed');
await send(ix('accept_authority',[meta(stranger,true),meta(config),meta(governance,false,true)]),[stranger]);
const recovered=await read(governance);
assert.equal(recovered[136],0);assert.deepEqual(recovered.subarray(146,178),Buffer.alloc(32));
check('accepted recovery clears quote authority and disables payments');
console.log(`PASS ${count} payment checks on synthetic local genesis. No public-chain deployment or real stablecoin transfers.`);
