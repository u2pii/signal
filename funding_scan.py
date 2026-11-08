# -*- coding: utf-8 -*-
"""抓币安 U 本位永续的资金费率，生成 funding.json 给网页用。

要点：
- 正费率 = 多头付钱给空头 → 买现货 + 做空永续 = 收租（用户要的套保套利）
- 年化 = 单次费率 ×（24/结算间隔）× 365
- 结算间隔大多数是 8 小时，少数币被改成 4/2/1 小时，取 /fapi/v1/fundingInfo
- 只保留 USDT 本位、24h 成交额 >= 500 万的，避免僵尸币
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

BASES = ["https://www.binance.com", "https://fapi.binance.com"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BJ = timezone(timedelta(hours=8))

MIN_VOL_TOP = 5_000_000.0     # 进榜单的最低 24h 成交额（USDT）
MIN_VOL_MAP = 200_000.0       # 进查询表的最低成交额
TOP_N = 40
NEG_N = 20


def get_json(path, timeout=30):
    last = None
    for base in BASES:
        try:
            req = urllib.request.Request(base + path, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:      # noqa: BLE001
            last = e
    raise last


def main():
    print("拉 premiumIndex ...")
    prem = get_json("/fapi/v1/premiumIndex")
    print("  ", len(prem), "个合约")

    print("拉 24h ticker ...")
    tick = get_json("/fapi/v1/ticker/24hr")
    vol = {}
    for t in tick:
        try:
            vol[t["symbol"]] = float(t["quoteVolume"])
        except Exception:           # noqa: BLE001
            pass
    print("  ", len(vol), "个有成交额")

    ivl = {}
    try:
        finfo = get_json("/fapi/v1/fundingInfo")
        for x in finfo:
            if x.get("symbol"):
                ivl[x["symbol"]] = int(x.get("fundingIntervalHours") or 8)
        print("   自定义结算间隔:", len(ivl), "个")
    except Exception as e:          # noqa: BLE001
        print("   fundingInfo 拿不到，全部按 8h 算：", str(e)[:80])

    ts = time.time()
    now_ms = int(ts * 1000)
    rows = []
    table = {}

    for p in prem:
        sym = p.get("symbol") or ""
        if not sym.endswith("USDT") or "_" in sym:
            continue
        try:
            rate = float(p.get("lastFundingRate") or 0)
            mark = float(p.get("markPrice") or 0)
            idx = float(p.get("indexPrice") or 0)
            nxt = int(p.get("nextFundingTime") or 0)
        except Exception:           # noqa: BLE001
            continue
        base = sym[:-4]
        v = vol.get(sym, 0.0)
        h = ivl.get(sym, 8)
        if h <= 0:
            h = 8

        per_day = rate * (24.0 / h)
        ann = per_day * 365.0 * 100.0
        basis = ((mark / idx - 1.0) * 100.0) if idx > 0 else 0.0

        if v >= MIN_VOL_MAP and base:
            table[base] = {
                "r": round(rate, 6),
                "i": h,
                "n": nxt,
                "v": int(v),
            }

        if not base or v < MIN_VOL_TOP:
            continue
        rows.append({
            "s": base,
            "rate": round(rate * 100, 4),       # 单次费率 %
            "i": h,
            "ann": round(ann, 1),               # 年化 %
            "basis": round(basis, 3),           # 标记价相对指数价的溢价 %
            "vol": int(v),
            "next": nxt,
            "price": mark,
        })

    pos = sorted([r for r in rows if r["rate"] > 0], key=lambda x: -x["ann"])[:TOP_N]
    neg = sorted([r for r in rows if r["rate"] < 0], key=lambda x: x["ann"])[:NEG_N]

    out = {
        "updated": datetime.fromtimestamp(ts, BJ).strftime("%Y-%m-%d %H:%M"),
        "ts": now_ms,
        "count": len(rows),
        "top": pos,
        "neg": neg,
        "map": table,
    }
    with open("funding.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    print("写过 funding.json")
    print("  候选合约 %d，正费率榜 %d，负费率榜 %d，查询表 %d"
          % (len(rows), len(pos), len(neg), len(table)))
    for r in pos[:8]:
        print("    %-10s 年化 %8.1f%%  每%dh %6.4f%%  额 %6.1fM"
              % (r["s"], r["ann"], r["i"], r["rate"], r["vol"] / 1e6))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:          # noqa: BLE001
        print("失败:", e)
        sys.exit(1)
