import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from typing import NamedTuple

from thsr_ticket import MODULE_PATH

class Record(NamedTuple):
    personal_id: str = None
    phone: str = None
    start_station: int = None
    dest_station: int = None
    outbound_time: str = None
    adult_num: str = None


@dataclass
class TicketRequest:
    """
    Represents a request to buy a ticket.
    Stored in tobuy.json.

    Attributes:
        id (str): Unique identifier for this request (e.g., "TripName_2023-01-01").
        config (Dict[str, Any]): The configuration dictionary used by SearchTrainFlow (from config.yaml).
        date (str): The specific target date (YYYY-MM-DD) for this single request.
        created_at (str): ISO timestamp of creation.
    """
    # Unique identifier for the request, useful for deduction
    id: str

    # The dictionary required by SearchTrainFlow (config.yaml structure)
    # expected keys: start_station, dest_station, outbound_time, ticket_num, etc.
    config: Dict[str, Any]

    # Specific target date for this request (YYYY-MM-DD or YYYY/MM/DD)
    date: str

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Reservation:
    """
    Represents a successful reservation.
    Stored in reservations.json
    """
    # The booking ID (PNR) returned by THSR
    pnr: str

    # When this reservation must be paid by
    payment_deadline: str

    # The original request logic
    request: TicketRequest

    # Additional info
    train_id: Optional[str] = None
    seat_str: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ParamDB:
    def __init__(self, db_root: str = None):
        if db_root is None:
            # Default to project root (parent of thsr_ticket module)
            # MODULE_PATH is .../thsr_ticket
            # We want .../reservations.json
            self.db_root = os.path.dirname(MODULE_PATH.rstrip('/'))
        else:
            self.db_root = db_root

        self.tobuy_path = os.path.join(self.db_root, "tobuy.json")
        self.reservations_path = os.path.join(self.db_root, "reservations.json")

    def _load_json(self, path: str) -> List[Dict]:
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save_json(self, path: str, data: List[Dict]):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving to {path}: {e}")

    def get_ticket_requests(self) -> List[TicketRequest]:
        data = self._load_json(self.tobuy_path)
        requests = []
        for item in data:
            try:
                requests.append(TicketRequest(**item))
            except TypeError:
                print(f"Skipping invalid ticket request item: {item}")
        return requests

    def save_ticket_requests(self, requests: List[TicketRequest]):
        data = [asdict(req) for req in requests]
        self._save_json(self.tobuy_path, data)

    def get_reservations(self) -> List[Reservation]:
        data = self._load_json(self.reservations_path)
        reservations = []
        for item in data:
            try:
                # Handle nested TicketRequest
                if 'request' in item and isinstance(item['request'], dict):
                    item['request'] = TicketRequest(**item['request'])
                reservations.append(Reservation(**item))
            except TypeError:
                print(f"Skipping invalid reservation item: {item}")
        return reservations

    def save_reservations(self, reservations: List[Reservation]):
        data = [asdict(res) for res in reservations]
        self._save_json(self.reservations_path, data)
