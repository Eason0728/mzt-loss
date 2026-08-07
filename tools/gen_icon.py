#!/usr/bin/env python3
"""
產生耗損登記表的主畫面圖示（apple-touch-icon 180 + favicon-32）。

    python3 tools/gen_icon.py && python3 build.py

版型照鼎兆元／墨竹亭那族（宿舍 → 調撥 → 稽核 → 本支），
上方墨竹亭竹葉 emblem、下方兩個字，只換底色與文字。
emblem 直接從宿舍那顆抽 alpha 出來，幾何位置逐 px 相同，不是重畫一顆近似的。

配色 2026-08-01 由 Eason 定案：墨竹亭薄荷綠 #86CBBF 底、竹葉維持白、文字赭黃 #B8791F。
（先提過赭黃底＋白字，他改成這個組合並在看過 D／E／反轉三版後選 D。）
已知取捨：底色與宿舍那顆相同，兩顆只靠文字色區分；且赭黃壓薄荷綠對比約 2:1，
32px 分頁圖示的字會偏糊——這是明知後仍選定的方向，不要「順手修正」回高對比。

產完把兩顆以 base64 data URI 內嵌進 src/index.html 的 <head>
（有 `<!-- 耗損 icon -->` 標記防重複插入），再跑 build.py 就會帶進正式版與示範版。
"""

import base64
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DORM_ICON = os.path.expanduser('~/mala-dorm-contract/assets/icon-180.png')
OUT_DIR = os.path.join(ROOT, 'assets')

BG = (0x86, 0xCB, 0xBF)          # 墨竹亭薄荷綠（＝宿舍那顆的底色）
EMBLEM_FG = (0xFF, 0xFF, 0xFF)   # 竹葉維持白
TEXT_FG = (0xB8, 0x79, 0x1F)     # 文字赭黃
TEXT = '耗損'

# 宿舍那顆量出來的幾何（180 畫布）
DORM_MINT = np.array([134, 203, 191])   # 底色
DORM_NAVY = np.array([19, 23, 91])      # emblem 線色
EMBLEM_SPLIT_Y = 105                    # 105 以上是 emblem，以下是文字
TEXT_TOP = 113                          # 文字 bbox 上緣
TEXT_HEIGHT = 53                        # 文字 bbox 高（≈ 畫布 29%）
FONT_PATH = '/System/Library/Fonts/Hiragino Sans GB.ttc'
FONT_INDEX = 2                          # W6，跟同族其他顆一致


def emblem_alpha():
    """從宿舍那顆抽出 emblem 的 alpha 遮罩（含反鋸齒）。"""
    src = np.array(Image.open(DORM_ICON).convert('RGB')).astype(float)
    den = np.abs(DORM_NAVY - DORM_MINT).sum()
    alpha = np.clip(np.abs(src - DORM_MINT).sum(axis=2) / den, 0, 1)
    alpha[EMBLEM_SPLIT_Y:, :] = 0        # 切掉「宿舍」兩個字，只留 emblem
    return Image.fromarray((alpha * 255).astype(np.uint8))


def fit_font():
    for size in range(30, 90):
        font = ImageFont.truetype(FONT_PATH, size, index=FONT_INDEX)
        box = font.getbbox(TEXT, stroke_width=1)
        if box[3] - box[1] >= TEXT_HEIGHT:
            return font, box
    raise SystemExit('找不到合適字級')


def build_180():
    icon = Image.new('RGB', (180, 180), BG)
    icon.paste(Image.new('RGB', (180, 180), EMBLEM_FG), (0, 0), emblem_alpha())

    font, box = fit_font()
    draw = ImageDraw.Draw(icon)
    x = (180 - (box[2] - box[0])) / 2 - box[0]
    y = TEXT_TOP - box[1]
    draw.text((x, y), TEXT, font=font, fill=TEXT_FG, stroke_width=1, stroke_fill=TEXT_FG)
    return icon


MARK = '<!-- 耗損 icon -->'
ANCHOR = '<meta name="viewport"'


def data_uri(path):
    return 'data:image/png;base64,' + base64.b64encode(open(path, 'rb').read()).decode()


def inject(html_path, uri180, uri32):
    html = open(html_path, encoding='utf-8').read()
    if MARK in html:                     # 已經嵌過：換掉整段，不要疊第二份
        head, rest = html.split(MARK, 1)
        html = head + rest.split(MARK, 1)[1]
    block = (f'{MARK}\n'
             f'<link rel="icon" type="image/png" sizes="32x32" href="{uri32}">\n'
             f'<link rel="apple-touch-icon" href="{uri180}">\n'
             f'<meta name="apple-mobile-web-app-title" content="耗損">\n'
             f'{MARK}\n')
    line_end = html.index('\n', html.index(ANCHOR)) + 1
    html = html[:line_end] + block + html[line_end:]
    open(html_path, 'w', encoding='utf-8').write(html)
    print('  內嵌 → ' + os.path.relpath(html_path, ROOT))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    icon = build_180()
    p180 = os.path.join(OUT_DIR, 'icon-180.png')
    p32 = os.path.join(OUT_DIR, 'favicon-32.png')
    icon.save(p180)
    icon.resize((32, 32), Image.LANCZOS).save(p32)

    for path in (p180, p32):
        print(f'{os.path.relpath(path, ROOT)}  {os.path.getsize(path)} bytes')

    inject(os.path.join(ROOT, 'src', 'index.html'), data_uri(p180), data_uri(p32))


if __name__ == '__main__':
    main()
