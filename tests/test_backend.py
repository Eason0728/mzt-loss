#!/usr/bin/env python3
"""後端端對端測試。用 requests（curl 對 Apps Script 的 302 會騙人）。

用法：python3 tests/test_backend.py
"""
import sys

import requests

URL = ("https://script.google.com/macros/s/"
       "AKfycbzpCW2ZwSjX14D0Ry5rMnNmoaBr52VHDKWKiQlUjSW0zy1jdJGlaeRicgsvWn-LQqdNKA/exec")

results = []


def call(payload):
    r = requests.post(URL, data=str(payload).replace("'", '"').encode("utf-8"),
                      headers={"Content-Type": "text/plain;charset=utf-8"}, timeout=60)
    r.raise_for_status()
    return r.json()


def post(payload):
    import json
    r = requests.post(URL, data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "text/plain;charset=utf-8"}, timeout=60)
    r.raise_for_status()
    return r.json()


def check(name, got, want):
    results.append((name, got == want, got, want))


REC = {
    "id": "L-20260801130000-e2etest1", "日期": "2026-08-01", "店別": "墨竹亭光復",
    "品類": "肉類", "品名": "端對端測試雞胸肉", "耗損量": 1.5, "單位": "包",
    "單位成本": 120, "金額": 180, "原因": "報廢", "原因說明": "", "備註": "e2e",
}


def main() -> int:
    r = post({"action": "ping"})
    check("ping 通", r.get("ok"), True)

    r = post({"action": "bootstrap"})
    check("bootstrap 成功", r.get("ok"), True)
    ss_url = r["data"].get("ssUrl", "")
    check("試算表已自動建立", ss_url.startswith("https://docs.google.com/spreadsheets/"), True)
    print("  試算表：", ss_url)

    r = post({"action": "saveItem", "item": {
        "品名": "端對端測試雞胸肉", "品類": "肉類", "單位": "包", "單位成本": 120, "停用": False}})
    names = [i["品名"] for i in r["data"]["items"]]
    check("saveItem 寫入", "端對端測試雞胸肉" in names, True)

    r = post({"action": "saveItem", "item": {
        "品名": "端對端測試雞胸肉", "品類": "肉類", "單位": "包", "單位成本": 200, "停用": False}})
    same = [i for i in r["data"]["items"] if i["品名"] == "端對端測試雞胸肉"]
    check("同名只有一列（upsert）", len(same), 1)
    check("單價已更新", same[0]["單位成本"], 200)

    r = post({"action": "addLoss", "records": [REC]})
    check("addLoss 接受", r["data"]["accepted"], [REC["id"]])

    r = post({"action": "addLoss", "records": [REC]})
    check("同 id 第二次被擋", r["data"]["duplicated"], [REC["id"]])
    r = post({"action": "addLoss", "records": [REC]})
    check("同 id 第三次被擋", r["data"]["duplicated"], [REC["id"]])

    r = post({"action": "listLoss", "from": "2026-08-01", "to": "2026-08-01"})
    rows = [x for x in r["data"]["records"] if x["id"] == REC["id"]]
    check("試算表只有一列", len(rows), 1)
    check("日期回傳格式", rows[0]["日期"], "2026-08-01")
    check("金額是送上去的快照", rows[0]["金額"], 180)
    check("單位成本快照未被新單價汙染", rows[0]["單位成本"], 120)
    check("作廢預設 false", rows[0]["作廢"], False)

    r = post({"action": "voidLoss", "id": REC["id"]})
    check("voidLoss 成功", r["data"]["ok"], True)
    r = post({"action": "listLoss", "from": "2026-08-01", "to": "2026-08-01"})
    rows = [x for x in r["data"]["records"] if x["id"] == REC["id"]]
    check("作廢後仍在（不刪列）", len(rows), 1)
    check("作廢已標記", rows[0]["作廢"], True)
    check("作廢後金額原封不動", rows[0]["金額"], 180)

    r = post({"action": "不存在的動作"})
    check("不認得的 action 回錯誤而非爆掉", r.get("ok"), False)

    bad = 0
    for name, ok, got, want in results:
        if ok:
            print(f"  ok   {name}")
        else:
            bad += 1
            print(f"  FAIL {name}: got={got!r} want={want!r}")
    print(f"\n{len(results) - bad}/{len(results)} 通過")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
