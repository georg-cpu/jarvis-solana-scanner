import React from 'react';
import { act, create } from 'react-test-renderer';
import { afterEach, expect, it, vi } from 'vitest';

const mint = 'So11111111111111111111111111111111111111112';
const signTransaction = vi.fn();
const simulateTransaction = vi.fn(async () => ({ value: { err: 'mock simulation failure' } }));
const connection = {
  getBalance: async () => 0,
  getParsedTokenAccountsByOwner: async () => ({ value: [] }),
  getParsedAccountInfo: async () => ({ value: null }),
  simulateTransaction,
};
const publicKey = { toBase58: () => mint };

vi.mock('@solana/wallet-adapter-react', () => ({
  useWallet: () => ({ publicKey, connected: true, signTransaction }),
  useConnection: () => ({ connection }),
  WalletProvider: () => null, ConnectionProvider: () => null,
}));
vi.mock('@solana/wallet-adapter-react-ui', () => ({ WalletMultiButton: () => null, WalletModalProvider: () => null }));
vi.mock('@solana/wallet-adapter-phantom', () => ({ PhantomWalletAdapter: class {} }));
vi.mock('@solana/wallet-adapter-solflare', () => ({ SolflareWalletAdapter: class {} }));
vi.mock('@solana/web3.js', () => ({ PublicKey: class {}, VersionedTransaction: { deserialize: () => ({}) } }));
vi.mock('react-dom/client', () => ({ createRoot: () => ({ render() {} }) }));

afterEach(() => vi.unstubAllGlobals());

it('previews in PAPER, invalidates edited orders and stops LIVE on failed simulation', async () => {
  vi.stubGlobal('document', { getElementById: () => ({}) });
  const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({ transaction: 'AA==', requestId: 'mock', outAmount: '9' }) }));
  vi.stubGlobal('fetch', fetchMock);
  const { App } = await import('./main');
  let tree;
  await act(async () => { tree = create(<App />); });
  const root = tree.root;
  const quote = () => act(async () => { await root.findByProps({ className: 'primary' }).props.onClick(); });
  const change = (element, value) => act(() => element.props.onChange({ target: { value } }));
  const liveButtons = () => root.findAllByProps({ className: 'live-button' });
  change(root.findByProps({ inputMode: 'text' }), '11111111111111111111111111111111');
  await quote();
  expect(root.findAllByProps({ className: 'quote' })).toHaveLength(1);
  expect(liveButtons()).toHaveLength(0);
  change(root.findByType('select'), 'LIVE');
  await quote();
  act(() => root.findByProps({ type: 'checkbox' }).props.onChange({ target: { checked: true } }));
  change(root.findByProps({ value: '0.01' }), '0.02');
  expect(liveButtons()).toHaveLength(0);
  await quote();
  expect(liveButtons()[0].props.disabled).toBe(true);
  act(() => root.findByProps({ type: 'checkbox' }).props.onChange({ target: { checked: true } }));
  await act(async () => { liveButtons()[0].props.onClick(); });
  expect(simulateTransaction).toHaveBeenCalledOnce();
  expect(root.findByProps({ role: 'alert' }).children.join('')).toContain('simulation failed');
  expect(signTransaction).not.toHaveBeenCalled();
  expect(fetchMock.mock.calls.every(([url]) => url.includes('/order?'))).toBe(true);
  act(() => tree.unmount());
});
