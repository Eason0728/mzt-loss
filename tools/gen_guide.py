#!/usr/bin/env python3
"""產生「操作步驟」長圖（給同仁看的教學圖，可直接丟 LINE 群）。

    python3 build_demo.py && python3 tools/gen_guide.py

畫面一律**從示範版 demo.html 實際截圖**，不是畫示意圖——
改了 app 之後重跑一次，教學圖就自動跟著更新，不會出現「圖跟實際畫面對不上」。

要改文案改 STEPS 的標題與說明；要改版面改 COLS／PAD／GAP。
需要 playwright 與 Pillow。輸出：assets/操作步驟.png
"""

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DEMO = (ROOT / 'demo.html').as_uri()
OUT = ROOT / 'assets' / '操作步驟.png'
TMP = Path(tempfile.mkdtemp(prefix='mztguide-'))

W = 400          # 截圖用的手機寬度
FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'

# 檔名, 標題, 說明兩行
STEPS = [
    ('g1.png', '第一次開啟：選你的店',
     ['選一次就好，之後不會再問。', '選錯了可以在「成本設定」頁改。']),
    ('g2.png', '打品名，打前幾個字就好',
     ['打「雞」就會跳出所有含雞的品項，', '直接點選，不用打完整。']),
    ('g3.png', '品類、單位、單價自動帶出',
     ['你只要打「耗損量」這一個數字。', '1.5 就是一包半。金額自己算好。']),
    ('g4.png', '選原因，按送出',
     ['選「其他」才要打字說明。', '送完表單自動清空，可以馬上打下一筆。']),
    ('g5.png', '打錯了？按「作廢」',
     ['按一下會變紅色「確定作廢？」，', '再按一次才生效，不會手滑。']),
    ('g6.png', '成本設定：建品項與單價',
     ['登記頁的單價從這裡來。', '三家店共用一份，改一次三店都變。']),
    ('g7.png', '統計：看錢漏在哪裡',
     ['可切本日／本週／本月，或自訂區間；', '可切單店或全部三店。能匯出、能列印。']),
]


def font(size, index=2):
    return ImageFont.truetype(FONT, size, index=index)


def capture():
    """開示範版，一步一步操作並截圖。"""
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': W, 'height': 820}, device_scale_factor=2)

        def shot(name, y, h):
            pg.screenshot(path=str(TMP / name), clip={'x': 0, 'y': y, 'width': W, 'height': h})

        # 1 選店畫面（先清掉示範版記住的店，才會跳出來）
        pg.goto(DEMO); pg.wait_for_timeout(1200)
        pg.evaluate("localStorage.removeItem('mztlossdemo.store')")
        pg.reload(); pg.wait_for_timeout(1200)
        shot('g1.png', 0, 470)
        pg.locator('#pick-list button', has_text='光復店').click(); pg.wait_for_timeout(600)

        # 2 打品名出現提示
        pg.fill('#f-name', '雞'); pg.dispatch_event('#f-name', 'input'); pg.wait_for_timeout(500)
        shot('g2.png', 150, 420)

        # 3 選中→自動帶入→打耗損量
        pg.locator('#ac-list li', has_text='雞腿肉').first.click(); pg.wait_for_timeout(300)
        pg.fill('#f-qty', '1.5'); pg.dispatch_event('#f-qty', 'input'); pg.wait_for_timeout(400)
        shot('g3.png', 190, 430)

        # 4 選原因→送出
        pg.select_option('#f-reason', '報廢'); pg.wait_for_timeout(300)
        shot('g4.png', 420, 400)
        pg.click('#log-form button[type=submit]'); pg.wait_for_timeout(900)

        # 5 今日清單＋作廢的確認狀態（兩段式點按）
        pg.evaluate('window.scrollTo(0, document.body.scrollHeight)'); pg.wait_for_timeout(300)
        pg.locator('#today-list .void').first.click(); pg.wait_for_timeout(400)
        box = pg.locator('.today').bounding_box()
        shot('g5.png', max(0, box['y'] - 10), 330)

        # 6 成本設定
        pg.evaluate('window.scrollTo(0,0)'); pg.click('.tab[data-tab=cost]'); pg.wait_for_timeout(500)
        shot('g6.png', 0, 560)

        # 7 統計（用示範資料的區間才有走勢可看）
        pg.click('.tab[data-tab=stat]'); pg.wait_for_timeout(500)
        pg.click('#s-seg button[data-k=custom]'); pg.wait_for_timeout(300)
        pg.fill('#s-from', '2026-07-01'); pg.dispatch_event('#s-from', 'change')
        pg.fill('#s-to', '2026-08-01'); pg.dispatch_event('#s-to', 'change'); pg.wait_for_timeout(800)
        shot('g7.png', 0, 700)

        b.close()
    print(f'截圖 {len(STEPS)} 張 → {TMP}')


GREEN = (0x2f, 0x5d, 0x50)
DARK = (0x23, 0x45, 0x39)
INK = (0x1c, 0x1c, 0x1a)
MUTED = (0x6b, 0x6b, 0x66)
BG = (0xf6, 0xf6, 0xf3)
LINE = (0xe2, 0xe2, 0xdd)
PALE = (0xc9, 0xdd, 0xd6)

PAD, GAP, IMGW, COLS = 26, 22, 400, 4
TITLE_H, CELL_TXT = 74, 92


def compose():
    imgs = [Image.open(TMP / f) for f, _, _ in STEPS]
    rows = [imgs[i:i + COLS] for i in range(0, len(imgs), COLS)]
    row_h = [max(im.height // 2 for im in r) + CELL_TXT for r in rows]

    width = PAD * 2 + IMGW * COLS + GAP * (COLS - 1)
    height = TITLE_H + 46 + sum(row_h) + GAP * (len(rows) - 1) + PAD + 54

    canvas = Image.new('RGB', (width, height), BG)
    d = ImageDraw.Draw(canvas)

    d.rectangle([0, 0, width, TITLE_H], fill=GREEN)
    d.text((PAD, 14), '耗損登記表　操作步驟', font=font(34), fill=(255, 255, 255))
    d.text((PAD + 400, 27), '墨竹亭 · 光復／金山／六張犁', font=font(20), fill=PALE)
    d.text((width - PAD - 560, 27), 'eason0728.github.io/mzt-loss', font=font(20, 1), fill=PALE)

    y = TITLE_H + 20
    d.text((PAD, y), '現場一筆只要三個動作：① 打品名　② 打耗損量　③ 選原因', font=font(24), fill=DARK)
    y += 46

    for r, chunk in enumerate(rows):
        for c, im in enumerate(chunk):
            i = r * COLS + c
            _, title, lines = STEPS[i]
            x = PAD + c * (IMGW + GAP)

            d.ellipse([x, y, x + 34, y + 34], fill=GREEN)
            num = str(i + 1)
            bb = font(22).getbbox(num)
            d.text((x + 17 - (bb[2] - bb[0]) / 2 - bb[0], y + 7 - bb[1]), num, font=font(22), fill=(255, 255, 255))
            d.text((x + 46, y + 3), title, font=font(24), fill=INK)

            ty = y + 38
            for ln in lines:
                d.text((x, ty), ln, font=font(19), fill=MUTED)
                ty += 25

            half = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
            iy = y + CELL_TXT
            d.rectangle([x - 1, iy - 1, x + half.width, iy + half.height], outline=LINE)
            canvas.paste(half, (x, iy))
        y += row_h[r] + GAP

    d.text((PAD, height - 44),
           '把網址加到手機主畫面，之後點圖示就能開，跟一般 App 一樣。　沒網路也能登記，有訊號會自動補上傳。',
           font=font(21), fill=MUTED)

    OUT.parent.mkdir(exist_ok=True)
    canvas.save(OUT)
    print(f'{OUT}  {canvas.size[0]}x{canvas.size[1]}')


if __name__ == '__main__':
    capture()
    compose()
