# -*- coding: utf-8 -*-
"""给 scan_alts.py 用的暴涨预测评分

研究依据（70991 个日样本、474 个暴涨日）：
  基础暴涨率 0.668%
  综合评分前 1% → 8.32%（12.5 倍）
  样本内 6.1x / 样本外 6.9x  —— 稳定

六个特征（越高越容易暴涨）：
  amp   近5日平均振幅      最强（最高档 2.30%）
  gap   距20日低点         最高档 1.94%
  r5    前5日涨幅          最高档 1.65%
  vr5   量比 5日/20日      最高档 1.61%
  atrc  ATR5/ATR20 扩张    最高档 1.58%
  r1    前1日涨幅          最高档 1.49%
"""
import statistics


def _atr(bars, i, n):
    s = 0.0
    cnt = 0
    for k in range(i - n + 1, i + 1):
        if k <= 0:
            continue
        h, l = bars[k]["h"], bars[k]["l"]
        pc = bars[k - 1]["c"]
        s += max(h - l, abs(h - pc), abs(l - pc))
        cnt += 1
    return s / cnt if cnt else 0


def pump_features(bars):
    """用最后一根已收盘的 K 线算特征（不含未来信息）"""
    if not bars or len(bars) < 45:
        return None
    closed = bars[:-1]            # 排除进行中的当天
    if len(closed) < 40:
        return None
    i = len(closed)             # 用 closed[i-1] 作基准
    c = closed[i - 1]["c"]
    if c <= 0:
        return None

    def ret(k):
        j = i - 1 - k
        if j < 0 or closed[j]["c"] <= 0:
            return None
        return c / closed[j]["c"] - 1

    r1, r5, r20 = ret(1), ret(5), ret(20)
    if r1 is None or r5 is None or r20 is None:
        return None

    v5 = statistics.mean([b["v"] for b in closed[i - 5:i]])
    v20 = statistics.mean([b["v"] for b in closed[i - 20:i]])
    vr5 = (v5 / v20) if v20 > 0 else 0

    a5 = _atr(closed, i - 1, 5)
    a20 = _atr(closed, i - 1, 20)
    atrc = (a5 / a20) if a20 > 0 else 1

    seg = closed[i - 20:i]
    hi = max(b["h"] for b in seg)
    lo = min(b["l"] for b in seg)
    gap = c / lo - 1 if lo > 0 else 0
    to_hi = c / hi - 1 if hi > 0 else 0

    amps = []
    for b in closed[i - 5:i]:
        if b["o"] > 0:
            amps.append((b["h"] - b["l"]) / b["o"])
    amp = statistics.mean(amps) if amps else 0

    return {"amp": amp, "gap": gap, "r5": r5, "r20": r20,
            "vr5": vr5, "atrc": atrc, "r1": r1, "to_hi": to_hi,
            "close": c}


WEIGHTS = [("amp", 1.5), ("gap", 1.2), ("r5", 1.0),
           ("vr5", 0.8), ("atrc", 0.8), ("r1", 0.6)]


def score_universe(feats_list):
    """feats_list: [{"sym":..., "feat":{...}}] → 原地写入 score(0~100)"""
    items = [x for x in feats_list if x.get("feat")]
    if len(items) < 5:
        for x in feats_list:
            x["score"] = 0.0
        return
    for key, w in WEIGHTS:
        vals = sorted(x["feat"][key] for x in items)
        n = len(vals)
        for x in items:
            v = x["feat"][key]
            # 分位排名
            lo, hi = 0, n
            while lo < hi:
                mid = (lo + hi) // 2
                if vals[mid] < v:
                    lo = mid + 1
                else:
                    hi = mid
            rank = lo / n
            x["score"] = x.get("score", 0.0) + w * rank
    # 归一化到 0~100
    tot_w = sum(w for _, w in WEIGHTS)
    for x in items:
        x["score"] = round(x["score"] / tot_w * 100, 1)
    for x in feats_list:
        x.setdefault("score", 0.0)
