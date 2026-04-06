import logging
from datetime import date, datetime
from typing import List, Dict, Any

from thsr_ticket.model.db import ParamDB, TicketRequest, Reservation

logger = logging.getLogger(__name__)


class Planner:
    def __init__(self, config: Dict[str, Any], db: ParamDB):
        self.config = config
        self.db = db

    def run(self) -> None:
        today = date.today()
        existing_reservations = self.db.get_reservations()
        current_tobuy = self.db.get_ticket_requests()

        # Remove expired requests from queue
        valid_queue = [r for r in current_tobuy if self._parse_date(r.date) >= today]
        if len(valid_queue) < len(current_tobuy):
            logger.info(f"Removed {len(current_tobuy) - len(valid_queue)} expired requests from queue.")
            self.db.save_ticket_requests(valid_queue)
            current_tobuy = valid_queue

        desired = self._generate_desired_requests(today)

        new_requests = [
            req for req in desired
            if not self._is_covered(req, existing_reservations)
            and not self._is_in_queue(req, current_tobuy)
        ]

        if new_requests:
            logger.info(f"Adding {len(new_requests)} new ticket requests to queue.")
            self.db.save_ticket_requests(current_tobuy + new_requests)
        else:
            logger.info("No new ticket requests needed.")

    def _generate_desired_requests(self, today: date) -> List[TicketRequest]:
        requests = []
        for ticket_conf in self.config.get('tickets', []):
            name = ticket_conf.get('name', '')
            for date_str in ticket_conf.get('dates', []):
                d = self._parse_date(date_str)
                if d is None or d < today:
                    continue
                req_config = {k: v for k, v in ticket_conf.items() if k != 'dates'}
                req_config['outbound_date'] = date_str
                requests.append(TicketRequest(
                    id=f"{name}_{d.isoformat()}",
                    config=req_config,
                    date=date_str,
                ))
        return requests

    def _parse_date(self, date_str: str):
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            logger.warning(f"Invalid date format: {date_str}")
            return None

    def _is_covered(self, req: TicketRequest, reservations: List[Reservation]) -> bool:
        return any(r.request.id == req.id for r in reservations)

    def _is_in_queue(self, req: TicketRequest, queue: List[TicketRequest]) -> bool:
        return any(item.id == req.id for item in queue)
