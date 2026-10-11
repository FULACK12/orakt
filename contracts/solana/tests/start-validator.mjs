// A disposable Docker validator bound to loopback. No remote RPC or wallet input.
import {mkdirSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {genesisAccounts, program} from './payment-fixtures.mjs';
const root = fileURLToPath(new URL('../', import.meta.url));
const buildCache = process.env.ORAKT_SOLANA_BUILD_CACHE || join(root, '.ci-cache');
const fixtureDir = join(root, '.ci-cache', 'payment-fixtures');
mkdirSync(fixtureDir, {recursive: true});
// Agave 4 requires io_uring. Preserve Docker's pinned default deny policy and
// allow only its three io_uring calls for THIS disposable container; never use
// privileged mode or change the host daemon's security settings.
const profileResponse=await fetch('https://raw.githubusercontent.com/moby/profiles/6fe7deb1b9fb7c0397a4593480d7d22b9ee8caef/seccomp/default.json');
if(!profileResponse.ok)throw Error('Cannot fetch pinned validator seccomp profile');
const profileText=await profileResponse.text();
if(createHash('sha256').update(profileText).digest('hex')!=='6416b47770785a41ac59073cdc77d9fe98517df2799dc83ef207e622de3053f6')throw Error('Seccomp checksum mismatch');
const profile=JSON.parse(profileText);
profile.syscalls.push({names:['io_uring_setup','io_uring_enter','io_uring_register'],action:'SCMP_ACT_ALLOW'});
const profilePath=join(fixtureDir,'validator-seccomp.json');writeFileSync(profilePath,JSON.stringify(profile));
const args = [];
for (const {name, ...fixture} of genesisAccounts()) {
  writeFileSync(join(fixtureDir, name + '.json'), JSON.stringify(fixture));
  args.push('--account', fixture.pubkey, '/work/.ci-cache/payment-fixtures/' + name + '.json');
}
console.log('LOCAL ONLY: synthetic balances at allowlisted addresses; NOT real stablecoins.');
execFileSync('docker', ['run', '-d', '--name', 'orakt-validator',
  '--security-opt','no-new-privileges','--security-opt','seccomp='+profilePath,
  '-p', '127.0.0.1:8899:8899', '-p', '127.0.0.1:8900:8900', '-v', root + ':/work:ro', '-v', buildCache + ':/cache:ro',
  'solanafoundation/anchor@sha256:21ab8a16e19df4301a198d7a55ab2988549aa2d996e6b5ad229c1d95b9f2d326',
  'bash', '-ec', 'exec /cache/agave/solana-release/bin/solana-test-validator --bind-address "$(hostname -i)" "$@"', 'validator',
  '--bpf-program', program.toBase58(), '/work/target/deploy/orakt_protocol.so',
  '--ledger', '/tmp/orakt-test-ledger', '--quiet', ...args], {stdio: 'inherit'});
