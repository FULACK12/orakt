# ORAKT Protocol — experimental Solana contracts

**Status: implementation candidate; NOT deployed, NOT independently audited.**
The program ID in `lib.rs` / `Anchor.toml` is a compilation fixture, not a live address. No program keypair, wallet secret, production account identifier, report body or licensed news text is included. Do not send funds to the fixture address.

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

The CI build pins Rust 1.95.0, cargo-build-sbf 4.4.0 and platform-tools v1.57. Its SBPFv0 output is for the pinned legacy local validator only; it is **not a production deployment artifact**. A current-cluster-compatible SBPFv3 migration/build and runtime tests are an additional release gate before public-chain deployment.

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

## Release gates and remaining work

1. Host compile/unit tests and the locked-dependency reruns passed (linked above).
2. SBF and IDL generation passed for the legacy local-validator target. A current-cluster-compatible build remains required; the fixture binary must not be deployed as-is.
3. The 28 provenance/permission/trial and 25 local payment checks passed, including actual failed-transfer rollback, duplicate invoices, amount checks, wrong mint/recipient/token program and renewals. Still required: broader adversarial/fuzz coverage, malformed decimals/account data, reinitialization, expired-term runtime tests, suspension integration and concurrency tests. These cases do not establish exhaustive coverage.
4. Independent contract/security review; resolve findings and document program upgrade authority.
5. Current payment tests use synthetic local-genesis fixtures. Public test-network deployment is still pending; **never describe a fake mint as issuer USDC/USDT**. The current fixed mainnet mints cannot simply be used as Devnet currencies. Choose and review an explicit test-only build configuration before Devnet payment tests.
6. A default-off, administrator-only read-only receipt verifier is implemented in website v142; its synthetic RPC and account-database tests do not establish live-network integration. A durable indexer, reviewed deployment pins, contract checkout, authenticated cross-provider wallet linking and atomic entitlement settlement remain required before switching production entitlements.
7. Quote program rent + transaction fees from the built binary and target RPC. Obtain the owner's network/budget approval and wallet signatures. Register actual program/config addresses and deployment signatures in the public manifest only after verification.

The contracts are useful source deliverables, not a claim of production readiness, decentralized AI or verified investment performance.

## Website receipt preview (v142, default off)

`pilot-site/worker/protocol-receipt.mjs` validates a candidate custom-program purchase without modifying membership, billing orders or membership audit records. It is separate from the existing live SPL-transfer checkout. The endpoints are administrator-only:

- `GET /api/billing/protocol-status` reports configuration status, not a live deployment attestation.
- `POST /api/billing/protocol-preview` accepts only `{orderId, signature}` with the authenticated same-origin session and `X-ORAKT-Billing: checkout`. It is rate-limited to six requests per minute per administrator. Successful output always includes `mode: admin_read_only` and `grantsAccess: false`; only request-throttling counters may change.

No production flag or deployment pin is supplied by this release. Enabling a separately reviewed deployment requires all of `ORAKT_PROTOCOL_PREVIEW_ENABLED=true`, `ORAKT_PROTOCOL_PROGRAM_ID`, `ORAKT_PROTOCOL_AUTHORITY`, `ORAKT_PROTOCOL_UPGRADE_AUTHORITY` (address or literal `none`), and positive integer `ORAKT_PROTOCOL_DEPLOY_SLOT`. The compilation fixture program ID is rejected. The verifier derives config, receipt, subscription and upgradeable-loader ProgramData PDAs; it pins the mainnet genesis, finalized status/slot, loader ownership, deployment slot and upgrade authority. An upgrade invalidates the pin and requires operator review. A configured pin is a trust assumption, not an independent binary audit or trustless RPC proof.

Only a pending server-created one-calendar-month order is supported. Invoice bytes are SHA-256 of UTF-8 `JSON.stringify(["orakt-contract-order-v1", order.id, order.member_id, order.reference])`; no email is committed. The target must be an active account whose **proven Phantom login subject** equals the payer. Connecting a wallet in the admin panel is not this proof. Google/local accounts are intentionally rejected until secure explicit identity linking exists.

Verification checks the top-level purchase instruction and all nine account positions, strict Anchor account sizes/discriminators/bumps, mint/amount/plan/invoice, fixed merchant and exact source/destination token-balance deltas. Transaction block time and receipt Clock time must both fall in the original order window, differ by at most 60 seconds, and satisfy the contract's ten-minute deadline bound. Receipt expiry must still be active; a later subscription renewal does not extend the returned receipt entitlement. Finalized account reads must not predate the transaction; program metadata is re-read after the receipt snapshot. The server also re-reads the account and order to reject observed changes during RPC verification. This is a read-only snapshot, **not** a concurrency-safe entitlement grant.

Run from `pilot-site`: `node --test tests/protocol-receipt.test.mjs tests/billing.test.mjs tests/membership.test.mjs tests/wallet-auth.test.mjs tests/account-trial-v140.test.mjs tests/account-state.test.mjs`. The 55 new preview checks use synthetic RPC/account fixtures, never public-network transactions; the combined focused suite has 99 tests. Neither these fixtures nor a successful preview authorize funding, deployment, account upgrades or automatic renewal.

## References

- https://www.anchor-lang.com/docs/references/account-constraints
- https://www.anchor-lang.com/docs/tokens/basics/transfer-tokens
- https://solana.com/docs/programs/deploying
