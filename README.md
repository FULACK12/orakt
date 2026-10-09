# ORAKT — Evidence-linked intelligence

ORAKT connects company disclosures, event evidence, research reports and verifiable submission histories. Product: https://orakt.com

## Honest project and hackathon scope

ORAKT existed before this repository export. This is **not a claim that the complete application was written during a hackathon**. Competition name and eligible dates are awaiting the project owner's confirmation. No prior commit dates have been rewritten. A dated, reviewable change list must be supplied before submission to Colosseum.

This source-only export was synchronized on October 9, 2026, through the deployed ORAKT v138 application (Sites source commit `31c7fb219b0e0fe631419c894c1a26a416cac4ff`). It includes the existing application and subsequent changes; this synchronization date is not a claim about when every file was originally written. Earlier rejected report attempts remain rejected unless separately reviewed; updating this repository does not approve research results.

## Latest synchronized features

- Bilingual research workspace, company-report review and fiscal-period checks, source-linked evidence reading, improved map controls and responsive landing-page layout.
- Apple supply-atlas implementation, AAPLx on-chain asset research, and a sourced Hormuz–helium–semiconductor study with conditional investment hypotheses, three map branches, source inspection and user-controlled mechanism playback. Candidate routes are not real-time cargo tracking or confirmed procurement relationships.
- Alpha-factor study and research UI, with explicit benchmark, methodology and validation limits. Research examples are not guaranteed returns or approved investment signals.
- Intelligence-market Solana interactions, account administration and tier gates, and monthly USDT/USDC payment implementation with server-side settlement checks. Billing availability requires operator configuration; this source export does not activate payments or contain merchant signing keys.
- Redesigned account/billing screens and Ask ORAKT, a browser-local chat demo with local history. It does not call a live model, queue research work or charge an account.

The v138 production-source build passed locally. The focused Hormuz/Apple regression suite passed 9/9; the full application suite reported 319/324 passing, with five existing landing-page/educational-copy assertion failures. Those results require the provisioned production inputs described below; they are not a claim that this deliberately data-excluded export can run the entire suite unmodified.

## Architecture

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
