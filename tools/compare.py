#!/usr/bin/env python3
"""逐頁比對本地複製版與線上版的可見文字內容。"""
import os, sys, re, json, difflib
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup, Comment

OUT, MANIFEST = sys.argv[1], sys.argv[2]
man = json.load(open(MANIFEST, encoding="utf-8"))
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"})


def visible_text(html):
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    for c in soup.find_all(string=lambda x: isinstance(x, Comment)):
        c.extract()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def img_count(html):
    return len(BeautifulSoup(html, "lxml").find_all("img"))


def one(item):
    url, rel = item
    fp = os.path.join(OUT, rel)
    if not os.path.exists(fp):
        return rel, "本地檔案不存在", None
    local = open(fp, encoding="utf-8").read()
    try:
        r = s.get(url, timeout=30)
    except Exception as e:
        return rel, f"線上抓取失敗 {e}", None
    if r.status_code != 200:
        return rel, f"線上回應 {r.status_code}", None
    remote = r.content.decode("utf-8", "replace")
    lt, rt = visible_text(local), visible_text(remote)
    li, ri = img_count(local), img_count(remote)
    if lt == rt and li == ri:
        return rel, None, None
    detail = []
    if lt != rt:
        sm = difflib.SequenceMatcher(None, lt, rt)
        detail.append(f"文字相似度 {sm.ratio():.4f} (本地 {len(lt)} 字 / 線上 {len(rt)} 字)")
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                detail.append(f"  {tag}: 本地「{lt[i1:i2][:60]}」 vs 線上「{rt[j1:j2][:60]}」")
                if len(detail) > 4:
                    break
    if li != ri:
        detail.append(f"img 數量 本地 {li} / 線上 {ri}")
    return rel, None, "\n".join(detail)


pages = sorted(man["pages"].items())
errors, diffs, same = [], [], 0
with ThreadPoolExecutor(max_workers=8) as ex:
    for rel, err, diff in ex.map(one, pages):
        if err:
            errors.append((rel, err))
        elif diff:
            diffs.append((rel, diff))
        else:
            same += 1

print(f"比對 {len(pages)} 頁:完全一致 {same},有差異 {len(diffs)},錯誤 {len(errors)}")
for rel, d in diffs[:10]:
    print(f"\n--- {rel}\n{d}")
for rel, e in errors[:10]:
    print(f"  ✗ {rel}: {e}")
