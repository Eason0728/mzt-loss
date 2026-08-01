#!/usr/bin/env python3
"""把上線版 index.html 包成一份「離線示範版」：塞滿假資料、後端改成本機模擬。"""
import json
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(20260801)

SRC = Path("/Users/guoeason/mzt-loss/index.html")
OUT = Path("/Users/guoeason/mzt-loss/demo.html")
# 示範版跟正式版同網域，儲存空間必須完全分開，否則假資料會污染正式版的本機快取
KEY = "mztlossdemo."

ITEMS = [
    ("五花肉片", "肉類", "包", 180), ("雞腿肉", "肉類", "公斤", 195),
    ("牛肋條", "肉類", "公斤", 420), ("松阪豬", "肉類", "包", 260),
    ("白蝦", "海鮮", "斤", 320), ("蛤蜊", "海鮮", "斤", 150),
    ("鮭魚肚", "海鮮", "片", 95), ("花枝", "海鮮", "斤", 280),
    ("高麗菜", "蔬菜", "顆", 35), ("青江菜", "蔬菜", "把", 18),
    ("金針菇", "蔬菜", "包", 15), ("玉米筍", "蔬菜", "盒", 45),
    ("青蔥", "蔬菜", "斤", 90),
    ("凍豆腐", "豆製品・加工品", "包", 40), ("油豆腐", "豆製品・加工品", "包", 35),
    ("魚板", "豆製品・加工品", "包", 55), ("貢丸", "豆製品・加工品", "包", 70),
    ("乾香菇", "乾貨・南北貨", "兩", 120), ("黑木耳", "乾貨・南北貨", "包", 60),
    ("沙拉油", "調味料", "桶", 780), ("醬油", "調味料", "瓶", 95),
    ("白胡椒粉", "調味料", "罐", 130),
    ("台灣啤酒", "飲品・酒水", "瓶", 38), ("可樂", "飲品・酒水", "瓶", 22),
    ("外帶紙盒", "包材・耗材", "個", 4.5), ("免洗筷", "包材・耗材", "包", 65),
    ("提袋", "包材・耗材", "個", 2.5),
    ("食用冰塊", "其他", "包", 30),
]

REASONS = ["報廢"] * 8 + ["過期"] * 5 + ["備料失誤"] * 4 + ["客訴重做"] * 2 + ["試菜"] + ["盤點差異"] * 2
QTY = {"包": [0.5, 1, 1.5, 2, 3], "公斤": [0.3, 0.5, 0.8, 1.2], "斤": [0.5, 1, 1.5],
       "顆": [1, 2, 3, 4], "把": [1, 2, 3], "盒": [1, 2], "片": [1, 2, 3],
       "兩": [0.5, 1], "桶": [1], "瓶": [1, 2], "罐": [1], "個": [10, 20, 30, 50]}

TODAY = date(2026, 8, 1)
START = date(2026, 7, 1)


def main() -> None:
    items = [{"品名": n, "品類": c, "單位": u, "單位成本": p, "停用": False,
              "更新時間": "2026-07-01T09:00:00.000Z"} for n, c, u, p in ITEMS]

    loss, seq = [], 0
    d = START
    while d <= TODAY:
        # 週末耗損多一點，中間偶爾有一天沒登記
        n = random.choice([0, 1, 2, 2, 3, 3, 4] if d.weekday() >= 4 else [0, 1, 2, 2, 3])
        for _ in range(n):
            name, cat, unit, price = random.choice(ITEMS)
            qty = random.choice(QTY[unit])
            seq += 1
            reason = random.choice(REASONS)
            loss.append({
                "id": f"L-{d:%Y%m%d}{9 + seq % 12:02d}{seq % 60:02d}{seq % 60:02d}-demo{seq:04d}",
                "日期": d.isoformat(), "店別": "墨竹亭光復", "品類": cat, "品名": name,
                "耗損量": qty, "單位": unit, "單位成本": price,
                "金額": round(qty * price, 2), "原因": reason,
                "原因說明": "湯底試味道" if reason == "試菜" else "",
                "備註": "", "建立時間": f"{d.isoformat()}T{9 + seq % 12:02d}:00:00.000Z",
                "作廢": random.random() < 0.04,
            })
        d += timedelta(days=1)

    html = SRC.read_text(encoding="utf-8").replace("mztloss.", KEY)
    assert "mztloss.items" not in html, "儲存空間沒有改乾淨，會污染正式版"
    demo = """
<script>
(function () {
  var ITEMS = __ITEMS__;
  var LOSS = __LOSS__;
  if (!localStorage.getItem('__K__demo')) {
    localStorage.setItem('__K__items', JSON.stringify(ITEMS));
    localStorage.setItem('__K__loss', JSON.stringify(LOSS));
    localStorage.setItem('__K__queue', '[]');
    localStorage.setItem('__K__demo', '1');
  }
  // 示範版：後端改成本機模擬，完全不連雲端
  API_URL = '(demo)';
  api.post = function (p) {
    return new Promise(function (res) {
      setTimeout(function () {
        var items = JSON.parse(localStorage.getItem('__K__items') || '[]');
        var loss = JSON.parse(localStorage.getItem('__K__loss') || '[]');
        if (p.action === 'bootstrap') return res({ items: items, meta: {}, serverTime: new Date().toISOString() });
        if (p.action === 'listLoss') return res({ records: loss.filter(function (r) { return r.日期 >= p.from && r.日期 <= p.to; }) });
        if (p.action === 'addLoss') return res({ accepted: p.records.map(function (r) { return r.id; }), duplicated: [] });
        if (p.action === 'voidLoss') return res({ ok: true });
        if (p.action === 'saveItem') return res({ items: items });
        res({});
      }, 100);
    });
  };
  document.addEventListener('DOMContentLoaded', function () {
    var s = document.querySelector('.store');
    if (s) s.textContent = '墨竹亭 · 光復店　（示範資料，未連雲端）';
  });
})();
</script>
"""
    demo = demo.replace("__K__", KEY)
    demo = demo.replace("__ITEMS__", json.dumps(items, ensure_ascii=False))
    demo = demo.replace("__LOSS__", json.dumps(loss, ensure_ascii=False))
    OUT.write_text(html + demo, encoding="utf-8")

    total = sum(r["金額"] for r in loss if not r["作廢"])
    print(f"{OUT}\n品項 {len(items)} 筆｜耗損紀錄 {len(loss)} 筆"
          f"（作廢 {sum(1 for r in loss if r['作廢'])} 筆）｜7/1–8/1 合計 ${total:,.0f}")


if __name__ == "__main__":
    main()
