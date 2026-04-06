# 架構設計文件

## 核心策略

**滾動式預訂（Rolling Reservation）**：系統每日執行，持續追蹤指定班次的訂位狀態。付款期限到期前自動重新訂票，確保長期持有座位而無需實際付款。

## 系統工作流程

### Plan → Buy → Manage

```
config.yaml
    ↓ Planner
tobuy.json ──────→ Buyer ──→ reservations.json
    ↑                              ↓
    └─────────── Manager ──────────┘
               (到期重訂)
```

### 第一階段：Planner

- 讀取 `config.yaml` 中的 `dates` 與 `candidates`
- 過濾掉已過期的日期
- 對尚未在 queue 或 reservations 中的日期，新增 `TicketRequest` 到 `tobuy.json`

### 第二階段：Buyer

對每個 `TicketRequest`，依 `candidates` 清單優先順序嘗試訂票：

```
for candidate in candidates:
    SearchTrainFlow(by train_id) → ConfirmTrainFlow → ConfirmTicketFlow
    成功 → 存入 reservations.json
           若非第一優先 → re-queue 更優先的 candidates
    失敗 → 試下一個 candidate
全部失敗 → 保留在 tobuy.json，明日重試
```

### 第三階段：Manager

- 檢查 `reservations.json` 中每個訂位的付款期限
- 若距到期 < 1 天 → 移出 reservations，加回 `tobuy.json` 重訂

## 技術選型

| 項目 | 選擇 | 原因 |
|------|------|------|
| HTTP 客戶端 | `curl-cffi` | 模擬 Chrome TLS fingerprint，繞過 Akamai bot 偵測 |
| HTML 解析 | `BeautifulSoup` | 解析 THSR 訂票頁面回應 |
| CAPTCHA | Gemini Vision / ddddocr | Hybrid 模式：OCR 優先，失敗則用 Gemini |
| 排程 | GitHub Actions | `cron: '0 18 * * *'`（02:00 UTC+8） |
| 設定驗證 | Pydantic v1 | `config.yaml` schema 驗證 |
| 狀態儲存 | JSON 檔案 | `tobuy.json`、`reservations.json` commit 回 repo |

## 訂票流程細節

```
GET /IMINT/?locale=tw          ← 取得 session (JSESSIONID) + CAPTCHA 圖片
POST /IMINT/;jsessionid=XXX    ← 提交搜尋表單（by train_id）+ CAPTCHA 解答
POST /IMINT/?wicket:...S2Form  ← 確認選取班次
POST /IMINT/?wicket:...S3Form  ← 填入個人資料
← BookingResult (PNR + 付款期限)
```

## 專案結構

```
.
├── .github/workflows/
│   └── booking.yml              # GitHub Actions（每日 02:00 UTC+8）
├── config.yaml                  # 使用者設定（日期、候選班次）
├── tobuy.json                   # 待訂清單（狀態檔）
├── reservations.json            # 已訂清單（狀態檔）
├── health_check.py              # 驗證 THSR 頁面結構是否變更
├── docs/                        # 文件
└── thsr_ticket/
    ├── main.py                  # 進入點（--mode plan/buy/manage/auto）
    ├── configs/
    │   ├── config_schema.py     # Pydantic schema
    │   └── web/                 # HTML selectors、表單參數、站點對應
    ├── controller/
    │   ├── planner.py           # Phase 1
    │   ├── buyer.py             # Phase 2
    │   ├── manager.py           # Phase 3
    │   ├── search_train_flow.py # 搜尋班次（by train_id）
    │   ├── confirm_train_flow.py# 確認班次
    │   └── confirm_ticket_flow.py # 填入個資
    ├── model/
    │   └── db.py                # ParamDB、TicketRequest、Reservation
    ├── remote/
    │   ├── http_request.py      # curl-cffi HTTP 客戶端
    │   ├── captcha_solver.py    # CAPTCHA 解析
    │   └── notification.py      # Webhook 通知
    └── view_model/              # HTML 回應解析器
```

## 注意事項

- Pydantic v1（`pydantic<2.0`）— 升級前需完整 migration
- `ddddocr` 為 optional extra（`[ocr]`），Intel Mac 需固定 onnxruntime < 1.20.0
- THSR 頁面結構變更時，只需更新 `configs/web/` 中的 selectors
