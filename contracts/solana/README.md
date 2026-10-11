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

Pinned framework: Anchor 0.31.1, with a checked-in Cargo.lock. Install Rust, Solana CLI and Anchor using the official documentation; Windows normally uses WSL. The authoring machine currently has no such toolchain. Host compilation and 13 unit tests passed in GitHub Actions. CI also attempts an SBF/IDL build and a disposable local-validator suite; inspect the actual workflow conclusion, not just this configuration, before treating them as passed. No test is an independent security audit.

The CI build pins Rust 1.95.0, cargo-build-sbf 4.4.0 and platform-tools v1.57. Its SBPFv0 output is for the pinned legacy local validator only; it is **not a production deployment artifact**. A current-cluster-compatible SBPFv3 migration/build and runtime tests are an additional release gate before public-chain deployment.

```sh
cd contracts/solana
cargo test --workspace
cargo build --workspace --release
# On a compatible Solana/Anchor workstation:
anchor build
```

Before deployment, an operator must generate and securely retain a program keypair and run `anchor keys sync` to replace the compilation fixture ID. Do not upload `target/deploy/*-keypair.json`. There is deliberately no mainnet deploy workflow or automatic deploy command.

## Required release gates (not yet satisfied)

1. Successful host compile/unit tests and reproducible locked dependencies.
2. Successful `anchor build`, generated IDL and SBF binary hash.
3. Local-validator / LiteSVM integration tests covering actual signatures, PDA/account substitution, role revocation, duplicate receipts, underpayment, wrong mint/recipient/token program, transfer failure atomicity, reinitialization, suspension and concurrent publishes.
4. Independent contract/security review; resolve findings and document program upgrade authority.
5. Devnet deployment using clearly identified test assets, or cloned mainnet mint accounts in a local validator; **never describe a fake mint as issuer USDC/USDT**. The current fixed mainnet mints cannot simply be used as Devnet currencies. Choose and review an explicit test-only build configuration before Devnet payment tests.
6. Implement and test a pinned-deployment server indexer / finalized-receipt verifier and authenticated wallet binding before switching production entitlements.
7. Quote program rent + transaction fees from the built binary and target RPC. Obtain the owner's network/budget approval and wallet signatures. Register actual program/config addresses and deployment signatures in the public manifest only after verification.

The contracts are useful source deliverables, not a claim of production readiness, decentralized AI or verified investment performance.

## References

- https://www.anchor-lang.com/docs/references/account-constraints
- https://www.anchor-lang.com/docs/tokens/basics/transfer-tokens
- https://solana.com/docs/programs/deploying
