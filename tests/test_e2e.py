#!/usr/bin/env python3
"""端對端測試：用真瀏覽器把整支 app 的流程跑過一遍。

    python3 build.py && python3 tests/test_e2e.py

**後端是假的**——用 Playwright 攔截送往 Apps Script 的請求，改由本檔的 FakeBackend 回應。
這樣做有三個好處：
  1. 測試不會把垃圾資料寫進正式試算表。
  2. 可以模擬離線、伺服器錯誤、重複送出這些真後端很難重現的狀況。
  3. 不需要網路，跑得快。

真後端另有 `tests/test_backend.py` 直接打線上端點驗證。

需要 playwright（`pip install playwright && playwright install chromium`）。
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / 'index.html').as_uri()
TODAY = date.today().isoformat()

ITEMS = [
    {'品名': '雞胸肉', '品類': '肉類', '單位': '包', '單位成本': 120, '停用': False, '更新時間': ''},
    {'品名': '雞腿肉', '品類': '肉類', '單位': '公斤', '單位成本': 195, '停用': False, '更新時間': ''},
    {'品名': '高麗菜', '品類': '蔬菜', '單位': '顆', '單位成本': 35, '停用': False, '更新時間': ''},
    {'品名': '停售舊品', '品類': '其他', '單位': '包', '單位成本': 10, '停用': True, '更新時間': ''},
]


class FakeBackend:
    """假的 Apps Script：在記憶體裡模擬試算表，並記錄收到的每一個請求。"""

    def __init__(self):
        self.items = [dict(x) for x in ITEMS]
        self.loss = []
        self.calls = []
        self.offline = False        # True 時所有請求直接失敗，模擬沒網路

    def handle(self, req):
        self.calls.append(req.get('action'))
        a = req.get('action')

        if a == 'bootstrap':
            return {'items': self.items, 'meta': {}, 'serverTime': ''}

        if a == 'listLoss':
            f, t = req.get('from'), req.get('to')
            return {'records': [r for r in self.loss if f <= r['日期'] <= t]}

        if a == 'addLoss':
            seen = {r['id'] for r in self.loss}
            accepted, duplicated = [], []
            for rec in req.get('records', []):
                if rec['id'] in seen:            # 真後端的去重行為
                    duplicated.append(rec['id'])
                    continue
                seen.add(rec['id'])
                self.loss.append(dict(rec))
                accepted.append(rec['id'])
            return {'accepted': accepted, 'duplicated': duplicated}

        if a == 'voidLoss':
            for r in self.loss:
                if r['id'] == req['id']:
                    r['作廢'] = True
                    return {'ok': True, 'id': r['id']}
            return {'ok': False}

        if a == 'saveItem':
            it = req['item']
            key = it.get('舊品名') or it['品名']
            for i, cur in enumerate(self.items):
                if cur['品名'] == key:
                    self.items[i] = {k: v for k, v in it.items() if k != '舊品名'}
                    break
            else:
                self.items.append({k: v for k, v in it.items() if k != '舊品名'})
            return {'items': self.items}

        return {}


def install(page, backend):
    def route(r):
        if backend.offline:
            r.abort('failed')
            return
        req = json.loads(r.request.post_data or '{}')
        r.fulfill(status=200, content_type='application/json',
                  body=json.dumps({'ok': True, 'data': backend.handle(req)}, ensure_ascii=False))
    page.route('**/script.google.com/**', route)


results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def money(text):
    return float(re.sub(r'[^0-9.]', '', text) or 0)


def log(page, name, qty, reason='報廢'):
    """走完整的 UI 流程登記一筆。"""
    page.fill('#f-name', name)
    page.dispatch_event('#f-name', 'input')
    page.wait_for_timeout(200)
    page.locator('#ac-list li', has_text=name).first.click()
    page.fill('#f-qty', str(qty))
    page.dispatch_event('#f-qty', 'input')
    page.select_option('#f-reason', reason)
    page.click('#log-form button[type=submit]')
    page.wait_for_timeout(600)


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 420, 'height': 900})
        back = FakeBackend()
        install(page, back)

        # ── 開頁：第一次要先選店 ───────────────────────────
        page.goto(APP)
        page.wait_for_timeout(1500)
        check('第一次開啟跳出選店', page.is_visible('#store-pick'), True)
        check('四家店都在', page.locator('#pick-list button').count(), 4)
        page.locator('#pick-list button', has_text='新竹光復店').click()
        page.wait_for_timeout(1200)
        check('標題顯示所選門市', page.inner_text('.store'), '墨竹亭 · 新竹光復店')

        # ── 品項記憶：打字提示與自動帶入 ──────────────────
        page.fill('#f-name', '雞')
        page.dispatch_event('#f-name', 'input')
        page.wait_for_timeout(300)
        check('打「雞」出現兩個品項', page.locator('#ac-list li').count(), 2)
        page.locator('#ac-list li', has_text='雞腿肉').first.click()
        page.wait_for_timeout(200)
        check('自動帶入品類', page.input_value('#f-cat'), '肉類')
        check('自動帶入單位', page.input_value('#f-unit'), '公斤')
        check('自動帶入單價', page.input_value('#f-cost'), '195')
        check('單位不可編輯', page.get_attribute('#f-unit', 'readonly') is not None, True)
        check('單價不可編輯', page.get_attribute('#f-cost', 'readonly') is not None, True)

        # ── 停用品項不能出現在提示（設計約束第 5 條）──────
        page.fill('#f-name', '停售')
        page.dispatch_event('#f-name', 'input')
        page.wait_for_timeout(300)
        check('停用品項不出現在提示', page.locator('#ac-list li').count(), 0)
        page.fill('#f-name', '')
        page.dispatch_event('#f-name', 'input')

        # ── 登記一筆：金額 = 耗損量 × 單位成本 ─────────────
        log(page, '雞胸肉', 1.5)
        check('送出後表單清空', page.input_value('#f-name'), '')
        check('今日合計 1.5×120', money(page.inner_text('#today-sum')), 180)
        check('今日清單有一筆', page.locator('#today-list li').count(), 1)
        check('已寫進後端', len(back.loss), 1)
        check('後端拿到的金額', back.loss[0]['金額'], 180)
        check('後端拿到的店別', back.loss[0]['店別'], '墨竹亭光復')

        # ── 作廢是兩段式點按，且不刪資料 ───────────────────
        page.locator('#today-list .void').first.click()
        page.wait_for_timeout(200)
        check('第一下只是變成確認', page.inner_text('#today-list .void'), '確定作廢？')
        check('還沒真的作廢', back.loss[0].get('作廢', False), False)
        page.locator('#today-list .void').first.click()
        page.wait_for_timeout(600)
        check('第二下才生效', back.loss[0]['作廢'], True)
        check('作廢後今日合計歸零', money(page.inner_text('#today-sum')), 0)
        check('作廢不刪列', len(back.loss), 1)
        check('作廢不改金額', back.loss[0]['金額'], 180)

        # ── 離線登記 → 恢復連線重送，且不重複 ──────────────
        back.offline = True
        log(page, '高麗菜', 2)
        check('離線時本機仍記下', page.locator('#today-list li').count(), 2)
        check('離線時沒進後端', len(back.loss), 1)
        check('顯示待上傳提示', '還沒上傳' in page.inner_text('#sync'), True)

        back.offline = False
        page.click('#sync-btn')
        page.wait_for_timeout(1500)
        check('重送後真的進後端', len(back.loss), 2)
        check('重送後提示消失或轉為已上傳', '還沒上傳' in page.inner_text('#sync'), False)

        # 模擬舊版踩過的坑：上傳成功但佇列沒清，開頁時又送一次。
        # id 是送出當下產生、永不重產，所以後端應該回 duplicated 而不是多寫一列。
        page.evaluate('''(rec) => {
            const q = JSON.parse(localStorage.getItem('mztloss.queue') || '[]');
            q.push({ kind: 'loss', rec: rec });
            localStorage.setItem('mztloss.queue', JSON.stringify(q));
        }''', back.loss[1])
        page.reload()
        page.wait_for_timeout(2000)
        check('同一筆重送不會變兩筆', len(back.loss), 2)
        check('後端有回報是重複的', 'addLoss' in back.calls, True)
        check('佇列已清空', page.evaluate("localStorage.getItem('mztloss.queue')"), '[]')

        # ── 統計頁 ────────────────────────────────────────
        page.click('.tab[data-tab=stat]')
        page.wait_for_timeout(400)
        page.click('#s-seg button[data-k=today]')
        page.wait_for_timeout(600)
        check('統計預設看本店', page.input_value('#s-store'), '墨竹亭光復')
        check('統計排除作廢（只算高麗菜 2×35）', money(page.inner_text('#s-total')), 70)
        check('筆數也排除作廢', page.inner_text('#s-count'), '1 筆')
        check('分頁換色', page.evaluate("document.body.dataset.page"), 'stat')

        page.select_option('#s-store', '墨竹亭金山')
        page.wait_for_timeout(600)
        check('切到沒資料的店＝0', money(page.inner_text('#s-total')), 0)
        page.select_option('#s-store', '')
        page.wait_for_timeout(600)
        check('全部門市＝70', money(page.inner_text('#s-total')), 70)

        # ── 成本表：改單價不動歷史金額（設計約束第 2 條）──
        page.click('.tab[data-tab=cost]')
        page.wait_for_timeout(400)
        check('成本頁顯示目前門市', page.inner_text('#cur-store'), '新竹光復店')
        page.locator('#cost-list li', has_text='高麗菜').locator('button', has_text='修改').click()
        page.wait_for_timeout(300)
        page.fill('#c-cost', '999')
        page.click('#c-save')
        page.wait_for_timeout(800)
        cabbage = [i for i in back.items if i['品名'] == '高麗菜'][0]
        check('單價已改成 999', cabbage['單位成本'], 999)
        old = [r for r in back.loss if r['品名'] == '高麗菜'][0]
        check('舊紀錄單價不變', old['單位成本'], 35)
        check('舊紀錄金額不變', old['金額'], 70)
        page.click('.tab[data-tab=stat]')
        page.wait_for_timeout(600)
        check('改單價後統計數字不變', money(page.inner_text('#s-total')), 70)

        # ── 換門市：統計要跟著切回本店 ────────────────────
        page.click('.tab[data-tab=cost]')
        page.wait_for_timeout(300)
        page.click('#change-store')
        page.wait_for_timeout(300)
        page.locator('#pick-list button', has_text='台北六張犁店').click()
        page.wait_for_timeout(800)
        check('換店後標題更新', page.inner_text('.store'), '墨竹亭 · 台北六張犁店')
        page.click('.tab[data-tab=stat]')
        page.wait_for_timeout(600)
        check('換店後統計切回本店', page.input_value('#s-store'), '墨竹亭六張犁')

        # ── 重整後記得門市，不再問 ────────────────────────
        page.reload()
        page.wait_for_timeout(1500)
        check('重整後不再跳選店', page.is_visible('#store-pick'), False)
        check('重整後仍是六張犁', page.inner_text('.store'), '墨竹亭 · 台北六張犁店')

        b.close()

    bad = 0
    for name, ok, got, want in results:
        if ok:
            print(f'  ok   {name}')
        else:
            bad += 1
            print(f'  FAIL {name}: got={got!r} want={want!r}')
    print(f'\n{len(results) - bad}/{len(results)} 通過')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
