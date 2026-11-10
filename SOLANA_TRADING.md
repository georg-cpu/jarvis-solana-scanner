# Solana Wallet Connect & Safe Trading Module

This repository is a Python-based Solana scanner with data collection and risk signals. To preserve the scanner while adding a secure wallet/trading layer, the project now includes a safety-first trading module that keeps the scanner intact and prevents live execution without explicit user consent.

## Security model

- Default mode is PAPER.
- LIVE mode requires explicit activation and explicit wallet approval for every transaction.
- Seed phrases and private keys are never accepted, stored, or logged.
- Only public wallet addresses are used for display and route requests.
- Real trades are never executed during development.

## Supported wallet providers

- Phantom
- Solflare

These are represented as official wallet adapter names in the frontend integration and as safe provider identifiers in the Python backend. The web frontend should use:

- `@solana/wallet-adapter-phantom`
- `@solana/wallet-adapter-solflare`

The backend enforces public wallet-only behavior and blocks any attempt to accept seed phrases or private keys.

## Configuration

The trading layer reads the following environment variables if present:

```bash
export TRADING_MODE=PAPER
export JUPITER_API_KEY="your-key-if-you-have-one"
export JUPITER_BASE_URL="https://quote-api.jup.ag"
export SOLANA_RPC_URL="https://api.mainnet-beta.solana.com"
```

If no API key is configured, the code still performs quote checks safely but may be rate-limited by the provider.

## Quote and risk checks

The module validates:

- wallet public key format
- token mint validity
- max slippage threshold
- max price impact threshold
- max position limit
- liquidity guardrails
- authority warnings (mint/freeze authority exposure)
- route existence and output quantity

## Example usage

```python
from solana_wallet_trading import QuoteRequest, TradeRiskPolicy, TradingMode, JupiterClient, build_trade_plan

client = JupiterClient()
request = QuoteRequest(
    input_mint="11111111111111111111111111111111",
    output_mint="So11111111111111111111111111111111111111112",
    amount=25.0,
    wallet_public_key="11111111111111111111111111111111",
    slippage_bps=50,
    user_approval=False,
    mode=TradingMode.PAPER.value,
    wallet_provider="phantom",
)
result = build_trade_plan(request, client, TradeRiskPolicy())
print(result)
```

## Deployment notes

- Keep `SOLANA_RPC_URL` and `JUPITER_BASE_URL` behind environment variables.
- Do not store wallet secrets in repository files or GitHub Actions secrets unless absolutely required; prefer ephemeral local wallet sessions in the browser.
- Keep LIVE mode disabled by default and require manual activation for each order.
- Use dry-run or simulation mode for development and QA.

## Live trading requirements

LIVE trades are intentionally blocked unless all of the following are true:

1. Mode is explicitly set to LIVE.
2. The user explicitly activates live mode.
3. The user approves each transaction in the connected wallet.
4. Risk thresholds are within policy limits.
5. Quote/route simulation is successful.

No automatic trading or unattended signing is allowed.
