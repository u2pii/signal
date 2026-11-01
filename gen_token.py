# -*- coding: utf-8 -*-
"""每日口令生成器
   算法必须和 key.html / index.html 里的 JS 完全一致。

   口令 = 由「主密码 + 日期」迭代哈希得到，不从任何地方读取明文。
   仓库里只提交口令的哈希，所以：
     · 你能用主密码在本地算出今天的口令
     · 别人拿到 token.json 只有哈希，反推不出 10 位口令（32^10 ≈ 1e15）
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "token.json")
TZ = timezone(timedelta(hours=8))
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # 去掉易混淆的 0 O I 1


def h(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def make_token(password, date_str, rounds=20000):
    x = h(password + ":" + date_str)
    for _ in range(rounds):
        x = h(x + password)
    # 取前 20 个 hex 字符 → 每 2 个转成一个字母
    tok = "".join(ALPHABET[int(x[i * 2:i * 2 + 2], 16) % 32] for i in range(10))
    return tok


def verify_hash(token, date_str):
    return h(token + "|" + date_str)


def main():
    pw = os.environ.get("MASTER_PW", "").strip()
    if not pw:
        print("缺少环境变量 MASTER_PW", file=sys.stderr)
        sys.exit(1)

    today = datetime.now(TZ).strftime("%Y-%m-%d")
    yest = (datetime.now(TZ) - timedelta(days=1)).strftime("%Y-%m-%d")

    tok_today = make_token(pw, today)
    payload = {
        "date": today,
        "hash": verify_hash(tok_today, today),
        # 昨天生成的仍然有效，避免 0 点前后卡住
        "prev": {"date": yest, "hash": verify_hash(make_token(pw, yest), yest)},
        "updated": datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    print(f"日期 {today}  口令 {tok_today}")
    print(f"已写入 {OUT}")


if __name__ == "__main__":
    main()
