import json, os, time, urllib.request, datetime
from pathlib import Path
BASE='https://api.dexscreener.com'
ROOT=Path(__file__).parent
STATE=ROOT/'state.json'
REPORT=ROOT/'report.md'

def get(path):
    req=urllib.request.Request(BASE+path,headers={'User-Agent':'JARVIS-Solana-Scanner/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)

def number(x):
    try:return float(x or 0)
    except (ValueError,TypeError):return 0.

def main():
    now=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    sources=['/token-profiles/latest/v1','/token-boosts/latest/v1','/token-boosts/top/v1']
    addresses=[];errors=[]
    for endpoint in sources:
        try:
            result=get(endpoint)
            for item in result if isinstance(result,list) else []:
                if item.get('chainId')=='solana' and item.get('tokenAddress'):
                    addresses.append(item['tokenAddress'])
        except Exception as exc:errors.append(f'{endpoint}: {type(exc).__name__}')
    addresses=list(dict.fromkeys(addresses))[:180]
    pairs=[]
    for i in range(0,len(addresses),30):
        try:
            batch=get('/tokens/v1/solana/'+','.join(addresses[i:i+30]))
            if isinstance(batch,list):pairs.extend(batch)
        except Exception as exc:errors.append(f'batch {i//30}: {type(exc).__name__}')
        time.sleep(.2)
    by_token={}
    for p in pairs:
        if p.get('chainId')!='solana':continue
        addr=(p.get('baseToken') or {}).get('address')
        if not addr or addr not in addresses:continue
        if number((p.get('liquidity') or {}).get('usd'))>number((by_token.get(addr,{}).get('liquidity') or {}).get('usd')):
            by_token[addr]=p
    candidates=[]
    for addr,p in by_token.items():
        liq=number((p.get('liquidity') or {}).get('usd'))
        cap=number(p.get('marketCap') or p.get('fdv'))
        vol=number((p.get('volume') or {}).get('h1'))
        tx=(p.get('txns') or {}).get('h1') or {}
        buys=number(tx.get('buys'));sells=number(tx.get('sells'))
        change=number((p.get('priceChange') or {}).get('h1'))
        if not (liq>=15000 and cap>=20000 and vol>=10000 and buys>=20 and buys>sells and -10<=change<=80):continue
        score=round(min(liq/50000,2)*15+min(vol/max(liq,1),4)*12+min(buys/max(sells,1),3)*10+max(0,min(change,40))*.4,1)
        candidates.append({'address':addr,'symbol':(p.get('baseToken') or {}).get('symbol','?'), 'market_cap_usd':cap,'liquidity_usd':liq,'volume_h1_usd':vol,'buys_h1':int(buys),'sells_h1':int(sells),'price_change_h1_pct':change,'price_usd':p.get('priceUsd'),'dex':p.get('dexId'),'url':p.get('url'),'score':score,'status':'WATCH — UNVERIFIED RUG RISK'})
    candidates.sort(key=lambda c:c['score'],reverse=True)
    top=candidates[:5]
    state={'checked_at_utc':now,'discovered_addresses':len(addresses),'pairs':len(pairs),'qualified':len(candidates),'candidates':top,'errors':errors,'limitations':['Discovery endpoints are partial and promotion-biased','Holder concentration, authorities, deployer and sellability not verified','No trade recommendation or execution']}
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# JARVIS SOLANA TREND SCANNER',f'Проверка (UTC): {now}',f'Открити адреси: {len(addresses)} | Пазарни двойки: {len(pairs)} | Минали базов филтър: {len(candidates)}','', '**Всички резултати са WATCH / NO TRADE, докато не минат on-chain проверки за сигурност.**','']
    for i,c in enumerate(top,1):
        lines.extend([f"## {i}. {c['symbol']} — WATCH",f"Mint: `{c['address']}`",f"Liquidity ${c['liquidity_usd']:,.0f} | Market cap/FDV ${c['market_cap_usd']:,.0f} | 1h volume ${c['volume_h1_usd']:,.0f}",f"1h buys/sells: {c['buys_h1']}/{c['sells_h1']} | 1h change: {c['price_change_h1_pct']:+.1f}%",f"Source: {c['url']}","Risk: holder concentration / authorities / sellability UNKNOWN. No verified entry, SL or TP.",''])
    if not top:lines.append('Няма кандидати, преминали базовите филтри. Това не означава, че няма трендове на пазара.')
    if errors:lines.append('API errors: '+', '.join(errors))
    REPORT.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))
if __name__=='__main__':main()
