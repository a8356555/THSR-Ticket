from typing import Mapping, Any

import requests
from requests.adapters import HTTPAdapter, Retry
from requests.models import Response
from bs4 import BeautifulSoup

from thsr_ticket.configs.web.http_config import HTTPConfig
from thsr_ticket.configs.web.parse_html_element import BOOKING_PAGE


class HTTPRequest:
    def __init__(self, max_retries: int = 3) -> None:
        self.sess = requests.Session()

        # Configure retry strategy with backoff
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.sess.mount("https://", adapter)
        self.sess.mount("http://", adapter)

        self.common_head_html: dict = {
            "Host": HTTPConfig.HTTPHeader.BOOKING_PAGE_HOST,
            "User-Agent": HTTPConfig.HTTPHeader.USER_AGENT,
            "Accept": HTTPConfig.HTTPHeader.ACCEPT_HTML,
            "Accept-Language": HTTPConfig.HTTPHeader.ACCEPT_LANGUAGE,
            "Accept-Encoding": HTTPConfig.HTTPHeader.ACCEPT_ENCODING
        }

    def request_booking_page(self) -> Response:
        return self.sess.get(HTTPConfig.BOOKING_PAGE_URL, headers=self.common_head_html, allow_redirects=True, timeout=60)

    def request_security_code_img(self, book_page: bytes) -> Response:
        img_url = parse_security_img_url(book_page)
        return self.sess.get(img_url, headers=self.common_head_html, timeout=60)

    def submit_booking_form(self, params: Mapping[str, Any]) -> Response:
        url = HTTPConfig.SUBMIT_FORM_URL.format(self.sess.cookies["JSESSIONID"])
        return self.sess.post(url, headers=self.common_head_html, data=params, allow_redirects=True, timeout=60)

    def submit_train(self, params: Mapping[str, Any]) -> Response:
        return self.sess.post(
            HTTPConfig.CONFIRM_TRAIN_URL,
            headers=self.common_head_html,
            data=params,
            allow_redirects=True,
            timeout=60,
        )

    def submit_ticket(self, params: Mapping[str, Any]) -> Response:
        return self.sess.post(
            HTTPConfig.CONFIRM_TICKET_URL,
            headers=self.common_head_html,
            data=params,
            allow_redirects=True,
            timeout=60,
        )


def parse_security_img_url(html: bytes) -> str:
    page = BeautifulSoup(html, features="html.parser")
    element = page.find(**BOOKING_PAGE["security_code_img"])
    return HTTPConfig.BASE_URL + element["src"]
