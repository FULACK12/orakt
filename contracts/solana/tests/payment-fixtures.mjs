// SYNTHETIC LOCAL-GENESIS FIXTURES, NOT issuer USDC/USDT or live wallet keys.
// Public deterministic test seeds are deliberately non-secret. Never fund them.
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
const require = createRequire(new URL('../../../pilot-site/package.json', import.meta.url));
export const web3 = require('@solana/web3.js');
const {Keypair, PublicKey} = web3;
export const digest = label => createHash('sha256').update(label).digest();
export const testKey = label => Keypair.fromSeed(digest('ORAKT LOCAL ONLY PUBLIC TEST SEED:' + label));
export const buyer = testKey('payment-buyer');
export const authority = testKey('payment-operator');
export const stranger = testKey('payment-stranger');
export const program = new PublicKey('BaAX5nB9yxMh5K1tdEserFDq7MMcisVGVNshrVNLqDyn');
export const token = new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA');
export const merchant = new PublicKey('9WLRmvq8a86A6q9JwrzKqyVoUXDJoXC14SKNix3xZ79Z');
export const usdc = new PublicKey('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v');
export const usdt = new PublicKey('Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB');
export const unsupported = new PublicKey(digest('ORAKT LOCAL unsupported mint'));
const address = label => new PublicKey(digest('ORAKT LOCAL account:' + label));
export const accounts = {
  source: {address: address('source'), mint: usdc, owner: buyer.publicKey, amount: 2_000_000_000n},
  sourceUsdt: {address: address('source-usdt'), mint: usdt, owner: buyer.publicKey, amount: 2_000_000_000n},
  treasury: {address: address('treasury'), mint: usdc, owner: merchant, amount: 0n},
  treasuryUsdt: {address: address('treasury-usdt'), mint: usdt, owner: merchant, amount: 0n},
  wrongTreasury: {address: address('wrong-treasury'), mint: usdc, owner: stranger.publicKey, amount: 0n},
  wrongSource: {address: address('wrong-source'), mint: usdc, owner: stranger.publicKey, amount: 100_000_000n},
  empty: {address: address('empty'), mint: usdc, owner: buyer.publicKey, amount: 0n},
  frozen: {address: address('frozen'), mint: usdc, owner: buyer.publicKey, amount: 100_000_000n, state: 2},
  unsupportedSource: {address: address('unsupported-source'), mint: unsupported, owner: buyer.publicKey, amount: 100_000_000n},
  unsupportedTreasury: {address: address('unsupported-treasury'), mint: unsupported, owner: merchant, amount: 0n},
};

// Classic SPL Token packed layouts, verified against solana-program/token state.rs.
export function genesisAccounts() {
  const wrap = (pubkey, data) => ({pubkey: pubkey.toBase58(), account: {
    lamports: 10_000_000, data: [data.toString('base64'), 'base64'], owner: token.toBase58(),
    executable: false, rentEpoch: 0, space: data.length,
  }});
  const entries = [usdc, usdt, unsupported].map((mint, i) => {
    const data = Buffer.alloc(82);
    // No mint authority; synthetic fixed supply equals the fixture token balances.
    data.writeBigUInt64LE(Object.values(accounts).filter(a => a.mint.equals(mint)).reduce((s, a) => s + a.amount, 0n), 36);
    data[44] = 6; data[45] = 1;
    return {name: 'mint-' + i, ...wrap(mint, data)};
  });
  for (const [name, a] of Object.entries(accounts)) {
    const data = Buffer.alloc(165);
    a.mint.toBuffer().copy(data, 0); a.owner.toBuffer().copy(data, 32);
    data.writeBigUInt64LE(a.amount, 64); data[108] = a.state ?? 1;
    entries.push({name, ...wrap(a.address, data)});
  }
  return entries;
}
