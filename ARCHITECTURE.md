
# 高鐵自動訂票機器人 - 架構設計文件 (THSR Ticket Booker - Architecture Design)

本文檔旨在記錄「高鐵自動訂票機器人」專案的設計思路、技術選型、核心流程與未來規劃。

## 1. 核心目標與策略

本專案的核心目標是實現一個能自動化預訂台灣高鐵車票的系統，以滿足使用者**在不確定行程時，仍希望長期佔有特定座位**的需求。

為此，我們採用**「滾動式預訂 (Rolling Reservation)」**策略：

1.  **長期佔位**：系統會自動預訂未來四周內，所有使用者指定的車票。
2.  **自動續命**：在車票付款期限到達前，系統會自動「取消舊票、並立即重訂新票」，以達到延長訂位紀錄、無需付款的目的。
3.  **失敗重試**：如果「續命」操作因座位被搶而失敗，該車票會被加入一個「待購清單」，系統會在此後每天持續嘗試為使用者重新購回，直到成功為止。

## 2. 技術選型 (Technology Stack)

-   **語言 (Language)**: **Python 3.x**
-   **網路請求 (Network Requests)**: **Requests** + **BeautifulSoup**
    -   **選用理由**: 相比瀏覽器自動化，直接使用 HTTP 請求模擬能大幅提升執行速度與效率，且資源消耗極低。配合 BeautifulSoup 解析 HTML，能準確提取所需資訊並進行訂票操作。
-   **排程與執行 (Scheduling & Execution)**: **GitHub Actions**
    -   透過 `on.schedule` 以 `cron` 形式每日定時執行。
    -   支援 `workflow_dispatch` 以便手動觸發。
-   **設定管理 (Configuration)**: `config.yaml`
    -   用於定義使用者需要預訂的行程（星期、時間、起訖站）、通知方式等。
-   **狀態管理 (State Management)**: `reservations.json` & `tobuy.json`
    -   `reservations.json`: 儲存當前已成功訂到、拿在手上的車票紀錄。
    -   `tobuy.json`: 儲存想要購買、或「續命」失敗後需要重新搶購的車票目標。
-   **安全 (Secrets Management)**:
    -   **正式環境**: GitHub Secrets (儲存高鐵帳密、Gmail 帳密等)。
    -   **本地開發**: `.env` 檔案 (配合 `.gitignore` 使用)。
-   **驗證碼處理 (CAPTCHA Handling)**:
    -   **首選方案 (待驗證)**: 調用 **Gemini Vision API** 進行識別。此方案的成本效益最高，但成功率待 `captcha_test.py` 腳本測試結果決定。
    -   **備用方案**: 若 Gemini 方案成功率不足，將採用第三方真人代打服務 (如 2Captcha)。

-   **開發環境與規範 (Development Environment & Standards)**:
    -   **套件管理 (Package Management)**: **uv**
        -   使用 `uv` 取代 pip/poetry 進行極速的依賴安裝與虛擬環境管理。
    -   **程式碼風格 (Code Style)**: **Black**
        -   強制統一的程式碼格式，減少 Code Review 時的風格爭議。
    -   **靜態分析 (Linter)**: **Ruff**
        -   取代 Flake8/Isort，提供極致效能的程式碼檢查與 import 排序。
    -   **測試框架 (Testing)**: **pytest**
        -   撰寫單元測試與整合測試，確保核心訂票邏輯的穩定性。

## 3. 系統工作流程

系統由一個每日執行的腳本構成，包含清晰的三個階段：

### 第一階段：規劃師 (The Planner / Reconciler)

-   **任務**: 確保未來四周內所有該買的票，都已在追蹤清單中。
-   **動作**:
    1.  **產生理想清單**: 根據 `config.yaml`，產生一份未來四周內所有目標車票的「理想清單」。
    2.  **核對現狀**: 讀取 `reservations.json` 和 `tobuy.json` 的內容。
    3.  **找出遺漏**: 如果「理想清單」中的某張票，既不存在於「已持有」列表，也不存在於「待購買」列表，則將其視為「遺漏的票」。
    4.  **加入待購**: 將所有「遺漏的票」加入 `tobuy.json`。
-   **特性**: 此階段的設計讓系統具備**自我修復**能力。

### 第二階段：採購員 (The Buyer)

-   **任務**: 努力清空「待購清單」。
-   **動作**:
    1.  遍歷 `tobuy.json` 中的每一張目標車票。
    2.  調用 HTTP Client (Requests) 模擬訂票流程。
    3.  **成功**: 將該車票從 `tobuy.json` **移至** `reservations.json`，並發送成功通知。
    4.  **失敗**: 將車票保留在 `tobuy.json` 中，待第二天重試。

### 第三階段：管理員 (The Manager / Roller)

-   **任務**: 確保已持有的車票不會因忘記付款而過期。
-   **動作**:
    1.  遍歷 `reservations.json` 中的每一張車票。
    2.  檢查其付款期限，若即將到期，則觸發「續命」操作。
    3.  執行「取消 -> 立即重訂」。
    4.  **成功**: 更新 `reservations.json` 中該車票的訂位代號與新的付款期限。
    5.  **失敗**: 將該車票從 `reservations.json` **移回** `tobuy.json`，並發送高優先級的「座位丟失，已轉為待購」警告通知。

## 4. 專案檔案結構

```
.
├── .github/
│   └── workflows/
│       └── booking.yml       # GitHub Actions workflow
├── .gitignore                # Git 忽略清單
├── ARCHITECTURE.md           # 本文件
├── config.yaml               # (Optional) 使用者行程設定檔
├── requirements.txt          # Python 套件依賴
├── reservations.json         # 【狀態】已持有的訂位紀錄
├── tobuy.json                # 【狀態】待購買的目標紀錄
└── thsr_ticket/              # 核心程式碼
    ├── configs/              # 網頁參數與設定
    ├── controller/           # 訂票流程控制
    ├── model/                # 資料模型 (資料庫存取)
    ├── remote/               # HTTP 請求封裝
    ├── view/                 # CLI 顯示介面
    └── main.py               # 程式進入點
```

## 5. 潛在風險與未來改進

-   **狀態管理**: JSON 檔案在意外中斷時可能損壞。未來可升級為 **SQLite** 資料庫，以利用其事務性確保資料完整。
-   **網頁結構變更**: 高鐵網站若改版 (如欄位名稱或 API 變更)，HTML 解析邏輯可能失效。應將關鍵的選擇器 (Selectors) 抽離至獨立設定檔 (`configs/`)，以便快速修復。
-   **驗證碼策略**: 整個專案的成敗高度依賴一個穩定可靠的驗證碼解決方案，這是目前最大的外部依賴與風險。

