from typing import Tuple, List
import json
import io
from datetime import date, timedelta, datetime
from PIL import Image
from bs4 import BeautifulSoup
from requests.models import Response

from thsr_ticket.remote.http_request import HTTPRequest
from thsr_ticket.remote.captcha_solver import HybridCaptchaSolver
from thsr_ticket.view_model.error_feedback import ErrorFeedback
from thsr_ticket.configs.web.param_schema import BookingModel
from thsr_ticket.configs.web.parse_html_element import BOOKING_PAGE
from thsr_ticket.configs.web.enums import StationMapping, TicketType, SeatPrefer, SearchType, TripType
from thsr_ticket.configs.common import (
    AVAILABLE_TIME_TABLE,
    DAYS_BEFORE_BOOKING_AVAILABLE,
    MAX_TICKET_NUM,
)
from thsr_ticket.model.db import Record

class SearchTrainFlow:
    def __init__(self, client: HTTPRequest, record: Record = None, ticket_config: dict = None, captcha_config: dict = None) -> None:
        self.client = client
        self.record = record
        self.config = ticket_config or {}
        self.captcha_config = captcha_config or {}
        self.error_feedback = ErrorFeedback()
        try:
            self.solver = HybridCaptchaSolver()
            print("Hybrid Solver initialized.")
        except Exception as e:
            print(f"Warning: Solver failed to init: {e}. Fallback to manual.")
            self.solver = None


    def run(self) -> Tuple[Response, BookingModel]:
        # Pre-process ticket config for date/time
        outbound_date = self.config.get('outbound_date')
        if 'schedule' in self.config:
            target_date = self.parse_schedule(self.config['schedule'])
            outbound_date = target_date.strftime('%Y-%m-%d')

        outbound_time = self.config.get('outbound_time')
        if 'time_preference' in self.config:
            outbound_time = self.convert_time_str(self.config['time_preference'])

        # Retry logic:
        ocr_retries = self.captcha_config.get('ocr_retries', 5)
        gemini_retries = self.captcha_config.get('gemini_retries', 0)

        # Skip OCR attempts if OCR solver is unavailable
        if not self.solver or not self.solver.ocr_solver:
            ocr_retries = 0

        total_attempts = ocr_retries + gemini_retries
        if not self.solver:
             total_attempts = 1

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
                outbound_time=outbound_time,
                adult_ticket_num=self.config.get('ticket_amount', {}).get('adult', 1),
                seat_prefer=self.config.get('seat_preference'),
                types_of_trip=self.config.get('trip_type'),
                search_by=self.get_search_by(page),
                to_train_id=int(self.config.get('train_no')) if self.config.get('train_no') else None,
                security_code=security_code,
            )
            json_params = book_model.json(by_alias=True)
            dict_params = json.loads(json_params)
            resp = self.client.submit_booking_form(dict_params)

            errors = self.error_feedback.parse(resp.content)
            if not errors:
                return resp, book_model

            is_captcha_error = any("驗證碼" in err.msg for err in errors)
            if is_captcha_error:
                print(f"Captcha failed ({method}). Retrying...")
                continue
            else:
                 return resp, book_model

        print("Max retries reached. Returning last response.")
        return resp, book_model

    def get_security_code(self, img_resp: bytes, method: str = "OCR") -> str:
        if self.solver:
            print(f'Using {method} Solver...')
            try:
                if method == "OCR":
                    code = self.solver.solve_ocr(img_resp)
                else:
                    code = self.solver.solve_gemini(img_resp)
                print(f'{method} Predicted: {code}')
                return code
            except Exception as e:
                print(f'{method} Failed: {e}.')
        return None


    def get_search_by(self, page: BeautifulSoup) -> str:
        # Always read radio values from the page since THSR assigns dynamic values per session.
        # We always search by TIME and let ConfirmTrainFlow select the specific train_no from results.
        candidates = page.find_all('input', {'name': 'bookingMethod'})
        if checked := next((cand for cand in candidates if 'checked' in cand.attrs), None):
            return checked.attrs['value']
        return SearchType.TIME.value

    def get_next_weekday(self, weekday_name: str) -> date:
        today = date.today()
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        try:
            target_weekday = weekdays.index(weekday_name.capitalize())
        except ValueError:
            raise ValueError(f"Invalid weekday name: {weekday_name}. Please check config.yaml.")

        days_ahead = (target_weekday - today.weekday() + 7) % 7
        return today + timedelta(days=days_ahead)

    def parse_schedule(self, schedule_config: dict) -> date:
        if schedule_config['type'] == 'specific':
            try:
                return datetime.strptime(schedule_config['value'], '%Y-%m-%d').date()
            except ValueError:
                return date.today()
        elif schedule_config['type'] == 'recurring':
            return self.get_next_weekday(schedule_config['value'])
        return date.today()

    def convert_time_str(self, time_str: str) -> str:
        if not time_str:
            raise ValueError("time_preference is missing or empty in config.")
        try:
            dt = datetime.strptime(time_str, "%H:%M")
        except ValueError:
            return time_str

        hour = dt.hour
        minute = dt.minute

        if hour == 12 and minute == 0:
            return "1200N"

        suffix = "A"
        if hour >= 12:
            suffix = "P"
            if hour > 12:
                hour -= 12
        elif hour == 0:
            hour = 12

        return f"{hour}{minute:02d}{suffix}"
