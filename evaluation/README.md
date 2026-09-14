# LLM Website Classifier Evaluation

這個資料夾用來評估 `modules/website_classifier.py` 的候選品牌分類品質。

目標不是把模型自己產生的 `agency_fit_score` 當成準確率，而是建立一批**人工標註（human-labeled）**資料，將 AI 判斷與人工答案比較，計算 Accuracy、Precision、Recall、F1。

## 1. 建立人工標註資料

複製範例：

```bash
cp evaluation/dataset.example.jsonl evaluation/dataset.jsonl
```

每一行是一筆 JSON：

```json
{"url":"https://brand.example","page_text":"官網擷取文字...","expected_is_candidate":true,"note":"為什麼人工判定應保留"}
```

欄位：

- `url`: 候選網站 URL
- `page_text`: 當時交給 classifier 的網站文字
- `expected_is_candidate`: 人工判定，`true` = 應保留，`false` = 應排除
- `note`: 人工判斷理由（選填，但建議填）

正式評估建議至少 50 筆，而且正例與負例都要有。不要只挑「很容易」的案例；應包含品牌官網、零售商、Marketplace、媒體、OEM/ODM、產品不符、定位不符、國家不符等邊界案例。

> `dataset.example.jsonl` 只有 synthetic examples，用來確認程式能跑，不可拿它的分數當作品集成果。

## 2. 執行評估

先確認 `.env` 有 `OPENAI_API_KEY`，並已安裝專案 requirements。

例如評估「歐洲有機天然洗髮精」：

```bash
python evaluation/run_evaluation.py evaluation/dataset.jsonl \
  --query "European organic natural shampoo brands" \
  --product-keywords "shampoo,hair care" \
  --positioning-keywords "organic,natural" \
  --included-regions "europe"
```

Windows Git Bash 也可以使用同樣寫法；若使用 PowerShell，可將指令寫成一行。

先用少量資料測試 API：

```bash
python evaluation/run_evaluation.py evaluation/dataset.jsonl --query "European organic natural shampoo brands" --product-keywords "shampoo,hair care" --positioning-keywords "organic,natural" --included-regions "europe" --limit 5
```

預設詳細結果會寫入：

```text
evaluation/evaluation_results.json
```

## 3. 四個主要指標

- **Accuracy**：全部案例中判對多少。
- **Precision**：AI 說「值得保留」的品牌裡，有多少真的值得保留。對本系統很重要，因為低 Precision 會讓業務收到大量垃圾候選。
- **Recall**：人工認為值得保留的品牌裡，AI 找回多少。低 Recall 代表可能錯過商機。
- **F1**：Precision 與 Recall 的綜合指標。

同時會輸出 confusion matrix 的四個數字：TP、TN、FP、FN。

## 4. 面試時怎麼講

完成真實 50+ 筆人工標註後，可以說：

> 我沒有直接把 LLM 自己給的分數當成模型準確率，而是建立人工標註資料集，把 classifier 的 `is_candidate` 和人工答案比較，使用 Precision、Recall、F1 檢查分類品質。我也會另外看 False Positive / False Negative，找出 prompt 或規則最容易誤判的情境。

只有在實際跑完真實資料後，才能在履歷或作品集寫具體百分比。

## 5. 下一步可以怎麼迭代

第一次跑完後，優先檢查 `evaluation_results.json` 中 `correct=false` 的案例：

1. False Positive 為什麼被留下？
2. False Negative 為什麼被排除？
3. 問題來自網站文字抓取、搜尋條件、prompt，還是模型輸出？
4. 修改後重新跑**同一份固定資料集**，才能公平比較前後版本。

之後可把資料分成 `development` 與 `test` 兩組，避免一直針對同一批測試資料調 prompt，造成過度擬合。
