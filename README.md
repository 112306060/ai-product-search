# AI 國外新品搜尋系統 MVP

## 目標
輸入搜尋條件後，自動搜尋歐盟洗髮精品牌/廠商，整理成公司既有廠商紀錄格式，預設輸出50筆。

## 第一階段功能
- 多語系關鍵字生成
- 搜尋引擎結果擷取
- 網站文字讀取
- AI品牌資料分析
- Excel輸出

## 第二階段預留
- 台灣是否已有代理商
- 是否中國製造
- 台灣是否已上市
- AI評分排序

## 安裝
```bash
pip install -r requirements.txt
cp .env.example .env
```

## 執行
```bash
python main.py
```

## 輸出
```text
data/output.xlsx
```

## 注意
第一版搜尋與AI分析模組先保留介面，正式開發時填入API Key並接搜尋服務與OpenAI API。
