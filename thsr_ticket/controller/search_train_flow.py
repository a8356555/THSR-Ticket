from typing import Tuple
import json
import time
from bs4 import BeautifulSoup
from curl_cffi.requests import Response

from thsr_ticket.remote.http_request import HTTPRequest
from thsr_ticket.remote.captcha_solver import HybridCaptchaSolver
from thsr_ticket.view_model.error_feedback import ErrorFeedback
from thsr_ticket.configs.web.param_schema import BookingModel
from thsr_ticket.configs.web.parse_html_element import BOOKING_PAGE
from thsr_ticket.configs.web.enums import StationMapping, SeatPrefer, SearchType, TripType
from thsr_ticket.model.db import Record


class SearchTrainFlow:
    def __init__(self, client: HTTPRequest, record: Record = None,
                 ticket_config: dict = None, captcha_config: dict = None) -> None:
        self.client = client
        self.record = record
        self.config = ticket_config or {}
        self.captcha_config = captcha_config or {}
        self.error_feedback = ErrorFeedback()
        try:
            self.solver = HybridCaptchaSolver()
            print("Hybrid Solver initialized.")
        except Exception as e:
            print(f"Warning: Solver failed to init: {e}.")
            self.solver = None

    def run(self) -> Tuple[Response, BookingModel]:
        candidate = self.config.get('current_candidate')
        outbound_date = self.config.get('outbound_date')

        ocr_retries = self.captcha_config.get('ocr_retries', 5)
        gemini_retries = self.captcha_config.get('gemini_retries', 0)

        if not self.solver or not self.solver.ocr_solver:
            ocr_retries = 0

        total_attempts = ocr_retries + gemini_retries or 1

        for attempt in range(total_attempts):
            method = "OCR" if attempt < ocr_retries else "GEMINI"
            print(f"Booking Attempt {attempt+1}/{total_attempts} (Method: {method})")
            if attempt == 0:
                print('請稍等...')

            book_page = self.client.request_booking_page().content
            img_resp = self.client.request_security_code_img(book_page).content
            page = BeautifulSoup(book_page, features='html.parser')

            security_code = self.get_security_code(img_resp, method)
            if not security_code:
                print(f"CAPTCHA solve returned empty for attempt {attempt+1}. Retrying...")
                continue

            book_model = BookingModel(
                start_station=self.config.get('start_station'),
                dest_station=self.config.get('dest_station', StationMapping.Zuouing.name),
                outbound_date=outbound_date,
                outbound_time=self._default_time(),
                adult_ticket_num=self.config.get('ticket_amount', {}).get('adult', 1),
                seat_prefer=self.config.get('seat_preference'),
                types_of_trip=self.config.get('trip_type'),
                search_by=self.get_search_by(page),
                to_train_id=int(candidate) if candidate else None,
                security_code=security_code,
            )
            json_params = book_model.json(by_alias=True, exclude_none=True)
            dict_params = json.loads(json_params)

            # Dynamically discover form action URL
            form = page.find('form', {'id': 'BookingS1Form'})
            if form and form.get('action'):
                from thsr_ticket.configs.web.http_config import HTTPConfig
                action_url = HTTPConfig.BASE_URL + form['action']
                resp = self.client.sess.post(
                    action_url, headers=self.client.common_head_html,
                    data=dict_params, allow_redirects=True, timeout=60,
                )
            else:
                resp = self.client.submit_booking_form(dict_params)

            # Detect server error (e.g. invalid train ID, THSR internal issue)
            resp_page = BeautifulSoup(resp.content, features='html.parser')
            if resp_page.find(string=lambda s: s and '內部伺服器發生錯誤' in s if s else False):
                print(f"THSR server error on attempt {attempt+1}. Retrying after delay...")
                time.sleep(3)
                continue

            errors = self.error_feedback.parse(resp.content)
            if not errors:
                return resp, book_model

            is_captcha_error = any(
                kw in err.msg for err in errors for kw in ("驗證碼", "檢測碼")
            )
            if is_captcha_error:
                print(f"Captcha failed ({method}). Retrying...")
                time.sleep(1)
                continue
            else:
                return resp, book_model

        print("Max retries reached. Returning last response.")
        return resp, book_model

    def get_security_code(self, img_resp: bytes, method: str = "OCR") -> str:
        if self.solver:
            print(f'Using {method} Solver...')
            try:
                code = self.solver.solve_ocr(img_resp) if method == "OCR" else self.solver.solve_gemini(img_resp)
                print(f'{method} Predicted: {code}')
                return code
            except Exception as e:
                print(f'{method} Failed: {e}.')
        return None

    def get_search_by(self, page: BeautifulSoup) -> str:
        radios = page.find_all('input', {'name': 'bookingMethod'})
        label_map = self._discover_radio_values(radios)

        if self.config.get('current_candidate'):
            if train_id_val := label_map.get('train_id'):
                return train_id_val
            return SearchType.TRAIN_ID.value

        if time_val := label_map.get('time'):
            return time_val
        if checked := next((r for r in radios if 'checked' in r.attrs), None):
            return checked.attrs['value']
        return SearchType.TIME.value

    @staticmethod
    def _discover_radio_values(radios) -> dict:
        """Discover radio values by label text instead of hardcoded enum values.

        Returns dict with keys 'time' and/or 'train_id' mapped to their
        current radio values, resilient to THSR changing value attributes.
        """
        result = {}
        for radio in radios:
            value = radio.attrs.get('value', '')
            label = radio.find_parent('label')
            text = label.get_text(strip=True) if label else ''
            if '時間' in text or 'time' in text.lower():
                result['time'] = value
            elif '車次' in text or 'train' in text.lower():
                result['train_id'] = value
        return result

    def _default_time(self) -> str:
        """Default time used when searching by train ID (required field but ignored by THSR)."""
        return '600A'
