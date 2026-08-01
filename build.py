#!/usr/bin/env python3
"""把 src/ 的三個檔內嵌成根目錄的單一 index.html（GitHub Pages 出這一支）。

src/ 是正本。根目錄 index.html 是產出物，永遠不要手改。
用法：python3 build.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"


def main() -> None:
    html = (SRC / "index.html").read_text(encoding="utf-8")
    css = (SRC / "styles.css").read_text(encoding="utf-8")
    js = (SRC / "app.js").read_text(encoding="utf-8")

    for marker, payload, name in (
        ("/*STYLES*/", css, "styles.css"),
        ("/*SCRIPT*/", js, "app.js"),
    ):
        if marker not in html:
            raise SystemExit(f"src/index.html 少了 {marker} 標記，無法內嵌 {name}")
        html = html.replace(marker, payload, 1)

    if "</script" in js or "</style" in css:
        raise SystemExit("CSS/JS 內含結束標籤字串，內嵌後會壞掉")

    out = ROOT / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"OK  {out}  ({len(html):,} 字元)")


if __name__ == "__main__":
    main()
