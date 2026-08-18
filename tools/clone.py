#!/usr/bin/env python3
"""topfamous.com.tw 靜態站台複製工具。

Phase 1: 由 sitemap + 內部連結遞迴抓取所有 HTML 頁面與其引用的資產。
Phase 2: 將所有 URL 重寫為相對路徑,產生可離線開啟的靜態站台。
"""
import os, re, sys, time, json
from urllib.parse import urljoin, urlsplit, urlunsplit, unquote, quote
import requests
from bs4 import BeautifulSoup

SITE = "https://topfamous.com.tw"
HOST = "topfamous.com.tw"
OUT = sys.argv[1] if len(sys.argv) > 1 else "./topfamous-clone"

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
SKIP_RE = re.compile(r"/(wp-admin|wp-login|xmlrpc\.php|wp-json)|/feed/?$|\?s=|/comments/", re.I)
ASSET_EXT = re.compile(r"\.(css|js|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot|otf|mp4|webm|pdf)$", re.I)

session = requests.Session()
session.headers.update(HEADERS)

pages = {}      # url -> local relative path
assets = {}     # url -> local relative path
failed = {}
queue = []
seen = set()


def norm(url):
    """正規化 URL:去掉 fragment,保留 query 供下載用。"""
    p = urlsplit(url)
    if p.scheme not in ("http", "https"):
        return None
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))


def is_internal(url):
    return urlsplit(url).netloc.lower().replace("www.", "") == HOST


def local_path_for_page(url):
    path = unquote(urlsplit(url).path)
    if path in ("", "/"):
        return "index.html"
    path = path.strip("/")
    if os.path.splitext(path)[1].lower() in (".html", ".htm"):
        return path
    return path + "/index.html"


def local_path_for_asset(url):
    p = urlsplit(url)
    path = unquote(p.path).lstrip("/")
    if not path:
        path = "index"
    if is_internal(url):
        base = path
    else:
        base = os.path.join("_ext", p.netloc, path)
    # query 只作為快取破壞參數,但外部 API(如 Google Fonts)靠 query 決定內容
    if p.query and not ASSET_EXT.search(path):
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", p.query)[:80]
        base = base + "_" + safe
    if not os.path.splitext(base)[1]:
        base += ".css" if "fonts.googleapis" in p.netloc else ".bin"
    return base


def save(rel, content):
    dest = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    mode = "wb" if isinstance(content, bytes) else "w"
    with open(dest, mode, **({} if mode == "wb" else {"encoding": "utf-8"})) as f:
        f.write(content)
    return dest


def fetch(url, binary=False):
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                return r
            if 300 <= r.status_code < 400:
                return r
            failed[url] = r.status_code
            return None
        except Exception as e:
            if attempt == 2:
                failed[url] = str(e)
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


# ---------- Phase 1: 抓取 ----------

def collect_sitemap_urls():
    urls = set()
    idx = fetch(SITE + "/sitemap_index.xml")
    maps = re.findall(r"<loc>([^<]+)</loc>", idx.text) if idx else []
    for m in maps:
        r = fetch(m)
        if not r:
            continue
        for u in re.findall(r"<loc>([^<]+)</loc>", r.text):
            if not SKIP_RE.search(u):
                urls.add(norm(u))
    urls.add(SITE + "/")
    return {u for u in urls if u and is_internal(u)}


CSS_URL_RE = re.compile(r"""url\(\s*['"]?([^'")]+?)['"]?\s*\)""", re.I)
CSS_IMPORT_RE = re.compile(r"""@import\s+(?:url\()?\s*['"]([^'"]+)['"]""", re.I)


def queue_asset(url):
    u = norm(url)
    if not u or u in assets or u in seen:
        return
    if u.startswith("data:") or SKIP_RE.search(u):
        return
    seen.add(u)
    queue.append(("asset", u))


def queue_page(url):
    u = norm(url)
    if not u or u in pages or u in seen or not is_internal(u):
        return
    if SKIP_RE.search(u) or ASSET_EXT.search(urlsplit(u).path):
        return
    seen.add(u)
    queue.append(("page", u))


def extract_from_srcset(value):
    out = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(part.split()[0])
    return out


def scan_html(url, html):
    soup = BeautifulSoup(html, "lxml")
    attrs = [("src", None), ("href", None), ("data-src", None),
             ("data-lazy-src", None), ("poster", None), ("content", "meta")]
    for tag in soup.find_all(True):
        # iframe 指向 Google Maps / Facebook 等動態服務,抓成靜態檔會失效
        if tag.name == "iframe":
            continue
        for attr in ("src", "data-src", "data-lazy-src", "poster"):
            if tag.get(attr):
                queue_asset(urljoin(url, tag[attr]))
        for attr in ("srcset", "data-srcset", "data-lazy-srcset"):
            if tag.get(attr):
                for u in extract_from_srcset(tag[attr]):
                    queue_asset(urljoin(url, u))
        if tag.name == "link" and tag.get("href"):
            rel = " ".join(tag.get("rel") or []).lower()
            if any(k in rel for k in ("stylesheet", "icon", "preload", "manifest")):
                queue_asset(urljoin(url, tag["href"]))
            elif rel in ("canonical", "alternate", "next", "prev", "shortlink"):
                pass
            else:
                queue_page(urljoin(url, tag["href"]))
        if tag.name == "a" and tag.get("href"):
            href = tag["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            full = urljoin(url, href)
            if not is_internal(full):
                continue
            if ASSET_EXT.search(urlsplit(full).path):
                queue_asset(full)
            else:
                queue_page(full)
        if tag.get("style"):
            for u in CSS_URL_RE.findall(tag["style"]):
                if not u.startswith("data:"):
                    queue_asset(urljoin(url, u))
    for st in soup.find_all("style"):
        for u in CSS_URL_RE.findall(st.get_text()) + CSS_IMPORT_RE.findall(st.get_text()):
            if not u.startswith("data:"):
                queue_asset(urljoin(url, u))
    # inline script 內的資產路徑(Enfold 常見)
    for sc in soup.find_all("script"):
        txt = sc.string or ""
        for u in re.findall(r"""['"](/wp-content/[^'"\s]+?\.(?:png|jpe?g|gif|svg|webp|css|js|woff2?))['"]""", txt, re.I):
            queue_asset(urljoin(url, u))


def scan_css(url, text):
    for raw in CSS_URL_RE.findall(text) + CSS_IMPORT_RE.findall(text):
        raw = raw.strip()
        if raw.startswith("data:") or raw.startswith("#"):
            continue
        queue_asset(urljoin(url, raw))


def crawl():
    for u in sorted(collect_sitemap_urls()):
        queue_page(u)
    n = 0
    while queue:
        kind, url = queue.pop(0)
        n += 1
        if kind == "page":
            r = fetch(url)
            if not r:
                print(f"  ✗ page {url}")
                continue
            # 站台宣告 charset=UTF-8,不可讓 requests 自行猜測(會猜成 latin-1 造成中文檔名亂碼)
            html = r.content.decode("utf-8", "replace")
            rel = local_path_for_page(url)
            pages[url] = rel
            save(rel, html)
            scan_html(url, html)
            print(f"[{n:4d}] page  {rel}")
        else:
            r = fetch(url)
            if not r:
                print(f"  ✗ asset {url}")
                continue
            rel = local_path_for_asset(url)
            assets[url] = rel
            ctype = r.headers.get("content-type", "").lower()
            if "css" in ctype or rel.endswith(".css"):
                text = r.content.decode("utf-8", "replace")
                save(rel, text)
                scan_css(url, text)
            else:
                save(rel, r.content)
            if n % 25 == 0:
                print(f"[{n:4d}] asset {rel}")
    print(f"\n抓取完成:{len(pages)} 頁,{len(assets)} 個資產,{len(failed)} 個失敗")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    crawl()
    with open(os.path.join(OUT, "..", "crawl-manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"pages": pages, "assets": assets, "failed": failed}, f,
                  ensure_ascii=False, indent=2)
