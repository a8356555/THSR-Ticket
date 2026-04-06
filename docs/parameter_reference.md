# Config Parameter Reference

Valid values for `config.yaml`.

## Stations (`start_station`, `dest_station`)

| ID | Name |
|:---|:---|
| 1 | 南港 Nangang |
| 2 | 台北 Taipei |
| 3 | 板橋 Banqiao |
| 4 | 桃園 Taoyuan |
| 5 | 新竹 Hsinchu |
| 6 | 苗栗 Miaoli |
| 7 | 台中 Taichung |
| 8 | 彰化 Changhua |
| 9 | 雲林 Yunlin |
| 10 | 嘉義 Chiayi |
| 11 | 台南 Tainan |
| 12 | 左營 Zuouing |

## Trip Type (`trip_type`)

| Value | Description |
|:---|:---|
| `one-way` | 單程 |
| `round-trip` | 去回程 |

## Car Class (`car_class`)

| Value | Description |
|:---|:---|
| `standard` | 標準車廂 |
| `business` | 商務車廂 |

## Seat Preference (`seat_preference`)

| Value | Description |
|:---|:---|
| `none` | 無偏好 |
| `window` | 靠窗優先 |
| `aisle` | 走道優先 |

## Ticket Types (`ticket_amount`)

| Key | Type |
|:---|:---|
| `adult` | 成人 |
| `child` | 孩童（6-11歲） |
| `disabled` | 愛心 |
| `elder` | 敬老（65歲以上） |
| `college` | 大學生 |

## CAPTCHA Method (`captcha.method`)

| Value | Description |
|:---|:---|
| `GEMINI` | Gemini Vision API |
| `OCR` | 本地 ddddocr（需安裝 `[ocr]` extra） |
| `HYBRID` | OCR 優先，失敗則用 Gemini（推薦） |
