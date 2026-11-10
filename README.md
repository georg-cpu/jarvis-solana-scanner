# JARVIS Solana Trend Scanner v1

Scans public DEX Screener discovery endpoints every 15 minutes (best effort) using GitHub Actions. No wallet, private keys, trade execution or AI costs.

## Setup
1. Create a GitHub repository (public is simplest for free Actions use).
2. Upload `scanner.py`, `README.md`, and `.github/workflows/scan.yml` preserving the folder structure. Do not upload secrets.
3. Under **Settings > Actions > General > Workflow permissions**, allow **Read and write permissions** if available. Alternatively configure a fine-grained token securely; do not put it in the repo.
4. Open **Actions > JARVIS Solana Scanner > Run workflow** for the first run.
5. Read `report.md` and `state.json` in your repository. GitHub scheduled runs can be delayed or skipped, and scheduled workflows on public repos may be disabled after 60 days of inactivity.

## Limits
- This is **not full-market coverage**. The DEX Screener latest-profile and boost feeds are a partial, promotion-biased sample.
- Scoring is a transparent heuristic, not a prediction. No holder concentration, mint/freeze authority, deployer, liquidity lock or honeypot/sellability validation is performed.
- Every result is WATCH/NO TRADE. No entry/SL/TP levels without validated market structure and safety checks.
- GitHub commit permissions may be restricted by organizational policy; the scan may succeed but report push fail.
- API errors are listed in the report; the workflow should be monitored.
- To integrate Telegram/Discord alerts, add a separately reviewed notifier and store credentials in GitHub Actions Secrets. ChatGPT automations cannot be triggered directly by this workflow without an additional supported integration.

Sources: https://docs.dexscreener.com/api/reference and https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
