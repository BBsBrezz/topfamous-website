#!/usr/bin/env python3
"""將抓取下來的站台中所有 URL 重寫為相對路徑,產生可離線開啟的靜態站。

相對路徑以「該檔案所在目錄」為基準計算。因為本地目錄結構與原站 URL 路徑
一一對應,同一組相對路徑在 HTML 屬性、CSS url() 與 inline JS 中都成立。
"""
import os, re, sys, json
from urllib.parse import urljoin, urlsplit, urlunsplit, unquote, quote
from bs4 import BeautifulSoup

OUT = sys.argv[1]
MANIFEST = sys.argv[2]
HOST = "topfamous.com.tw"

man = json.load(open(MANIFEST, encoding="utf-8"))
pages, assets = man["pages"], man["assets"]

# --- 建立查表 ---
by_url = {}            # 完整 URL(含 query)-> 本地路徑
by_path = {}           # (host, 解碼後 path) -> 本地路徑
page_paths = set()


def reg(url, rel, is_page):
    p = urlsplit(url)
    net = p.netloc.lower().replace("www.", "")
    path = unquote(p.path)
    by_url[urlunsplit((p.scheme, net, path, p.query, ""))] = rel
    by_path.setdefault((net, path), rel)
    if is_page:
        page_paths.add(rel)
        # 涵蓋 目錄/ 、目錄 、目錄/index.html 三種寫法,重寫才具冪等性
        stem = path.rstrip("/")
        by_path.setdefault((net, stem), rel)
        by_path.setdefault((net, stem + "/"), rel)
        by_path.setdefault((net, stem + "/index.html"), rel)
        by_path.setdefault((net, "/" + rel), rel)


for u, r in pages.items():
    reg(u, r, True)
for u, r in assets.items():
    reg(u, r, False)

rewritten = {"html": 0, "css": 0}
misses = {}


def lookup(abs_url):
    p = urlsplit(abs_url)
    if p.scheme not in ("http", "https"):
        return None
    net = p.netloc.lower().replace("www.", "")
    path = unquote(p.path)
    hit = by_url.get(urlunsplit((p.scheme, net, path, p.query, "")))
    if hit:
        return hit
    for scheme in ("https", "http"):
        hit = by_url.get(urlunsplit((scheme, net, path, p.query, "")))
        if hit:
            return hit
    return by_path.get((net, path))


def relativize(raw, base_url, base_local):
    """raw: 原始屬性值;base_url: 該檔案的原始 URL;base_local: 該檔案的本地相對路徑。"""
    raw = raw.strip()
    if not raw or raw.startswith(("data:", "mailto:", "tel:", "javascript:", "#", "{")):
        return None
    abs_url = urljoin(base_url, raw)
    target = lookup(abs_url)
    if not target:
        net = urlsplit(abs_url).netloc.lower().replace("www.", "")
        if net == HOST:
            misses[abs_url] = misses.get(abs_url, 0) + 1
        return None
    rel = os.path.relpath(target, os.path.dirname(base_local) or ".")
    rel = quote(rel, safe="/._-~")
    frag = urlsplit(abs_url).fragment
    if target in page_paths and rel.endswith("/index.html"):
        pass  # 指向 index.html 是明確且到處都能開的寫法
    return rel + (("#" + frag) if frag else "")


CSS_URL_RE = re.compile(r"""(url\(\s*)(['"]?)([^'")]+?)(\2\s*\))""", re.I)
CSS_IMPORT_RE = re.compile(r"""(@import\s+(?:url\()?\s*)(['"])([^'"]+)(\2)""", re.I)


def rewrite_css_text(text, base_url, base_local):
    def sub_url(m):
        new = relativize(m.group(3), base_url, base_local)
        return m.group(0) if new is None else f"{m.group(1)}{m.group(2)}{new}{m.group(4)}"

    def sub_imp(m):
        new = relativize(m.group(3), base_url, base_local)
        return m.group(0) if new is None else f"{m.group(1)}{m.group(2)}{new}{m.group(4)}"

    return CSS_IMPORT_RE.sub(sub_imp, CSS_URL_RE.sub(sub_url, text))


URL_ATTRS = ("src", "data-src", "data-lazy-src", "poster", "data-thumb")
SRCSET_ATTRS = ("srcset", "data-srcset", "data-lazy-srcset")
KEEP_ABSOLUTE_REL = {"canonical", "shortlink", "alternate", "pingback",
                     "https://api.w.org/", "wlwmanifest", "edituri", "profile"}


DEAD_ENDPOINT_RE = re.compile(
    r"/(feed|comments/feed)/?$|xmlrpc\.php|/wp-json/|wlwmanifest|/wp-content/themes/[^/]+/framework/?$", re.I)


def strip_dead_endpoints(soup):
    """靜態站沒有 WP 後端,移除 feed/xmlrpc/REST 等指向動態端點的連結。"""
    n = 0
    for tag in soup.find_all("link"):
        href = tag.get("href", "")
        rel = " ".join(tag.get("rel") or []).lower()
        if DEAD_ENDPOINT_RE.search(href) or rel in ("edituri", "wlwmanifest", "pingback"):
            tag.decompose()
            n += 1
    return n


def rewrite_html(base_url, base_local):
    fp = os.path.join(OUT, base_local)
    html = open(fp, encoding="utf-8").read()
    soup = BeautifulSoup(html, "lxml")
    strip_dead_endpoints(soup)

    for tag in soup.find_all(True):
        if tag.name == "iframe":
            continue  # 動態服務的 src 必須維持原始網址
        for attr in URL_ATTRS:
            if tag.get(attr):
                new = relativize(tag[attr], base_url, base_local)
                if new:
                    tag[attr] = new
        for attr in SRCSET_ATTRS:
            if tag.get(attr):
                parts = []
                for part in tag[attr].split(","):
                    part = part.strip()
                    if not part:
                        continue
                    bits = part.split(None, 1)
                    new = relativize(bits[0], base_url, base_local)
                    url = new or bits[0]
                    parts.append(url + ((" " + bits[1]) if len(bits) > 1 else ""))
                tag[attr] = ", ".join(parts)
        if tag.name == "link" and tag.get("href"):
            rel = " ".join(tag.get("rel") or []).lower()
            # canonical / alternate 等 SEO 標記保留原始絕對網址
            if not any(k in rel for k in KEEP_ABSOLUTE_REL):
                new = relativize(tag["href"], base_url, base_local)
                if new:
                    tag["href"] = new
        elif tag.name in ("a", "area") and tag.get("href"):
            new = relativize(tag["href"], base_url, base_local)
            if new:
                tag["href"] = new
        elif tag.name == "form" and tag.get("action"):
            pass  # 搜尋/表單送出端點維持原樣,靜態站無後端
        if tag.get("style"):
            tag["style"] = rewrite_css_text(tag["style"], base_url, base_local)

    for st in soup.find_all("style"):
        if st.string:
            st.string.replace_with(rewrite_css_text(st.string, base_url, base_local))

    out = str(soup)

    # inline JS 內的站內絕對路徑
    def sub_js(m):
        new = relativize(m.group(2), base_url, base_local)
        return m.group(0) if new is None else m.group(1) + new + m.group(3)

    def sub_js_escaped(m):
        decoded = re.sub(r"\\u([0-9a-fA-F]{4})",
                         lambda e: chr(int(e.group(1), 16)), m.group(2))
        new = relativize(decoded, base_url, base_local)
        return m.group(0) if new is None else m.group(1) + new + m.group(3)

    out = re.sub(r"""(['"])((?:https?:)?//(?:www\.)?topfamous\.com\.tw/[^'"\s]*?)(['"])""",
                 sub_js_escaped, out)
    out = re.sub(r"""(['"])(/wp-(?:content|includes)/[^'"\s]*?)(['"])""", sub_js, out)

    open(fp, "w", encoding="utf-8").write(out)
    rewritten["html"] += 1


def main():
    for url, rel in pages.items():
        rewrite_html(url, rel)
    for url, rel in assets.items():
        if not rel.endswith(".css"):
            continue
        fp = os.path.join(OUT, rel)
        if not os.path.exists(fp):
            continue
        text = open(fp, encoding="utf-8", errors="replace").read()
        open(fp, "w", encoding="utf-8").write(rewrite_css_text(text, url, rel))
        rewritten["css"] += 1

    print(f"重寫完成:{rewritten['html']} 個 HTML,{rewritten['css']} 個 CSS")
    if misses:
        print(f"\n未在本地找到對應檔案的站內 URL({len(misses)} 個,已維持原樣):")
        for u, c in sorted(misses.items(), key=lambda x: -x[1])[:25]:
            print(f"  x{c:3d}  {u}")


main()
