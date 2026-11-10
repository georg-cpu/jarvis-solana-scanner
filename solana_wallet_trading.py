from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


PUBLIC_KEY_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
FORBIDDEN_SECRET_PATTERNS = (
    "seed phrase",
    "seedphrase",
    "mnemonic",
    "private key",
    "private_key",
    "secret key",
    "secret_key",
)


class TradingMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class WalletProvider(str, Enum):
    PHANTOM = "phantom"
    SOLFLARE = "solflare"


class TradingValidationError(ValueError):
    """Raised when a wallet-trading request violates safety rules."""


@dataclass
class TradeRiskPolicy:
    max_slippage_bps: int = 100
    max_price_impact_pct: float = 2.0
    max_position_usd: float = 250.0
    min_liquidity_usd: float = 50000.0
    require_live_approval: bool = True


@dataclass
class WalletConnectionStatus:
    provider: str
    public_key: Optional[str] = None
    mode: str = TradingMode.PAPER.value
    connected: bool = False
    status: str = "DISCONNECTED"
    last_error: Optional[str] = None
    wallet_details: Dict[str, Any] = field(default_factory=dict)

    def safe_summary(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "public_key": sanitize_public_key(self.public_key) if self.public_key else None,
            "connected": self.connected,
            "mode": self.mode,
            "status": self.status,
            "last_error": self.last_error,
            "wallet_details": {
                "sol_balance": self.wallet_details.get("sol_balance"),
                "token_balances": self.wallet_details.get("token_balances", []),
            },
        }

    def ensure_no_sensitive_material(self) -> None:
        if self.public_key and not sanitize_public_key(self.public_key):
            raise TradingValidationError("Wallet public key is invalid.")
        for field_name in ("seed_phrase", "private_key", "secret_key", "mnemonic"):
            value = self.wallet_details.get(field_name)
            if value:
                raise TradingValidationError(f"Sensitive wallet material is never accepted in {field_name}.")


@dataclass
class QuoteRequest:
    input_mint: str
    output_mint: str
    amount: float
    wallet_public_key: Optional[str] = None
    slippage_bps: int = 50
    user_approval: bool = False
    mode: str = TradingMode.PAPER.value
    wallet_provider: Optional[str] = None
    max_position_usd: float = 250.0

    def validate(self) -> None:
        validate_token_mint(self.input_mint)
        validate_token_mint(self.output_mint)
        if self.amount <= 0:
            raise TradingValidationError("Trade amount must be positive.")
        if self.slippage_bps <= 0 or self.slippage_bps > 5000:
            raise TradingValidationError("Slippage must be between 1 and 5000 bps.")
        if self.wallet_public_key:
            sanitized = sanitize_public_key(self.wallet_public_key)
            if not sanitized:
                raise TradingValidationError("Wallet public key is invalid.")
        if self.wallet_provider and self.wallet_provider.lower() not in {provider.value for provider in WalletProvider}:
            raise TradingValidationError("Unsupported wallet provider. Supported: phantom, solflare.")
        if any(pattern in str(self.input_mint).lower() for pattern in FORBIDDEN_SECRET_PATTERNS):
            raise TradingValidationError("Seed phrases and private keys are never accepted in token fields.")


@dataclass
class QuoteResult:
    approved: bool
    mode: str
    quote: Dict[str, Any]
    risk: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    executed: bool = False
    signature_required: bool = False


def sanitize_public_key(public_key: Optional[str]) -> Optional[str]:
    if public_key is None:
        return None
    text = str(public_key).strip()
    if not text:
        return None
    if any(pattern in text.lower() for pattern in FORBIDDEN_SECRET_PATTERNS):
        raise TradingValidationError("Seed phrases and private keys are never accepted as wallet information.")
    return text if PUBLIC_KEY_RE.fullmatch(text) else None


def validate_token_mint(mint: Optional[str]) -> str:
    if mint is None:
        raise TradingValidationError("Token mint cannot be empty.")
    text = str(mint).strip()
    if not text:
        raise TradingValidationError("Token mint cannot be empty.")
    if any(pattern in text.lower() for pattern in FORBIDDEN_SECRET_PATTERNS):
        raise TradingValidationError("Seed phrases and private keys are never accepted in token addresses.")
    if not PUBLIC_KEY_RE.fullmatch(text):
        raise TradingValidationError(f"Invalid Solana token mint: {text}")
    return text


def wallet_provider_from_name(provider_name: Optional[str]) -> str:
    if not provider_name:
        return WalletProvider.PHANTOM.value
    normalized = str(provider_name).strip().lower()
    if normalized in {WalletProvider.PHANTOM.value, "phantom"}:
        return WalletProvider.PHANTOM.value
    if normalized in {WalletProvider.SOLFLARE.value, "solflare"}:
        return WalletProvider.SOLFLARE.value
    raise TradingValidationError("Unsupported wallet provider. Supported: phantom, solflare.")


def _request_json(url: str, headers: Optional[Dict[str, str]] = None, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Any:
    request_headers = {"Accept": "application/json", "User-Agent": "JARVIS-Solana-Scanner/3.0"}
    if headers:
        request_headers.update(headers)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            if not body:
                return {}
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TradingValidationError(f"HTTP error contacting Solana/Jupiter provider: {exc.code} {body[:250]}") from exc
    except urllib.error.URLError as exc:
        raise TradingValidationError(f"Network error contacting Solana/Jupiter provider: {exc.reason}") from exc


class JupiterClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, rpc_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("JUPITER_API_KEY")
        self.base_url = (base_url or os.getenv("JUPITER_BASE_URL") or "https://quote-api.jup.ag").rstrip("/")
        self.rpc_url = (rpc_url or os.getenv("SOLANA_RPC_URL") or "https://api.mainnet-beta.solana.com").rstrip("/")

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def get_quote(self, input_mint: str, output_mint: str, amount: float, slippage_bps: int = 50, wallet_public_key: Optional[str] = None) -> Dict[str, Any]:
        validate_token_mint(input_mint)
        validate_token_mint(output_mint)
        if amount <= 0:
            raise TradingValidationError("Quote amount must be positive.")
        url = f"{self.base_url}/v6/quote"
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(int(amount)),
            "slippageBps": str(slippage_bps),
            "onlyDirectRoutes": "false",
            "asLegacyTransaction": "false",
        }
        if wallet_public_key:
            sanitized = sanitize_public_key(wallet_public_key)
            if sanitized:
                params["walletAddress"] = sanitized
        query = urllib.parse.urlencode(params)
        return _request_json(f"{url}?{query}", headers=self._headers(), method="GET")

    def simulate_transaction(self, transaction: str) -> Dict[str, Any]:
        if not transaction:
            raise TradingValidationError("A transaction payload is required for simulation.")
        payload = {"transaction": transaction, "sigVerify": True}
        url = f"{self.rpc_url}/simulateTransaction"
        return _request_json(url, headers={"Content-Type": "application/json"}, method="POST", payload=payload)


def estimate_usd_from_quote(quote: Dict[str, Any]) -> float:
    try:
        if "outAmount" in quote and "price" in quote:
            return float(quote.get("price", 0.0)) * float(quote.get("outAmount", 0.0))
        return float(quote.get("outAmount", 0.0))
    except (TypeError, ValueError):
        return 0.0


def risk_check_quote(quote: Dict[str, Any], policy: TradeRiskPolicy, slippage_bps: int, mode: str) -> Dict[str, Any]:
    price_impact = float(quote.get("priceImpactPct", 0.0) or 0.0)
    liquidity = float(quote.get("liquidityUsd", 0.0) or 0.0)
    out_amount = float(quote.get("outAmount", 0.0) or 0.0)
    warnings: List[str] = []
    if slippage_bps > policy.max_slippage_bps:
        warnings.append(f"Slippage {slippage_bps} bps exceeds configured cap {policy.max_slippage_bps} bps.")
    if price_impact > policy.max_price_impact_pct:
        warnings.append(f"Price impact {price_impact:.2f}% exceeds limit {policy.max_price_impact_pct:.2f}%.")
    if liquidity and liquidity < policy.min_liquidity_usd:
        warnings.append(f"Estimated liquidity ${liquidity:,.0f} is below ${policy.min_liquidity_usd:,.0f}.")
    if out_amount <= 0:
        warnings.append("No output quantity returned by routing provider.")
    approved = not warnings and mode == TradingMode.PAPER.value
    if mode == TradingMode.LIVE.value:
        approved = False
        if not policy.require_live_approval:
            warnings.append("LIVE mode must explicitly require wallet approval for every transaction.")
        if not quote.get("swapTransaction"):
            warnings.append("LIVE mode requires a signed or simulated swap transaction payload.")
    return {
        "approved": approved,
        "price_impact_pct": price_impact,
        "liquidity_usd": liquidity,
        "out_amount": out_amount,
        "warnings": warnings,
    }


def validate_wallet_connection(provider: str, public_key: Optional[str], mode: str) -> WalletConnectionStatus:
    wallet_provider = wallet_provider_from_name(provider)
    user_public_key = sanitize_public_key(public_key)
    status = WalletConnectionStatus(
        provider=wallet_provider,
        public_key=user_public_key,
        mode=mode,
        connected=bool(user_public_key),
        status="CONNECTED" if user_public_key else "DISCONNECTED",
    )
    if mode == TradingMode.LIVE.value and not user_public_key:
        status.status = "BLOCKED"
        status.last_error = "LIVE mode requires a connected wallet public key."
        status.connected = False
    return status


def build_trade_plan(request: QuoteRequest, client: JupiterClient, policy: TradeRiskPolicy) -> QuoteResult:
    request.validate()
    if request.mode != TradingMode.PAPER.value and request.mode != TradingMode.LIVE.value:
        raise TradingValidationError("Mode must be PAPER or LIVE.")
    mode = str(request.mode).upper()
    if mode == TradingMode.LIVE.value and not request.user_approval:
        raise TradingValidationError("Explicit approval is required for every LIVE transaction; no unattended signing is allowed.")
    wallet_status = validate_wallet_connection(request.wallet_provider or WalletProvider.PHANTOM.value, request.wallet_public_key, mode)
    if wallet_status.status == "BLOCKED":
        raise TradingValidationError(wallet_status.last_error or "Wallet not ready for LIVE trading.")

    quote = client.get_quote(
        input_mint=request.input_mint,
        output_mint=request.output_mint,
        amount=request.amount,
        slippage_bps=request.slippage_bps,
        wallet_public_key=request.wallet_public_key,
    )
    risk = risk_check_quote(quote, policy, request.slippage_bps, mode)
    warnings = list(risk["warnings"])

    if mode == TradingMode.LIVE.value:
        if not request.user_approval:
            raise TradingValidationError("LIVE mode requires explicit user approval for every transaction.")
        if not quote.get("swapTransaction"):
            warnings.append("No signed swapTransaction returned for LIVE conversion; preview only.")
        approved = False
        if not warnings:
            approved = True
    else:
        approved = risk["approved"] and not warnings

    if not approved and mode == TradingMode.PAPER.value:
        return QuoteResult(approved=False, mode=mode, quote=quote, risk=risk, warnings=warnings, executed=False, signature_required=False)

    if mode == TradingMode.LIVE.value and request.user_approval:
        if risk["price_impact_pct"] > policy.max_price_impact_pct:
            raise TradingValidationError("Transaction rejected by price impact guardrail.")
        if request.max_position_usd <= 0 or request.amount > request.max_position_usd:
            raise TradingValidationError("Trade exceeds configured position limit.")

    return QuoteResult(
        approved=approved,
        mode=mode,
        quote=quote,
        risk=risk,
        warnings=warnings,
        executed=(mode == TradingMode.PAPER.value),
        signature_required=(mode == TradingMode.LIVE.value),
    )


def build_dashboard_snapshot(scanner_state: Dict[str, Any], wallet_status: WalletConnectionStatus, policy: TradeRiskPolicy) -> Dict[str, Any]:
    scanner_state = scanner_state or {}
    return {
        "scanner": {
            "checked_at_utc": scanner_state.get("checked_at_utc"),
            "qualified": scanner_state.get("qualified", 0),
            "candidates": scanner_state.get("candidates", []),
            "errors": scanner_state.get("errors", []),
            "limitations": scanner_state.get("limitations", []),
        },
        "wallet": wallet_status.safe_summary(),
        "trading": {
            "mode": wallet_status.mode,
            "default_mode": TradingMode.PAPER.value,
            "wallet_approval_required": policy.require_live_approval,
            "max_slippage_bps": policy.max_slippage_bps,
            "max_position_usd": policy.max_position_usd,
            "max_price_impact_pct": policy.max_price_impact_pct,
            "live_execution_disabled": True,
        },
    }


__all__ = [
    "JupiterClient",
    "QuoteRequest",
    "QuoteResult",
    "TradeRiskPolicy",
    "TradingMode",
    "WalletConnectionStatus",
    "WalletProvider",
    "TradingValidationError",
    "build_dashboard_snapshot",
    "build_trade_plan",
    "risk_check_quote",
    "sanitize_public_key",
    "validate_token_mint",
    "validate_wallet_connection",
    "wallet_provider_from_name",
]


if __name__ == "__main__":
    print({
        "default_mode": TradingMode.PAPER.value,
        "supported_wallets": [WalletProvider.PHANTOM.value, WalletProvider.SOLFLARE.value],
        "security_note": "No seed phrases or private keys are collected or stored.",
    })
