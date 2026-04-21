import logging
import time
from typing import List, Tuple, Optional
from curl_cffi.requests import Response

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
        queue = self.db.get_ticket_requests()
        if not queue:
            logger.info("No tickets in queue to buy.")
            return

        logger.info(f"Processing {len(queue)} ticket requests.")

        remaining_queue = []
        requeue_list = []
        new_reservations = []

        for req in queue:
            booked, reservation, used_index = self._process_request(req)
            if booked:
                self.notification.send(
                    f"Successfully booked ticket: {req.id} (PNR: {reservation.pnr})"
                )
                new_reservations.append(reservation)
                # Re-queue to keep chasing higher-priority candidates
                if used_index > 0:
                    higher_candidates = req.config.get('candidates', [])[:used_index]
                    retry_req = TicketRequest(
                        id=f"{req.id}_retry",
                        config={**req.config, 'candidates': higher_candidates},
                        date=req.date,
                    )
                    logger.info(
                        f"Fallback used (candidate index {used_index}). "
                        f"Re-queuing to chase: {higher_candidates}"
                    )
                    requeue_list.append(retry_req)
            else:
                self.notification.send(
                    f"Failed to book ticket: {req.id}. Keeping in queue.", level="ERROR"
                )
                remaining_queue.append(req)

        if new_reservations:
            current_reservations = self.db.get_reservations()
            self.db.save_reservations(current_reservations + new_reservations)

        self.db.save_ticket_requests(remaining_queue + requeue_list)

    def _process_request(self, req: TicketRequest) -> Tuple[bool, Optional[Reservation], int]:
        """Try each candidate in order. Returns (success, reservation, candidate_index_used)."""
        candidates = req.config.get('candidates', [])
        captcha_config = self.config.get("captcha", {})

        for i, candidate in enumerate(candidates):
            if i > 0:
                delay = 10
                logger.info(f"Waiting {delay}s before next candidate to avoid rate limit...")
                time.sleep(delay)

            logger.info(f"Attempting to book: {req.id} for {req.date} (candidate {candidate})")
            try:
                # Fresh session per candidate to reduce Akamai fingerprint correlation
                client = HTTPRequest()
                ticket_config = {**req.config, 'current_candidate': candidate}
                book_resp, book_model = SearchTrainFlow(
                    client=client,
                    record=self.record,
                    ticket_config=ticket_config,
                    captcha_config=captcha_config,
                ).run()

                if self._has_error(book_resp):
                    logger.info(f"Candidate {candidate} not available.")
                    continue

                train_resp, train_model = ConfirmTrainFlow(
                    client, book_resp, config=req.config
                ).run()

                if self._has_error(train_resp):
                    continue

                ticket_resp, _ = ConfirmTicketFlow(
                    client, train_resp, self.record
                ).run()

                if self._has_error(ticket_resp):
                    continue

                results = BookingResult().parse(ticket_resp.content)
                if not results:
                    logger.error("BookingResult returned empty list.")
                    continue

                result_model = results[0]
                reservation = Reservation(
                    pnr=result_model.id,
                    payment_deadline=result_model.payment_deadline,
                    request=req,
                    train_id=result_model.train_id,
                    seat_str=result_model.seat,
                )
                return True, reservation, i

            except Exception as e:
                logger.error(f"Flow Exception (candidate {candidate}): {e}")
                continue

        return False, None, -1

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
