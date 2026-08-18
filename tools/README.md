# 爬取工具

網站仍在線上,日後想重新抓一份時依序執行(需 `pip install requests beautifulsoup4 lxml`):

```bash
python3 clone.py         ../docs ../crawl-manifest.json   # 1. 依 sitemap 抓取全站頁面與資產
python3 restore.py       ../docs ../crawl-manifest.json   # 2. 還原 WP Fastest Cache 壓縮前的原始 CSS/JS
python3 fetch_missing.py ../docs ../crawl-manifest.json   # 3. 補抓 inline JS 條件載入的資產
python3 rewrite.py       ../docs ../crawl-manifest.json   # 4. 將所有網址改寫為相對路徑
python3 verify.py        ../docs                          # 5. 檢查有無斷連結
python3 compare.py       ../docs ../crawl-manifest.json   # 6. 與線上版逐頁比對文字內容
```

`clone.py` 之外的步驟都可重複執行(具冪等性)。
