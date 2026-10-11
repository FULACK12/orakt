import {test} from 'node:test';
import assert from 'node:assert/strict';
import {genesisAccounts, accounts, token, buyer} from './payment-fixtures.mjs';
test('synthetic fixtures contain no keypair material and use classic token ownership', () => {
  const fixtures = genesisAccounts();
  assert.equal(fixtures.length, 13);
  assert.equal(new Set(fixtures.map(f => f.pubkey)).size, 13);
  for (const fixture of fixtures) {
    assert.deepEqual(Object.keys(fixture).sort(), ['account', 'name', 'pubkey']);
    assert.equal(fixture.account.owner, token.toBase58());
    assert.equal(fixture.account.executable, false);
    assert.equal(Buffer.from(fixture.account.data[0], 'base64').length, fixture.account.space);
  }
});
test('synthetic fixed supplies equal the initialized account balances', () => {
  for (const mint of genesisAccounts().filter(f => f.account.space === 82)) {
    const data = Buffer.from(mint.account.data[0], 'base64');
    assert.equal(data.readUInt32LE(0), 0); // no mint authority
    assert.equal(data[44], 6); assert.equal(data[45], 1);
    assert.equal(data.readBigUInt64LE(36), Object.values(accounts).filter(a => a.mint.toBase58() === mint.pubkey).reduce((sum, a) => sum + a.amount, 0n));
  }
});
test('empty and frozen fixtures preserve the intended buyer for CPI failure tests', () => {
  for (const name of ['empty', 'frozen']) {
    const fixture = genesisAccounts().find(f => f.name === name);
    const data = Buffer.from(fixture.account.data[0], 'base64');
    assert.deepEqual(data.subarray(32, 64), buyer.publicKey.toBuffer());
    assert.equal(data[108], name === 'frozen' ? 2 : 1);
    assert.equal(data.readBigUInt64LE(64), accounts[name].amount);
  }
});
