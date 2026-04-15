"""
Hourly booking scheduler — runs at :02, :17, :32 each hour.
Stops automatically when all candidate trains from config.yaml are reserved.

Usage:
    uv run python hourly_booking.py
    nohup uv run python hourly_booking.py &
"""

import json
import logging
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Set

import yaml

RUN_MINUTES = [2, 17, 32]
PROJECT_ROOT = Path(__file__).parent
RESERVATIONS_PATH = PROJECT_ROOT / "reservations.json"
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

_shutdown = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            PROJECT_ROOT / "hourly_booking.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("hourly_booking")


def _handle_signal(signum, _frame):
    global _shutdown
    logger.info("Received signal %d, shutting down gracefully...", signum)
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def load_ticket_config() -> list:
    """Load ticket configs from config.yaml."""
    if not CONFIG_PATH.exists():
        return []
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        return data.get("tickets", [])
    except yaml.YAMLError:
        return []


def get_target_trains() -> Set[str]:
    """Derive target trains from config.yaml candidates."""
    targets = set()
    for ticket in load_ticket_config():
        for c in ticket.get("candidates", []):
            targets.add(str(c))
    return targets


def log_ticket_info() -> None:
    """Log target ticket details from config."""
    for t in load_ticket_config():
        candidates = ", ".join(t.get("candidates", []))
        amounts = t.get("ticket_amount", {})
        amount_parts = [f"{k}={v}" for k, v in amounts.items() if v]
        logger.info(
            "  [%s] %s -> %s | %s | candidates: %s | %s | %s",
            t.get("name", "?"),
            t.get("start_station"),
            t.get("dest_station"),
            ", ".join(t.get("dates", [])),
            candidates,
            ", ".join(amount_parts),
            t.get("car_class", ""),
        )


def get_booked_trains() -> Set[str]:
    """Return set of train_ids currently in reservations.json."""
    if not RESERVATIONS_PATH.exists():
        return set()
    try:
        data = json.loads(RESERVATIONS_PATH.read_text(encoding="utf-8"))
        return {r["train_id"] for r in data if r.get("train_id")}
    except (json.JSONDecodeError, KeyError):
        return set()


def check_targets(target_trains: Set[str]) -> bool:
    """Return True if all target trains are booked."""
    booked = get_booked_trains()
    missing = target_trains - booked
    done = target_trains & booked

    if done:
        logger.info("Booked:  %s", ", ".join(sorted(done)))
    if missing:
        logger.info("Missing: %s", ", ".join(sorted(missing)))

    return len(missing) == 0


def next_run_time(now: datetime) -> datetime:
    """Calculate the next :02, :17, or :32 slot."""
    for m in RUN_MINUTES:
        candidate = now.replace(minute=m, second=0, microsecond=0)
        if candidate > now:
            return candidate
    next_hour = (now + timedelta(hours=1)).replace(
        minute=RUN_MINUTES[0], second=0, microsecond=0
    )
    return next_hour


def run_booking() -> None:
    """Execute the booking bot via subprocess."""
    logger.info("--- Starting booking run ---")
    result = subprocess.run(
        [sys.executable, "-m", "thsr_ticket.main", "--mode", "auto"],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        logger.warning("Booking exited with code %d", result.returncode)
    else:
        logger.info("Booking run completed successfully")


def main() -> None:
    target_trains = get_target_trains()
    if not target_trains:
        logger.error("No candidate trains found in config.yaml. Exiting.")
        return

    logger.info("=" * 50)
    logger.info("Hourly booking scheduler started")
    logger.info("Target trains: %s (from config.yaml)", ", ".join(sorted(target_trains)))
    logger.info("Schedule: every hour at :%02d, :%02d, :%02d", *RUN_MINUTES)
    logger.info("-" * 50)
    log_ticket_info()
    logger.info("=" * 50)

    if check_targets(target_trains):
        logger.info("All target trains already booked. Exiting.")
        return

    # Run immediately on startup
    run_booking()
    if check_targets(target_trains):
        logger.info("All target trains booked! Scheduler complete.")
        return

    while not _shutdown:
        now = datetime.now()
        target = next_run_time(now)
        wait_seconds = (target - now).total_seconds()

        logger.info("Next run at %s (in %.0fs)", target.strftime("%H:%M:%S"), wait_seconds)

        try:
            time.sleep(wait_seconds)
        except (OSError, InterruptedError):
            if _shutdown:
                break
            continue

        if _shutdown:
            break

        try:
            run_booking()
        except Exception:
            logger.exception("Booking run failed unexpectedly")
            continue

        try:
            if check_targets(target_trains):
                logger.info("All target trains booked! Scheduler complete.")
                return
        except Exception:
            logger.exception("Failed to check targets, continuing...")

    logger.info("Scheduler shut down.")


if __name__ == "__main__":
    main()
