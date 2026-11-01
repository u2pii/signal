# -*- coding: utf-8 -*-
"""一键更换主密码
   用法（PowerShell）：
     $env:NEW_PW="你的新密码"
     python change_pw.py

   会做三件事：
     1. 更新 GitHub Secret MASTER_PW
     2. 用新密码重新生成 token.json 并上传
     3. 触发一次 token.yml 验证
"""
import base64
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_token

OWNER, REPO = "u2pii", "signal"
HERE = os.path.dirname(os.path.abspath(__file__))


def api(method, path, payload=None):
    args = ["gh", "api", "-X", method, path, "-H", "Accept: application/vnd.github+json"]
    tmp = None
    if payload is not None:
        fd, tmp = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        args += ["--input", tmp]
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if tmp:
        try:
            os.remove(tmp)
        except Exception:
            pass
    if p.returncode != 0:
        return None, p.stderr.strip()[:250]
    try:
        return (json.loads(p.stdout) if p.stdout.strip() else {}), None
    except Exception:
        return p.stdout, None


def set_secret(name, value):
    pub, err = api("GET", f"/repos/{OWNER}/{REPO}/actions/secrets/public-key")
    if err:
        return "取公钥失败: " + err
    try:
        from nacl import encoding, public as np
    except ImportError:
        return "缺少 pynacl：python -m pip install pynacl"
    pk = np.PublicKey(pub["key"].encode(), encoding.Base64Encoder())
    enc = base64.b64encode(np.SealedBox(pk).encrypt(value.encode())).decode()
    r, err = api("PUT", f"/repos/{OWNER}/{REPO}/actions/secrets/{name}",
                 {"encrypted_value": enc, "key_id": pub["key_id"]})
    return "ok" if not err else err


def upload_token():
    local = os.path.join(HERE, "token.json")
    info, _ = api("GET", f"/repos/{OWNER}/{REPO}/contents/token.json")
    sha = info.get("sha") if isinstance(info, dict) else None
    raw = open(local, "rb").read()
    body = {"message": "chore: rotate master password", "content": base64.b64encode(raw).decode(),
            "branch": "main"}
    if sha:
        body["sha"] = sha
    r, err = api("PUT", f"/repos/{OWNER}/{REPO}/contents/token.json", body)
    return "ok" if not err else err


def main():
    pw = os.environ.get("NEW_PW", "").strip()
    if not pw:
        print("用法：$env:NEW_PW=\"新密码\"; python change_pw.py")
        sys.exit(1)
    if len(pw) < 10:
        print("密码太短，至少 10 位")
        sys.exit(1)

    from datetime import datetime, timezone, timedelta
    TZ = timezone(timedelta(hours=8))
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    yest = (datetime.now(TZ) - timedelta(days=1)).strftime("%Y-%m-%d")

    daily = gen_token.make_token(pw, today)
    invite = gen_token.make_token(pw, "INVITE30")

    print("=" * 52)
    print("  新密码        :", pw)
    print("  今日口令      :", daily)
    print("  30天邀请码    :", invite)
    print("=" * 52)

    payload = {
        "date": today,
        "hash": gen_token.verify_hash(daily, today),
        "prev": {"date": yest, "hash": gen_token.verify_hash(gen_token.make_token(pw, yest), yest)},
        "invite": {"hash": gen_token.h(invite + "|INVITE30"), "days": 30},
        "updated": datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
    }
    with open(os.path.join(HERE, "token.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("1) 本地 token.json 已更新")

    print("2) 更新 GitHub Secret ...", set_secret("MASTER_PW", pw))
    print("3) 上传 token.json ...", upload_token())

    p = subprocess.run(["gh", "workflow", "run", "token.yml", "--repo", f"{OWNER}/{REPO}"],
                       capture_output=True, text=True)
    print("4) 触发 token.yml ...", "ok" if p.returncode == 0 else p.stderr.strip()[:100])

    print()
    print("完成。注意事项：")
    print("  · 旧口令、旧邀请码立即失效")
    print("  · 已经进去过的设备不会掉线（授权到期前一直有效）")
    print("  · 想让某台设备重新验证：清掉它的浏览器数据")


if __name__ == "__main__":
    main()
