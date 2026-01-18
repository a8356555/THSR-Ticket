import json
from typing import List, Tuple
from requests.models import Response

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

        confirm_model = ConfirmTrainModel(
            selected_train=self.select_available_trains(trains),
        )
        json_params = confirm_model.json(by_alias=True)
        dict_params = json.loads(json_params)
        resp = self.client.submit_train(dict_params)
        return resp, confirm_model

    def select_available_trains(self, trains: List[Train]) -> str:
        # Auto-selection based on config
        if self.config:
            # 1. Match specific train number
            if train_no := self.config.get('train_no'):
                train_no = str(train_no)
                for train in trains:
                    if str(train.id) == train_no:
                        print(f"Auto-selecting train ID: {train.id}")
                        return train.form_value
                print(f"Train {train_no} not found in results.")
            
            # 2. Fallback: Select first available
            print(f"Auto-selecting first available train: {trains[0].id}")
            return trains[0].form_value

        # Fallback to first
        print(f"No specific config match. Auto-selecting first available train: {trains[0].id}")
        return trains[0].form_value
