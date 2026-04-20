"""Tests for dynamic form discovery, skip-step2, and form action parsing."""
import pytest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup

from thsr_ticket.controller.search_train_flow import SearchTrainFlow
from thsr_ticket.controller.confirm_train_flow import ConfirmTrainFlow
from thsr_ticket.controller.confirm_ticket_flow import ConfirmTicketFlow


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

def _booking_page_html(time_value="radio31", train_id_value="radio33"):
    """Simulate THSR booking page with bookingMethod radios."""
    return f"""
    <html><body>
    <form id="BookingS1Form" action="/IMINT/;jsessionid=ABC?wicket:interface=:0:BookingS1Form::IFormSubmitListener">
      <label><input type="radio" name="bookingMethod" value="{time_value}" checked>時間</label>
      <label><input type="radio" name="bookingMethod" value="{train_id_value}">車次</label>
    </form>
    </body></html>
    """


def _step2_page_html(form_action=None):
    """Simulate THSR Step 2 (train selection) page."""
    action = form_action or "/IMINT/?wicket:interface=:1:BookingS2Form::IFormSubmitListener"
    return f"""
    <html><body>
    <form id="BookingS2Form" action="{action}">
      <label class="result-item">
        <input type="radio" name="TrainQueryDataViewPanel:TrainGroup" value="radio0">
      </label>
    </form>
    </body></html>
    """.encode()


def _step3_page_html(form_action=None):
    """Simulate THSR Step 3 (confirm ticket) page — has dummyId field."""
    action = form_action or "/IMINT/?wicket:interface=:2:BookingS3Form::IFormSubmitListener"
    return f"""
    <html><body>
    <form id="BookingS3FormSP" action="{action}">
      <input type="text" name="dummyId" value="">
      <input type="text" name="dummyPhone" value="">
      <input type="radio" name="TicketMemberSystemInputPanel:TakerMemberSystemDataView:memberSystemRadioGroup"
             value="radio44" checked>
    </form>
    </body></html>
    """.encode()


def _server_error_html():
    return "<html><body>內部伺服器發生錯誤。Server has internal error.</body></html>".encode("utf-8")


def _error_feedback_html():
    return """
    <html><body>
    <span class="feedbackPanelERROR">
      <span>去程查無可售車次或選購的車票已售完</span>
    </span>
    </body></html>
    """.encode("utf-8")


def _bot_blocked_html():
    return b"<html><head><title>Access Denied</title></head><body></body></html>"


def _empty_html():
    return b"<html><body></body></html>"


def _booking_form_still_html():
    return (
        "<html><body>"
        '<input name="bookingMethod" value="radio31">'
        "<div>some other content here to pass length check</div>"
        "</body></html>"
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# SearchTrainFlow._discover_radio_values
# ---------------------------------------------------------------------------

class TestDiscoverRadioValues:
    def test_discovers_time_and_train_id(self):
        page = BeautifulSoup(_booking_page_html(), "html.parser")
        radios = page.find_all("input", {"name": "bookingMethod"})
        result = SearchTrainFlow._discover_radio_values(radios)
        assert result == {"time": "radio31", "train_id": "radio33"}

    def test_discovers_changed_values(self):
        """Resilient to THSR changing radio values (e.g. radio99, radio100)."""
        page = BeautifulSoup(_booking_page_html("radio99", "radio100"), "html.parser")
        radios = page.find_all("input", {"name": "bookingMethod"})
        result = SearchTrainFlow._discover_radio_values(radios)
        assert result == {"time": "radio99", "train_id": "radio100"}

    def test_empty_radios(self):
        result = SearchTrainFlow._discover_radio_values([])
        assert result == {}

    def test_no_parent_label(self):
        """Radios without parent label return empty dict."""
        html = '<div><input type="radio" name="bookingMethod" value="radio31"></div>'
        page = BeautifulSoup(html, "html.parser")
        radios = page.find_all("input", {"name": "bookingMethod"})
        result = SearchTrainFlow._discover_radio_values(radios)
        assert result == {}

    def test_english_label_fallback(self):
        """Supports English labels as fallback."""
        html = """
        <label><input type="radio" name="bookingMethod" value="r1">Time</label>
        <label><input type="radio" name="bookingMethod" value="r2">Train No.</label>
        """
        page = BeautifulSoup(html, "html.parser")
        radios = page.find_all("input", {"name": "bookingMethod"})
        result = SearchTrainFlow._discover_radio_values(radios)
        assert result == {"time": "r1", "train_id": "r2"}


# ---------------------------------------------------------------------------
# SearchTrainFlow.get_search_by
# ---------------------------------------------------------------------------

class TestGetSearchBy:
    def _make_flow(self, config=None):
        client = MagicMock()
        flow = SearchTrainFlow.__new__(SearchTrainFlow)
        flow.client = client
        flow.config = config or {}
        return flow

    def test_returns_train_id_when_candidate_set(self):
        flow = self._make_flow({"current_candidate": "645"})
        page = BeautifulSoup(_booking_page_html(), "html.parser")
        assert flow.get_search_by(page) == "radio33"

    def test_returns_time_when_no_candidate(self):
        flow = self._make_flow({})
        page = BeautifulSoup(_booking_page_html(), "html.parser")
        assert flow.get_search_by(page) == "radio31"

    def test_uses_discovered_values_not_hardcoded(self):
        """Even if enum has old values, discovered values are used."""
        flow = self._make_flow({"current_candidate": "803"})
        page = BeautifulSoup(_booking_page_html("radioX", "radioY"), "html.parser")
        assert flow.get_search_by(page) == "radioY"

    def test_fallback_to_enum_when_no_labels(self):
        """Falls back to SearchType enum if labels can't be parsed."""
        html = '<div><input type="radio" name="bookingMethod" value="xyz"></div>'
        page = BeautifulSoup(html, "html.parser")

        flow = self._make_flow({"current_candidate": "645"})
        result = flow.get_search_by(page)
        # Should fallback to SearchType.TRAIN_ID.value
        from thsr_ticket.configs.web.enums import SearchType
        assert result == SearchType.TRAIN_ID.value

    def test_uses_checked_radio_as_default(self):
        """Without candidate and without label discovery, uses checked radio."""
        html = """
        <div>
          <input type="radio" name="bookingMethod" value="radioA">
          <input type="radio" name="bookingMethod" value="radioB" checked>
        </div>
        """
        page = BeautifulSoup(html, "html.parser")
        flow = self._make_flow({})
        assert flow.get_search_by(page) == "radioB"


# ---------------------------------------------------------------------------
# ConfirmTrainFlow.is_step3_page
# ---------------------------------------------------------------------------

class TestIsStep3Page:
    def _make_flow(self):
        client = MagicMock()
        resp = MagicMock()
        return ConfirmTrainFlow(client, resp)

    def test_detects_step3_page(self):
        flow = self._make_flow()
        assert flow.is_step3_page(_step3_page_html()) is True

    def test_rejects_step2_page(self):
        flow = self._make_flow()
        assert flow.is_step3_page(_step2_page_html()) is False

    def test_rejects_error_page(self):
        flow = self._make_flow()
        assert flow.is_step3_page(_server_error_html()) is False


# ---------------------------------------------------------------------------
# ConfirmTrainFlow._parse_form_action
# ---------------------------------------------------------------------------

class TestConfirmTrainFormAction:
    def test_parses_s2_action(self):
        page = BeautifulSoup(_step2_page_html(), "html.parser")
        result = ConfirmTrainFlow._parse_form_action(page)
        assert result == "/IMINT/?wicket:interface=:1:BookingS2Form::IFormSubmitListener"

    def test_returns_empty_when_no_form(self):
        page = BeautifulSoup(b"<html><body></body></html>", "html.parser")
        assert ConfirmTrainFlow._parse_form_action(page) == ""

    def test_returns_empty_when_no_action(self):
        page = BeautifulSoup(b'<html><form id="BookingS2Form"></form></html>', "html.parser")
        assert ConfirmTrainFlow._parse_form_action(page) == ""


# ---------------------------------------------------------------------------
# ConfirmTrainFlow._diagnose_empty_trains
# ---------------------------------------------------------------------------

class TestDiagnoseEmptyTrains:
    def _make_flow(self):
        client = MagicMock()
        resp = MagicMock()
        return ConfirmTrainFlow(client, resp)

    def test_diagnose_server_error(self):
        flow = self._make_flow()
        result = flow._diagnose_empty_trains(_server_error_html())
        assert "internal server error" in result.lower() or "內部伺服器" in result

    def test_diagnose_bot_blocked(self):
        flow = self._make_flow()
        result = flow._diagnose_empty_trains(_bot_blocked_html())
        assert "Bot detection" in result

    def test_diagnose_empty_page(self):
        flow = self._make_flow()
        result = flow._diagnose_empty_trains(_empty_html())
        assert "Nearly empty page" in result

    def test_diagnose_still_on_booking_form(self):
        flow = self._make_flow()
        result = flow._diagnose_empty_trains(_booking_form_still_html())
        assert "Still on booking form" in result


# ---------------------------------------------------------------------------
# ConfirmTrainFlow.run — skip step 2
# ---------------------------------------------------------------------------

class TestConfirmTrainFlowRun:
    def test_skip_step2_returns_direct(self):
        client = MagicMock()
        resp = MagicMock()
        resp.content = _step3_page_html()

        flow = ConfirmTrainFlow(client, resp)
        result_resp, model = flow.run()

        assert result_resp is resp
        assert model.selected_train == "direct"
        # Should NOT call submit_train since we skipped step 2
        client.submit_train.assert_not_called()


# ---------------------------------------------------------------------------
# ConfirmTicketFlow._parse_form_action
# ---------------------------------------------------------------------------

class TestConfirmTicketFormAction:
    def test_parses_s3_action_normal(self):
        """Normal flow: wicket interface :2."""
        page = BeautifulSoup(_step3_page_html(), "html.parser")
        result = ConfirmTicketFlow._parse_form_action(page)
        assert ":2:BookingS3Form" in result

    def test_parses_s3_action_skip_step2(self):
        """Skip-step2 flow: wicket interface :1."""
        html = _step3_page_html(
            form_action="/IMINT/?wicket:interface=:1:BookingS3Form::IFormSubmitListener"
        )
        page = BeautifulSoup(html, "html.parser")
        result = ConfirmTicketFlow._parse_form_action(page)
        assert ":1:BookingS3Form" in result

    def test_returns_empty_when_no_form(self):
        page = BeautifulSoup(b"<html><body></body></html>", "html.parser")
        assert ConfirmTicketFlow._parse_form_action(page) == ""


# ---------------------------------------------------------------------------
# hourly_booking — get_target_trains, next_run_time
# ---------------------------------------------------------------------------

class TestHourlyBooking:
    def test_get_target_trains_from_config(self, tmp_path):
        config = tmp_path / "config.yaml"
        config.write_text(
            "tickets:\n"
            "  - name: Test\n"
            "    candidates:\n"
            "      - '149'\n"
            "      - '1245'\n"
        )
        with patch("hourly_booking.CONFIG_PATH", config):
            from hourly_booking import get_target_trains
            targets = get_target_trains()
            assert targets == {"149", "1245"}

    def test_get_target_trains_empty_config(self, tmp_path):
        config = tmp_path / "config.yaml"
        config.write_text("tickets: []\n")
        with patch("hourly_booking.CONFIG_PATH", config):
            from hourly_booking import get_target_trains
            targets = get_target_trains()
            assert targets == set()

    def test_next_run_time_same_hour(self):
        from hourly_booking import next_run_time
        from datetime import datetime
        now = datetime(2026, 4, 16, 10, 0, 0)
        nxt = next_run_time(now)
        assert nxt.minute == 1
        assert nxt.hour == 10

    def test_next_run_time_wraps_to_next_hour(self):
        from hourly_booking import next_run_time
        from datetime import datetime
        now = datetime(2026, 4, 16, 10, 57, 0)
        nxt = next_run_time(now)
        assert nxt.minute == 1
        assert nxt.hour == 11

    def test_next_run_time_between_slots(self):
        from hourly_booking import next_run_time
        from datetime import datetime
        now = datetime(2026, 4, 16, 10, 10, 0)
        nxt = next_run_time(now)
        assert nxt.minute == 11
        assert nxt.hour == 10
