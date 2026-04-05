import pytest
from unittest.mock import MagicMock, patch
from datetime import date, datetime

from thsr_ticket.model.db import ParamDB, TicketRequest, Reservation
from thsr_ticket.controller.planner import Planner
from thsr_ticket.controller.manager import Manager

MOCK_CONFIG = {
    "tickets": [
        {
            "name": "TestTrip",
            "start_station": "Taipei",
            "dest_station": "Taichung",
            "dates": ["2026-06-06"],
            "candidates": ["149", "1245"],
            "ticket_amount": {"adult": 1},
            "car_class": "standard",
            "trip_type": "one-way",
            "seat_preference": "none",
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
        req = TicketRequest(id="test_id", config={"foo": "bar"}, date="2024-01-01")
        assert req.id == "test_id"
        assert req.date == "2024-01-01"

    def test_reservation_model(self):
        req = TicketRequest(id="r1", config={}, date="2024-01-01")
        res = Reservation(pnr="12345", payment_deadline="2024/01/02", request=req)
        assert res.pnr == "12345"
        assert res.request.id == "r1"


class TestPlanner:
    def test_generate_date_request(self, mock_db):
        planner = Planner(MOCK_CONFIG, mock_db)
        with patch("thsr_ticket.controller.planner.date") as mock_date:
            mock_date.today.return_value = date(2026, 1, 1)
            planner.run()
            mock_db.save_ticket_requests.assert_called_once()
            args = mock_db.save_ticket_requests.call_args[0][0]
            assert len(args) == 1
            assert args[0].date == "2026-06-06"
            assert args[0].id == "TestTrip_2026-06-06"
            assert args[0].config['candidates'] == ["149", "1245"]

    def test_skip_past_dates(self, mock_db):
        config = {"tickets": [{
            "name": "OldTrip",
            "start_station": "Taipei", "dest_station": "Taichung",
            "dates": ["2020-01-01"], "candidates": ["149"],
            "ticket_amount": {"adult": 1},
            "car_class": "standard", "trip_type": "one-way", "seat_preference": "none",
        }]}
        planner = Planner(config, mock_db)
        with patch("thsr_ticket.controller.planner.date") as mock_date:
            mock_date.today.return_value = date(2026, 1, 1)
            planner.run()
            mock_db.save_ticket_requests.assert_not_called()

    def test_remove_expired_queue_entries(self, mock_db):
        expired_req = TicketRequest(id="OldTrip_2020-01-01", config={}, date="2020-01-01")
        mock_db.get_ticket_requests.return_value = [expired_req]

        planner = Planner(MOCK_CONFIG, mock_db)
        with patch("thsr_ticket.controller.planner.date") as mock_date:
            mock_date.today.return_value = date(2026, 1, 1)
            planner.run()
            # save_ticket_requests should be called to clean up expired + add new
            calls = mock_db.save_ticket_requests.call_args_list
            assert len(calls) >= 1
            # First call should remove the expired entry
            first_call_args = calls[0][0][0]
            assert not any(r.id == "OldTrip_2020-01-01" for r in first_call_args)

    def test_avoid_duplicates(self, mock_db):
        existing_req = TicketRequest(id="TestTrip_2026-06-06", config={}, date="2026-06-06")
        mock_db.get_ticket_requests.return_value = [existing_req]
        planner = Planner(MOCK_CONFIG, mock_db)
        with patch("thsr_ticket.controller.planner.date") as mock_date:
            mock_date.today.return_value = date(2026, 1, 1)
            planner.run()
            # save_ticket_requests should NOT be called with new items (no new requests)
            calls = mock_db.save_ticket_requests.call_args_list
            # If called, it's only for cleanup (no new items)
            for call in calls:
                saved = call[0][0]
                new_items = [r for r in saved if r.id == "TestTrip_2026-06-06" and r is not existing_req]
                assert len(new_items) == 0


class TestManager:
    def test_soft_cancellation(self, mock_db):
        req = TicketRequest(id="r1", config={}, date="2024-01-01")
        expired_res = Reservation(
            pnr="EXP123", payment_deadline="2024/01/01", request=req
        )
        mock_db.get_reservations.return_value = [expired_res]
        mock_db.get_ticket_requests.return_value = []

        manager = Manager(mock_db)
        with patch("thsr_ticket.controller.manager.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 2)
            mock_datetime.strptime.side_effect = datetime.strptime
            manager.run()
            mock_db.save_reservations.assert_called_with([])
            saved_requests = mock_db.save_ticket_requests.call_args[0][0]
            assert len(saved_requests) == 1
            assert saved_requests[0].id == "r1"
