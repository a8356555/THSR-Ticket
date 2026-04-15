import json
import os
from dotenv import load_dotenv
from typing import Tuple

from bs4 import BeautifulSoup
from curl_cffi.requests import Response
from thsr_ticket.configs.web.param_schema import ConfirmTicketModel
from thsr_ticket.model.db import Record
from thsr_ticket.remote.http_request import HTTPRequest

class ConfirmTicketFlow:
    def __init__(self, client: HTTPRequest, train_resp: Response, record: Record = None):
        load_dotenv()
        self.client = client
        self.train_resp = train_resp
        self.record = record

    def run(self) -> Tuple[Response]:
        page = BeautifulSoup(self.train_resp.content, features='html.parser')
        ticket_model = ConfirmTicketModel(
            personal_id=self.set_personal_id(),
            phone_num=self.set_phone_num(),
            email=self.set_email(),
            member_radio=self._parse_member_radio(page),
        )

        json_params = ticket_model.json(by_alias=True)
        dict_params = json.loads(json_params)

        submit_url = self._parse_form_action(page)
        if submit_url:
            from thsr_ticket.configs.web.http_config import HTTPConfig
            full_url = HTTPConfig.BASE_URL + submit_url
            resp = self.client.sess.post(
                full_url, headers=self.client.common_head_html,
                data=dict_params, allow_redirects=True, timeout=60,
            )
        else:
            resp = self.client.submit_ticket(dict_params)
        return resp, ticket_model

    @staticmethod
    def _parse_form_action(page: BeautifulSoup) -> str:
        """Extract the BookingS3Form action URL from HTML.

        Dynamically discovers the correct wicket interface number, which
        changes when train-ID search skips Step 2.
        """
        form = page.find('form', {'id': 'BookingS3FormSP'})
        if form and form.get('action'):
            return form['action']
        return ''

    def set_personal_id(self) -> str:
        if self.record and (personal_id := self.record.personal_id):
            return personal_id

        if env_id := os.getenv('personal_identification'):
            return env_id

        raise ValueError("Personal ID not found in .env (key: personal_identification).")

    def set_phone_num(self) -> str:
        if self.record and (phone_num := self.record.phone):
            return phone_num

        if env_phone := os.getenv('phone_number'):
            return env_phone

        return ''

    def set_email(self) -> str:
        if env_email := os.getenv('email'):
            return env_email
        return ''

    def _parse_member_radio(self, page: BeautifulSoup) -> str:
        candidates = page.find_all(
            'input',
            attrs={
                'name': 'TicketMemberSystemInputPanel:TakerMemberSystemDataView:memberSystemRadioGroup'
            },
        )
        tag = next((cand for cand in candidates if 'checked' in cand.attrs), None)
        if tag is None:
            raise ValueError("No member radio button is checked on the confirm ticket page.")
        return tag.attrs['value']
