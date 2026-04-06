# THSR-Ticket

> **⚠️ 純研究用途，請勿用於不當用途**

台灣高鐵自動訂票機器人。提供指定日期與候選班次，系統依優先順序自動訂票，每日重試直到訂到為止。

## 功能

- 依優先順序嘗試多個候選班次，訂到第一個有位的班次
- 若用次要班次訂到票，仍會繼續追求優先班次
- 付款期限到期前自動重新訂票（滾動式預訂）
- GitHub Actions 每日 02:00 UTC+8 自動執行

## 快速開始

### 1. 安裝依賴

```bash
uv sync --dev
# 若需要本地 OCR CAPTCHA 解析
uv sync --extra ocr
```

### 2. 設定 `.env`

```env
GEMINI_API_KEY=your_key
personal_identification=A123456789
phone_number=0912345678
email=your@email.com
```

### 3. 設定 `config.yaml`

```yaml
captcha:
  method: "HYBRID"   # GEMINI / OCR / HYBRID
  ocr_retries: 5
  gemini_retries: 3

tickets:
  - name: "Friday Home"
    start_station: "Taipei"
    dest_station: "Taichung"
    dates:
      - "2026-04-17"
      - "2026-04-24"
    candidates:
      - "149"     # 優先 1
      - "1245"    # 優先 2（備選）
    ticket_amount:
      adult: 1
    car_class: "standard"
    trip_type: "one-way"
    seat_preference: "none"
```

### 4. 執行

```bash
uv run python -m thsr_ticket.main --mode auto
```

## 執行模式

| 模式 | 說明 |
|------|------|
| `auto` | 依序執行 plan → buy → manage |
| `plan` | 根據 config.yaml 產生待訂清單 |
| `buy` | 處理待訂清單，嘗試訂票 |
| `manage` | 檢查並處理即將到期的訂位 |

## 站點代碼

| 名稱 | 英文 |
|------|------|
| 南港 | Nangang |
| 台北 | Taipei |
| 板橋 | Banqiao |
| 桃園 | Taoyuan |
| 新竹 | Hsinchu |
| 苗栗 | Miaoli |
| 台中 | Taichung |
| 彰化 | Changhua |
| 雲林 | Yunlin |
| 嘉義 | Chiayi |
| 台南 | Tainan |
| 左營 | Zuouing |

## CI/CD（GitHub Actions）

在 repo Settings → Secrets 設定：`GEMINI_API_KEY`、`PERSONAL_ID`、`PHONE_NUMBER`、`EMAIL`

每日 02:00 UTC+8 自動執行，訂票結果（`tobuy.json`、`reservations.json`）自動 commit 回 repo。

## 技術說明

- HTTP 客戶端使用 `curl-cffi`（模擬 Chrome TLS fingerprint，繞過 Akamai bot 偵測）
- CAPTCHA 支援三種模式：Gemini Vision API、本地 ddddocr OCR、Hybrid（OCR 優先）
- 狀態以 JSON 檔案儲存於 repo（`tobuy.json`、`reservations.json`）
- 詳細架構見 `ARCHITECTURE.md`，參數說明見 `docs/parameter_reference.md`
