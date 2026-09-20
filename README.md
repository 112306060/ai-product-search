# AI 海外品牌搜尋系統

自動化尋找「還沒有台灣代理商、調性又符合」的海外消費品牌——取代原本人工一個一個 Google、一家一家開官網確認、再查台灣代理狀況的流程。

實際導入後，原本業務團隊平均要花 2–3 個月才能鎖定 1–2 個合適品牌並展開接洽，現在一週內就能篩出候選並主動寄出開發信；資料庫目前已累積 300 多筆經查證的品牌候選，系統也已用於東歐有機洗髮精、保加利亞玫瑰保養品、義大利專業美髮用品等真實搜尋任務。

## 這是什麼

貿易公司要開發一個新的代理品類，傳統流程完全靠人工：想關鍵字 → Google 搜尋國外品牌 → 打開每個官網確認產品/價位/調性 → 查台灣是不是已經有代理商 → 整理成名單。每一步都要真人看內容，一個品類常常要花上好幾週甚至數月。

這套系統把上面這條判斷邏輯拆成四個可以獨立除錯、獨立調整的階段，並用 AI 取代其中需要「理解語意、不是單純關鍵字比對」的判斷環節：

```
① 多語言搜尋擴展 → ② AI 產業分類 → ③ 台灣代理狀態查核 → ④ 匯出決策報表
```

## 核心流程

### ① 多語言搜尋擴展

海外品牌官網常用當地語言撰寫，只用英文關鍵字搜尋會漏掉大量候選。系統會依搜尋條件指定的國家/地區，動態解析出對應語言的優先順序（`modules/language_resolver.py`）：

- 每個國家對應一種主要商用語言（例如德國→德文、義大利→義大利文）
- 英文永遠排第一（國際商用共通語言，搜哪裡都有意義）
- 其餘語言依「涵蓋國家數」排序

關鍵字翻譯（`modules/keyword_translator.py`）採**內建詞庫優先、AI 只補漏**：常見商品/定位詞先查一份人工校對過的詞庫，完全不用花錢；詞庫沒有的詞才即時呼叫 OpenAI 翻譯，且結果**永久快取**（同一個詞不會重複翻譯、重複花錢）。

**動態語言擴張與飽和判斷**（`modules/search_pipeline.py`）：不是一開始就固定用幾種語言，而是一次搜一種語言，依實際成效（平均每組關鍵字挖到幾家「先前沒看過」的新候選）決定要不要換下一個語言。同時，每個語言都保證至少會被搜過一輪基本額度（`MIN_KEYWORDS_PER_LANGUAGE`），避免排序在前面的語言（尤其是英文）自己就填滿候選池，導致後面的語言完全沒被搜過——這是一個真實踩過、後來修正的設計問題。

### ② AI 產業分類

OpenAI 讀取候選公司**官網的實際內容**（不是只看搜尋摘要或公司名稱），依使用者設定的商品詞/定位詞/排除詞判斷是否為候選品牌。分類前會先用「候選網站必須符合定位詞」這類規則式硬過濾，把明顯不符合的先濾掉，不是什麼都丟給 AI 判斷，也省下 API 成本。

### ③ 台灣代理狀態查核

用三組中英文查詢（總代理、經銷商、Taiwan distributor 等關鍵字）搜尋，把結果交給 AI 判斷是否已有正式代理商——輸出不是單純是非題，證據不夠時會標「無法判斷」，並附上信心分數，供業務團隊決定要不要人工再確認。查證過程本身出錯（例如 API 故障）只會把台灣代理狀態標成「查證失敗」，不會連累前面已經花錢做完的分類結果。

### ④ 匯出決策報表

寫入共用的 Excel 資料庫，保留人工填寫欄位（例如聯絡狀況、聯絡人資料）不被系統覆蓋。多人共用、可能中途中斷的寫入情境改用**原子寫入**（先寫暫存檔再整份替換），避免資料庫損毀。

## 系統架構

| 分類 | 模組 | 說明 |
|---|---|---|
| 前端 | `app.py` | Streamlit 介面，四個頁籤：搜尋設定與執行／資料庫瀏覽／搜尋紀錄／關於使用說明 |
| 搜尋條件 | `modules/search_profile.py` | `SearchProfile`：本次搜尋的商品詞/定位詞/排除詞/國家地區條件 |
| 搜尋主流程 | `modules/search_pipeline.py` | 語言解析、關鍵字生成、候選收集、去重、寫入 |
| 語言/關鍵字 | `modules/language_resolver.py`、`modules/keyword_generator.py`、`modules/keyword_translator.py` | 語言優先順序解析、關鍵字組合生成、翻譯（詞庫優先＋AI 補漏＋快取） |
| AI 分析 | `modules/ai_analyzer.py`、`modules/website_classifier.py`、`modules/brand_name_validator.py` | 官網內容分析、產業分類、品牌名稱有效性檢查 |
| 台灣代理查核 | `modules/taiwan_distributor_checker.py` | 搜尋 + AI 判斷是否已有台灣代理商 |
| 展覽名錄（選用） | `modules/exhibitions/` | Cosmoprof Asia／Bologna／North America 官方參展商名錄，延遲載入、可拔插，缺少此模組系統仍可運作（僅剩 Google 搜尋來源） |
| 成本控管 | `modules/search_cost_estimator.py` | 執行前預估本次會呼叫幾次 API、大概多少花費與耗時，超過門檻會提醒 |
| 涵蓋率追蹤 | `modules/coverage_tracker.py` | 同一組搜尋條件重複執行時，記錄每次新增品牌家數，新增數持續偏低會提醒該換角度搜尋 |
| 資料輸出 | `modules/excel_exporter.py` | 原子寫入、既有品牌去重（依網域，忽略 TLD，避免同品牌不同國別網域被誤判為不同公司） |
| 搜尋紀錄 | `modules/search_history.py` | 記錄每次搜尋的條件與結果，供「搜尋紀錄」頁籤查詢 |
| 授權機制 | `modules/license_manager.py`、`generate_keys.py`、`generate_license.py` | Ed25519 簽章式軟體授權（詳見下方「授權機制」） |
| 安裝流程 | `launcher.py`、`run_frontend.bat` | 防呆啟動檢查（Python 版本／套件／API 金鑰／授權檔）與雙擊執行入口 |
| 打包交付 | `build_release.py` | 用 PyArmor 封裝原始碼，產出可交付客戶的版本（`--no-exhibitions` 可排除展覽模組，交付其他產業客戶） |

## 安裝與執行

### 一般使用方式（防呆流程）

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入 API 金鑰
```

雙擊 `run_frontend.bat`（或執行 `python launcher.py`），會依序檢查：套件安裝 → `.env` 金鑰是否填妥 → `license.lic` 授權檔是否存在，全部通過才會啟動 Streamlit。任何一關沒過都會印出中文說明，不會讓使用者卡在看不懂的英文錯誤訊息。

### 開發模式（略過檢查，直接啟動）

```bash
streamlit run app.py
```

### 指令列版本（不透過網頁介面，跑 `config.py` 裡的預設搜尋條件）

```bash
python main.py
```

## 環境設定

`.env` 需要：

| 變數 | 說明 |
|---|---|
| `OPENAI_API_KEY` | AI 分類、翻譯補漏、台灣代理狀態判斷 |
| `SEARCH_API_KEY` | SerpAPI 金鑰，Google 搜尋與台灣代理查核用 |
| `SEARCH_PROVIDER` | 固定填 `serpapi` |

`config.py` 的 `SearchConfig` 提供搜尋執行面的開關（測試模式、資料來源開關、成本估算、深度分頁等），`DEFAULT_SEARCH_PROFILE` 則是使用者打開搜尋頁面時預先填好的品類範本——交付給不同產業的客戶前，只需要手動改這裡的預設商品詞/定位詞/地區即可，不需要改動核心邏輯。

## 授權機制

系統設計成「客戶自架 + 自帶 API 金鑰（BYOK）」而不是 SaaS：客戶在自己電腦上執行，用自己的 OpenAI／SerpAPI 帳號，搜尋內容跟客戶名單完全不會經過供應方。

授權採 **Ed25519 簽章**：

```bash
python generate_license.py --customer "客戶名稱" --days 30 --output license.lic
```

`modules/license_manager.py` 在啟動時驗證簽章、檢查到期日，並用本機狀態檔防止使用者竄改系統時間繞過到期限制；到期前 14 天會顯示續約提醒。私鑰只存放在開發端的 `keys/` 目錄（已加入 `.gitignore`，不會進版控），交付客戶的是封裝後的程式加上簽好章的 `license.lic`，客戶端沒有能力自己簽發授權。

## 測試

`tests/` 底下是各模組的測試（多數針對 Cosmoprof 展覽名錄的篩選/比對邏輯，以及關鍵字生成、品牌名稱驗證、URL 處理等模組），採 `test_*()` 函式斷言寫法，可用 pytest 執行：

```bash
pip install pytest
pytest tests/
```

## 維護腳本

Cosmoprof 三大展覽名錄（Asia／Bologna／North America）需要定期同步，這幾支腳本從專案根目錄執行：

```bash
# Cosmoprof North America：同步展商與官方分類
python sync_cpna_catalog.py [--enrich-new] [--max-records N]

# Cosmoprof North America：建立/更新完整詳情快取
python build_cpna_cache.py

# Cosmoprof Worldwide Bologna：同步展商名錄與官網
python sync_bologna_catalog.py
python update_bologna_details.py
```

`probe_*.py`、`update_cpna_hair_countries.py`、`run_demo_search.py` 則是開發過程中用來探測官方 API 回應、修正特定分類資料、跑單次示範搜尋的一次性腳本，非日常操作必需。

## 已知限制

- **語言搜尋是無狀態的**：每次搜尋都是全新執行，不會記住「上次同樣條件的搜尋已經搜過哪些語言」。重複搜尋同一組條件會從頭開始，雖然已經用「每語言保底額度」確保每次搜尋內部不會有語言被完全略過，但跨次搜尋之間目前還沒有進度接續機制。
- **候選池門檻是聚合指標**：判斷「要不要繼續擴張語言」看的是累積候選數，不區分是哪個語言貢獻的，理論上仍可能出現英文/德文等大語言貢獻的候選撐大了池子、其他語言的保底額度用完後就不再加碼的情況。

## 專案結構

```
app.py                     # Streamlit 前端入口
main.py                    # 指令列入口（跑 config.py 的預設搜尋條件）
config.py                  # SearchConfig／DEFAULT_SEARCH_PROFILE
launcher.py                # 防呆啟動檢查
run_frontend.bat           # 雙擊執行入口
generate_keys.py           # 產生授權簽章金鑰對（開發端用）
generate_license.py        # 簽發客戶授權檔
build_release.py           # PyArmor 封裝打包
modules/                   # 核心邏輯（搜尋、AI 分析、授權、匯出等）
modules/exhibitions/       # 展覽名錄資料源（選用模組）
landing_page/              # 產品介紹頁與 Gmail 開發信輔助工具（靜態頁面，Vercel 部署）
prompts/                   # AI 分析用的 prompt 樣板
tests/                     # 各模組的測試（pytest）
sync_*.py / update_*.py / probe_*.py / build_cpna_cache.py / run_demo_search.py
                            # 展覽名錄資料同步、除錯用的一次性腳本（見「維護腳本」）
```
