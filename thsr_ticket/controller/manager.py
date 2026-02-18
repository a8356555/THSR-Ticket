import logging
from datetime import datetime
from typing import List

from thsr_ticket.model.db import ParamDB, Reservation, TicketRequest
from thsr_ticket.remote.notification import Notification

logger = logging.getLogger(__name__)

class Manager:
    def __init__(self, db: ParamDB, config: dict = None):
        self.db = db
        self.config = config or {}
        self.notification = Notification(self.config)

    def run(self) -> None:
        """
        Check reservations for expiration.
        If expiring:
            1. (TODO) Cancel ticket via API.
            2. Remove from reservations.
            3. Add back to tobuy queue (Rolling).
        """
        reservations = self.db.get_reservations()
        if not reservations:
            logger.info("No reservations to manage.")
            return

        active_reservations = []
        expired_reservations = []
        requeue_requests = []

        now = datetime.now()

        for res in reservations:
            if self._is_expiring(res.payment_deadline, now):
                msg = f"Reservation {res.pnr} is expiring (Deadline: {res.payment_deadline}). Rolling over."
                self.notification.send(msg, level="ERROR")

                # SOFT CANCELLATION: We do NOT call API cancel.
                # We just "forget" it from our list and re-queue.
                # This leaves the ticket active on THSR until it expires naturally or user cancels.
                # This is safer for bot account initially.

                expired_reservations.append(res)
                requeue_requests.append(res.request)
            else:
                active_reservations.append(res)

        if expired_reservations:
            # Update DB
            self.db.save_reservations(active_reservations)

            # Add to tobuy
            current_tobuy = self.db.get_ticket_requests()
            # Avoid duplicates if already there (edge case)
            current_ids = {r.id for r in current_tobuy}
            for req in requeue_requests:
                if req.id not in current_ids:
                    current_tobuy.append(req)

            self.db.save_ticket_requests(current_tobuy)
            logger.info(f"Rolled over {len(expired_reservations)} tickets.")
        else:
            logger.info("All reservations are good.")

    def _is_expiring(self, deadline_str: str, now: datetime) -> bool:
        """
        Check if deadline is within 24 hours (or passed).
        Deadline format from BookingResult: "2024/01/01" usually, sometimes with time?
        THSR usually gives a date.
        """
        try:
            # Assuming YYYY/MM/DD
            deadline = datetime.strptime(deadline_str, "%Y/%m/%d")
            # If (deadline - now) < 1 day
            delta = deadline - now
            return delta.days < 1
        except ValueError:
            logger.warning(f"Could not parse payment deadline: {deadline_str}")
            return False
