import io
import json
import yaml
from PIL import Image
from typing import Tuple
from datetime import date, timedelta

from bs4 import BeautifulSoup
from requests.models import Response

from thsr_ticket.model.db import Record
from thsr_ticket.remote.http_request import HTTPRequest
from thsr_ticket.remote.captcha_solver import GeminiCaptchaSolver
from thsr_ticket.configs.web.param_schema import BookingModel
from thsr_ticket.configs.web.parse_html_element import BOOKING_PAGE
from thsr_ticket.configs.web.enums import StationMapping, TicketType
from thsr_ticket.configs.common import (
    AVAILABLE_TIME_TABLE,
    DAYS_BEFORE_BOOKING_AVAILABLE,
    MAX_TICKET_NUM,
)


    def __init__(self, client: HTTPRequest, record: Record = None, config: dict = None) -> None:
        self.client = client
        self.record = record
        self.config = config if config is not None else self.load_config()
        try:
            self.solver = GeminiCaptchaSolver()
            print("Gemini Solver initialized.")
        except Exception as e:
            print(f"Warning: Gemini Solver failed to init: {e}. Fallback to manual.")
            self.solver = None

    def load_config(self):
        try:
            with open('config.yaml', 'r', encoding='utf-8') as f:
                return yaml.safe_load(f).get('booking', {})
        except FileNotFoundError:
            return {}

    def run(self) -> Tuple[Response, BookingModel]:
        # First page. Booking options
        print('請稍等...')
        book_page = self.client.request_booking_page().content
        img_resp = self.client.request_security_code_img(book_page).content
        page = BeautifulSoup(book_page, features='html.parser')

        book_model = BookingModel(
            start_station=self.select_station('啟程'),
            dest_station=self.select_station('到達', default_value=StationMapping.Zuouing.value),
            outbound_date=self.select_date('出發'),
            outbound_time=self.select_time('啟程'),
            adult_ticket_num=self.select_ticket_num(TicketType.ADULT),
            seat_prefer=self.select_seat_prefer(page),
            types_of_trip=self.select_types_of_trip(page),
            search_by=self.select_search_by(page),
            security_code=self.input_security_code(img_resp),
        )
        json_params = book_model.json(by_alias=True)
        dict_params = json.loads(json_params)
        resp = self.client.submit_booking_form(dict_params)
        return resp, book_model

    def select_station(self, travel_type: str, default_value: int = StationMapping.Taipei.value) -> int:
        if self.config:
            config_key = 'start_station' if travel_type == '啟程' else 'dest_station'
            station_name = self.config.get(config_key)
            if station_name:
                for station in StationMapping:
                    if station.name == station_name:
                        return station.value

        if (
            self.record
            and (
                station := {
                    '啟程': self.record.start_station,
                    '到達': self.record.dest_station,
                }.get(travel_type)
            )
        ):
            return station

        print(f'選擇{travel_type}站：')
        for station in StationMapping:
            print(f'{station.value}. {station.name}')

        return int(
            input(f'輸入選擇(預設: {default_value})：')
            or default_value
        )

    def select_date(self, date_type: str) -> str:
        if self.config:
            date_str = self.config.get('outbound_date')
            if date_str == 'today':
                return str(date.today())
            elif date_str == 'tomorrow':
                return str(date.today() + timedelta(days=1))
            elif date_str:
                return date_str


        today = date.today()
        last_avail_date = today + timedelta(days=DAYS_BEFORE_BOOKING_AVAILABLE)
        print(f'選擇{date_type}日期（{today}~{last_avail_date}）（預設為今日）：')
        return input() or str(today)

    def select_time(self, time_type: str, default_value: int = 10) -> str:
        if self.config and (time_str := self.config.get('outbound_time')):
             return time_str


        if self.record and (
            time_str := {
                '啟程': self.record.outbound_time,
                '回程': None,
            }.get(time_type)
        ):
            return time_str

        print('選擇出發時間：')
        for idx, t_str in enumerate(AVAILABLE_TIME_TABLE):
            t_int = int(t_str[:-1])
            if t_str[-1] == "A" and (t_int // 100) == 12:
                t_int = "{:04d}".format(t_int % 1200)  # type: ignore
            elif t_int != 1230 and t_str[-1] == "P":
                t_int += 1200
            t_str = str(t_int)
            print(f'{idx+1}. {t_str[:-2]}:{t_str[-2:]}')

        selected_opt = int(input(f'輸入選擇（預設：{default_value}）：') or default_value)
        return AVAILABLE_TIME_TABLE[selected_opt-1]

    def select_ticket_num(self, ticket_type: TicketType, default_ticket_num: int = 1) -> str:
        if self.config and ticket_type == TicketType.ADULT:
            num = self.config.get('adult_ticket_num')
            if num is not None:
                return f'{num}{ticket_type.value}'


        if self.record and (
            ticket_num_str := {
                TicketType.ADULT: self.record.adult_num,
                TicketType.CHILD: None,
                TicketType.DISABLED: None,
                TicketType.ELDER: None,
                TicketType.COLLEGE: None,
            }.get(ticket_type)
        ):
            return ticket_num_str

        ticket_type_name = {
            TicketType.ADULT: '成人',
            TicketType.CHILD: '孩童',
            TicketType.DISABLED: '愛心',
            TicketType.ELDER: '敬老',
            TicketType.COLLEGE: '大學生',
        }.get(ticket_type)

        print(f'選擇{ticket_type_name}票數（0~{MAX_TICKET_NUM}）（預設：{default_ticket_num}）')
        ticket_num = int(input() or default_ticket_num)
        return f'{ticket_num}{ticket_type.value}'


def _parse_seat_prefer_value(page: BeautifulSoup) -> str:
    options = page.find(**BOOKING_PAGE["seat_prefer_radio"])
    preferred_seat = options.find_next(selected='selected')
    return preferred_seat.attrs['value']


def _parse_types_of_trip_value(page: BeautifulSoup) -> int:
    options = page.find(**BOOKING_PAGE["types_of_trip"])
    tag = options.find_next(selected='selected')
    return int(tag.attrs['value'])


def _parse_search_by(page: BeautifulSoup) -> str:
    candidates = page.find_all('input', {'name': 'bookingMethod'})
    tag = next((cand for cand in candidates if 'checked' in cand.attrs))
    return tag.attrs['value']


    def input_security_code(self, img_resp: bytes) -> str:
        if self.solver:
            print('正在使用 Gemini 破解驗證碼...')
            try:
                code = self.solver.solve(img_resp)
                print(f'Gemini 破解結果: {code}')
                return code
            except Exception as e:
                print(f'Gemini 失敗: {e}，轉為手動輸入。')

        print('輸入驗證碼：')
        image = Image.open(io.BytesIO(img_resp))
        image.show()
        return input()

    def select_seat_prefer(self, page: BeautifulSoup) -> str:
        if self.config and (val := self.config.get('seat_prefer')):
            mapping = {
                'none': '0',
                'window': '1',
                'aisle': '2'
            }
            # Return mapped value or original if not found (to support direct code usage)
            return mapping.get(str(val).lower(), val)
        return _parse_seat_prefer_value(page)

    def select_types_of_trip(self, page: BeautifulSoup) -> int:
        if self.config and (val := self.config.get('types_of_trip')) is not None:
             # Support 0/1 integers or strings
            return int(val)
        return _parse_types_of_trip_value(page)

    def select_search_by(self, page: BeautifulSoup) -> str:
        if self.config and (val := self.config.get('search_by')):
            mapping = {
                'time': 'radio17',
                'train_number': 'radio19'
            }
            return mapping.get(str(val).lower(), val)
        return _parse_search_by(page)

