import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
from bs4 import BeautifulSoup
from curl_cffi.requests import Response

from thsr_ticket.remote.http_request import HTTPRequest
from thsr_ticket.view_model.avail_trains import AvailTrains
from thsr_ticket.view_model.error_feedback import ErrorFeedback
from thsr_ticket.configs.web.param_schema import Train, ConfirmTrainModel

logger = logging.getLogger(__name__)


class ConfirmTrainFlow:
    def __init__(self, client: HTTPRequest, book_resp: Response, config: dict = None):
        self.client = client
        self.book_resp = book_resp
        self.config = config or {}

    def _diagnose_empty_trains(self, html: bytes) -> str:
        """Diagnose why no trains were parsed from the response."""
        page = BeautifulSoup(html, features="html.parser")

        # Check for THSR error feedback (e.g. CAPTCHA wrong, date invalid)
        errors = ErrorFeedback().parse(html)
        if errors:
            msgs = [e.msg.strip() for e in errors]
            return f"THSR error: {'; '.join(msgs)}"

        # Check for THSR server error page (e.g. maintenance, internal error,
        # or invalid train ID causing 500)
        error_card = page.find("div", attrs={"class": "error-content"})
        if error_card:
            msg = error_card.get_text(strip=True)
            return f"THSR server error page: {msg}"

        if page.find(string=lambda s: s and '內部伺服器發生錯誤' in s if s else False):
            return "THSR internal server error (train ID may not exist on this date)"

        # Check for bot detection / Akamai challenge page
        title = page.find("title")
        title_text = title.text.strip() if title else ""
        if any(kw in title_text.lower() for kw in ["access denied", "akamai"]):
            return f"Bot detection / blocked (page title: '{title_text}')"

        # Check if it's actually the train list page but with no results
        # Look for the train list container (with or without results)
        if page.find("label", attrs={"class": "result-item"}) is not None or \
           page.find("div", attrs={"class": "result-area"}) is not None or \
           page.find("input", attrs={"name": "TrainQueryDataViewPanel:TrainGroup"}) is not None:
            return "No trains available for this date/train ID (genuine empty result)"

        # Check if response looks like a booking form (means we didn't advance)
        if page.find("input", attrs={"name": "bookingMethod"}):
            return "Still on booking form page (submission may have failed silently)"

        # Check if the page has minimal content (network issue or empty response)
        text_len = len(page.get_text(strip=True))
        if text_len < 100:
            return f"Nearly empty page ({text_len} chars) — possible network/connection issue"

        return f"Unknown page structure (title: '{title_text}', text length: {text_len})"

    def _dump_html(self, html: bytes, reason: str) -> None:
        """Save response HTML to debug_dumps/ for post-mortem analysis."""
        dump_dir = Path(__file__).resolve().parent.parent.parent / "debug_dumps"
        dump_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_path = dump_dir / f"no_trains_{timestamp}.html"
        dump_path.write_bytes(html)
        logger.info("Response HTML dumped to %s", dump_path)

    def is_step3_page(self, html: bytes) -> bool:
        """Check if the response is already the Step 3 (confirm ticket) page.

        This happens when searching by train ID — THSR skips Step 2 (train
        selection) because there is only one matching train.
        """
        page = BeautifulSoup(html, features='html.parser')
        return page.find('input', {'name': 'dummyId'}) is not None

    def run(self) -> Tuple[Response, ConfirmTrainModel]:
        # Train ID search may skip Step 2 entirely
        if self.is_step3_page(self.book_resp.content):
            logger.info("Train ID search skipped Step 2 — already on Step 3.")
            return self.book_resp, ConfirmTrainModel(selected_train='direct')

        trains = AvailTrains().parse(self.book_resp.content)
        if not trains:
            reason = self._diagnose_empty_trains(self.book_resp.content)
            self._dump_html(self.book_resp.content, reason)
            logger.error("No trains parsed — %s", reason)
            raise ValueError(f"No available trains! Reason: {reason}")

        confirm_model = ConfirmTrainModel(selected_train=trains[0].form_value)
        json_params = confirm_model.json(by_alias=True)
        dict_params = json.loads(json_params)

        page = BeautifulSoup(self.book_resp.content, features='html.parser')
        submit_url = self._parse_form_action(page)
        if submit_url:
            from thsr_ticket.configs.web.http_config import HTTPConfig
            full_url = HTTPConfig.BASE_URL + submit_url
            resp = self.client.sess.post(
                full_url, headers=self.client.common_head_html,
                data=dict_params, allow_redirects=True, timeout=60,
            )
        else:
            resp = self.client.submit_train(dict_params)
        return resp, confirm_model

    @staticmethod
    def _parse_form_action(page: BeautifulSoup) -> str:
        """Extract the BookingS2Form action URL from HTML."""
        form = page.find('form', {'id': 'BookingS2Form'})
        if form and form.get('action'):
            return form['action']
        return ''
