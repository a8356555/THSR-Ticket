from thsr_ticket.configs.web.param_schema import BookingModel
from thsr_ticket.configs.web.enums import SeatPrefer
from pydantic import ValidationError

def test_seat_prefer_mapping():
    # Helper to create a dummy model with only relevant fields populated enough to pass basic init
    # We need to fill required fields.
    base_data = {
        "selectStartStation": 1,
        "selectDestinationStation": 2,
        "bookingMethod": "radio17",
        "tripCon:typesoftrip": 0,
        "toTimeInputField": "2024/01/01", # Date validation might fail if I don't use a future date or mock it? 
        # Wait, check_date validator defaults to today if None, but here we pass value. 
        # The validator checks if target_date < today. So we need a future date.
        # Actually I can just mock the validator or use a dynamic date.
        "toTimeTable": "1201A",
        "homeCaptcha:securityCode": "1234",
        "trainCon:trainRadioGroup": 0,
        "seatCon:seatRadioGroup": "0", # placeholder
    }
    
    from datetime import date, timedelta
    future_date = (date.today() + timedelta(days=1)).strftime('%Y/%m/%d')
    base_data['toTimeInputField'] = future_date

    # Test Case 1: Enum names (case insensitive)
    print("Test 1: Testing 'window' -> '1'")
    data = base_data.copy()
    data['seatCon:seatRadioGroup'] = 'window'
    model = BookingModel(**data)
    assert model.seat_prefer == SeatPrefer.WINDOW.value, f"Expected {SeatPrefer.WINDOW.value}, got {model.seat_prefer}"
    print("PASS")

    print("Test 2: Testing 'AISLE' -> '2'")
    data['seatCon:seatRadioGroup'] = 'AISLE'
    model = BookingModel(**data)
    assert model.seat_prefer == SeatPrefer.AISLE.value, f"Expected {SeatPrefer.AISLE.value}, got {model.seat_prefer}"
    print("PASS")

    # Test Case 2: Raw values
    print("Test 3: Testing '0' -> '0'")
    data['seatCon:seatRadioGroup'] = '0'
    model = BookingModel(**data)
    assert model.seat_prefer == SeatPrefer.NONE.value, f"Expected {SeatPrefer.NONE.value}, got {model.seat_prefer}"
    print("PASS")

    # Test Case 4: Adult ticket num
    print("Test 4: Testing adult ticket num conversion '1' -> '1F'")
    data = base_data.copy()
    data['ticketPanel:rows:0:ticketAmount'] = 1 
    model = BookingModel(**data)
    assert model.adult_ticket_num == '1F', f"Expected '1F', got {model.adult_ticket_num}"
    print("PASS")
    
    print("Test 5: Testing adult ticket num conversion '2F' -> '2F'")
    data['ticketPanel:rows:0:ticketAmount'] = '2F'
    model = BookingModel(**data)
    assert model.adult_ticket_num == '2F', f"Expected '2F', got {model.adult_ticket_num}"
    print("PASS")

    # Test Case 5: Types of trip
    print("Test 6: Testing types of trip 'single' -> 0")
    data = base_data.copy()
    data['tripCon:typesoftrip'] = 'single'
    model = BookingModel(**data)
    assert model.types_of_trip == 0, f"Expected 0, got {model.types_of_trip}"
    print("PASS")
    
    print("Test 7: Testing types of trip 'ROUND' -> 0") # Note: Round is 1, but let's test lowercase
    data['tripCon:typesoftrip'] = 'ROUND'
    model = BookingModel(**data)
    assert model.types_of_trip == 1, f"Expected 1, got {model.types_of_trip}"
    print("PASS")

     # Test Case 6: Search by
    print("Test 8: Testing search by 'time' -> 'radio17'")
    data = base_data.copy()
    data['bookingMethod'] = 'time'
    model = BookingModel(**data)
    assert model.search_by == 'radio17', f"Expected 'radio17', got {model.search_by}"
    print("PASS")
    
    print("Test 9: Testing search by 'train_id' -> 'radio19'")
    data['bookingMethod'] = 'train_id'
    model = BookingModel(**data)
    assert model.search_by == 'radio19', f"Expected 'radio19', got {model.search_by}"
    print("PASS")


    # Test Case 3: Controller file syntax check
    print("Test 10: Importing SearchTrainFlow to check syntax")
    try:
        from thsr_ticket.controller.search_train_flow import SearchTrainFlow
        print("PASS")
    except ImportError as e:
        print(f"FAIL: {e}")
    except Exception as e:
        print(f"FAIL: {e}")

if __name__ == "__main__":
    test_seat_prefer_mapping()
