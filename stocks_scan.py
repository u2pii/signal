# -*- coding: utf-8 -*-
"""抓美股行情，生成 stocks.json 给网页用。

数据源 nasdaq.com 的公开接口（Actions 的机器能直连，比手机直连稳）。
每 2 小时跑一次，跟 funding.json 同一个节奏。
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

BJ = timezone(timedelta(hours=8))
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# (代码, 中文名, 资产类别)
LIST = [
    ("NVDA", "英伟达", "stocks"),
    ("TSLA", "特斯拉", "stocks"),
    ("AAPL", "苹果", "stocks"),
    ("MSFT", "微软", "stocks"),
    ("AMD", "超威", "stocks"),
    ("TSM", "台积电", "stocks"),
    ("META", "Meta", "stocks"),
    ("GOOGL", "谷歌", "stocks"),
    ("COIN", "Coinbase", "stocks"),
    ("QQQ", "纳指100", "etf"),
    ("SPY", "标普500", "etf"),
]


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def num(s):
    if s is None:
        return None
    try:
        return float(str(s).replace("$", "").replace(",", "").replace("%", "").strip())
    except Exception:
        return None


def quote(sym, cls):
    d = get("https://api.nasdaq.com/api/quote/%s/info?assetclass=%s" % (sym, cls))
    p = (d.get("data") or {}).get("primaryData") or {}
    return {
        "px": num(p.get("lastSalePrice")),
        "chg": num(p.get("percentageChange")),
        "net": num(p.get("netChange")),
        "vol": num(p.get("volume")),
    }


def history(sym, cls, days=300):
    end = datetime.now()
    start = end - timedelta(days=days * 2)
    u = ("https://api.nasdaq.com/api/quote/%s/historical?assetclass=%s"
         "&fromdate=%s&todate=%s&limit=400"
         % (sym, cls, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")))
    d = get(u)
    rows = ((d.get("data") or {}).get("tradesTable") or {}).get("rows") or []
    out = []
    for r in rows:
        c = num(r.get("close"))
        if c and c > 0:
            out.append({"h": num(r.get("high")) or c, "l": num(r.get("low")) or c, "c": c})
    out.reverse()
    return out


def stats(bars):
    if len(bars) < 20:
        return None
    cl = [b["c"] for b in bars]
    px = cl[-1]
    res = {"px": px}
    for n in (20, 60):
        if len(cl) >= n:
            res["ma%d" % n] = round(sum(cl[-n:]) / n, 2)
    tr = []
    for i in range(max(1, len(bars) - 14), len(bars)):
        b, prev = bars[i], bars[i - 1]
        tr.append(max(b["h"] - b["l"], abs(b["h"] - prev["c"]), abs(b["l"] - prev["c"])))
    atr = sum(tr) / len(tr) if tr else 0
    res["atr"] = round(atr / px * 100, 1) if px else 0
    yr = cl[-250:] if len(cl) >= 250 else cl
    hi, lo = max(yr), min(yr)
    res["hi"] = round(hi, 2)
    res["lo"] = round(lo, 2)
    res["from_hi"] = round((px / hi - 1) * 100, 1)
    res["from_lo"] = round((px / lo - 1) * 100, 1)
    res["n"] = len(cl)
    return res


def main():
    items = []
    for sym, name, cls in LIST:
        try:
            q = quote(sym, cls)
            st = stats(history(sym, cls)) or {}
            px = q.get("px") or st.get("px")
            if not px:
                print("跳过", sym, "没价格")
                continue
            it = {"s": sym, "n": name, "px": round(px, 2),
                  "chg": q.get("chg"),
                  "ma20": st.get("ma20"), "ma60": st.get("ma60"),
                  "atr": st.get("atr"), "hi": st.get("hi"), "lo": st.get("lo"),
                  "from_hi": st.get("from_hi"), "from_lo": st.get("from_lo")}
            items.append(it)
            print("%-6s %8.2f  %+6.2f%%  MA20 %8s  ATR %4s%%  距高 %s%%"
                  % (sym, it["px"], it["chg"] or 0,
                     it["ma20"], it["atr"], it["from_hi"]))
        except Exception as e:
            print("失败", sym, str(e)[:80])

    if not items:
        print("一个都没取到")
        return 1

    out = {
        "updated": datetime.now(BJ).strftime("%Y-%m-%d %H:%M"),
        "ts": int(time.time() * 1000),
        "n": len(items),
        "items": items,
    }
    with open("stocks.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("写过 stocks.json，%d 个" % len(items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
