#!/usr/bin/env python3
"""calc 純函式單元測試。用 node 直接載入 src/app.js（不碰 DOM 的部分）。

用法：python3 tests/test_units.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "src" / "app.js"

JS = r"""
const {calc} = require(APP_PATH);
const out = [];
const eq = (name, got, want) => out.push({name, got, want, ok: JSON.stringify(got) === JSON.stringify(want)});

// 金額 = 耗損量 x 單位成本
eq('1.5 包 x 120', calc.makeRecord({耗損量:1.5, 日期:'2026-08-01', 原因:'報廢'}, {品名:'雞胸肉', 品類:'肉類', 單位:'包', 單位成本:120}).金額, 180);
eq('0.3 x 33.33 四捨五入', calc.makeRecord({耗損量:0.3, 日期:'2026-08-01', 原因:'報廢'}, {品名:'x', 品類:'其他', 單位:'包', 單位成本:33.33}).金額, 10);
eq('0.1 + 0.2 型浮點不外漏', calc.makeRecord({耗損量:3, 日期:'2026-08-01', 原因:'報廢'}, {品名:'x', 品類:'其他', 單位:'包', 單位成本:1.1}).金額, 3.3);
eq('作廢預設 false', calc.makeRecord({耗損量:1, 日期:'2026-08-01', 原因:'報廢'}, {品名:'x', 品類:'其他', 單位:'包', 單位成本:10}).作廢, false);
eq('店別預設光復', calc.makeRecord({耗損量:1, 日期:'2026-08-01', 原因:'報廢'}, {品名:'x', 品類:'其他', 單位:'包', 單位成本:10}).店別, '墨竹亭光復');
eq('店別可指定', calc.makeRecord({耗損量:1, 日期:'2026-08-01', 原因:'報廢', 店別:'墨竹亭金山'}, {品名:'x', 品類:'其他', 單位:'包', 單位成本:10}).店別, '墨竹亭金山');

// id 格式與唯一性
const re = /^L-\d{14}-[a-z0-9]{8}$/;
eq('id 格式', re.test(calc.newId(new Date(2026,7,1,14,30,5))), true);
eq('id 時間戳', calc.newId(new Date(2026,7,1,14,30,5)).slice(0,16), 'L-20260801143005');
const ids = new Set(); for (let i=0;i<1000;i++) ids.add(calc.newId());
eq('1000 個 id 不重複', ids.size, 1000);

// 統計：排除作廢、直接加總快照金額
const R = [
  {日期:'2026-08-01', 品類:'肉類', 品名:'雞胸肉', 原因:'報廢', 金額:180, 作廢:false},
  {日期:'2026-08-01', 品類:'蔬菜', 品名:'高麗菜', 原因:'過期', 金額:70,  作廢:false},
  {日期:'2026-08-02', 品類:'肉類', 品名:'雞胸肉', 原因:'報廢', 金額:120, 作廢:false},
  {日期:'2026-08-02', 品類:'海鮮', 品名:'白蝦',   原因:'報廢', 金額:500, 作廢:true},
  {日期:'2026-07-31', 品類:'肉類', 品名:'雞胸肉', 原因:'試菜', 金額:999, 作廢:false},
];
const s = calc.summarize(R, '2026-08-01', '2026-08-02');
eq('總金額排除作廢與區間外', s.總金額, 370);
eq('筆數', s.筆數, 3);
eq('按品類排行', s.按品類.map(x=>[x.名稱,x.金額,x.筆數]), [['肉類',300,2],['蔬菜',70,1]]);
eq('佔比', s.按品類[0].佔比, 81.1);
eq('按原因排行', s.按原因.map(x=>x.名稱), ['報廢','過期']);
eq('每日走勢補零', calc.summarize(R,'2026-07-30','2026-08-02').每日.map(d=>d.金額), [0,999,250,120]);

// 店別篩選
const S = [
  {日期:'2026-08-01', 店別:'墨竹亭光復',   品類:'肉類', 品名:'a', 原因:'報廢', 金額:100, 作廢:false},
  {日期:'2026-08-01', 店別:'墨竹亭金山',   品類:'蔬菜', 品名:'b', 原因:'過期', 金額:200, 作廢:false},
  {日期:'2026-08-01', 店別:'墨竹亭六張犁', 品類:'海鮮', 品名:'c', 原因:'報廢', 金額:400, 作廢:false},
  {日期:'2026-08-01', 店別:'墨竹亭金山',   品類:'蔬菜', 品名:'d', 原因:'報廢', 金額:800, 作廢:true},
];
eq('只看金山', calc.summarize(S,'2026-08-01','2026-08-01','墨竹亭金山').總金額, 200);
eq('只看金山筆數(排除作廢)', calc.summarize(S,'2026-08-01','2026-08-01','墨竹亭金山').筆數, 1);
eq('店別留空＝全部三店', calc.summarize(S,'2026-08-01','2026-08-01','').總金額, 700);
eq('不存在的店＝0', calc.summarize(S,'2026-08-01','2026-08-01','墨竹亭不存在').總金額, 0);
eq('門市清單', require(APP_PATH).STORES, ['墨竹亭光復','墨竹亭金山','墨竹亭六張犁','墨竹亭美村']);
eq('每家店都有顯示名稱', require(APP_PATH).STORES.every(s => !!require(APP_PATH).STORE_LABEL[s]), true);
eq('店別值都帶品牌前綴', require(APP_PATH).STORES.every(s => s.startsWith('墨竹亭')), true);

// 期間
eq('本月起日', calc.dateRange('month','2026-08-15').from, '2026-08-01');
eq('本週起日(週一)', calc.dateRange('week','2026-08-01').from, '2026-07-27');
eq('本日', calc.dateRange('today','2026-08-01'), {from:'2026-08-01', to:'2026-08-01'});

// 上期（同樣長度，緊鄰在前）
eq('上期(單日)', calc.prevRange('2026-08-01','2026-08-01'), {from:'2026-07-31', to:'2026-07-31'});
eq('上期(七天)', calc.prevRange('2026-08-01','2026-08-07'), {from:'2026-07-25', to:'2026-07-31'});
eq('天數', calc.days('2026-08-01','2026-08-07'), 7);

// CSV
const csv = calc.csv([{id:'L-1', 日期:'2026-08-01', 店別:'墨竹亭光復', 品類:'肉類', 品名:'雞胸肉',
  耗損量:1.5, 單位:'包', 單位成本:120, 金額:180, 原因:'其他', 原因說明:'掉在地上,撿不起來', 備註:'', 建立時間:'x'}]);
eq('CSV 有 BOM', csv.charCodeAt(0), 0xFEFF);
eq('CSV 表頭', csv.split('\r\n')[0].replace('﻿',''), 'id,日期,店別,品類,品名,耗損量,單位,單位成本,金額,原因,原因說明,備註,建立時間');
eq('CSV 逗號要包引號', csv.split('\r\n')[1].indexOf('"掉在地上,撿不起來"') > 0, true);
eq('CSV 引號前有 10 個欄位', csv.split('\r\n')[1].split('"')[0].split(',').length - 1, 10);
eq('CSV 只有兩行', csv.split('\r\n').length, 2);

// 顯示
eq('金額格式', calc.money(1234.5), '$1,234.5');
console.log(JSON.stringify(out));
"""


def main() -> int:
    src = APP.read_text(encoding="utf-8")
    if "module.exports" not in src:
        print("FAIL  src/app.js 沒有 module.exports，Node 載入不了")
        return 1
    if re.search(r"^(document|window)\.", src, re.M):
        print("FAIL  src/app.js 頂層直接碰 document/window，Node 會炸")
        return 1

    script = JS.replace("APP_PATH", json.dumps(str(APP)))
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    if proc.returncode != 0:
        print("FAIL  node 執行錯誤：\n" + proc.stderr.strip())
        return 1

    results = json.loads(proc.stdout.strip().splitlines()[-1])
    bad = 0
    for r in results:
        if r["ok"]:
            print(f"  ok   {r['name']}")
        else:
            bad += 1
            print(f"  FAIL {r['name']}: got={r['got']!r} want={r['want']!r}")
    print(f"\n{len(results) - bad}/{len(results)} 通過")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
