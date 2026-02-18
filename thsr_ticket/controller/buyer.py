import logging
from typing import List, Tuple
from requests import Response

from thsr_ticket.model.db import ParamDB, TicketRequest, Reservation, Record
from thsr_ticket.remote.http_request import HTTPRequest
from thsr_ticket.remote.notification import Notification
from thsr_ticket.controller.search_train_flow import SearchTrainFlow
from thsr_ticket.controller.confirm_train_flow import ConfirmTrainFlow
from thsr_ticket.controller.confirm_ticket_flow import ConfirmTicketFlow
from thsr_ticket.view_model.booking_result import BookingResult
from thsr_ticket.view_model.error_feedback import ErrorFeedback

logger = logging.getLogger(__name__)

class Buyer:
    def __init__(self, db: ParamDB, config: dict = None):
        self.db = db
        self.config = config or {}
        self.client = HTTPRequest()
        self.record = Record()
        self.error_feedback = ErrorFeedback()
        self.notification = Notification(self.config)

    def run(self) -> None:
        """
        Process ticket requests in the queue.
        """
        queue = self.db.get_ticket_requests()
        if not queue:
            logger.info("No tickets in queue to buy.")
            return

        logger.info(f"Processing {len(queue)} ticket requests.")

        remaining_queue = []
        new_reservations = []

        # Load existing reservations to update list later?
        # Actually simplest is just append new ones.
        # But for atomic save, we should load current state at end or beginning.
        # Let's load at the end to minimize race conditions if we were parallel,
        # but here we are sequential.

        for req in queue:
            try:
                success, reservation = self._process_request(req)
                if success:
                    self.notification.send(f"Successfully booked ticket: {req.id} (PNR: {reservation.pnr})")
                    new_reservations.append(reservation)
                else:
                    self.notification.send(f"Failed to book ticket: {req.id}. Keeping in queue.", level="ERROR")
                    remaining_queue.append(req)
            except Exception as e:
                logger.error(f"Error processing request {req.id}: {e}")
                remaining_queue.append(req)

        # Update States
        if new_reservations:
            current_reservations = self.db.get_reservations()
            self.db.save_reservations(current_reservations + new_reservations)

        self.db.save_ticket_requests(remaining_queue)

    def _process_request(self, req: TicketRequest) -> Tuple[bool, Reservation]:
        logger.info(f"Attempting to book: {req.id} for {req.date}")

        # 1. Search Train
        captcha_config = self.config.get("captcha", {})

        try:
            book_resp, book_model = SearchTrainFlow(
                client=self.client,
                record=self.record,
                ticket_config=req.config,
                captcha_config=captcha_config
            ).run()

            if self._has_error(book_resp):
                return False, None

            # 2. Confirm Train
            train_resp, train_model = ConfirmTrainFlow(
                self.client,
                book_resp,
                config=req.config
            ).run()

            if self._has_error(train_resp):
                return False, None

            # 3. Confirm Ticket
            ticket_resp, ticket_model = ConfirmTicketFlow(self.client, train_resp, self.record).run()

            if self._has_error(ticket_resp):
                return False, None

            # 4. Parse Result
            results = BookingResult().parse(ticket_resp.content)
            if not results:
                logger.error("BookingResult returned empty list.")
                return False, None
            result_model = results[0]

            # Create Reservation
            reservation = Reservation(
                pnr=result_model.id,
                payment_deadline=result_model.payment_deadline,
                request=req,
                train_id=train_model.selected_train,
                seat_str="" # TODO: Extract seat info if available
            )
            return True, reservation

        except Exception as e:
            logger.error(f"Flow Exception: {e}")
            return False, None

    def _has_error(self, resp: Response) -> bool:
        if resp.status_code >= 400:
            logger.warning(f"HTTP Error: status {resp.status_code}")
            return True
        errors = self.error_feedback.parse(resp.content)
        if errors:
            err_msg = ", ".join([e.msg for e in errors])
            logger.warning(f"Booking Error: {err_msg}")
            return True
        return False
