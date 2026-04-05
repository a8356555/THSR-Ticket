import json
from typing import List, Tuple
from curl_cffi.requests import Response

from thsr_ticket.remote.http_request import HTTPRequest
from thsr_ticket.view_model.avail_trains import AvailTrains
from thsr_ticket.configs.web.param_schema import Train, ConfirmTrainModel


class ConfirmTrainFlow:
    def __init__(self, client: HTTPRequest, book_resp: Response, config: dict = None):
        self.client = client
        self.book_resp = book_resp
        self.config = config or {}

    def run(self) -> Tuple[Response, ConfirmTrainModel]:
        trains = AvailTrains().parse(self.book_resp.content)
        if not trains:
            raise ValueError('No available trains!')

        confirm_model = ConfirmTrainModel(selected_train=trains[0].form_value)
        json_params = confirm_model.json(by_alias=True)
        dict_params = json.loads(json_params)
        resp = self.client.submit_train(dict_params)
        return resp, confirm_model
