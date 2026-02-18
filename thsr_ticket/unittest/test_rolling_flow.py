import pytest
from unittest.mock import MagicMock, mock_open, patch
from datetime import date, datetime, timedelta
import json

from thsr_ticket.model.db import ParamDB, TicketRequest, Reservation
from thsr_ticket.controller.planner import Planner
from thsr_ticket.controller.manager import Manager

# Mock data
MOCK_CONFIG = {
    "tickets": [
        {
            "name": "TestTrip",
            "start_station": "Taipei",
            "dest_station": "Taichung",
            "schedule": {"type": "specific", "value": "2026-02-06"},
            "time_preference": "12:00"
        }
    ]
}

@pytest.fixture
def mock_db():
    db = MagicMock(spec=ParamDB)
    db.get_reservations.return_value = []
    db.get_ticket_requests.return_value = []
    return db

class TestParamDB:
    def test_ticket_request_model(self):
        req = TicketRequest(
            id="test_id",
            config={"foo": "bar"},
            date="2024-01-01"
        )
        assert req.id == "test_id"
        assert req.date == "2024-01-01"

    def test_reservation_model(self):
        req = TicketRequest(id="r1", config={}, date="2024-01-01")
        res = Reservation(
            pnr="12345",
            payment_deadline="2024/01/02",
            request=req
        )
        assert res.pnr == "12345"
        assert res.request.id == "r1"

class TestPlanner:
    def test_generate_specific_date_request(self, mock_db):
        planner = Planner(MOCK_CONFIG, mock_db)

        # Test: Should generate 1 request for specific date
        with patch("thsr_ticket.controller.planner.date") as mock_date:
            mock_date.today.return_value = date(2026, 1, 1)

            # Since _generate_desired_requests is internal, we check side effects of run()
            # or we can test the internal method if we prefer white-box testing.
            # Let's test run() and verify db.save_ticket_requests is called.

            planner.run()

            mock_db.save_ticket_requests.assert_called_once()
            args = mock_db.save_ticket_requests.call_args[0][0] # List[TicketRequest]
            assert len(args) == 1
            assert args[0].date == "2026-02-06"
            assert args[0].id == "TestTrip_2026-02-06"

    def test_recurring_request(self, mock_db):
        recurring_config = {
            "tickets": [{
                "name": "DailyCommute",
                "schedule": {"type": "recurring", "value": "Friday"},
                "time_preference": "10:00"
            }]
        }
        planner = Planner(recurring_config, mock_db)

        with patch("thsr_ticket.controller.planner.date") as mock_date:
            # Mock today as Monday 2024-01-01
            # Next Friday is 2024-01-05, then 2024-01-12, 19, 26 (within 28 days)
            mock_date.today.return_value = date(2024, 1, 1)
            mock_date.side_effect = date # Allow other date methods to work if needed

            requests = planner._generate_desired_requests()

            assert len(requests) >= 4
            assert requests[0].date == "2024-01-05" # First Friday

    def test_avoid_duplicates(self, mock_db):
        # Setup: DB already has this request
        existing_req = TicketRequest(id="TestTrip_2026-02-06", config={}, date="2026-02-06")
        mock_db.get_ticket_requests.return_value = [existing_req]

        planner = Planner(MOCK_CONFIG, mock_db)

        with patch("thsr_ticket.controller.planner.date") as mock_date:
            mock_date.today.return_value = date(2026, 1, 1)
            planner.run()

            # Should NOT save again because no new requests
            mock_db.save_ticket_requests.assert_not_called()

class TestManager:
    def test_soft_cancellation(self, mock_db):
        # Setup: One expired reservation
        req = TicketRequest(id="r1", config={}, date="2024-01-01")
        expired_res = Reservation(
            pnr="EXP123",
            payment_deadline="2024/01/01", # Expired relative to now+1day
            request=req
        )
        mock_db.get_reservations.return_value = [expired_res]
        mock_db.get_ticket_requests.return_value = []

        manager = Manager(mock_db)

        # Mock datetime.now() to be 2024/01/02 (deadline passed)
        with patch("thsr_ticket.controller.manager.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 2)
            # Need strptime to work too
            mock_datetime.strptime.side_effect = datetime.strptime

            manager.run()

            # Expectation:
            # 1. save_reservations called with EMPTY list (removed)
            mock_db.save_reservations.assert_called_with([])

            # 2. save_ticket_requests called with [req] (re-queued)
            mock_db.save_ticket_requests.assert_called()
            saved_requests = mock_db.save_ticket_requests.call_args[0][0]
            assert len(saved_requests) == 1
            assert saved_requests[0].id == "r1"
