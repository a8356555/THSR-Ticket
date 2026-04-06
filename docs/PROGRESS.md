# THSR-Ticket Progress

> Last updated: 2026-04-04

## Completed

- [x] Three-phase booking system (Plan / Buy / Manage)
- [x] CAPTCHA solving: Gemini Vision API, ddddocr OCR, Hybrid
- [x] GitHub Actions CI (`booking.yml` — 08:00 UTC+8)
- [x] Pydantic config validation
- [x] JSON-based state persistence (tobuy.json, reservations.json)
- [x] onnxruntime version constraint for Intel Mac
- [x] Suppress FutureWarnings and Gemini deprecation warnings
- [x] Fix `daily-booking.yml`: `main.py` (interactive) → `--mode auto` (non-interactive)
- [x] Update `daily-booking.yml` schedule: 06:00 → 02:00 UTC+8

## In Progress

- [ ] Update User-Agent string (Chrome/42 → Chrome/131) — changed but unverified; THSR Akamai CDN may require more than header changes for local access
- [ ] Investigate THSR bot detection — curl/requests both timeout locally; TLS fingerprinting or JS challenge suspected

## Backlog

- [ ] 車次查詢 (train schedule query) — from TODO.md
- [ ] `daily-booking.yml` missing: health check step, commit-and-push state step, env vars via `env:` (see `booking.yml` for reference)
- [ ] Consolidate or remove duplicate workflows (`daily-booking.yml` vs `booking.yml`)

## Notes

- THSR website (`irs.thsrc.com.tw`) is behind Akamai CDN; local access via curl/requests may be blocked by bot detection
- GitHub Actions can reach THSR (confirmed from CI logs)
- Branch: `feature/auto-booking-gemini`
