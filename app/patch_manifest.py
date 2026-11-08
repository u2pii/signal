# -*- coding: utf-8 -*-
"""给生成的安卓工程补 <queries>，不然 Android 11+ 查不到币安/Bitget/OKX 装没装，
canOpenUrl 永远返回 false，就只好退回浏览器。

在 CI 里 cap add android 之后跑一次。
"""
import io
import os
import sys

P = os.path.join("android", "app", "src", "main", "AndroidManifest.xml")

QUERIES = """    <queries>
        <package android:name="com.binance.dev" />
        <package android:name="com.binance.us" />
        <package android:name="com.bitget.exchange" />
        <package android:name="com.okx.wallet" />
        <package android:name="com.okex.gtx" />
        <intent>
            <action android:name="android.intent.action.VIEW" />
            <data android:scheme="binance" />
        </intent>
        <intent>
            <action android:name="android.intent.action.VIEW" />
            <data android:scheme="bitget" />
        </intent>
        <intent>
            <action android:name="android.intent.action.VIEW" />
            <data android:scheme="okx" />
        </intent>
    </queries>

"""

if not os.path.exists(P):
    print("找不到", P)
    sys.exit(1)

s = io.open(P, encoding="utf-8").read()
if "<queries>" in s:
    print("已经有 queries，跳过")
else:
    i = s.find("<application")
    if i < 0:
        print("Manifest 里没有 <application>")
        sys.exit(1)
    s = s[:i] + QUERIES + s[i:]
    io.open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("已插入 queries")

# 打印确认
s = io.open(P, encoding="utf-8").read()
print("queries 存在:", "<queries>" in s)
