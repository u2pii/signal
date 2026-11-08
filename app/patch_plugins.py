# -*- coding: utf-8 -*-
"""把自写的 AppLaunchPlugin 注册进 capacitor.plugins.json。

官方插件是 cap sync 时自动写进这个文件、由 Bridge 自动注册的；
手写的 registerPlugin 在 Capacitor 6 上没生效（真机报 unable to find plugin: AppLaunch），
所以这里直接补进清单，走同一条路。
"""
import io
import json
import os
import sys

P = os.path.join("android", "app", "src", "main", "assets", "capacitor.plugins.json")
CP = "io.github.u2pii.signal.AppLaunchPlugin"

if not os.path.exists(P):
    print("找不到", P)
    sys.exit(1)

raw = io.open(P, encoding="utf-8").read().strip() or "[]"
data = json.loads(raw)
if not isinstance(data, list):
    print("格式不对:", type(data))
    sys.exit(1)

has = any((x.get("classpath") == CP or x.get("pkg") == "AppLaunch") for x in data)
if has:
    print("已经注册过，跳过")
else:
    data.append({"pkg": CP, "classpath": CP})
    io.open(P, "w", encoding="utf-8", newline="\n").write(json.dumps(data, separators=(",", ":")))
    print("已注册 AppLaunchPlugin")

print("现有插件:", [x.get("pkg", "").split(".")[-1] for x in data])
