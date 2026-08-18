# topfamous.com.tw 靜態複製版

宏定科技有限公司網站(https://topfamous.com.tw)的完整靜態複製,抓取日期 2026-08-18。
原站為 WordPress + Enfold 佈景主題;此版本已移除所有 WordPress 相依,是純靜態 HTML。

## 內容

| 項目 | 數量 |
|---|---|
| HTML 頁面 | 166 |
| 檔案總數 | 1,229 |
| 總大小 | 182 MB |

```
docs/
├── index.html              首頁
├── 關於我們/  防護產品/  產品認證/  qa/  聯絡我們/    主要頁面
├── portfolio-item/         20 個產品明細頁
├── portfolio_entries/      15 個產品分類頁
├── 首頁/                   WordPress 附件頁(原站既有,非首頁本身)
├── author/                 作者彙整頁(原站既有)
└── wp-content/
    ├── themes/enfold/      佈景主題原始 CSS/JS
    ├── themes/enfold-child/ 子主題(網站的客製樣式在此)
    ├── plugins/            外掛資源
    └── uploads/            所有圖片(含 WordPress 各尺寸縮圖)
```

## 本機預覽

```bash
python3 -m http.server 8765 --directory docs
```

開啟 http://localhost:8765 。

> 建議用上面的方式預覽,不要直接雙擊 HTML 檔。以 `file://` 開啟時瀏覽器會擋掉部分資源,顯示會不完整。

## 部署

把 `docs/` 目錄整包上傳到任何靜態主機的根目錄即可,不需要 PHP、資料庫或任何後端:

- 一般虛擬主機:整包丟進 `public_html/`
- Cloudflare Pages / Netlify / Vercel / GitHub Pages:指定 `docs` 為發布目錄

所有站內連結都是**相對路徑**,所以放在子目錄(例如 `example.com/topfamous/`)也能正常運作。

## 已知限制

以下是原站依賴 WordPress 後端的功能,靜態化後無法運作:

1. **聯絡表單無法送出** —— 原站的 Contact Form 7 需要 PHP 後端(`wp-admin/admin-ajax.php`)。
   表單畫面完整保留,但按下送出不會寄信。若需要恢復功能,可改接 Formspree、
   Google 表單等第三方服務,或在頁面上改為直接顯示 email 與電話。
2. **站內搜尋失效** —— 搜尋功能由 WordPress 提供。
3. **需要連網的嵌入元件** —— 聯絡我們頁的 Google 地圖、頁尾的 Facebook 粉絲頁外掛,
   以及社群分享按鈕,都維持指向原服務,離線瀏覽時不會顯示。

## 與原站的一致性

已驗證項目:

- **內容比對**:166 個頁面逐頁抓取線上版比對可見文字與圖片數量,**全部完全一致**。
- **連結完整性**:27,111 個站內引用全部指向存在的本地檔案,**零斷連結**。
- 瀏覽器實測首頁、防護產品、聯絡我們等頁面,版面、輪播、字型圖示、動畫皆與線上版相同。

## 關於原始碼結構

原站啟用了 WP Fastest Cache,線上頁面載入的是雜湊命名的合併壓縮檔
(`wp-content/cache/wpfc-minified/8hxlib61/dglf9.css` 這類)。
此複製版已還原成壓縮前的原始檔案結構 —— 也就是 `wp-content/themes/enfold/css/base.css`
這種有意義的路徑,方便日後修改維護。網站的客製樣式集中在 `wp-content/themes/enfold-child/style.css`。

## 其他

- `tools/` — 重新抓取用的腳本,詳見 `tools/README.md`。
- `crawl-manifest.json` — 抓取紀錄,記載每個網址對應的本地檔案路徑。
