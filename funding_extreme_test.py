# -*- coding: utf-8 -*-
"""资金费率极值是否预示反转？（在 GitHub Actions 上跑，因为币安合约接口国内直连不通）

事件研究设计：
- 每个币取多年资金费率历史（8 小时一条）+ 日线收盘
- 费率按天求和
- 每天算「今天这一刻在过去 90 天里的分位」（只用历史，无未来函数）
- 事件 A：分位 >= 90% 且费率为正（多头极度拥挤）
- 事件 B：分位 <= 10% 且费率为负（空头极度拥挤）
- 比较事件后 5/10/20 天收益 vs 全样本基准
- 用 Welch t 检验看「事件组 - 基准」是否显著
"""
import json
import math
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FAPI = ["https://www.binance.com", "https://fapi.binance.com"]
SPOT = ["https://data-api.binance.vision", "https://api.binance.com"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT", "LINKUSDT",
        "ADAUSDT", "AVAXUSDT", "BNBUSDT", "LTCUSDT", "TRXUSDT", "DOTUSDT",
        "1000PEPEUSDT", "WIFUSDT", "ORDIUSDT", "SUIUSDT", "APTUSDT", "ARBUSDT",
        "OPUSDT", "INJUSDT"]

LOOKBACK = 90
FWD = (5, 10, 20)
PCT = 0.10
YEARS = 3


def get(bases, path, timeout=30):
    last = None
    for b in bases:
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(b + path, headers=UA), timeout=timeout).read())
        except Exception as e:
            last = e
    raise last


def klines(sym, days):
    out = []
    end = int(time.time() * 1000)
    start = end - days * 86400 * 1000
    while start < end:
        d = get(SPOT, "/api/v3/klines?symbol=%s&interval=1d&limit=1000&startTime=%d"
                % (sym, start))
        if not d:
            break
        out += d
        start = d[-1][0] + 86400 * 1000
        if len(d) < 1000:
            break
    return [{"t": int(x[0]), "c": float(x[4])} for x in out]


def funding(sym, years):
    end = int(time.time() * 1000)
    start = end - years * 365 * 86400 * 1000
    out = []
    cur = start
    while cur < end:
        try:
            d = get(FAPI, "/fapi/v1/fundingRate?symbol=%s&limit=1000&startTime=%d"
                    % (sym, cur))
        except Exception:
            break
        if not d:
            break
        out += d
        nxt = int(d[-1]["fundingTime"]) + 1
        if nxt <= cur:
            break
        cur = nxt
        if len(d) < 1000:
            break
    return [{"t": int(x["fundingTime"]), "r": float(x["fundingRate"])} for x in out]


def welch(a, b):
    na, nb = len(a), len(b)
    if na < 5 or nb < 5:
        return 0.0
    ma, mb = sum(a) / na, sum(b) / nb
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    se = math.sqrt(va / na + vb / nb)
    return (ma - mb) / se if se > 0 else 0.0


def main():
    hi = {f: [] for f in FWD}
    lo = {f: [] for f in FWD}
    base = {f: [] for f in FWD}
    per_sym = []

    for sym in SYMS:
        try:
            ks = klines(sym, YEARS * 365)
            fr = funding(sym, YEARS)
        except Exception as e:
            print("跳过", sym, str(e)[:60])
            continue
        if len(ks) < LOOKBACK + 30 or len(fr) < 200:
            print("样本不足", sym, len(ks), len(fr))
            continue

        daily = {}
        for x in fr:
            d = time.strftime("%Y-%m-%d", time.gmtime(x["t"] / 1000))
            daily[d] = daily.get(d, 0.0) + x["r"]
        days = [time.strftime("%Y-%m-%d", time.gmtime(k["t"] / 1000)) for k in ks]
        frd = [daily.get(d, 0.0) for d in days]
        cl = [k["c"] for k in ks]

        nh = nl = 0
        for i in range(LOOKBACK, len(ks) - max(FWD)):
            win = frd[i - LOOKBACK:i]
            cur = frd[i]
            if sum(1 for x in win if abs(x) > 0) < 30:
                continue
            rank = sum(1 for x in win if x < cur) / len(win)
            fwd = {f: (cl[i + f] / cl[i] - 1) * 100 for f in FWD}
            for f in FWD:
                base[f].append(fwd[f])
            if rank >= 1 - PCT and cur > 0:
                nh += 1
                for f in FWD:
                    hi[f].append(fwd[f])
            elif rank <= PCT and cur < 0:
                nl += 1
                for f in FWD:
                    lo[f].append(fwd[f])
        per_sym.append((sym, len(ks), len(fr), nh, nl))
        print("%-14s 日线 %4d  费率 %5d ｜ 极正 %3d ｜ 极负 %3d" % (sym, len(ks), len(fr), nh, nl))

    print("\n=== 汇总 ===")
    print("样本：" + ", ".join("%s(%d/%d)" % (s[0], s[3], s[4]) for s in per_sym))
    print()
    print("%-6s %-12s %-22s %-28s %-28s" % ("天数", "基准均值%", "极正费率后%", "极负费率后%", "显著性"))
    for f in FWD:
        b = base[f]
        bm = sum(b) / len(b) if b else 0
        hm = sum(hi[f]) / len(hi[f]) if hi[f] else 0
        lm = sum(lo[f]) / len(lo[f]) if lo[f] else 0
        t_hi = welch(hi[f], b)
        t_lo = welch(lo[f], b)
        print("%-6d %-12.3f %+-8.3f (n=%4d)     %+-8.3f (n=%4d)    正:t=%+.2f  负:t=%+.2f"
              % (f, bm, hm, len(hi[f]), lm, len(lo[f]), t_hi, t_lo))
    print()
    print("判读：|t| > 1.96 才算显著。")
    print("  极正费率 t 显著为负 → 多头拥挤后确实会跌 → 可做空")
    print("  极负费率 t 显著为正 → 空头拥挤后确实会涨 → 可做多")


if __name__ == "__main__":
    main()
