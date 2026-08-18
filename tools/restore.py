#!/usr/bin/env python3
"""還原 WP Fastest Cache 壓縮前的原始資產結構。

線上頁面把原始的 <link>/<script> 註解掉,改載入雜湊命名的合併檔。
本腳本下載註解中列出的原始 CSS/JS,把註解還原為實際標籤,並移除
wpfc-minified 引用 —— 結果等同 minify 前的頁面,結構乾淨可維護。
"""
import os, re, sys, json, glob
from urllib.parse import urlsplit, unquote
import requests
from bs4 import BeautifulSoup, Comment

OUT, MANIFEST = sys.argv[1], sys.argv[2]
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
session = requests.Session()
session.headers.update(HEADERS)

man = json.load(open(MANIFEST, encoding="utf-8"))
assets = man["assets"]

TAG_RE = re.compile(r"<(link|script)\b", re.I)
CSS_URL_RE = re.compile(r"""url\(\s*['"]?([^'")]+?)['"]?\s*\)""", re.I)


def local_of(url):
    return unquote(urlsplit(url).path).lstrip("/")


def download(url, seen):
    """下載資產;回傳本地相對路徑。CSS 會遞迴處理其 url() 參照。"""
    if url in seen:
        return assets.get(url)
    seen.add(url)
    rel = local_of(url)
    dest = os.path.join(OUT, rel)
    try:
        r = session.get(url, timeout=30)
    except Exception as e:
        print(f"  ✗ {url} ({e})")
        return None
    if r.status_code != 200:
        print(f"  ✗ {url} ({r.status_code})")
        return None
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if rel.endswith(".css"):
        text = r.content.decode("utf-8", "replace")
        open(dest, "w", encoding="utf-8").write(text)
        from urllib.parse import urljoin
        for raw in CSS_URL_RE.findall(text):
            raw = raw.strip()
            if raw.startswith(("data:", "#")):
                continue
            sub = urljoin(url, raw)
            if urlsplit(sub).netloc.replace("www.", "") == "topfamous.com.tw":
                sub_rel = download(sub, seen)
                if sub_rel:
                    assets[sub] = sub_rel
    else:
        open(dest, "wb").write(r.content)
    assets[url] = rel
    return rel


def collect_and_download():
    urls = set()
    for f in glob.glob(os.path.join(OUT, "**", "*.html"), recursive=True):
        soup = BeautifulSoup(open(f, encoding="utf-8").read(), "lxml")
        for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
            t = str(c)
            if TAG_RE.search(t):
                urls.update(re.findall(r"""(?:href|src)=['"]([^'"]+)['"]""", t))
    urls = {u for u in urls if urlsplit(u).netloc.replace("www.", "") == "topfamous.com.tw"}
    print(f"註解中共 {len(urls)} 個原始資產,開始下載…")
    seen = set()
    ok = 0
    for u in sorted(urls):
        if download(u, seen):
            ok += 1
    print(f"下載完成:{ok}/{len(urls)}")


def restore_pages():
    n_tags = n_removed = 0
    for f in glob.glob(os.path.join(OUT, "**", "*.html"), recursive=True):
        html = open(f, encoding="utf-8").read()
        soup = BeautifulSoup(html, "lxml")

        for c in list(soup.find_all(string=lambda t: isinstance(t, Comment))):
            t = str(c)
            if not TAG_RE.search(t):
                continue
            frag = BeautifulSoup(t, "lxml")
            new_tags = frag.find_all(["link", "script"])
            if not new_tags:
                continue
            for tag in new_tags:
                c.insert_before(tag.extract())
                n_tags += 1
            c.extract()

        for tag in soup.find_all(["link", "script"]):
            val = tag.get("href") or tag.get("src") or ""
            if "wpfc-minified" in val:
                tag.decompose()
                n_removed += 1

        open(f, "w", encoding="utf-8").write(str(soup))
    print(f"還原:插入 {n_tags} 個原始標籤,移除 {n_removed} 個 minified 引用")


collect_and_download()
restore_pages()
man["assets"] = assets
json.dump(man, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"manifest 資產總數:{len(assets)}")
