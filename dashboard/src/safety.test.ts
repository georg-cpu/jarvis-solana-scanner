import { describe, expect, it } from 'vitest';
import { amountToLamports, DEFAULT_MODE, getQuoteWarnings, normalizePriceImpact, validateMint, validateTradeInputs } from './safety';

describe('wallet trading safety', () => {
  it('defaults to PAPER mode', () => expect(DEFAULT_MODE).toBe('PAPER'));
  it('validates base58-like mint length', () => {
    expect(validateMint('So11111111111111111111111111111111111111112')).toBe(true);
    expect(validateMint('not-a-mint')).toBe(false);
  });
  it('enforces input, slippage and position limits', () => {
    expect(validateTradeInputs(0, 50, 0.1)).toContain('positive');
    expect(validateTradeInputs(0.2, 50, 0.1)).toContain('position limit');
    expect(validateTradeInputs(0.05, 301, 0.1)).toContain('Slippage');
    expect(validateTradeInputs(0.05, 50, 0.1)).toBeNull();
  });
  it('converts only finite positive SOL amounts to lamports', () => {
    expect(amountToLamports(0.01)).toBe('10000000');
    expect(() => amountToLamports(0)).toThrow();
  });
  it('normalizes impact and warns on absent risk data', () => {
    expect(normalizePriceImpact(0.025)).toBeCloseTo(2.5);
    expect(getQuoteWarnings(null, null)).toHaveLength(2);
  });
});
