#!/usr/bin/env python3
"""從墨竹亭品牌 logo 抽出「囊形竹葉」標記，做成白色去背版並內嵌進標題列。

    python3 tools/gen_logo.py && python3 build.py

來源是品牌正本 `~/Desktop/麻的小辛辣/墨竹亭/墨竹亭LOGO.png`
（薄荷綠底 #86CBBF、藏藍線條 #13175B，下半是字標）。
只取上半的標記本體：標題列是橫的又會跟著分頁換色，整組直式 logo 塞不進去也會撞色；
白色版在墨綠／藏藍／赭褐三個底上都讀得清楚。

產出 assets/logo-mzt.png（白色去背，2 倍解析度）並以 base64 內嵌進 src/index.html。
標記防重複插入：<!-- 墨竹亭 logo -->
"""

import base64
import os

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.expanduser('~/Desktop/麻的小辛辣/墨竹亭/墨竹亭LOGO.png')
OUT = os.path.join(ROOT, 'assets', 'logo-mzt.png')

MINT = np.array([134, 203, 191])    # 底色
NAVY = np.array([19, 23, 91])       # 線條色
CROP = (320, 40, 620, 500)          # 只取上半的標記本體，不要字標
TARGET_H = 128                      # 顯示 64px，出 2 倍給高解析螢幕

MARK = '<!-- 墨竹亭 logo -->'
ANCHOR = '<header class="top">'


def build():
    im = Image.open(SRC).convert('RGB').crop(CROP)
    arr = np.array(im).astype(float)
    # 線條色與底色的曼哈頓距離當分母，反鋸齒像素會線性落在 0–1
    alpha = np.clip(np.abs(arr - MINT).sum(axis=2) / np.abs(NAVY - MINT).sum(), 0, 1)

    ys, xs = np.where(alpha > 0.15)          # 去掉四周空白，讓標記貼齊邊界
    top, bottom, left, right = ys.min(), ys.max(), xs.min(), xs.max()
    alpha = alpha[top:bottom + 1, left:right + 1]

    h, w = alpha.shape
    white = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    white.putalpha(Image.fromarray((alpha * 255).astype(np.uint8)))
    white.paste(Image.new('RGB', (w, h), (255, 255, 255)), (0, 0),
                Image.fromarray((alpha * 255).astype(np.uint8)))

    scale = TARGET_H / h
    out = white.resize((max(1, round(w * scale)), TARGET_H), Image.LANCZOS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT)
    return out


def inject(img):
    uri = 'data:image/png;base64,' + base64.b64encode(open(OUT, 'rb').read()).decode()
    path = os.path.join(ROOT, 'src', 'index.html')
    html = open(path, encoding='utf-8').read()
    if MARK in html:                          # 已經嵌過：整段換掉，不要疊第二份
        head, rest = html.split(MARK, 1)
        html = head + rest.split(MARK, 1)[1]
    block = (f'{MARK}<img class="brand" alt="墨竹亭" src="{uri}">{MARK}')
    html = html.replace(ANCHOR, ANCHOR + '\n  ' + block, 1)
    open(path, 'w', encoding='utf-8').write(html)
    print(f'{OUT}  {img.size[0]}x{img.size[1]}  → 已內嵌進 src/index.html')


if __name__ == '__main__':
    inject(build())
