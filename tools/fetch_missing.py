#!/usr/bin/env python3
"""補抓仍以絕對網址殘留在頁面中的站內資產。

來源有二:inline JS 條件載入的 script(如 wp-polyfill),以及 Enfold 燈箱
資料中以 \\uXXXX 轉義寫入的中文圖檔名 —— 兩者都不在 HTML 屬性上,
第一輪的 DOM 掃描抓不到。
"""
import os, re, sys, json, glob, codecs
from urllib.parse import urlsplit, unquote
import requests

OUT, MANIFEST = sys.argv[1], sys.argv[2]
man = json.load(open(MANIFEST, encoding="utf-8"))
assets = man["assets"]
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"})

ASSET_EXT = re.compile(r"\.(css|js|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot|otf|mp4|webm|pdf)$", re.I)
URL_RE = re.compile(r"""https?://(?:www\.)?topfamous\.com\.tw/[^\s'"<>\\)]*(?:\\u[0-9a-fA-F]{4}[^\s'"<>\\)]*)*""")


def decode_js(u):
    """還原 JS 字串中的 \\uXXXX 轉義。"""
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), u)


found = set()
for f in glob.glob(os.path.join(OUT, "**", "*.html"), recursive=True):
    for raw in URL_RE.findall(open(f, encoding="utf-8").read()):
        u = decode_js(raw)
        if ASSET_EXT.search(urlsplit(u).path):
            found.add(u.split("?")[0] + ("?" + urlsplit(u).query if urlsplit(u).query else ""))

todo = [u for u in sorted(found) if u not in assets]
print(f"殘留資產 {len(found)} 個,其中 {len(todo)} 個尚未下載")
ok = 0
for u in todo:
    rel = unquote(urlsplit(u).path).lstrip("/")
    dest = os.path.join(OUT, rel)
    if os.path.exists(dest):
        assets[u] = rel
        ok += 1
        continue
    try:
        r = s.get(u, timeout=30)
    except Exception as e:
        print(f"  ✗ {u} ({e})")
        continue
    if r.status_code != 200:
        print(f"  ✗ {u} ({r.status_code})")
        continue
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "wb").write(r.content)
    assets[u] = rel
    ok += 1

print(f"補抓完成:{ok}/{len(todo)}")
man["assets"] = assets
json.dump(man, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
