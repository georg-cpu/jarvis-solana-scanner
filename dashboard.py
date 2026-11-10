from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from solana_wallet_trading import TradeRiskPolicy, TradingMode, WalletConnectionStatus, validate_wallet_connection, build_dashboard_snapshot


DEFAULT_STATE_PATH = Path(__file__).resolve().parent / "state.json"


class JarvisDashboard:
    def __init__(self, state_path: Optional[str | Path] = None):
        self.state_path = Path(state_path) if state_path else DEFAULT_STATE_PATH
        self.wallet_status = WalletConnectionStatus(provider="phantom", mode=TradingMode.PAPER.value)

    def load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def snapshot(self) -> Dict[str, Any]:
        state = self.load_state()
        return build_dashboard_snapshot(state, self.wallet_status, TradeRiskPolicy())

    def set_wallet(self, provider: str, public_key: Optional[str], mode: str = TradingMode.PAPER.value) -> WalletConnectionStatus:
        self.wallet_status = validate_wallet_connection(provider, public_key, mode)
        return self.wallet_status


if __name__ == "__main__":
    dashboard = JarvisDashboard()
    print(json.dumps(dashboard.snapshot(), indent=2, ensure_ascii=False))
