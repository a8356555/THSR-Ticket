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

    def select_available_trains(self, trains: List[Train], default_value: int = 1) -> Train:
        # Auto-selection logic
        if self.config and (pref_id := self.config.get('preferred_train_id')):
            pref_id = str(pref_id) # Ensure string comparison
            for train in trains:
                if str(train.id) == pref_id:
                    print(f"Auto-selecting preferred train ID: {train.id}")
                    return train.form_value
            print(f"Preferred train {pref_id} not found.")
            if not self.config.get('allow_any_train', False):
                 print("Wait for manual selection...")
            else:
                 print("Auto-selecting first available train as fallback.")
                 return trains[0].form_value

        for idx, train in enumerate(trains, 1):
            print(
                f'{idx}. {train.id:>4} {train.depart:>3}~{train.arrive} {train.travel_time:>3} '
                f'{train.discount_str}'
            )
        selection = int(input(f'輸入選擇（預設：{default_value}）：') or default_value)
        return trains[selection-1].form_value
