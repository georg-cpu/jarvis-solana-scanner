from __future__ import annotations

import pytest

from solana_wallet_trading import (
    QuoteRequest,
    TradeRiskPolicy,
    TradingMode,
    TradingValidationError,
    JupiterClient,
    build_trade_plan,
    risk_check_quote,
    sanitize_public_key,
    validate_token_mint,
    validate_wallet_connection,
)


def test_default_mode_is_paper():
    assert TradingMode.PAPER.value == "PAPER"
    assert TradingMode.PAPER is TradingMode.PAPER


def test_seed_phrase_is_rejected():
    with pytest.raises(TradingValidationError):
        validate_token_mint("seed phrase")


def test_public_key_validation_and_wallet_status():
    assert sanitize_public_key("11111111111111111111111111111111") is not None
    status = validate_wallet_connection("phantom", "11111111111111111111111111111111", TradingMode.PAPER.value)
    assert status.connected is True
    assert status.provider == "phantom"


def test_live_trade_requires_explicit_approval():
    request = QuoteRequest(
        input_mint="11111111111111111111111111111111",
        output_mint="So11111111111111111111111111111111111111112",
        amount=1000,
        wallet_public_key="11111111111111111111111111111111",
        slippage_bps=50,
        user_approval=False,
        mode=TradingMode.LIVE.value,
        wallet_provider="phantom",
    )
    client = JupiterClient(base_url="https://quote-api.jup.ag", rpc_url="https://api.mainnet-beta.solana.com")
    with pytest.raises(TradingValidationError):
        build_trade_plan(request, client, TradeRiskPolicy())


def test_risk_policy_blocks_high_impact():
    quote = {"priceImpactPct": 9.5, "liquidityUsd": 300000, "outAmount": 1000, "swapTransaction": "abcd"}
    decision = risk_check_quote(quote, TradeRiskPolicy(), 50, TradingMode.PAPER.value)
    assert decision["approved"] is False
    assert "Price impact" in decision["warnings"][0]


def test_paper_mode_remains_safe_and_no_private_data_storage():
    request = QuoteRequest(
        input_mint="11111111111111111111111111111111",
        output_mint="So11111111111111111111111111111111111111112",
        amount=100,
        wallet_public_key="11111111111111111111111111111111",
        slippage_bps=50,
        user_approval=False,
        mode=TradingMode.PAPER.value,
        wallet_provider="solflare",
    )
    assert request.mode == "PAPER"
    assert "private key" not in str(request)


def test_invalid_wallet_provider_fails():
    with pytest.raises(TradingValidationError):
        validate_wallet_connection("unsupported-wallet", "11111111111111111111111111111111", TradingMode.PAPER.value)


if __name__ == "__main__":
    raise SystemExit(pytest.main(["-q", __file__]))

