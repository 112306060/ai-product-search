# AI 國外新品搜尋系統

自動依商品與定位條件，搜尋國外品牌廠商，評估是否適合台灣代理／經銷，並整理成公司既有廠商紀錄格式輸出。

## 目標

輸入商品類別、定位（如有機/天然/純素）、國家或地區後，系統會：

1. 動態產生多語系搜尋關鍵字並透過 Google 搜尋
2. 同時查詢三大官方展覽名錄（Cosmoprof Asia／Cosmoprof Worldwide Bologna／Cosmoprof North America）
3. 爬取候選官網內容，用 AI 判斷是否符合搜尋條件
4. 整理成公司廠商紀錄格式（商品類別、國家、評論等）
5. 用 AI 判斷該品牌台灣是否已有代理商
6. 增量匯出成 Excel，並保留人工填寫欄位不被覆蓋

搜尋條件（商品、定位、國家/地區）完全由 `SearchProfile` 動態產生，不寫死特定商品或地區——目前 `config.py` 裡的預設值（有機天然洗髮精／歐洲）只是開發測試用的範例設定。

## 資料來源

| 來源 | 說明 |
|---|---|
| Google 搜尋 | 透過 SerpAPI，依商品/定位/地區組合關鍵字搜尋 |
| Cosmoprof Asia | 即時查詢官方參展商 API |
| Cosmoprof Worldwide Bologna | 讀取本地快取名錄；官方目錄本身不提供品牌官網，會另外用公司名稱查詢 Google 找出真正官網（找不到則保留「待人工確認」紀錄） |
| Cosmoprof North America | 依搜尋需求動態比對官方商品分類，即時查詢官方 API 並合併本地快取 |

三大展覽名錄需要先執行對應的同步腳本才有資料（見下方「維護腳本」）。

## 安裝

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env` 需要填入：
- `OPENAI_API_KEY`：AI 分類與品牌/代理商分析
- `SEARCH_API_KEY`：SerpAPI 金鑰
- `SEARCH_PROVIDER=serpapi`

## 執行

```bash
python main.py
```

正式執行（關閉 `config.py` 的 `test_mode`）前，程式會先印出**預估用量**（大概會用幾次 SerpAPI／OpenAI、預估費用與耗時），確認合理再繼續。

## 輸出

```text
data/output.xlsx
```

採增量合併：同一品牌（以官網網域辨識）重複出現時只更新分析欄位，「後續連絡情況」「連絡人資料」這兩個人工填寫欄位永遠不會被系統覆蓋。

## 系統設計重點

- **速度**：Google 關鍵字搜尋、三大展覽來源收集、Bologna 官網查詢、台灣代理查證，皆已平行化。實測 `target_count=10` 的完整搜尋約 4 分鐘。
- **安全防護**：
  - 關鍵字組合數有硬性上限（`MAX_KEYWORDS`），避免搜尋條件太寬鬆時關鍵字暴增
  - AI 分類呼叫失敗會重試並安全降級，不會讓整個搜尋中斷
  - 單一候選處理失敗只會略過該候選，不影響其他候選
  - Google 端與展覽端結果分開即時儲存，任一批出狀況已完成的部分不會遺失
- **成本追蹤**：執行前會印出預估的 API 用量、費用與時間（`modules/search_cost_estimator.py`）
- **涵蓋率追蹤**：同一組搜尋條件重複執行時，會記錄每次新增的品牌家數，並在新增數持續偏低時提醒該換個角度搜尋（`modules/coverage_tracker.py`，資料存於 `data/coverage/`）
- **快取**：台灣代理查證（7天）、Bologna 官網查詢（180天）、近期已分析品牌（30天內不重複分析）皆有快取，重複執行同一組條件會越來越便宜

## 維護腳本

三大展覽名錄需要定期同步：

```bash
# Cosmoprof North America：同步展商與官方分類
python sync_cpna_catalog.py [--enrich-new] [--max-records N]

# Cosmoprof North America：建立/更新完整詳情快取
python build_cpna_cache.py

# Cosmoprof Worldwide Bologna：同步展商名錄
python sync_bologna_catalog.py
python update_bologna_details.py
```

## 之後規劃

- **前端**：Streamlit 網頁介面，讓使用者直接輸入商品／定位／國家，取代目前 `config.py` 的固定測試設定
- **資料庫**：目前以 Excel 為主要儲存方式，之後會改成正式資料庫（SQLite／其他，視與廠商討論結果），Excel 屆時會變成「從資料庫彙整匯出報表」的附加功能，而非主要資料來源
