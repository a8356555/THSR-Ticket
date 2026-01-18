# Booking Parameter Reference

Based on inspecting the live THSR booking page, here are the valid values for [config.yaml](file:///Users/a8356555/Projects/THSR-Ticket/config.yaml).

## 1. Stations (`start_station`, `dest_station`)
You can use the station name directly.

| ID | Name |
|:---|:---|
| 1 | 南港 (Nangang) |
| 2 | 台北 (Taipei) |
| 3 | 板橋 (Banqiao) |
| 4 | 桃園 (Taoyuan) |
| 5 | 新竹 (Hsinchu) |
| 6 | 苗栗 (Miaoli) |
| 7 | 台中 (Taichung) |
| 8 | 彰化 (Changhua) |
| 9 | 雲林 (Yunlin) |
| 10 | 嘉義 (Chiayi) |
| 11 | 台南 (Tainan) |
| 12 | 左營 (Zuouing) |

## 2. Search Method ([search_by](file:///Users/a8356555/Projects/THSR-Ticket/thsr_ticket/controller/first_page_flow.py#217-225))
| Config Value | Internal ID | Description |
|:---|:---|:---|
| `time` | `radio31` | Search by Departure Time |
| `train_number` | `radio33` | Search by Train Number |

## 3. Trip Type ([types_of_trip](file:///Users/a8356555/Projects/THSR-Ticket/thsr_ticket/controller/first_page_flow.py#211-216))
| Config Value | Internal Value | Description |
|:---|:---|:---|
| `0` | `0` | One-way (單程) |
| `1` | `1` | Round-trip (去回程) |

## 4. Seat Preference ([seat_prefer](file:///Users/a8356555/Projects/THSR-Ticket/thsr_ticket/controller/first_page_flow.py#200-210))
| Config Value | Internal Value | Description |
|:---|:---|:---|
| `none` | `0` | No Preference (無座位偏好) |
| `window` | `1` | Window Priority (靠窗優先) |
| `aisle` | `2` | Aisle Priority (走道優先) |
*(Note: My initial guess of radio31/32/33 was incorrect. The code has been updated to use 0/1/2 directly.)*

## 5. Ticket Types (Number)
The system supports multiple passenger types. Configuration currently supports `adult_ticket_num`.

| Code | Type |
|:---|:---|
| `F` | Adult (成人) |
| `H` | Child (孩童) (6-11y) |
| `W` | Disabled (愛心) |
| `E` | Elder (敬老) (65+) |
| `P` | College (大學生) |
| `T` | Teenager (少年) (12-18y) |

## 6. Car Class (Business/Standard)
| Config Value | Internal Value | Description |
|:---|:---|:---|
| `standard` | `0` | Standard Car (標準車廂) |
| `business` | `1` | Business Car (商務車廂) |

## 7. Departure Time (Time Table)
Use these specific strings for `outbound_time` (or `inbound_time`):

| Time | Value | | Time | Value |
|:---|:---|:---|:---|:---|
| 00:00 | `1201A` | | 12:00 | `1200N` |
| 00:30 | `1230A` | | 12:30 | `1230P` |
| 05:00 | `500A` | | 13:00 | `100P` |
| 05:30 | `530A` | | 13:30 | `130P` |
| 06:00 | `600A` | | 14:00 | `200P` |
| 06:30 | `630A` | | 14:30 | `230P` |
| 07:00 | `700A` | | 15:00 | `300P` |
| 07:30 | `730A` | | 15:30 | `330P` |
| 08:00 | `800A` | | 16:00 | `400P` |
| 08:30 | `830A` | | 16:30 | `430P` |
| 09:00 | `900A` | | 17:00 | `500P` |
| 09:30 | `930A` | | 17:30 | `530P` |
| 10:00 | `1000A` | | 18:00 | `600P` |
| 10:30 | `1030A` | | 18:30 | `630P` |
| 11:00 | `1100A` | | 19:00 | `700P` |
| 11:30 | `1130A` | | 19:30 | `730P` |
| | | | 20:00 | `800P` |
| | | | ... | ... |

`