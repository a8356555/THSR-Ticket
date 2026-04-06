# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

THSR-Ticket is a Taiwan High Speed Railway automated ticket booking bot. It uses a three-phase rolling reservation strategy (Plan → Buy → Manage) to maintain seat reservations by automatically rebooking before payment deadlines expire. Runs daily via GitHub Actions at 02:00 UTC+8.

## Commands

```bash
# Install dependencies
uv sync --dev

# Run tests
uv run python -m pytest thsr_ticket/unittest/test_rolling_flow.py -v

# Run the bot
uv run python -m thsr_ticket.main --mode auto    # all 3 phases
uv run python -m thsr_ticket.main --mode plan    # generate queue only
uv run python -m thsr_ticket.main --mode buy     # process queue only
uv run python -m thsr_ticket.main --mode manage  # manage expiring only

# Verify THSR website structure hasn't changed
uv run python health_check.py

# Linting
uv run ruff check thsr_ticket/ --select E,W --ignore E501,E402,E731,E741
```

## Architecture

### Three-Phase Controller System

1. **Planner** (`controller/planner.py`) — Reads `config.yaml`, generates ticket requests for configured dates, writes missing ones to `tobuy.json`. Auto-removes expired dates from queue.
2. **Buyer** (`controller/buyer.py`) — Processes `tobuy.json` queue. For each request, tries candidates in priority order (by train ID search). If a fallback candidate is used, re-queues higher-priority candidates for next run.
3. **Manager** (`controller/manager.py`) — Checks payment deadlines in `reservations.json`, re-queues expiring tickets back to `tobuy.json` for rebooking.

### Booking Flow Chain

`SearchTrainFlow` → `ConfirmTrainFlow` → `ConfirmTicketFlow` → `BookingResult`

Each step submits an HTML form to THSR and parses the response. No browser automation — direct HTTP via `curl-cffi` (impersonates Chrome TLS fingerprint to bypass Akamai bot detection) + `BeautifulSoup`.

### Key Components

- **`model/db.py` (ParamDB)** — JSON file-based state persistence (`tobuy.json`, `reservations.json`)
- **`remote/http_request.py`** — HTTP client using `curl-cffi` with `impersonate="chrome131"`
- **`remote/captcha_solver.py`** — CAPTCHA solving: Gemini Vision API, ddddocr OCR, or Hybrid (OCR first, Gemini fallback)
- **`configs/config_schema.py`** — Pydantic v1 validation for `config.yaml`
- **`configs/web/`** — HTML selectors, form parameter schemas, station/enum mappings
- **`view_model/`** — HTML response parsers for each booking step

### Configuration

**`config.yaml`** — Booking preferences:
```yaml
tickets:
  - name: "Friday Home"
    start_station: "Taipei"
    dest_station: "Taichung"
    dates:
      - "2026-04-17"         # specific dates to book
    candidates:
      - "149"                # train IDs in priority order
      - "1245"
    ticket_amount:
      adult: 1
    car_class: "standard"
    trip_type: "one-way"
    seat_preference: "none"
```

**`.env`** — Secrets: `GEMINI_API_KEY`, `personal_identification`, `phone_number`, `email`

### CI/CD

- **`booking.yml`** — Runs daily at 02:00 UTC+8 (`0 18 * * *` UTC), executes `--mode auto`, commits updated state files (`tobuy.json`, `reservations.json`) back to repo.

## Important Notes

- Uses Pydantic v1 (`pydantic<2.0`) — do not upgrade without migration
- `ddddocr` OCR is optional (`[ocr]` extra), pinned to 1.4.11 with onnxruntime constraints for Intel Mac
- State files (`tobuy.json`, `reservations.json`) are committed to the repo — no database
- THSR website HTML changes can break selectors; configs in `configs/web/` isolate these
- THSR's booking page is behind Akamai CDN — `curl-cffi` is required to bypass TLS fingerprinting; `requests` will timeout
