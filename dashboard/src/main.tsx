import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Connection, PublicKey, VersionedTransaction } from '@solana/web3.js';
import { ConnectionProvider, WalletProvider, useConnection, useWallet } from '@solana/wallet-adapter-react';
import { WalletModalProvider, WalletMultiButton } from '@solana/wallet-adapter-react-ui';
import { PhantomWalletAdapter } from '@solana/wallet-adapter-phantom';
import { SolflareWalletAdapter } from '@solana/wallet-adapter-solflare';
import { amountToLamports, DEFAULT_MODE, DEFAULT_POSITION_LIMIT_SOL, getQuoteWarnings, MAX_SLIPPAGE_BPS, normalizePriceImpact, validateMint, validateTradeInputs, type TradingMode } from './safety';
import './style.css';
import '@solana/wallet-adapter-react-ui/styles.css';

type JupiterOrder = {
  transaction?: string;
  requestId?: string;
  outAmount?: string;
  priceImpactPct?: number | string;
  priceImpact?: number | string;
  routePlan?: unknown[];
  [key: string]: unknown;
};

const DEFAULT_OUTPUT_MINT = 'So11111111111111111111111111111111111111112';
const RPC_ENDPOINT = import.meta.env.VITE_SOLANA_RPC_URL || 'https://api.mainnet-beta.solana.com';
const JUPITER_ORDER_URL = 'https://api.jup.ag/swap/v2/order';
const JUPITER_EXECUTE_URL = 'https://api.jup.ag/swap/v2/execute';

function App() {
  const { connection } = useConnection();
  const { publicKey, connected, signTransaction, sendTransaction, wallet, disconnect } = useWallet();
  const [mode, setMode] = useState<TradingMode>(DEFAULT_MODE);
  const [balance, setBalance] = useState<number | null>(null);
  const [tokens, setTokens] = useState<Array<{ mint: string; amount: string; decimals: number }>>([]);
  const [amountSol, setAmountSol] = useState('0.01');
  const [outputMint, setOutputMint] = useState('');
  const [slippageBps, setSlippageBps] = useState(50);
  const [positionLimit, setPositionLimit] = useState(DEFAULT_POSITION_LIMIT_SOL);
  const [order, setOrder] = useState<JupiterOrder | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [liveConfirmed, setLiveConfirmed] = useState(false);
  const [authorityWarning, setAuthorityWarning] = useState('Mint authority details not checked yet.');
  const [confirmation, setConfirmation] = useState('');
  const apiKey = import.meta.env.VITE_JUPITER_API_KEY as string | undefined;

  const adapters = useMemo(() => [new PhantomWalletAdapter(), new SolflareWalletAdapter()], []);
  void adapters; // WalletProvider is configured once in the root wrapper below.

  const refreshWallet = useCallback(async () => {
    if (!publicKey) {
      setBalance(null);
      setTokens([]);
      return;
    }
    try {
      const [lamports, accountData] = await Promise.all([
        connection.getBalance(publicKey, 'confirmed'),
        connection.getParsedTokenAccountsByOwner(publicKey, { programId: new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA') }, 'confirmed'),
      ]);
      setBalance(lamports / 1e9);
      setTokens(accountData.value.slice(0, 12).map(({ account }) => {
        const info = (account.data as any).parsed.info;
        return { mint: String(info.mint), amount: String(info.tokenAmount.uiAmountString ?? '0'), decimals: Number(info.tokenAmount.decimals) };
      }));
    } catch (e) {
      setError(`Could not load wallet balance: ${messageOf(e)}`);
    }
  }, [connection, publicKey]);

  useEffect(() => { void refreshWallet(); }, [refreshWallet]);

  async function checkAuthorities(mintText: string) {
    setAuthorityWarning('Checking mint and freeze authorities…');
    try {
      const parsed = await connection.getParsedAccountInfo(new PublicKey(mintText), 'confirmed');
      const data = (parsed.value?.data as any)?.parsed?.info;
      if (!data) {
        setAuthorityWarning('Mint account could not be parsed. Token program/extensions and authority risk remain unverified.');
        return;
      }
      const authorities: string[] = [];
      if (data.mintAuthority) authorities.push('mint authority is active');
      if (data.freezeAuthority) authorities.push('freeze authority is active');
      setAuthorityWarning(authorities.length ? `WARNING: ${authorities.join(' and ')}.` : 'No mint or freeze authority reported by the parsed mint account. Token-2022 extensions and broader rug risks are not checked.');
    } catch (e) {
      setAuthorityWarning(`Authority check failed: ${messageOf(e)}. Treat token as unverified.`);
    }
  }

  async function fetchOrder() {
    setError(''); setNotice(''); setConfirmation(''); setOrder(null); setBusy(true);
    try {
      if (!publicKey) throw new Error('Connect a Phantom or Solflare wallet to request a taker-specific route.');
      const mint = outputMint.trim();
      if (!validateMint(mint)) throw new Error('Enter a valid Solana output token mint address.');
      const amount = Number(amountSol);
      const validation = validateTradeInputs(amount, slippageBps, positionLimit);
      if (validation) throw new Error(validation);
      await checkAuthorities(mint);
      const params = new URLSearchParams({ inputMint: DEFAULT_OUTPUT_MINT, outputMint: mint, amount: amountToLamports(amount), taker: publicKey.toBase58(), slippageBps: String(slippageBps) });
      const response = await fetch(`${JUPITER_ORDER_URL}?${params}`, { headers: apiKey ? { 'x-api-key': apiKey } : {} });
      if (!response.ok) throw new Error(`Jupiter quote request failed (${response.status}); check current Jupiter API access/key requirements.`);
      const result = await response.json() as JupiterOrder;
      if (!result.transaction) throw new Error('Jupiter did not return a signable swap transaction. Quote preview is unavailable for this route.');
      setOrder(result);
      setNotice('Quote loaded. Review output, price impact, fees and wallet prompt before any approval. This preview does not submit a trade.');
    } catch (e) { setError(messageOf(e)); }
    finally { setBusy(false); }
  }

  const quoteImpact = order ? normalizePriceImpact(parseFloat(String(order.priceImpactPct ?? order.priceImpact ?? ''))) : null;
  const riskWarnings = getQuoteWarnings(quoteImpact, null);

  async function simulateAndSubmit() {
    setError(''); setNotice(''); setBusy(true); setConfirmation('');
    try {
      if (mode !== 'LIVE') throw new Error('LIVE mode must be explicitly activated before a live transaction.');
      if (!liveConfirmed) throw new Error('Confirm the per-transaction approval checkbox first.');
      if (!connected || !publicKey || !signTransaction) throw new Error('Connected wallet must support explicit transaction signing.');
      if (!order?.transaction || !order.requestId) throw new Error('Refresh the Jupiter quote before proceeding.');
      const tx = VersionedTransaction.deserialize(Uint8Array.from(atob(order.transaction), c => c.charCodeAt(0)));
      // Simulate unsigned message against RPC; sigVerify is deliberately false before wallet approval.
      const simulation = await connection.simulateTransaction(tx, { sigVerify: false, commitment: 'confirmed' });
      if (simulation.value.err) throw new Error(`Transaction simulation failed: ${JSON.stringify(simulation.value.err)}. ${simulation.value.logs?.slice(-3).join(' | ') ?? ''}`);
      const fee = await connection.getFeeForMessage(tx.message, 'confirmed');
      if (fee.value === null) throw new Error('Could not estimate the transaction network fee; refusing to proceed.');
      const approval = window.confirm(`LIVE TRANSACTION REVIEW\n\nWallet: ${publicKey.toBase58()}\nInput: ${amountSol} SOL\nOutput mint: ${outputMint}\nMax slippage: ${slippageBps} bps\nEstimated network fee: ${fee.value / 1e9} SOL\n\nContinue to your wallet for explicit transaction approval?`);
      if (!approval) throw new Error('Transaction cancelled before wallet signing.');
      // Each transaction requires this direct user action and a wallet-managed confirmation prompt.
      const signed = await signTransaction(tx);
      const signedBase64 = btoa(String.fromCharCode(...signed.serialize()));
      const response = await fetch(JUPITER_EXECUTE_URL, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...(apiKey ? { 'x-api-key': apiKey } : {}) },
        body: JSON.stringify({ signedTransaction: signedBase64, requestId: order.requestId }),
      });
      if (!response.ok) throw new Error(`Jupiter execution/landing failed (${response.status}). The signed transaction may or may not have landed; verify wallet history before retrying.`);
      const result = await response.json();
      const signature = String(result.signature ?? result.txid ?? '');
      if (!signature) throw new Error('Provider response did not contain a transaction signature. Check wallet and explorer before retrying.');
      const confirmationResult = await connection.confirmTransaction(signature, 'confirmed');
      if (confirmationResult.value.err) throw new Error(`Transaction was submitted but failed confirmation: ${JSON.stringify(confirmationResult.value.err)}`);
      setConfirmation(signature);
      setLiveConfirmed(false);
      setNotice('Transaction confirmed by Solana RPC.');
      await refreshWallet();
    } catch (e) { setError(messageOf(e)); }
    finally { setBusy(false); }
  }

  return <main className="shell">
    <header className="top"><div><div className="eyebrow">JARVIS / SOLANA INTELLIGENCE</div><h1>Market console</h1><p>Scanner remains the source of market signals; wallet actions are always manual.</p></div><div className="wallet-controls"><WalletMultiButton /><button className="secondary" onClick={() => void refreshWallet()} disabled={!connected}>Refresh balance</button></div></header>
    <section className="scanner card"><div><div className="eyebrow">EXISTING SCANNER</div><h2>Scanner & risk analysis</h2><p>Open the existing generated market report and state. No scanner process or signal is changed by this wallet interface.</p></div><a className="button" href="../report.md" target="_blank" rel="noreferrer">Open scan report</a><a className="button secondary" href="../state.json" target="_blank" rel="noreferrer">Open scanner data</a></section>
    <section className="grid">
      <article className="card"><div className="section-title"><div><div className="eyebrow">NON-CUSTODIAL CONNECTION</div><h2>Wallet</h2></div><span className={connected ? 'badge good' : 'badge'}>{connected ? 'CONNECTED' : 'DISCONNECTED'}</span></div>
        <p>Provider: <strong>{wallet?.adapter.name ?? 'None'}</strong></p><p className="address">{publicKey?.toBase58() ?? 'No public address connected'}</p><p className="balance">{balance === null ? '—' : `${balance.toFixed(5)} SOL`}</p><div className="token-list">{tokens.map(t => <div key={t.mint} className="token-row"><span>{t.mint.slice(0, 7)}…{t.mint.slice(-5)}</span><span>{t.amount}</span></div>)}</div><p className="muted">Wallet adapter handles keys. JARVIS never requests or stores a seed phrase or private key.</p>{connected && <button className="text-button" onClick={() => void disconnect()}>Disconnect</button>}</article>
      <article className="card trade"><div className="section-title"><div><div className="eyebrow">MANUAL SWAP PREVIEW</div><h2>Trading</h2></div><span className={`badge ${mode === 'PAPER' ? 'good' : 'warn'}`}>{mode}</span></div>
        <label>Mode<select value={mode} onChange={e => { setMode(e.target.value as TradingMode); setLiveConfirmed(false); setOrder(null); }}><option value="PAPER">PAPER — preview only</option><option value="LIVE">LIVE — wallet approval per transaction</option></select></label>
        {mode === 'LIVE' && <div className="warning">LIVE is active only for this browser session. Each transaction requires simulation, an explicit confirmation, and a wallet signature. Never approve an unfamiliar transaction.</div>}
        <label>Input amount (SOL)<input type="number" min="0" step="0.001" value={amountSol} onChange={e => setAmountSol(e.target.value)} /></label>
        <label>Output token mint<input inputMode="text" placeholder="Solana token mint address" value={outputMint} onChange={e => setOutputMint(e.target.value)} /></label>
        <div className="two"><label>Slippage (bps)<input type="number" min="1" max={MAX_SLIPPAGE_BPS} value={slippageBps} onChange={e => setSlippageBps(Number(e.target.value))} /></label><label>Position cap (SOL)<input type="number" min="0.001" step="0.001" value={positionLimit} onChange={e => setPositionLimit(Number(e.target.value))} /></label></div>
        <button className="primary" disabled={busy || !connected} onClick={() => void fetchOrder()}>{busy ? 'Working…' : 'Get Jupiter quote'}</button>
        {order && <div className="quote"><h3>Route preview</h3><div className="token-row"><span>Estimated output (raw units)</span><strong>{order.outAmount ?? 'Unavailable'}</strong></div><div className="token-row"><span>Price impact</span><strong>{quoteImpact === null ? 'Unavailable' : `${quoteImpact.toFixed(3)}%`}</strong></div><div className="token-row"><span>Pool liquidity / fee</span><strong>Not returned / unverified</strong></div><p className="muted">Quote is an estimate, may expire, and is not an execution recommendation.</p>{riskWarnings.map(w => <p className="warning" key={w}>{w}</p>)}</div>}
        {mode === 'LIVE' && order && <><label className="checkbox"><input type="checkbox" checked={liveConfirmed} onChange={e => setLiveConfirmed(e.target.checked)} />I reviewed this order and want to simulate it, then approve this exact transaction in my wallet.</label><button className="live-button" disabled={busy || !liveConfirmed} onClick={() => void simulateAndSubmit()}>{busy ? 'Simulating…' : 'Simulate, review & request wallet signature'}</button></>}
        <div className="warning">{authorityWarning}</div>
        {notice && <p className="success">{notice}</p>}{error && <p className="error" role="alert">{error}</p>}{confirmation && <p className="success">Confirmed: <a href={`https://explorer.solana.com/tx/${confirmation}`} target="_blank" rel="noreferrer">{confirmation}</a></p>}
      </article>
    </section>
    <footer>Manual use only · PAPER is default · no automated or unattended signing · never execute trades during development</footer>
  </main>;
}

function messageOf(error: unknown): string { return error instanceof Error ? error.message : 'Unexpected wallet or provider error.'; }

const walletAdapters = [new PhantomWalletAdapter(), new SolflareWalletAdapter()];
function Root() {
  return <ConnectionProvider endpoint={RPC_ENDPOINT}><WalletProvider wallets={walletAdapters} autoConnect={false}><WalletModalProvider><App /></WalletModalProvider></WalletProvider></ConnectionProvider>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><Root /></React.StrictMode>);
