import yaml
from typing import List
from curl_cffi.requests import Response

from thsr_ticket.controller.search_train_flow import SearchTrainFlow
from thsr_ticket.controller.confirm_train_flow import ConfirmTrainFlow
from thsr_ticket.controller.confirm_ticket_flow import ConfirmTicketFlow
from thsr_ticket.view_model.error_feedback import ErrorFeedback
from thsr_ticket.view_model.booking_result import BookingResult
from thsr_ticket.view.web.show_error_msg import ShowErrorMsg
from thsr_ticket.view.web.show_booking_result import ShowBookingResult
from thsr_ticket.view.common import history_info
from thsr_ticket.model.db import ParamDB, Record
from thsr_ticket.remote.http_request import HTTPRequest


class BookingFlow:
    def __init__(self) -> None:
        self.client = HTTPRequest()
        self.db = ParamDB()
        self.record = Record()
        self.config = self.load_config()

        self.error_feedback = ErrorFeedback()
        self.show_error_msg = ShowErrorMsg()

    def load_config(self):
        try:
            with open('config.yaml', 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}

    def run(self) -> List[Response]:
        tickets = self.config.get('tickets')
        captcha_config = self.config.get('captcha', {})

        if tickets:
            responses = []
            for ticket in tickets:
                print(f"\n--- Processing Ticket: {ticket.get('name', 'Unnamed')} ---")
                try:
                    # 1. Search Train
                    book_resp, book_model = SearchTrainFlow(
                        client=self.client,
                        record=self.record,
                        ticket_config=ticket,
                        captcha_config=captcha_config
                    ).run()

                    if self.show_error(book_resp.content):
                        print("Error on Search Page. Skipping ticket.")
                        continue

                    # 2. Confirm Train
                    train_resp, train_model = ConfirmTrainFlow(
                        self.client,
                        book_resp,
                        config=ticket
                    ).run()

                    if self.show_error(train_resp.content):
                         print("Error on Train Confirmation. Skipping ticket.")
                         continue

                    # 3. Confirm Ticket
                    ticket_resp, ticket_model = ConfirmTicketFlow(self.client, train_resp, self.record).run()
                    if self.show_error(ticket_resp.content):
                         print("Error on Ticket Confirmation. Skipping ticket.")
                         continue

                    # Result page.
                    result_model = BookingResult().parse(ticket_resp.content)
                    book = ShowBookingResult()
                    book.show(result_model)
                    print("\n請使用官方提供的管道完成後續付款以及取票!!")

                    self.db.save(book_model, ticket_model)
                    responses.append(ticket_resp)

                except Exception as e:
                    print(f"Exception processing ticket: {e}")
                    import traceback
                    traceback.print_exc()

            return responses

        else:
             print("No tickets configured. Please add tickets to config.yaml.")
             return []

    def show_history(self) -> None:
        hist = self.db.get_history()
        if not hist:
            return
        h_idx = history_info(hist)
        if h_idx is not None:
            self.record = hist[h_idx]

    def show_error(self, html: bytes) -> bool:
        errors = self.error_feedback.parse(html)
        if len(errors) == 0:
            return False

        self.show_error_msg.show(errors)
        return True
