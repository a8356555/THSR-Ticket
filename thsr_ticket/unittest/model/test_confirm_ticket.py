import pytest
import jsonschema

from thsr_ticket.model.web.confirm_ticket import ConfirmTicket


@pytest.fixture
def ticket():
    return ConfirmTicket()


@pytest.mark.parametrize("val", ["tooshort", "toooooooooolong"])
def test_set_id(val, ticket):
    with pytest.raises(ValueError):
        ticket.personal_id = val


@pytest.mark.parametrize("val,err_msg", [
    ("0812345667", "Wrong prefix"),
    ("0911244", "Wrong length")
])
def test_phone(val, err_msg, ticket):
    with pytest.raises(ValueError) as exc_info:
        ticket.phone = val
    assert err_msg in str(exc_info.value)
    ticket.phone = "0945789123"
    assert ticket.phone == "0945789123"


def test_get_params(ticket):
    # dummyId is None before personal_id is set -> schema validation fails
    with pytest.raises(jsonschema.exceptions.ValidationError):
        ticket.get_params()

    ticket.personal_id = "A186902624"
    ticket.phone = "0945789123"
    ticket.member_radio = "radio44"
    assert ticket.personal_id == "A186902624"

    params = ticket.get_params()
    assert params["dummyId"] == "A186902624"
    assert params["dummyPhone"] == "0945789123"
    assert params["agree"] == "on"
    assert params["BookingS3FormSP:hf:0"] == ""
