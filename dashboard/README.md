# JARVIS Wallet Dashboard (experimental)

The repository is a Python 3.12 scanner and report generator; it did not previously contain a web dashboard, JavaScript package manifest, or wallet-adapter integration. This is a separate Vite/React dashboard under `dashboard/`. Scanner code and scheduled report generation remain unchanged. The earlier attempt added malformed filenames rather than usable module files; this standalone app is the corrected integration path and does not rely on those files.

## Run locally

```bash
cd dashboard
npm install
npm run dev
```

Optional configuration in `dashboard/.env.local`:

```dotenv
VITE_SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
VITE_JUPITER_API_KEY=your-Jupiter-key
```

Never commit `.env.local`. Vite variables are bundled into public browser code: do not treat a frontend Jupiter key as secret. Prefer a rate-limited same-origin proxy for production. The dashboard requires browser access to the configured Solana RPC and Jupiter Swap API v2 endpoints.

Build/checks:

```bash
npm run build
npm run lint
npm test
```

## Implemented

- Official Phantom and Solflare wallet-adapter packages; auto-connect is disabled.
- Public wallet address, SOL balance, and first 12 SPL Token Program balances (not Token-2022).
- Jupiter Swap API v2 order preview with SOL input, validated mint, slippage (max 300 bps), and a default 0.1 SOL position cap.
- PAPER is the default and only presents a quote; no wallet signing or transaction submission in PAPER.
- LIVE path is a manual user-triggered flow: a per-order checkbox, RPC simulation, explicit browser review, then wallet-adapter `signTransaction`, followed by Jupiter `/execute` and RPC confirmation. No background or unattended signing is implemented. Wallets should show their own transaction approval prompt.
- Mint/freeze authority check from parsed mint account where available; price-impact warning and explicit missing-liquidity warning.
- Scanner report/state links are integrated without changing scanner execution.

## Important gaps and safety boundaries

- No real swaps were executed in development. Live submission has not been validated against funded wallets or network conditions.
- Jupiter API access, required API-key policy, response schema, and order expiry are subject to Jupiter's current docs/terms. Configure/test with an approved key and check those requirements before deployment. Failed `/execute` calls may have ambiguous landing status; check the wallet/explorer before retrying.
- Quote does not currently return a verified liquidity value in this interface; liquidity and sellability therefore remain unknown and are warned, not assumed safe. Authority parsing does not inspect Token-2022 extensions, holder concentration, transfer restrictions, or all rug risks.
- The SPL balance list only queries the original SPL Token Program, not Token-2022.
- Dashboard is a browser UI and not hosted by GitHub Actions. Deploy as static site with HTTPS; RPC and API requests go directly from browser. Set restrictive CSP and consider a rate-limited same-origin proxy. Do not store wallet secrets or API keys in the repository.
- The isolated quote endpoint integration cannot guarantee simulation covers every provider-specific execution path; verify current Jupiter transaction flow before enabling LIVE in a production environment.

Never put a seed phrase/private key into JARVIS. Disconnect or reject any wallet prompt that does not match your own review. This tool is informational software, not investment advice.
