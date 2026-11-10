export const LAMPORTS_PER_SOL = 1_000_000_000;
export const MAX_SLIPPAGE_BPS = 300;
export const DEFAULT_POSITION_LIMIT_SOL = 0.1;
export const DEFAULT_MODE = 'PAPER' as const;
export type TradingMode = 'PAPER' | 'LIVE';

export function validateMint(mint: string): boolean {
  try {
    // PublicKey validation includes base58 and 32-byte key size checks.
    return /^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(mint.trim());
  } catch {
    return false;
  }
}

export function validateTradeInputs(amountSol: number, slippageBps: number, positionLimitSol: number): string | null {
  if (!Number.isFinite(amountSol) || amountSol <= 0) return 'Enter a positive SOL amount.';
  if (!Number.isFinite(positionLimitSol) || positionLimitSol <= 0) return 'Position limit must be positive.';
  if (amountSol > positionLimitSol) return `Amount exceeds your ${positionLimitSol} SOL position limit.`;
  if (!Number.isInteger(slippageBps) || slippageBps < 1 || slippageBps > MAX_SLIPPAGE_BPS) {
    return `Slippage must be between 1 and ${MAX_SLIPPAGE_BPS} bps.`;
  }
  return null;
}

export function amountToLamports(amountSol: number): string {
  if (!Number.isFinite(amountSol) || amountSol <= 0) throw new Error('Invalid SOL amount.');
  return BigInt(Math.floor(amountSol * LAMPORTS_PER_SOL)).toString();
}

export function normalizePriceImpact(value: unknown): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  // Jupiter versions have represented impact as decimal fractions or percentage values.
  return Math.abs(value) <= 1 ? value * 100 : value;
}

export function getQuoteWarnings(priceImpactPct: number | null, liquidityUsd: number | null): string[] {
  const warnings: string[] = [];
  if (priceImpactPct === null) warnings.push('Price impact was not provided by the route provider; verify independently.');
  else if (priceImpactPct > 2) warnings.push(`High price impact: ${priceImpactPct.toFixed(2)}%.`);
  if (liquidityUsd === null) warnings.push('Pool liquidity was not provided; liquidity and sellability are unverified.');
  else if (liquidityUsd < 50_000) warnings.push(`Low reported liquidity: $${liquidityUsd.toLocaleString()}.`);
  return warnings;
}
