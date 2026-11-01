# -*- coding: utf-8 -*-
"""单个币的币安合约体检（在 GitHub Actions 上跑，本地连不上币安）
   用法：python probe.py LYNUSDT
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
BASE = "https://www.binance.com"
TZ = timezone(timedelta(hours=8))


def g(path, timeout=20):
    req = urllib.request.Request(BASE + path, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main():
    sym = (sys.argv[1] if len(sys.argv) > 1 else "LYNUSDT").upper()
    print(f"===== {sym} =====")

    t = g(f"/fapi/v1/ticker/24hr?symbol={sym}")
    print(f"价格 {t['lastPrice']}   24h {t['priceChangePercent']}%")
    print(f"24h最高 {t['highPrice']}  最低 {t['lowPrice']}")
    print(f"合约24h成交额 {float(t['quoteVolume'])/1e6:.2f}M USDT")

    oi = g(f"/fapi/v1/openInterest?symbol={sym}")
    print(f"持仓量 {oi['openInterest']} 张")

    pm = g(f"/fapi/v1/premiumIndex?symbol={sym}")
    mark = float(pm["markPrice"] or 0)
    idx = float(pm["indexPrice"] or 0)
    print(f"标记价 {mark}   指数价 {idx}")
    print(f"资金费率 {float(pm['lastFundingRate'])*100:+.4f}%")

    # 持仓名义
    try:
        ei = g(f"/fapi/v1/exchangeInfo")
        mult = None
        for s in ei["symbols"]:
            if s["symbol"] == sym:
                for f in s.get("filters", []):
                    if f.get("filterType") == "LOT_SIZE":
                        mult = float(f.get("stepSize") or 0)
                break
        print(f"最小变动 {mult}")
    except Exception as e:
        print("合约信息失败:", str(e)[:40])

    print("\n最近 15 根日线：")
    lk = g(f"/fapi/v1/klines?symbol={sym}&interval=1d&limit=15")
    for k in lk:
        d = datetime.fromtimestamp(int(k[0]) / 1000, TZ).strftime("%m-%d")
        o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
        v = float(k[7])
        print(f"  {d} 开{o:.6f} 高{h:.6f} 低{l:.6f} 收{c:.6f} {(c/o-1)*100:+6.1f}% 额{v/1e6:6.2f}M")

    print("\n最近 12 根小时线：")
    lk = g(f"/fapi/v1/klines?symbol={sym}&interval=1h&limit=12")
    for k in lk:
        d = datetime.fromtimestamp(int(k[0]) / 1000, TZ).strftime("%m-%d %H:%M")
        o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
        v = float(k[7])
        print(f"  {d} 开{o:.6f} 高{h:.6f} 低{l:.6f} 收{c:.6f} {(c/o-1)*100:+6.1f}% 额{v/1e3:8.0f}K")


if __name__ == "__main__":
    main()
