"""JARVIS Solana Scanner: discovery + conditional M5/M1 setups (no execution)."""
import datetime
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
STATE = ROOT / "state.json"
REPORT = ROOT / "report.md"
DEX = "https://api.dexscreener.com"
GECKO = "https://api.geckoterminal.com/api/v2"
HEADERS = {"User-Agent": "JARVIS-Solana-Scanner/2.0", "Accept": "application/json"}


def fetch(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=22) as response:
        return json.load(response)


def num(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else 0.0
    except (TypeError, ValueError):
        return 0.0


def candles(pool, aggregate):
    path = f"/networks/solana/pools/{urllib.parse.quote(pool, safe='')}/ohlcv/minute"
    url = GECKO + path + f"?aggregate={aggregate}&limit=70&currency=usd&token=base"
    data = fetch(url)
    raw = data["data"]["attributes"]["ohlcv_list"]
    rows = []
    for item in raw:
        if len(item) < 6:
            continue
        timestamp, op, high, low, close, volume = item[:6]
        vals = [num(v) for v in (op, high, low, close, volume)]
        if min(vals[:4]) <= 0 or vals[1] < vals[2]:
            continue
        rows.append({"ts": int(timestamp), "open": vals[0], "high": vals[1],
                     "low": vals[2], "close": vals[3], "volume": vals[4]})
    rows.sort(key=lambda row: row["ts"])
    # Exclude the still-forming candle, based on UTC clock.
    now = time.time()
    seconds = aggregate * 60
    return [row for row in rows if row["ts"] + seconds <= now]


def atr(rows, length=14):
    if len(rows) < length + 1:
        return None
    ranges = []
    for i in range(1, len(rows)):
        row, prev = rows[i], rows[i - 1]
        ranges.append(max(row["high"] - row["low"],
                          abs(row["high"] - prev["close"]),
                          abs(row["low"] - prev["close"])))
    return sum(ranges[-length:]) / length


def setup(m5, m1):
    """Conservative breakout/retest candidate; informational, not an order."""
    if len(m5) < 30 or len(m1) < 25:
        return {"status": "NO TRADE", "reason": "Insufficient closed M5/M1 candles"}
    last5, last1 = m5[-1], m1[-1]
    # Require recent and reasonably synchronized data.
    if time.time() - last5["ts"] > 15 * 60 or time.time() - last1["ts"] > 5 * 60:
        return {"status": "NO TRADE", "reason": "Stale OHLCV data"}
    a = atr(m5)
    if not a or a <= 0:
        return {"status": "NO TRADE", "reason": "ATR unavailable"}
    previous_high = max(x["high"] for x in m5[-13:-1])
    previous_low = min(x["low"] for x in m5[-13:-1])
    avg_vol = sum(x["volume"] for x in m5[-13:-1]) / 12
    trend = last5["close"] > sum(x["close"] for x in m5[-21:-1]) / 20
    breakout = last5["close"] > previous_high
    volume_ok = avg_vol > 0 and last5["volume"] >= avg_vol * 1.5
    m1_confirm = last1["close"] > max(x["high"] for x in m1[-7:-1])
    if not (trend and breakout and volume_ok and m1_confirm):
        return {"status": "WAIT", "reason": "M5 breakout + volume + M1 confirmation not all met",
                "m5_breakout": breakout, "volume_confirmed": volume_ok,
                "m1_confirmed": m1_confirm, "trend_confirmed": trend}
    entry = last1["close"]
    # Avoid setups whose M1 entry is too extended beyond the M5 breakout.
    if entry > previous_high + 1.5 * a or entry < previous_high:
        return {"status": "WAIT", "reason": "M1 entry is extended or below breakout"}
    stop = max(previous_low, entry - 2 * a)
    if stop >= entry:
        return {"status": "NO TRADE", "reason": "Invalid stop geometry"}
    risk = entry - stop
    if risk / entry > 0.15 or risk / entry < 0.005:
        return {"status": "NO TRADE", "reason": "Risk distance outside 0.5%-15% bounds"}
    return {"status": "CONDITIONAL ENTRY", "reason": "M5 breakout, volume and M1 confirmation",
            "entry_usd": entry, "stop_usd": stop, "tp1_usd": entry + 2 * risk,
            "tp2_usd": entry + 3 * risk, "tp3_usd": entry + 5 * risk,
            "rr": [2, 3, 5], "risk_pct": 100 * risk / entry,
            "m5_candle_utc": datetime.datetime.fromtimestamp(last5["ts"], datetime.timezone.utc).isoformat(),
            "m1_candle_utc": datetime.datetime.fromtimestamp(last1["ts"], datetime.timezone.utc).isoformat(),
            "note": "Indicative candle prices; not executable quotes. Slippage, fees and MEV excluded."}


def main():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    addresses, errors = [], []
    for endpoint in ["/token-profiles/latest/v1", "/token-boosts/latest/v1", "/token-boosts/top/v1"]:
        try:
            data = fetch(DEX + endpoint)
            for item in data if isinstance(data, list) else []:
                if item.get("chainId") == "solana" and item.get("tokenAddress"):
                    addresses.append(item["tokenAddress"])
        except Exception as exc:
            errors.append(f"{endpoint}: {type(exc).__name__}: {str(exc)[:100]}")
    # Broaden discovery with GeckoTerminal's public Solana new-pool feed.
    # This is sampled discovery, NOT an exhaustive on-chain market index.
    gecko_pools = []
    gecko_sources = {"new_pools": 0, "trending_pools": 0}
    for feed_name in ("new_pools", "trending_pools"):
      for page in (1, 2, 3):
        try:
            feed = fetch(GECKO + f"/networks/solana/{feed_name}?page={page}")
            for item in feed.get("data", []):
                pool_id = item.get("id", "")
                pool_address = pool_id.split("solana_", 1)[-1] if pool_id.startswith("solana_") else ""
                if pool_address:
                    gecko_pools.append(pool_address)
                    gecko_sources[feed_name] += 1
        except Exception as exc:
            errors.append(f"Gecko {feed_name} page {page}: {type(exc).__name__}")
        time.sleep(1.2)
    gecko_pools = list(dict.fromkeys(gecko_pools))
    addresses = list(dict.fromkeys(addresses))[:180]
    pairs = []
    for i in range(0, len(addresses), 30):
        try:
            batch = fetch(DEX + "/tokens/v1/solana/" + ",".join(addresses[i:i + 30]))
            if isinstance(batch, list):
                pairs.extend(batch)
        except Exception as exc:
            errors.append(f"DEX batch {i // 30}: {type(exc).__name__}")
        time.sleep(0.2)
    # Resolve newly listed pool addresses to DEX Screener pair records.
    for i in range(0, len(gecko_pools), 25):
        try:
            # Individual pair endpoint accepts a pair address.
            for pool in gecko_pools[i:i + 25]:
                result = fetch(DEX + "/latest/dex/pairs/solana/" + pool)
                batch = result.get("pairs") or []
                if isinstance(batch, list):
                    pairs.extend(batch)
                time.sleep(0.15)
        except Exception as exc:
            errors.append(f"New-pool pair lookup batch {i // 25}: {type(exc).__name__}")
    # Include newly discovered pool base-token addresses in the candidate set.
    addresses = list(dict.fromkeys(addresses + [
        (p.get("baseToken") or {}).get("address")
        for p in pairs if p.get("chainId") == "solana"
        and (p.get("baseToken") or {}).get("address")
    ]))
    by_token = {}
    for p in pairs:
        addr = (p.get("baseToken") or {}).get("address")
        if p.get("chainId") != "solana" or addr not in addresses:
            continue
        if num((p.get("liquidity") or {}).get("usd")) > num((by_token.get(addr, {}).get("liquidity") or {}).get("usd")):
            by_token[addr] = p
    dex_coverage = {}
    for p in by_token.values():
        dex = p.get("dexId") or "unknown"
        dex_coverage[dex] = dex_coverage.get(dex, 0) + 1
    qualified = []
    for addr, p in by_token.items():
        liq = num((p.get("liquidity") or {}).get("usd"))
        cap = num(p.get("marketCap") or p.get("fdv"))
        vol = num((p.get("volume") or {}).get("h1"))
        tx = (p.get("txns") or {}).get("h1") or {}
        buys, sells = num(tx.get("buys")), num(tx.get("sells"))
        change = num((p.get("priceChange") or {}).get("h1"))
        if not (liq >= 15000 and cap >= 20000 and vol >= 10000 and buys >= 20 and buys > sells and -10 <= change <= 80):
            continue
        score = round(min(liq / 50000, 2) * 15 + min(vol / max(liq, 1), 4) * 12 +
                      min(buys / max(sells, 1), 3) * 10 + max(0, min(change, 40)) * 0.4, 1)
        qualified.append({"address": addr, "symbol": (p.get("baseToken") or {}).get("symbol", "?"),
                          "pool": p.get("pairAddress"), "dex": p.get("dexId"), "url": p.get("url"),
                          "market_cap_usd": cap, "liquidity_usd": liq, "volume_h1_usd": vol,
                          "buys_h1": int(buys), "sells_h1": int(sells),
                          "price_change_h1_pct": change, "score": score})
    qualified.sort(key=lambda c: c["score"], reverse=True)
    top = qualified[:5]
    for c in top:
        c["signal"] = {"status": "NO TRADE", "reason": "OHLCV not checked"}
        if not c["pool"]:
            c["signal"]["reason"] = "Missing pool address"
            continue
        try:
            m5 = candles(c["pool"], 5)
            time.sleep(1.2)
            m1 = candles(c["pool"], 1)
            c["signal"] = setup(m5, m1)
        except Exception as exc:
            c["signal"] = {"status": "NO TRADE", "reason": "OHLCV unavailable or API error"}
            errors.append(f"OHLCV {c['symbol']}: {type(exc).__name__}: {str(exc)[:100]}")
        time.sleep(1.2)
    state = {"checked_at_utc": now, "discovered_addresses": len(addresses), "new_pools_sampled": len(gecko_pools),
             "gecko_source_counts": gecko_sources, "dex_coverage": dex_coverage,
             "pairs": len(pairs), "qualified": len(qualified), "candidates": top,
             "errors": errors, "limitations": [
                 "Discovery combines DEX Screener promotion feeds and GeckoTerminal sampled new/trending pools; NOT whole-market coverage",
                 "Holder concentration, token authorities, deployer and sellability NOT verified",
                 "Signals are conditional educational setups; no wallet or execution",
                 "M1/M5 candles may be unavailable; exact levels omitted when unverified"]}
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# JARVIS SOLANA TREND SCANNER v2", f"Проверка UTC: {now}",
             f"Открити: {len(addresses)} | Нови пулове (извадка): {len(gecko_pools)} | Двойки: {len(pairs)} | Филтър: {len(qualified)}", "",
             "**Внимание: всички токени са с НЕПРОВЕРЕН on-chain rug риск. Нивата не са препоръки за сделки.**", ""]
    lines += ["### DEX coverage (observed tokens, not complete market)",
              *[f"- {dex}: {count}" for dex, count in sorted(dex_coverage.items(), key=lambda x: -x[1])], ""]
    for i, c in enumerate(top, 1):
        s = c["signal"]
        lines += [f"## {i}. {c['symbol']} — {s['status']}", f"Mint: `{c['address']}`",
                  f"Pool: `{c['pool']}` | DEX: {c['dex']}",
                  f"Liquidity: ${c['liquidity_usd']:,.0f} | Cap/FDV: ${c['market_cap_usd']:,.0f} | Volume 1h: ${c['volume_h1_usd']:,.0f}",
                  f"Buys/sells 1h: {c['buys_h1']}/{c['sells_h1']} | Change 1h: {c['price_change_h1_pct']:+.1f}%",
                  f"Status reason: {s['reason']}"]
        if s["status"] == "CONDITIONAL ENTRY":
            lines += [f"ENTRY: ${s['entry_usd']:.10g} | SL: ${s['stop_usd']:.10g}",
                      f"TP1: ${s['tp1_usd']:.10g} (RR 1:2) | TP2: ${s['tp2_usd']:.10g} (1:3) | TP3: ${s['tp3_usd']:.10g} (1:5)",
                      f"Risk distance: {s['risk_pct']:.2f}% | Last M1 closed candle: {s['m1_candle_utc']}"]
        else:
            lines.append("ENTRY / SL / TP: NOT CONFIRMED — no invented prices")
        lines += [f"Source: {c['url']}", "Holder risk / authorities / sellability: UNKNOWN", ""]
    if not top:
        lines.append("Няма кандидати, минали базовите филтри.")
    if errors:
        lines += ["### Data errors", *[f"- {e}" for e in errors]]
    lines.extend(["", "## ☕ Почерпи ме с кафе\n\nДоброволна подкрепа с native SOL · Solana mainnet\n\n`CYmGyR3E2rEheJiG48t9LNPjCU9dxGG6sBeUh9mJB9Fy`"])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
