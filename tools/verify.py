#!/usr/bin/env python3
"""驗證複製站台:檢查每個頁面引用的本地檔案是否都存在。"""
import os, sys, re, glob
from urllib.parse import unquote, urlsplit
from bs4 import BeautifulSoup

OUT = sys.argv[1]
missing, checked, ext_hosts = {}, 0, {}
CSS_URL_RE = re.compile(r"""url\(\s*['"]?([^'")]+?)['"]?\s*\)""", re.I)


def check(ref, base_file):
    global checked
    ref = ref.strip()
    if not ref or ref.startswith(("data:", "mailto:", "tel:", "javascript:", "#", "//", "http")):
        if ref.startswith(("http", "//")):
            h = urlsplit(ref if ref.startswith("http") else "https:" + ref).netloc
            ext_hosts[h] = ext_hosts.get(h, 0) + 1
        return
    path = unquote(ref.split("#")[0].split("?")[0])
    if not path:
        return
    target = os.path.normpath(os.path.join(os.path.dirname(base_file), path))
    checked += 1
    if not os.path.exists(target):
        rel_src = os.path.relpath(base_file, OUT)
        missing.setdefault(os.path.relpath(target, OUT), set()).add(rel_src)


for f in glob.glob(os.path.join(OUT, "**", "*.html"), recursive=True):
    soup = BeautifulSoup(open(f, encoding="utf-8").read(), "lxml")
    for tag in soup.find_all(True):
        for a in ("src", "href", "data-src", "data-lazy-src", "poster"):
            if tag.get(a):
                check(tag[a], f)
        for a in ("srcset", "data-srcset", "data-lazy-srcset"):
            if tag.get(a):
                for part in tag[a].split(","):
                    if part.strip():
                        check(part.strip().split()[0], f)
        if tag.get("style"):
            for u in CSS_URL_RE.findall(tag["style"]):
                check(u, f)
    for st in soup.find_all("style"):
        for u in CSS_URL_RE.findall(st.get_text()):
            check(u, f)

for f in glob.glob(os.path.join(OUT, "**", "*.css"), recursive=True):
    for u in CSS_URL_RE.findall(open(f, encoding="utf-8", errors="replace").read()):
        check(u, f)

print(f"檢查 {checked} 個本地引用")
print(f"缺失目標:{len(missing)}")
for t, srcs in sorted(missing.items())[:20]:
    print(f"  ✗ {t}   ← 被 {len(srcs)} 個檔案引用,例:{sorted(srcs)[0]}")
print("\n仍指向外部主機的引用:")
for h, c in sorted(ext_hosts.items(), key=lambda x: -x[1]):
    print(f"  {c:5d}  {h}")
