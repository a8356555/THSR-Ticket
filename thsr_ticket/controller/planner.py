from datetime import date, timedelta, datetime
from typing import List, Dict, Any
import logging

from thsr_ticket.model.db import ParamDB, TicketRequest, Reservation

logger = logging.getLogger(__name__)

class Planner:
    def __init__(self, config: Dict[str, Any], db: ParamDB):
        self.config = config
        self.db = db

    def run(self) -> None:
        """
        1. Parse config to find desired tickets for the next 28 days.
        2. Filter out tickets that are already reserved.
        3. Filter out tickets that are already in tobuy list.
        4. Add remaining to tobuy list.
        """
        desired_requests = self._generate_desired_requests()
        existing_reservations = self.db.get_reservations()
        current_tobuy = self.db.get_ticket_requests()

        new_requests = []
        for req in desired_requests:
            if self._is_covered(req, existing_reservations):
                continue
            if self._is_in_queue(req, current_tobuy):
                continue
            new_requests.append(req)

        if new_requests:
            logger.info(f"Adding {len(new_requests)} new ticket requests to queue.")
            # Append to existing queue
            updated_queue = current_tobuy + new_requests
            self.db.save_ticket_requests(updated_queue)
        else:
            logger.info("No new ticket requests needed.")

    def _generate_desired_requests(self) -> List[TicketRequest]:
        requests = []
        tickets_config = self.config.get('tickets', [])

        # Look ahead 28 days
        today = date.today()
        date_range = [today + timedelta(days=i) for i in range(29)] # 0 to 28

        for ticket_conf in tickets_config:
            schedule = ticket_conf.get('schedule', {})
            sch_type = schedule.get('type')
            sch_val = schedule.get('value') # specific date or weekday name

            target_dates = []

            if sch_type == 'specific':
                # format YYYY-MM-DD
                try:
                    d = datetime.strptime(str(sch_val), "%Y-%m-%d").date()
                    if d >= today:
                        target_dates.append(d)
                except ValueError:
                    logger.warning(f"Invalid date format in config: {sch_val}")

            elif sch_type == 'recurring':
                # Value matches weekday? e.g. "Friday"
                # 0=Monday, 6=Sunday
                weekdays = {
                    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                    'friday': 4, 'saturday': 5, 'sunday': 6
                }
                desired_wd = weekdays.get(str(sch_val).lower())
                if desired_wd is not None:
                    for d in date_range:
                        if d.weekday() == desired_wd:
                            target_dates.append(d)

            for d in target_dates:
                # Create a request
                # We generate a deterministic ID based on config + date to avoid dupes logic
                req_id = f"{ticket_conf.get('name')}_{d.isoformat()}"

                # Clone config and inject the specific date for this request
                # This ensures the Buyer knows exactly which date to book
                req_config = ticket_conf.copy()
                req_config['outbound_date'] = d.strftime("%Y-%m-%d") # Inject for SearchTrainFlow

                # IMPORTANT: Remove 'schedule' so SearchTrainFlow doesn't recalculate/overwrite the date
                if 'schedule' in req_config:
                    del req_config['schedule']

                requests.append(TicketRequest(
                    id=req_id,
                    config=req_config,
                    date=d.strftime("%Y-%m-%d")
                ))

        return requests

    def _is_covered(self, req: TicketRequest, reservations: List[Reservation]) -> bool:
        # Check if there is a reservation corresponding to this request
        # Assumption: Reservation stores the original request or enough info to match
        for const in reservations:
            # Flexible matching: by ID if available, or by content
            if const.request.id == req.id:
                return True
        return False

    def _is_in_queue(self, req: TicketRequest, queue: List[TicketRequest]) -> bool:
        for item in queue:
            if item.id == req.id:
                return True
        return False
