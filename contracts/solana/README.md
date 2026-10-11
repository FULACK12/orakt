# ORAKT Protocol — experimental Solana contracts

## Signed-order candidate — NOT deployed, NOT a v145 in-place upgrade

October 11 local validation: SBPFv3 compilation, IDL generation, 45 provenance/
permission checks, 44 synthetic payment/rollback checks and 136 fixture/website/
readiness regression tests passed. The payment suite actually executes rejected
baseline, insufficient-funds and frozen-account transactions to verify rollback,
and submits a tampered signed message to the validator. An initial SBF panic from
`Pubkey::is_on_curve` was caught and removed: the pinned 2.x SDK intentionally does
not implement that method on-chain. A direct-instruction stack-height guard is
used instead. A dedicated CPI-proxy adversarial harness is still an audit gap.

The source now requires a dedicated order co-signer **and** the buyer on every
`purchase`. The Solana runtime verifies signatures over the entire transaction
message: changing the invoice, plan, amount, accounts, program or blockhash
invalidates the authorization. The co-signer is not an administrator, guardian
or merchant and cannot purchase as its own buyer. Only the current administrator
can configure this key; rotation disables payments. Purchase is restricted to a
top-level transaction instruction, so CPI/PDA signer privileges cannot substitute
for the actual transaction signature. Operators must provision a controlled signing
key; configuring an unusable public key fails closed at purchase, not at configuration.

The new arguments after `deadline` are `quote_epoch: u64` and
`expected_expires_at: i64` (UTC seconds, zero for a new subscription). The appended
eleventh account is the configured read-only `quote_signer: Signer`. A purchase
fails if the governance epoch or the subscription's previous expiry changed.
Disabling payments, pausing, proposing/cancelling/accepting authority recovery and
rotating the quote signer increment the epoch. Re-enabling, unpausing or rotating
A -> B -> A cannot revive an old quote. Accepted authority recovery also clears
the quote key. The immutable invoice receipt still prevents replay; failed CPI
transactions roll back payment and entitlement together.

**Compatibility boundary:** candidate Governance is 178 bytes, versus live v145's
138 bytes. This is a new-program/local-validator candidate, not an account realloc
or supported in-place upgrade. Keep `devnet-deployment-v145.json`, its binary hash,
the current web checkout/receipt reader and read-only inspection tools pinned to
v145. Old unsigned purchase payloads fail closed against this candidate. Do not
point the existing checkout at the candidate or overwrite the deployed program.

Not yet delivered: hosted quote-signing service, production key provisioning,
candidate web transaction/receipt adapter, new isolated Devnet deployment and
end-to-end migration acceptance. A signing service must construct its own exact
allowlisted transaction from authenticated, server-stored orders and fresh chain
state; check wallet binding, account status, migration/legacy terms and invoice
idempotency; never sign arbitrary browser-supplied transaction bytes. Return a
partially signed transaction for the buyer to sign without rebuilding its message.
No PII belongs in the on-chain invoice. Signer compromise could authorize orders
outside website policy, although buyer consent and the fixed merchant/price/term
constraints still apply. Key custody, outages, replay/race handling and an
independent security audit remain release gates. Mainnet and real charging are
not authorized by source tests.

Website account suspension or cancellation is not automatically an on-chain
revocation: an already co-signed transaction can remain valid until its deadline
(up to ten minutes), blockhash expiry or governance epoch invalidation. The
service integration must define this race and cancellation/reconciliation policy;
per-order on-chain cancellation is not implemented by this candidate. The on-chain
subscription baseline prevents duplicate renewal races, not off-chain status races.

Mechanism references: [Solana transaction signatures](https://solana.com/docs/core/transactions)
and [Anchor account constraints](https://www.anchor-lang.com/docs/references/account-constraints).

## Migration readiness tools — no account migration or charging activation

Run `node contracts/solana/tools/devnet-readiness.mjs` from the repository root
to inspect the pinned v145 Devnet program. It reads the program, ProgramData,
config and governance in one finalized snapshot; checks the complete binary hash,
deployment slot, loader ownership, PDA identity and upgrade authority; and reports
the independent payment switch and recovery state. It never reads keys, sends
transactions or changes flags. Network errors are unverified, not passing checks.
The result is an RPC observation, not an independent audit or mainnet authorization.
`node contracts/solana/tools/devnet-readiness-acceptance.mjs` additionally tests
tampered binary/identity snapshots and payment, pause and authority drift using
in-memory copies of that public read. It performs no chain mutations. On October
11, 2026, all 15 checks passed at finalized slot 510004957; payments remained OFF.
The 54 focused local tests (27 new tool checks plus 27 existing checkout/recovery
checks) also passed. These counts are not independent audit or migration approval.

`tools/migration-preflight.mjs` classifies anonymized Devnet rehearsal snapshots.
It preserves every remaining millisecond of paid/complimentary access and keeps
wallet-free trials separate. Existing unresolved orders, suspended accounts,
missing wallet bindings, chain/off-chain term conflicts and active legacy terms
produce blockers. Even a candidate has `chargingAllowed: false`; no balances,
rights or chain credits are created. It does not verify caller-supplied snapshots.

An operator can run `node contracts/solana/tools/migration-rehearsal.mjs <local.json>`
with a fresh (at most 60 seconds old), strictly anonymized input:

```json
{
  "schema": "orakt-migration-rehearsal-v1",
  "network": "solana:devnet",
  "observedAt": 0,
  "accounts": [{
    "status": "active", "plan": "explorer", "grantKind": "free",
    "expiresAt": null, "walletBound": true, "unresolvedOrders": 0,
    "trialClaimedAt": null, "trialExpiresAt": null,
    "chain": {"signal": 0, "research": 0}
  }]
}
```

Replace `observedAt` with the actual snapshot UTC epoch milliseconds; all other
times use the same unit. The example's zero timestamp deliberately fails freshness.
Do not put emails, wallet addresses, private account IDs or production exports in
this input/repository. The CLI writes JSON to stdout only; exit 2 means blockers,
exit 1 means invalid/unverified input, and exit 0 is **not** permission to charge.

Proposed safe default: preserve existing off-chain access and defer new charging
until its term expires; reverify wallet, receipts and terms before any new order.
This proposal is not activated. Early conversion, pro-rating, refunds, quote
authorization and production governance still require a reviewed migration policy.
These tools do not implement an on-chain import instruction or modify the website.

## v146 Meteora integration — separate, read-only Devnet module

ORAKT does not redeploy or claim ownership of Meteora's DBC program. A synthetic
`OREVTEST / Devnet SOL` pool was created through the official SDK 1.5.13 at
`9uLUFf1W1zFoiWa4zhhJG9GzeYNKaHVKaHdQMp4BE64G`. It is not AAPLx or a Chinese
equity, has no redemption or dividend rights, and no swaps were executed by the
setup. DAMM v2 is the configured graduation destination; graduation is not tested.

The metadata study is committed in ORAKT v145's existing registry, record
`ASUhxBeGupwFHthJ9St8VBrZSLugXDj4f9vJhDC92Xkm`. Public canonical metadata and proof
are in `pilot-site/worker/meteora-demo.mjs` and `meteora-proof.mjs`. The website
reads finalized pool/config/mint/record accounts, checks ownership, fixed layouts,
network and hashes, and displays the observation time. No swaps, wallets, token
issuance or transaction signing are available in the web integration. RPC failure
is an explicit unavailable state, never synthetic balances. Reads are cached for
up to 60 seconds and do not require changing production secrets or payment flags.

The full SDK is dev-only due to its dependency surface and npm audit findings;
the hosted worker imports only a generated, bounded read-only layout. Tests compare
every primitive with the official Anchor decoder. That comparison is not an
independent security audit. No membership, account grant, payment switch, production
fund or mainnet deployment was changed by this integration.

## v145 security changes — Devnet acceptance passed

The new [v145 Devnet program](https://explorer.solana.com/address/2NkTGAB6peUsDzCxZQsyzntpAeuNuoveXe2kEsUKQFa4?cluster=devnet) passed 24 public-chain checks, including real synthetic-token renewal and guardian recovery. [Immutable acceptance evidence](devnet-deployment-v145.json) records finalized signatures, binary/source hashes and the final payment-OFF state. Local verification passed 14 Rust tests, 45 provenance/recovery runtime checks, 27 synthetic payment runtime checks, 3 fixture tests and 173 focused website/rendering checks. Mainnet remains unauthorized; this is not independent assurance.

- Governance is a separate, config-bound PDA. Payment authorization defaults OFF independently of publication and the global pause. A recovery proposal also disables payments.
- Current authority or a privileged backup guardian may nominate a replacement. Only that replacement can accept; the old authority then loses administration of the existing namespace. Cancellation keeps payments OFF. This is NOT a timelock or multisig: a compromised guardian is a takeover risk, and production requires independently controlled governance and upgrade keys.
- The server checks finalized subscription expiry before creating or preparing an order. A longer active manual, complimentary or legacy term is rejected with `existing_term_requires_migration`; no overlapping charge or invented on-chain credit is created. Explicit term migration is not implemented. Direct contract purchases cannot inspect off-chain grants; signed server quotes / migration policy remain a production review item.
- `ORAKT_PROTOCOL_GOVERNOR` pins the current authority for NEW payments. `ORAKT_PROTOCOL_RECONCILE_ENABLED=true` can permit verification of already-paid orders while `ORAKT_PROTOCOL_CHECKOUT_ENABLED` remains false. Both default OFF; reconciliation cannot prepare, sign or broadcast a payment. Existing deployment/code pins, wallet binding, account suspension and once-only settlement remain enforced. Operational pauses and authority rotation do not invalidate a previously finalized receipt; a code upgrade still requires explicit review. Preserve the saved policy when reconciling old orders.
- There is no always-on settlement indexer, automatic refund or automatic legacy-term migration. A retry or authorized operator reconciliation is still necessary after a service interruption.
- New acceptance uses a NEW Devnet program; `devnet-deployment.json` preserves v144 evidence. No mainnet deployment or production fee activation is authorized for this change.

For isolated public-chain acceptance dependencies: `npm install --prefix .tmp/orakt-devnet-v145/client --ignore-scripts @solana/spl-token@0.4.14 @solana/web3.js@1.98.4` from the repository root. Local disposable keys stay under ignored `.tmp`; never fund them on mainnet. Deployment scripts have a hardcoded Devnet genesis guard.

**Status: v144 deployed and acceptance-tested on Solana Devnet; mainnet NOT enabled, NOT independently audited.**
The program ID in `lib.rs` / `Anchor.toml` is a compilation fixture, not a live address. No program keypair, wallet secret, production account identifier, report body or licensed news text is included. Do not send funds to the fixture address.

Devnet program: [`PyvDP4Gg7TZUk7uzb9AQxNwPV7kTVmf3vwfSbgpsmsX`](https://explorer.solana.com/address/PyvDP4Gg7TZUk7uzb9AQxNwPV7kTVmf3vwfSbgpsmsX?cluster=devnet). [Public deployment and acceptance evidence](devnet-deployment.json) contains the binary/source hashes, deploy slot, config/upgrade authority, synthetic mint addresses and finalized test transactions. Chain bytes were compared with the 367,840-byte SBPFv3 build. Fourteen Devnet acceptance checks passed: six content kinds with inclusion proofs, two exact synthetic-token payments and duplicate-invoice simulation rejection, attributed review, immutable retraction, consented 24-hour trial, and pause/resume. The test wallets share one isolated operator; the review fixture is NOT independent assurance. Tests do not publish real research or grant production membership.

Only the fixture program ID and the two mint constants were substituted in the separate Devnet build; use the values in the manifest to reproduce its `lib.rs` SHA-256. `TEST_USDC` / `TEST_USDT` are synthetic test tokens, not issuer stablecoins. The disposable test operator retains upgrade and config authority. Production governance, independent review, fee approval, deployment pins and feature activation are separate release gates.

## Covered application boundaries

| ORAKT function | Contract instructions | What stays off-chain |
| --- | --- | --- |
| Company and cross-asset reports | `open_series`, `publish_version` | Full text, original evidence, private data and permission checks |
| Intelligence submissions | Same registry, kind 1 | Moderation, legal rights, spam control, factual verification |
| Evidence chains, Alpha factors, portfolios, AI drafts | Registry kinds 2–5 | Maps, inference, calculations, market feeds and all investment decisions |
| Review and correction history | `attest`, new version, `retract` | Reviewer identity assurance and substantive judgment |
| Monthly USDC / USDT access | `purchase` | Login/wallet ownership binding, server receipt verification, service availability |
| Optional account-trial proof | `issue_trial` | Eligibility, salted account commitments, unique-person / Sybil checks |
| Publishing governance | `initialize`, `set_roles`, `set_paused` | Operational approval and upgrade-authority governance |

The deployed website still uses its existing Memo provenance, payment verification and server trial implementation. These contracts do **not** silently migrate that system. The free web trial remains wallet-free and does not require paying rent or gas.

## Security model

- Every instance has a PDA `[config, authority]`. A stranger can create another instance but cannot administer the pinned ORAKT instance. Clients MUST pin both a verified deployed program ID and the operator's config PDA/authority; never accept these from a URL or a user-supplied receipt.
- Only explicitly permitted publishers create series/versions. Reviewer permission is separate, and authors cannot review themselves. Review verdicts are attributed statements, not an oracle certifying truth.
- Version creation is sequential and checks the previous hash. Each version, attestation and retraction is a separate immutable PDA; there are no close/delete instructions. Retraction remains available to the author during a pause. Revoked roles cannot write new versions, but their old statements remain attributable.
- Merkle roots commit selected evidence bytes. The contract neither downloads sources nor independently verifies the root's content. Use a documented off-chain canonicalization and retain inclusion proofs.
- Payments accept only the existing mainnet USDC/USDT mint addresses and classic SPL Token (not Token-2022, arbitrary token programs or transfer-hook tokens). Token ownership, mint, six decimals, recipient, duplicate accounts, amount, deadline, plan and term are checked. Funds transfer directly to the existing merchant wallet's token account. No token allowance, custody vault, auto-charge, yield or trading instruction exists.
- Prices are currently fixed at 19 / 79 stablecoin units, matching v140. A purchase quotes the exact amount and expires within ten minutes. Unique payer-scoped invoice PDAs reject replay. Transaction failure rolls back payment and receipt together.
- Signal and Research subscriptions use separate PDAs; buying Signal cannot erase Research. Calendar-month UTC expiry clamps month-end days; renewals extend an unexpired term. Indexers select the highest still-active entitlement and MUST still enforce server suspension and verified login/wallet ownership.
- Trial receipts require BOTH the operator authority's signature and the recipient wallet's consent. A salted account commitment may appear only once per instance. The authority pays account rent. This is a trust assumption, not proof of one human. Never derive public commitments from unsalted email addresses.
- Signing keys are not provisioned by this repository. An operator-controlled multisig / appropriate governance should own the upgrade authority and protocol authority. The fixed recipient does not prevent an upgrade authority from changing code; publish and monitor that authority before launch.

## Build and test

Pinned framework: Anchor 0.31.1, with a checked-in Cargo.lock. Install Rust, Solana CLI and Anchor using the official documentation; Windows normally uses WSL. The authoring machine currently has no such toolchain. [Actions run 38124334908](https://github.com/FULACK12/orakt/actions/runs/38124334908) passed host compilation, 13 unit tests, SBF compilation, IDL generation and 28 disposable local-validator checks. These runtime checks cover provenance, roles, immutable records and account trials, **not stablecoin fund transfers**. No test is an independent security audit. Subsequent runs lock the resolved dependencies and retain `target/idl/orakt_protocol.json` with the binary as a short-lived Actions artifact.

**Payment validation update, October 11, 2026:** [run 38143268037](https://github.com/FULACK12/orakt/actions/runs/38143268037), test-source commit `c6fb85c34fb76d5c40dc9bff21da3403b9ebbc3a`, passed all 13 Rust tests, 3 fixture tests, 28 provenance/trial runtime checks and **25 payment runtime checks**. SBF/IDL generation also passed. This closes the initial local payment-flow test gap, not the independent-audit or production-deployment gates. Historical failed workflow runs remain available; their notification emails do not describe the latest run.

The legacy CI run produced SBPFv0 for its local validator. **v144 supersedes that build**: Rust 1.95.0, cargo-build-sbf 4.4.0 and platform-tools v1.57 now explicitly target SBPFv3. The new binary, IDL build, 14 host tests, 3 fixture checks, 33 provenance/permission/trial checks and 25 payment checks passed locally on Agave 4.3.0 on October 11, 2026. These are observed local results, not a claim that the next GitHub Actions run has completed.

```sh
cd contracts/solana
cargo test --workspace --locked
cargo build --workspace --release --locked
# On a compatible Solana/Anchor workstation:
anchor build
```

Before deployment, an operator must generate and securely retain a program keypair and run `anchor keys sync` to replace the compilation fixture ID. Do not upload `target/deploy/*-keypair.json`. There is deliberately no mainnet deploy workflow or automatic deploy command.

### Isolated payment test ledger

`tests/start-validator.mjs` boots the pinned disposable Docker validator with 13 **synthetic genesis accounts**, including fixed-supply mint fixtures at the contract's allowlisted addresses. These balances are not issuer USDC/USDT, not a clone of production holdings and not transferable to any public chain. Test signing keys derive from explicitly public test labels; never fund them. No Phantom secrets or real merchant keys are read. The RPC is hardcoded to loopback and the test verifies the expected fixture balances before signing.

`tests/payments.mjs` exercises the actual SPL transfer CPI, exact payment and receipt fields, sequential UTC calendar-month renewal, lower-tier isolation, invoice replay, amount/term/deadline rejection, wrong mint/owner/recipient/token program, substituted PDAs and pause enforcement. Insufficient-balance and frozen-source cases are submitted with preflight disabled **only on this local ledger**; the test requires a confirmed failing transaction, unchanged token balances/entitlements and absent new receipts. The network fee of a failed local transaction is intentionally not asserted to roll back. Fixture encoding also has three independent Node tests. Inspect the latest Actions result for the runtime outcome; code coverage claims are not a security audit.

## Historical v141–143 release gates

This list records earlier release boundaries. The v144 section below supersedes the build, checkout and test-integration entries; independent review and production approval remain outstanding.

1. Host compile/unit tests and the locked-dependency reruns passed (linked above).
2. SBF and IDL generation passed for the legacy local-validator target. A current-cluster-compatible build remains required; the fixture binary must not be deployed as-is.
3. The 28 provenance/permission/trial and 25 local payment checks passed, including actual failed-transfer rollback, duplicate invoices, amount checks, wrong mint/recipient/token program and renewals. Still required: broader adversarial/fuzz coverage, malformed decimals/account data, reinitialization, expired-term runtime tests, suspension integration and concurrency tests. These cases do not establish exhaustive coverage.
4. Independent contract/security review; resolve findings and document program upgrade authority.
5. Current payment tests use synthetic local-genesis fixtures. Public test-network deployment is still pending; **never describe a fake mint as issuer USDC/USDT**. The current fixed mainnet mints cannot simply be used as Devnet currencies. Choose and review an explicit test-only build configuration before Devnet payment tests.
6. A default-off, administrator-only read-only receipt verifier is implemented in website v142, with explicit wallet ownership linking in v143. Synthetic RPC and account-database tests do not establish live-network integration. A durable indexer, reviewed deployment pins, contract checkout and atomic entitlement settlement remain required before switching production entitlements.
7. Quote program rent + transaction fees from the built binary and target RPC. Obtain the owner's network/budget approval and wallet signatures. Register actual program/config addresses and deployment signatures in the public manifest only after verification.

The contracts are useful source deliverables, not a claim of production readiness, decentralized AI or verified investment performance.

## Website receipt preview (v142, default off)

`pilot-site/worker/protocol-receipt.mjs` validates a candidate custom-program purchase without modifying membership, billing orders or membership audit records. It is separate from the existing live SPL-transfer checkout. The endpoints are administrator-only:

- `GET /api/billing/protocol-status` reports configuration status, not a live deployment attestation.
- `POST /api/billing/protocol-preview` accepts only `{orderId, signature}` with the authenticated same-origin session and `X-ORAKT-Billing: checkout`. It is rate-limited to six requests per minute per administrator. Successful output always includes `mode: admin_read_only` and `grantsAccess: false`; request-throttling counters and ordinary account activity metadata may change, not membership grants or payment state.

No production flag or deployment pin is supplied by this release. Enabling a separately reviewed deployment requires all of `ORAKT_PROTOCOL_PREVIEW_ENABLED=true`, `ORAKT_PROTOCOL_PROGRAM_ID`, `ORAKT_PROTOCOL_AUTHORITY`, `ORAKT_PROTOCOL_UPGRADE_AUTHORITY` (address or literal `none`), and positive integer `ORAKT_PROTOCOL_DEPLOY_SLOT`. The compilation fixture program ID is rejected. The verifier derives config, receipt, subscription and upgradeable-loader ProgramData PDAs; it pins the mainnet genesis, finalized status/slot, loader ownership, deployment slot and upgrade authority. An upgrade invalidates the pin and requires operator review. A configured pin is a trust assumption, not an independent binary audit or trustless RPC proof.

Only a pending server-created one-calendar-month order is supported. Invoice bytes are SHA-256 of UTF-8 `JSON.stringify(["orakt-contract-order-v1", order.id, order.member_id, order.reference])`; no email is committed. The target must be an active account whose proven Phantom login subject equals the payer, or (since v143) whose durable, explicitly signed wallet binding matches the payer. A revoked or differently owned address cannot fall back to a Phantom login proof. Connecting a wallet in the admin panel alone is not ownership binding. The preview rechecks binding identity after RPC reads and rejects an observed change.

Verification checks the top-level purchase instruction and all nine account positions, strict Anchor account sizes/discriminators/bumps, mint/amount/plan/invoice, fixed merchant and exact source/destination token-balance deltas. Transaction block time and receipt Clock time must both fall in the original order window, differ by at most 60 seconds, and satisfy the contract's ten-minute deadline bound. Receipt expiry must still be active; a later subscription renewal does not extend the returned receipt entitlement. Finalized account reads must not predate the transaction; program metadata is re-read after the receipt snapshot. The server also re-reads the account and order to reject observed changes during RPC verification. This is a read-only snapshot, **not** a concurrency-safe entitlement grant.

Run from `pilot-site`: `node --test tests/protocol-receipt.test.mjs tests/billing.test.mjs tests/membership.test.mjs tests/wallet-auth.test.mjs tests/account-trial-v140.test.mjs tests/account-state.test.mjs`. The 55 new preview checks use synthetic RPC/account fixtures, never public-network transactions; the combined focused suite has 99 tests. Neither these fixtures nor a successful preview authorize funding, deployment, account upgrades or automatic renewal.

## v143 account wallet ownership linking

The bilingual account-center panel uses two separate clicks: connect/review, then sign the exact displayed message. `POST /api/account/wallet` requires an authenticated active account, exact Origin, a custom CSRF header and a bounded JSON body. A challenge commits its link/unlink action, durable account ID, wallet, origin, random nonce and five-minute expiry. Its HttpOnly Secure SameSite=Strict browser cookie and account revision are verified server-side. Ed25519 verification happens before a single transactional batch rechecks the live challenge, account status/revision, address ownership and one-active-wallet-per-account uniqueness. The batch updates binding state, appends its signature audit and consumes the challenge. Logout cancels pending browser challenges; concurrent verification and stale unlink proofs cannot reuse them.

The signature, exact signed message, account/wallet identifiers and timestamp stay in the private server audit, not on-chain. GET exposes only the current account's binding and ten recent action summaries. Signing proves wallet control, not that the person is unique. This is **not account merging or a new sign-in method**: a wallet with a separate Phantom account is rejected rather than silently transferred. A Phantom account links only its sign-in wallet. Linking/unlinking never changes grants, existing orders, site merchant address or live SPL checkout. Unlink also requires the bound wallet's signature; unexpired pending orders block it. Expired quotes are preserved and do not lock the wallet forever. Lost-wallet recovery and explicit account merging remain separate, unimplemented workflows.

Migration `0016_dizzy_logan.sql` only appends three tables and their indexes. Prior migrations and billing/account records are unchanged. The v143 focused plus rendered suite passed 161 tests, including 22 new binding/client tests using temporary Ed25519 keys and synthetic SQLite identities and two additional receipt-bridge tests. Desktop and 390px Chinese/English layouts were checked with a synthetic read-only local preview; an actual user Phantom signing ceremony was not performed. No real network transaction or SOL expenditure occurred. The custom-contract preview remains default-off and automatic custom-contract entitlement settlement is still unimplemented.

## v144 contract checkout and evidence inclusion

The website implements separately gated `/api/billing/protocol/orders`, `/prepare`, and `/verify` routes. `ORAKT_PROTOCOL_CHECKOUT_ENABLED=true` additionally requires all reviewed deployment pins used by the receipt verifier; it is **not enabled by this release**. Production settlement remains mainnet-only. Devnet receipts cannot unlock production accounts. Legacy SPL checkout rejects contract orders in its preparation, verification and settlement paths.

Each contract order freezes the verified wallet binding and deployment identity, reserves a ten-minute invoice and records receipt/subscription PDAs. Preparation validates the deployed program and authority, requires an existing merchant token account, checks balance and rent, simulates exactly one purchase instruction and returns an unsigned transaction. Only the user's wallet signs/sends. Uncertain outcomes are reconciled using the original receipt address, never by automatically sending a second payment.

A single database transaction writes the settled order, unique receipt/signature record, membership revision and audit. It rechecks the active account revision and exact binding. A failure rolls back every write. Retries cannot grant another term. Access mirrors the contract receipt expiry, preserving a longer same-tier grant, rather than adding a month during late reconciliation. A conflicting active tier requires support reconciliation instead of silently overwriting access. This is explicit-request reconciliation, not an always-on background indexer. Migration 0017 adds two tables and a constant-default payment-method column; existing records/migrations remain intact.

The new `verify_evidence` instruction verifies up to 16 sorted-pair Merkle siblings against an immutable record and emits `EvidenceVerified`, without mutating the record. V1 leaves are SHA-256(`UTF8("orakt-evidence-leaf-v1") || leaf_hash`), where `leaf_hash` is a nonzero SHA-256 commitment to retained evidence bytes. Parents are SHA-256(`UTF8("orakt-evidence-node-v1") || min(left,right) || max(left,right)`). A single leaf has an empty proof. Keep the canonical source bytes and proof off-chain. Inclusion proves neither truth, licensing rights, audit approval nor investment performance.

`tests/build-v3.sh` targets SBPFv3 and downloads checksum-pinned Agave 4.3.0. `tests/prepare-devnet.mjs` creates a separate ignored workspace with disposable test-only operator/program keys and clearly synthetic `TEST_USDC`/`TEST_USDT` mints. It replaces only the fixture ID and mint constants in the isolated build. Mainnet constants, user wallets and production grants are unchanged. Generated secrets are never exported. Preparing an address or binary is not deployment. The user obtained 5 free Devnet SOL after the automatic faucet was rate-limited. Never send mainnet SOL to test identities.

Agave 4's local validator requires a concrete container bind address and `io_uring`. The test launcher derives the container IP, retains a checksum-pinned Docker default seccomp policy with only the three `io_uring` calls added, uses read-only source mounts and publishes only loopback RPC ports. No privileged container or host-wide security change is used. Earlier startup failures were environmental; they were not counted as passing tests.

The website's focused v144 suite passed 181 tests, including 18 contract-checkout tests: concurrency, duplicate callbacks, binding changes, suspension races, pin changes, exact instruction data, receipt recovery, and transaction rollback after an injected database failure. Tests use synthetic local accounts/RPC; they do not grant actual production access. No independent security audit has been performed.

Official build guidance: https://github.com/anza-xyz/cargo-build-sbf#sbfpv3-migration. Validator: https://github.com/anza-xyz/agave/releases/tag/v4.3.0. An architecture check and passing runtime tests are not an independent security audit.

## References

- https://www.anchor-lang.com/docs/references/account-constraints
- https://www.anchor-lang.com/docs/tokens/basics/transfer-tokens
- https://solana.com/docs/programs/deploying
