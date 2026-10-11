# ORAKT — Evidence-linked intelligence

## v144: contract orders and evidence inclusion

This update adds signed-wallet-bound contract orders, pinned-program transaction preparation and atomic replay-safe membership settlement. A unique finalized receipt/signature can be credited only once; retries do not add another month. Legacy SPL payments are isolated. Production contract checkout remains disabled pending reviewed deployment and real-network validation. The new Rust `verify_evidence` instruction checks a bounded Merkle inclusion proof, not truth or investment quality. SBPFv3 builds and separate Devnet-only preparation scripts are included. Preparing a program address is not deployment; generated test keys, test state and private member records are excluded from this repository. No mainnet deployment or expense is authorized by these source changes.

**Devnet is now deployed and acceptance-tested:** [inspect the actual program](https://explorer.solana.com/address/PyvDP4Gg7TZUk7uzb9AQxNwPV7kTVmf3vwfSbgpsmsX?cluster=devnet) and [public deployment/transaction evidence](contracts/solana/devnet-deployment.json). Finalized chain bytes match the SBPFv3 build. Fourteen Devnet checks passed across six registry kinds, inclusion proofs, synthetic-token receipts, duplicate rejection, review/retraction, trial and pause/resume. Local validation passed 14 Rust tests, 3 fixture tests, 33 provenance/trial checks, 25 payment checks and 181 focused website checks. Public test-network tokens are NOT issuer USDC/USDT, do not unlock production memberships, and no mainnet funds were spent. This is not an independent security audit. Earlier v141–143 status descriptions below are historical; this section supersedes their unimplemented checkout and undeployed testnet status.

ORAKT connects company disclosures, event evidence, research reports and verifiable submission histories. Product: https://orakt.com

[![Solana contract checks](https://github.com/FULACK12/orakt/actions/workflows/solana-contracts.yml/badge.svg?branch=main)](https://github.com/FULACK12/orakt/actions/workflows/solana-contracts.yml)

## Honest project and hackathon scope

ORAKT existed before this repository export. This is **not a claim that the complete application was written during a hackathon**. Competition name and eligible dates are awaiting the project owner's confirmation. No prior commit dates have been rewritten. A dated, reviewable change list must be supplied before submission to Colosseum.

This source-only export was synchronized on October 11, 2026. The v140 application was synchronized first (`dbdef7b`); the subsequent v141 website source (`4b3bbd8b720c25b184c47cd11d978bdab4c8761b` in Sites) adds a bilingual experimental-contract disclosure. It includes the existing application and subsequent changes; this synchronization date is not a claim about when every file was originally written. Earlier rejected report attempts remain rejected unless separately reviewed; updating this repository does not approve research results.

## Latest synchronized features

- Bilingual research workspace, company-report review and fiscal-period checks, source-linked evidence reading, improved map controls and responsive landing-page layout.
- Apple supply-atlas implementation, AAPLx on-chain asset research, and a sourced Hormuz–helium–semiconductor study with conditional investment hypotheses, three map branches, source inspection and user-controlled mechanism playback. Candidate routes are not real-time cargo tracking or confirmed procurement relationships.
- Alpha-factor study and research UI, with explicit benchmark, methodology and validation limits. Research examples are not guaranteed returns or approved investment signals.
- Intelligence-market Solana interactions, account administration and tier gates, and monthly USDT/USDC payment implementation with server-side settlement checks. Billing availability requires operator configuration; this source export does not activate payments or contain merchant signing keys.
- Account-linked Ask ORAKT research jobs, processed by a separately operated local `orakt-14b` worker. Research allows five jobs daily and one active job; the worker must be online. Outputs are unreviewed drafts, not investment approval. Model weights, bridge credentials and private evidence packs are not included.
- A once-per-account, explicitly claimed 24-hour Research trial, server-enforced and separate from paid grants; no payment or automatic renewal. Admin-only Phantom connection reads the public address and finalized SOL balance without automatic signing, transfers or login-identity linking.
- Administrator-controlled Solana mainnet Memo provenance preparation and finalized-receipt verification for reports, separate from the original Devnet submission workflow. This implementation is not a custom deployed ORAKT smart contract; hashes prove version integrity, not truth.

The v140 production-source build and 38 rendered-page tests passed locally. The focused account/research suite passed 25/25; the full application suite reported 335/340 passing, with five existing landing-page/educational-copy assertion failures. Those results require the provisioned production inputs described below; they are not a claim that this deliberately data-excluded export can run the entire suite unmodified.

For v141, the production-source build, 40 focused disclosure/rendered-page tests and 22 existing billing/trial/news regressions passed. [Contract Actions run 38124334908](https://github.com/FULACK12/orakt/actions/runs/38124334908) passed host compilation, 13 Rust unit tests, SBF/IDL generation and 28 local-validator provenance/permission/trial checks. Payment VM tests, independent audit, current-public-cluster binary compatibility and production receipt integration remain release gates. No custom contract has been deployed. The website links the source, checks and unsatisfied release gates at https://orakt.com/#protocol.

Subsequent [payment validation run 38143268037](https://github.com/FULACK12/orakt/actions/runs/38143268037) passed **25 additional payment checks** and 3 fixture tests, while repeating the 13 Rust and 28 provenance/trial checks successfully. Payments execute against synthetic local-genesis balances, not issuer stablecoins or a public network. Wrong payment inputs, replay, renewal, tier isolation and actual failed-transfer rollback were checked. Independent audit, broader adversarial coverage, production receipt integration and deployment approval remain outstanding. Existing live payments are unchanged; this update spent no real SOL.

## Architecture

### v142 receipt-verification bridge

The v142 release adds an administrator-only, default-off **read-only** custom-contract receipt verifier. It checks pinned mainnet program/config/deployment/upgrade authority, finalized transaction and account snapshots, exact order/mint/payment fields and proven wallet ownership. It does not sign transactions, deploy contracts, settle an order or grant access. Existing checkout and trials are unchanged. Its original 55 synthetic preview checks and 99-test focused suite passed locally. Public-chain deployment, an indexer and atomic custom-contract entitlement settlement remain outstanding. See `contracts/solana/README.md` for configuration and boundaries.

### v143 explicit wallet ownership

The account center now separates wallet connection, visible message review and explicit signing. Five-minute single-use Ed25519 proofs bind one wallet to an authenticated account, with same-origin/browser/account checks, atomic uniqueness, signed unlinking and private audit history. This is not login-provider merging, payment authorization, an automatic membership grant or an on-chain transaction. Wallets belonging to a separate Phantom account are rejected; lost-wallet recovery is not implemented. The receipt preview can use this durable binding and rejects an observed revocation during verification. All 161 focused/rendered tests passed locally; the 22 new binding tests use temporary keys and synthetic accounts. Chinese/English desktop and mobile layout checks used a read-only local fixture, not a real-wallet signing session. Production migrations add only new tables; existing grants and checkout are preserved.

### Experimental custom contracts (not deployed)

`contracts/solana` contains a new Anchor program candidate for versioned report/news/chain/factor/portfolio/AI-draft commitments, attributed reviews and retractions, SPL-stablecoin membership receipts, and optional operator-attested account trial receipts. The website still uses the existing live services; these candidate contracts are not a claim of deployed or audited infrastructure. See the contract README and CI for exact release gates. No live signing key or deployment authorization is included, and AI/factual review stays off-chain.

- `backend/app`: Python / FastAPI research, ingestion, source retention and local-model orchestration.
- `backend/app/sec_bulk_import.py`: bounded, resumable ingestion of retained official SEC ZIP archives, SHA-256 checks and raw member CRC validation. Quarter and YTD variants are preserved on cold storage, not merged under a legacy unique key.
- `backend/app/sec_cold_facts.py`: filing/date-filtered retrieval for new report evidence packets.
- `backend/app/disclosure_reports.py`: immutable accession-linked factual reviews with native-unit, comparable-period arithmetic; missing operating/valuation evidence stays explicit.
- `backend/app/research_lab_export.py`: reproducible price-path reference experiments and descriptive FOMC/payroll windows. No causal certification, model training or claimed forward Alpha.
- `pilot-site/app`: bilingual React workspace: event map, evidence reports, portfolio lab, intelligence market and market charts.
- `pilot-site/worker`: Cloudflare Worker identity, authorization, publication and intelligence provenance APIs.
- `pilot-site/worker/intelligence-market.mjs`: original-byte hashes, immutable version history, independent review and opt-in Solana **Devnet** receipts. A receipt proves integrity/signing, not truth.

## Current limits

- Automated structural validation is not factual approval. Rejected drafts are retained and must not be published automatically.
- Historical reports are retrospective reconstructions. They cannot count as contemporaneous predictions or independently validated Alpha.
- Portfolio stress scenarios are manually supplied assumptions, not return forecasts or backtests.
- Chart data is provided by TradingView and may be delayed. This is not a market-data redistribution API.
- No embedded mainnet tokenized-stock execution. Provider credentials, issuer mint verification, eligibility, simulation and explicit wallet approval remain required.
- Reputation is computed off-chain from reviewed records, is non-transferable and is not a minted financial asset.

## Source-only export and setup

Production secrets, account records, private reports, licensed news full text, cold archives, generated bundles, database files and deployment credentials are intentionally absent. Existing production Git history is not included. `source-manifest.json` lists exported file hashes; an automated secret scan is not a guarantee of exhaustive review.

Backend environment: Python 3.12+, PostgreSQL, optional local Ollama. See `backend/pyproject.toml` for dependencies. Set deployment-specific credentials in environment variables, never source code. Cold SEC archives and their manifests must be supplied separately; the import command does not download or fabricate them.

Example importer (operator-controlled paths):

```sh
PYTHONPATH=backend python -m app.sec_bulk_import --root /your/cold/sec/bulk/date --limit 10
```

Create `pause-import` in that archive directory to stop safely at the next company boundary. The ZIPs remain immutable. PostgreSQL writes only absent, unambiguous rows; completed issuers can be resumed.

Frontend: Node 22.13+ and the versions in `pilot-site/package.json`. Pure-module tests such as `node --test tests/portfolio-math.test.mjs` do not require private datasets. **A full production build requires separately provisioned, rights-cleared snapshot and report-index inputs**; they are deliberately not bundled in this export. Do not claim this export is a populated production database or a complete offline demo.

## Review and licensing

The repository visibility, source-code license and competition dates are owner decisions. No third-party data redistribution rights are implied. Dependency licenses remain with their respective owners. This initial export does not assign a new open-source license to the owner's code.
