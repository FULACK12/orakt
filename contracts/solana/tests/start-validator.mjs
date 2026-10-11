// A disposable Docker validator bound to loopback. No remote RPC or wallet input.
import {mkdirSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';
import {genesisAccounts, program} from './payment-fixtures.mjs';
const root = fileURLToPath(new URL('../', import.meta.url));
const fixtureDir = join(root, '.ci-cache', 'payment-fixtures');
mkdirSync(fixtureDir, {recursive: true});
const args = [];
for (const {name, ...fixture} of genesisAccounts()) {
  writeFileSync(join(fixtureDir, name + '.json'), JSON.stringify(fixture));
  args.push('--account', fixture.pubkey, '/work/.ci-cache/payment-fixtures/' + name + '.json');
}
console.log('LOCAL ONLY: synthetic balances at allowlisted addresses; NOT real stablecoins.');
execFileSync('docker', ['run', '-d', '--name', 'orakt-validator',
  '-p', '127.0.0.1:8899:8899', '-p', '127.0.0.1:8900:8900', '-v', root + ':/work',
  'solanafoundation/anchor@sha256:21ab8a16e19df4301a198d7a55ab2988549aa2d996e6b5ad229c1d95b9f2d326',
  'solana-test-validator', '--bpf-program', program.toBase58(), '/work/target/deploy/orakt_protocol.so',
  '--bind-address', '0.0.0.0', '--ledger', '/tmp/orakt-test-ledger', '--quiet', ...args], {stdio: 'inherit'});
