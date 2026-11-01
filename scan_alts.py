# -*- coding: utf-8 -*-
"""山寨币做空扫描 —— 全部基于币安 U 本位永续合约
   价格、K线、交易对 与用户实际下单完全一致。
"""
import json, os, sys, time, urllib.request, urllib.error, statistics
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "alt_watch.json")
CACHE = os.path.join(HERE, "cache_bn")
os.makedirs(CACHE, exist_ok=True)
TZ = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
      "Accept": "application/json"}
BASES = ["https://www.binance.com", "https://fapi.binance.com"]
SKIP = {"USDC","FDUSD","TUSD","DAI","BUSD","PYUSD","XAUT","PAXG","USDD","USDE","RLUSD","USDY","USTC","EUR","AEUR","EURC"}

def get_json(path, retries=3, timeout=25):
    last = None
    for base in BASES:
        for i in range(retries):
            try:
                req = urllib.request.Request(base + path, headers=UA)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                last = e
                if e.code == 451: break
                time.sleep(3 if e.code == 429 else 1.2)
            except Exception as e:
                last = e; time.sleep(1.2)
    raise last

def klines(sym, limit=60):
    fn = os.path.join(CACHE, sym + ".json")
    if os.path.exists(fn) and time.time() - os.path.getmtime(fn) < 3600*4:
        try: return json.load(open(fn, encoding="utf-8"))
        except Exception: pass
    raw = get_json(f"/fapi/v1/klines?symbol={sym}&interval=1d&limit={limit}")
    bars = [{"t":int(k[0])//1000,"o":float(k[1]),"h":float(k[2]),"l":float(k[3]),"c":float(k[4]),"v":float(k[5])} for k in raw]
    bars.sort(key=lambda x: x["t"])
    json.dump(bars, open(fn,"w",encoding="utf-8"))
    return bars

def analyze(bars):
    if len(bars) < 40: return None
    cur = bars[-1]["c"]
    if cur <= 0: return None
    recent = bars[-6:]; max_day, max_idx = 0.0, None
    for i in range(1, len(recent)):
        prev = recent[i-1]["c"]
        if prev > 0:
            r = recent[i]["c"]/prev - 1
            if r > max_day: max_day, max_idx = r, len(bars)-len(recent)+i
    c20 = bars[-21]["c"]; prior20 = cur/c20 - 1 if c20 > 0 else 0
    vol_ratio = 0.0
    if max_idx and max_idx >= 21:
        base_v = statistics.mean([b["v"] for b in bars[max_idx-20:max_idx]]) or 1
        vol_ratio = bars[max_idx]["v"] / base_v
    cur_vol = statistics.mean([b["v"] for b in bars[-3:]]) or 0
    avg_vol = statistics.mean([b["v"] for b in bars[-23:-3]]) or 1
    now_vol = cur_vol/avg_vol
    amp = statistics.mean([(b["h"]-b["l"])/b["c"] if b["c"]>0 else 0 for b in bars[-20:]])
    hh = max(b["h"] for b in bars[-21:-1]); ll = min(b["l"] for b in bars[-21:-1])
    to_high = cur/hh - 1 if hh > 0 else 0
    high5 = max(b["h"] for b in bars[-5:]); dd5 = cur/high5 - 1 if high5 > 0 else 0
    return {"cur":cur,"max_day":max_day,"prior20":prior20,"vol_ratio":vol_ratio,
            "now_vol":now_vol,"amp":amp,"to_high":to_high,"drawdown5":dd5,"hh":hh,"ll":ll}

def risk_score(m):
    s = 0
    if m["max_day"] >= 0.50: s += 30
    elif m["max_day"] >= 0.30: s += 20
    elif m["max_day"] >= 0.15: s += 8
    if m["prior20"] >= 1.00: s += 30
    elif m["prior20"] >= 0.50: s += 20
    elif m["prior20"] >= 0.20: s += 10
    if 0 < m["vol_ratio"] < 1.5: s += 25
    elif m["vol_ratio"] < 2.5: s += 15
    elif m["vol_ratio"] < 5: s += 5
    if m["drawdown5"] <= -0.30: s += 15
    elif m["drawdown5"] <= -0.15: s += 8
    return min(s, 100)

def watch_score(m):
    s = 0
    if m["now_vol"] >= 5: s += 40
    elif m["now_vol"] >= 3: s += 28
    elif m["now_vol"] >= 2: s += 15
    if abs(m["prior20"]) < 0.25: s += 20
    if m["to_high"] > -0.03: s += 25
    elif m["to_high"] > -0.08: s += 15
    if m["amp"] >= 0.08: s += 15
    elif m["amp"] >= 0.05: s += 8
    return min(s, 100)

def fetch_market_structure():
    """采集币安现货+合约的成交额、基差、资金费率
       返回 {symbol: {spot_vol, fut_vol, basis, funding, mark, spot}}
    """
    out = {}
    # 1) 现货 24h
    spot = {}
    try:
        for t in get_json("/api/v3/ticker/24hr"):
            try:
                spot[t["symbol"]] = {"price": float(t["lastPrice"]), "qv": float(t["quoteVolume"])}
            except Exception:
                pass
    except Exception as e:
        print("  现货行情失败:", str(e)[:40], file=sys.stderr)

    # 2) 合约 24h
    fut = {}
    try:
        for t in get_json("/fapi/v1/ticker/24hr"):
            try:
                fut[t["symbol"]] = {"price": float(t["lastPrice"]), "qv": float(t["quoteVolume"])}
            except Exception:
                pass
    except Exception as e:
        print("  合约行情失败:", str(e)[:40], file=sys.stderr)

    # 3) 资金费率 + 标记价/指数价
    fund = {}
    try:
        for p in get_json("/fapi/v1/premiumIndex"):
            try:
                fund[p["symbol"]] = {
                    "funding": float(p.get("lastFundingRate") or 0),
                    "mark": float(p.get("markPrice") or 0),
                    "index": float(p.get("indexPrice") or 0),
                }
            except Exception:
                pass
    except Exception as e:
        print("  资金费率失败:", str(e)[:40], file=sys.stderr)

    for sym in set(fut) | set(fund):
        f = fut.get(sym)
        s = spot.get(sym)
        fd = fund.get(sym)
        if not f:
            continue
        item = {
            "fut_vol": f["qv"],
            "spot_vol": s["qv"] if s else 0,
            "fut_price": f["price"],
            "spot_price": s["price"] if s else 0,
            "funding": fd["funding"] if fd else None,
            "mark": fd["mark"] if fd else f["price"],
            "index": fd["index"] if fd else 0,
        }
        # 基差：标记价 vs 现货
        # 只在「币安现货真的存在」时才算基差
        # 没有币安现货时用 index 算会失真（index 可能混入薄盘交易所）
        if item["spot_price"] > 0 and item["mark"] > 0:
            item["basis"] = item["mark"] / item["spot_price"] - 1
        else:
            item["basis"] = None
        item["has_spot"] = item["spot_price"] > 0
        # 成交额倍数
        item["vol_mult"] = (item["fut_vol"] / item["spot_vol"]) if item["spot_vol"] > 0 else None
        out[sym] = item
    print(f"  市场结构 {len(out)} 条", file=sys.stderr)
    return out


def main():
    print("拉取币安合约列表...", flush=True)
    info = get_json("/fapi/v1/exchangeInfo")
    symbols = []
    for s in info.get("symbols", []):
        if (s.get("status")=="TRADING" and s.get("quoteAsset")=="USDT"
                and s.get("contractType")=="PERPETUAL" and s["baseAsset"] not in SKIP):
            symbols.append(s["symbol"])
    print(f"  永续合约 {len(symbols)} 个", flush=True)

    print("拉取 24h 行情...", flush=True)
    tickers = get_json("/fapi/v1/ticker/24hr")
    tk = {}
    for t in tickers:
        try:
            tk[t["symbol"]] = {"price":float(t["lastPrice"]),
                               "chg":float(t["priceChangePercent"])/100,
                               "qv":float(t["quoteVolume"])}
        except Exception: pass
    print(f"  行情 {len(tk)} 条", flush=True)

    cand = [(s, tk[s]) for s in symbols if s in tk and tk[s]["qv"] >= 500_000]
    cand.sort(key=lambda x: -x[1]["qv"])
    heavy = set(s for s,_ in cand[:120])
    pick = [(s,t) for s,t in cand if t["chg"] >= 0.15 or t["chg"] <= -0.10 or s in heavy]
    print(f"  分析 {len(pick)} 个合约\n", flush=True)

    rows = []
    for i,(sym,t) in enumerate(pick):
        try:
            bars = klines(sym)
            m = analyze(bars)
            if not m or m["amp"] < 0.015: continue
            m.update({"sym":sym.replace("USDT",""),"symbol":sym,"qv":t["qv"],"chg24":t["chg"],"bars":bars})
            m["risk"] = risk_score(m); m["watch"] = watch_score(m)
            rows.append(m)
        except Exception: pass
        if (i+1) % 50 == 0: print(f"  已处理 {i+1}/{len(pick)}", flush=True)
        time.sleep(0.06)
    print(f"有效 {len(rows)}\n")

    print("采集市场结构（基差/资金费率/现货合约比）...", flush=True)
    mkt = fetch_market_structure()

    # 把市场结构挂到每个币上
    for m in rows:
        st = mkt.get(m["symbol"], {})
        m["basis"] = st.get("basis")
        m["funding"] = st.get("funding")
        m["vol_mult"] = st.get("vol_mult")
        m["spot_vol"] = st.get("spot_vol", 0)
        # 空头拥挤：合约大幅贴水 + 资金费率趴在低位
        crowded = False
        if m.get("basis") is not None and m["basis"] < -0.05:
            crowded = True
        if m.get("basis") is not None and m["basis"] < -0.03 and m.get("funding") is not None and m["funding"] < 0.0002:
            crowded = True
        m["crowded"] = crowded

    shorts = []
    for m in rows:
        bars = m["bars"]; hit = None
        for k in (1,2):
            idx = len(bars)-k
            if idx < 1: continue
            prev = bars[idx-1]["c"]
            if prev <= 0: continue
            r = bars[idx]["c"]/prev - 1
            if r >= 0.30:
                hit = {"pct":r*100,"date":datetime.fromtimestamp(bars[idx]["t"],TZ).strftime("%m-%d"),"days_ago":k-1}
                break
        if not hit: continue
        # ===== 空头陷阱过滤 =====
        # 1) 合约大幅贴水 → 空头已经拥挤
        # 2) 合约成交额远大于现货 → 纯杠杆对赌，易插针
        skip_reason = None
        if m.get("basis") is not None and m["basis"] < -0.05:
            skip_reason = "合约贴水 %.1f%%，空头已拥挤" % (m["basis"] * 100)
        elif m.get("vol_mult") is not None and m["vol_mult"] > 20:
            skip_reason = "合约/现货成交额 %.0f 倍，纯杠杆对赌" % m["vol_mult"]
        if skip_reason:
            print(f"  跳过 {m['sym']}：{skip_reason}", file=sys.stderr)
            continue
        shorts.append({"sym":m["sym"],"symbol":m["symbol"],"price":m["cur"],
                       "pump_pct":round(hit["pct"],1),"pump_date":hit["date"],"days_ago":hit["days_ago"],
                       "prior20":round(m["prior20"]*100,1),"vol_ratio":round(m["vol_ratio"],2),
                       "qv":round(m["qv"]/10000,0),"risk":m["risk"],
                       "chg24":round(m.get("chg24",0)*100,2),
                       "basis":(round(m["basis"]*100,2) if m.get("basis") is not None else None),
                       "vol_mult":(round(m["vol_mult"],1) if m.get("vol_mult") is not None else None)})
    shorts.sort(key=lambda x: -x["pump_pct"])

    risky = [m for m in rows if m["risk"] >= 55 and m["max_day"] >= 0.20]
    risky.sort(key=lambda x: -x["risk"])
    watch = [m for m in rows if m["watch"] >= 45 and m["risk"] < 50 and m["to_high"] > -0.10]
    watch.sort(key=lambda x: -x["watch"])

    def slim(m):
        return {"sym":m["sym"],"price":m["cur"],
                "chg24":round(m.get("chg24",0)*100,2),
                "max_day":round(m["max_day"]*100,1),
                "prior20":round(m["prior20"]*100,1),"vol_ratio":round(m["vol_ratio"],2),
                "now_vol":round(m["now_vol"],2),"to_high":round(m["to_high"]*100,1),
                "drawdown5":round(m["drawdown5"]*100,1),"amp":round(m["amp"]*100,1),
                "qv":round(m["qv"]/10000,0),"risk":m["risk"],"watch":m["watch"]}

    # ===== 空头拥挤预警（可能继续挤压上涨，不建议做空）=====
    crowded = [m for m in rows if m.get("crowded")]
    crowded.sort(key=lambda x: -x["max_day"])
    def cslim(m):
        d = slim(m)
        d["basis"] = round(m["basis"] * 100, 2) if m.get("basis") is not None else None
        d["funding"] = round(m["funding"] * 100, 4) if m.get("funding") is not None else None
        d["vol_mult"] = round(m["vol_mult"], 1) if m.get("vol_mult") is not None else None
        return d

    # ===== 24 小时涨跌榜 =====
    ranked = sorted(rows, key=lambda x: -x.get("chg24", 0))
    gainers = [slim(m) for m in ranked[:8] if m.get("chg24", 0) > 0]
    losers = [slim(m) for m in ranked[-8:] if m.get("chg24", 0) < 0]
    losers.reverse()

    payload = {"updated":datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),"source":"binance-futures",
               "scanned":len(rows),"short":shorts[:10],
               "gainers":gainers,"losers":losers,
               "crowded":[cslim(m) for m in crowded[:10]],
               "risky":[slim(m) for m in risky[:15]],"watch":[slim(m) for m in watch[:15]],
               "note":"价格与K线均来自币安U本位永续合约。做空规则：1x、不挂止损、持有20天、每笔5%本金。已自动排除合约贴水>5%或合约/现货成交额>20倍的标的（空头陷阱）。"}
    json.dump(payload, open(OUT,"w",encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"做空信号 {len(shorts)} / 风险 {len(risky)} / 观察 {len(watch)}\n")
    print("--- 做空信号 ---")
    for s in shorts[:10]:
        print(f"  {s['sym']:<10} {s['symbol']:<14} 暴涨{s['pump_pct']:>6.1f}%  现价{s['price']:<12} 前20日{s['prior20']:>7.1f}%  量能{s['vol_ratio']:>6.2f}x")
    print("\n--- 24h 涨幅榜 ---")
    for m in gainers:
        print(f"  {m['sym']:<10} {m['chg24']:>+7.2f}%  现价{m['price']:<12} "
              f"日最大{m['max_day']:>6.1f}%  额{m['qv']:>8.0f}万U")
    print("\n--- 24h 跌幅榜 ---")
    for m in losers:
        print(f"  {m['sym']:<10} {m['chg24']:>+7.2f}%  现价{m['price']:<12} "
              f"日最大{m['max_day']:>6.1f}%  额{m['qv']:>8.0f}万U")

    print("\n--- 空头拥挤预警（别做空，可能继续挤）---")
    for m in crowded[:6]:
        b = f"{m['basis']*100:+.1f}%" if m.get("basis") is not None else "—"
        f = f"{m['funding']*100:+.3f}%" if m.get("funding") is not None else "—"
        v = f"{m['vol_mult']:.0f}x" if m.get("vol_mult") is not None else "—"
        print(f"  {m['sym']:<10} 现价{m['cur']:<12} 日涨{m['max_day']*100:>6.1f}%  "
              f"基差{b:>7}  费率{f:>8}  合约/现货{v:>6}")

    print("\n--- 风险名单 ---")
    for m in risky[:6]:
        print(f"  {m['sym']:<10} 风险{m['risk']:>3}  日涨{m['max_day']*100:>6.1f}%  20日{m['prior20']*100:>7.1f}%  现价{m['cur']}")
    print(f"\n已写入 {OUT}")

if __name__ == "__main__":
    main()
