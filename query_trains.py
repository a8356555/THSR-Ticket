import sys
import io
import time
from PIL import Image
from bs4 import BeautifulSoup
import yaml
from datetime import date, timedelta, datetime
from typing import List, Optional

# Ensure project root is in path
sys.path.append("./")

from thsr_ticket.remote.http_request import HTTPRequest
from thsr_ticket.remote.captcha_solver import GeminiCaptchaSolver, DdddOcrCaptchaSolver
from thsr_ticket.remote.captcha_solver import GeminiCaptchaSolver, DdddOcrCaptchaSolver
from thsr_ticket.view_model.avail_trains import AvailTrains
from thsr_ticket.configs.web.param_schema import Train
from thsr_ticket.model.web.booking_form.station_mapping import StationMapping

# Mappings
STATION_MAP = {s.name: s.value for s in StationMapping}
# Also support numeric inputs if someone prefers IDs
STATION_MAP_REV = {s.value: s.value for s in StationMapping} 

SEAT_MAP = {
    "none": "0",
    "window": "1",
    "aisle": "2"
}

TRIP_TYPE_MAP = {
    "one-way": 0,
    "round-trip": 1
}

CAR_CLASS_MAP = {
    "standard": 0,
    "business": 1
}

# 'GEMINI', 'OCR', 'MANUAL'
CAPTCHA_METHOD = 'OCR'

def get_next_weekday(weekday_name: str) -> date:
    today = date.today()
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    try:
        target_weekday = weekdays.index(weekday_name.capitalize())
    except ValueError:
        print(f"Invalid weekday name: {weekday_name}. Defaulting to Friday.")
        target_weekday = 4 # Friday
        
    days_ahead = (target_weekday - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)

def parse_schedule(schedule_config: dict) -> date:
    if schedule_config['type'] == 'specific':
        return datetime.strptime(schedule_config['value'], '%Y-%m-%d').date()
    elif schedule_config['type'] == 'recurring':
        return get_next_weekday(schedule_config['value'])
    else:
        print(f"Unknown schedule type: {schedule_config.get('type')}. Defaulting to next Friday.")
        return get_next_weekday('Friday')

def convert_time_str(time_str: str) -> str:
    # "17:30" -> "530P"
    try:
        dt = datetime.strptime(time_str, "%H:%M")
    except ValueError:
        # If it parses as something else or fails, maybe it's already in format?
        # Let's assume input is HH:MM
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
        hour = 12 # 1201A etc.
        
    return f"{hour}{minute:02d}{suffix}"

def load_config():
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("config.yaml not found.")
        return None

def search_trains(search_mode: str, search_value: str, target_date: date, target_time: str = "530P", max_retries: int = 3, profile: dict = None):
    """
    Perform a train search.
    search_mode: 'time' or 'train_no'
    search_value: ignored if mode is 'time', train number if mode is 'train_no'
    profile: dictionary containing booking options (stations, preferences, etc.)
    """
    profile = profile or {}

    
    for attempt in range(max_retries):
        print(f"\n--- Starting Search: {search_mode} ({search_value if search_mode == 'train_no' else target_time}) on {target_date} [Attempt {attempt+1}/{max_retries}] ---")
        
        client = HTTPRequest()
        
        print("Fetching booking page...")
        resp = client.request_booking_page()
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # Dynamic parsing of booking method values
        methods = soup.find_all('input', {'name': 'bookingMethod'})
        for method in methods:
            target = method.get('data-target')
            if target == "search-by-time":
                booking_method_time = method.get('value')
            elif target == "search-by-trainNo":
                booking_method_train_no = method.get('value')

        if search_mode == 'train_no':
            final_booking_method = booking_method_train_no
            train_no_input = search_value
            # Even when searching by Train No, toTimeTable might be required or validated. 
            # We set it to target_time to be safe, as it's a required field in schema.
            time_table_input = target_time 
        else:
            final_booking_method = booking_method_time
            train_no_input = ''
            time_table_input = target_time

        img_resp = client.request_security_code_img(resp.content).content
        
        print("Solving CAPTCHA...")
        gemini_code = ""
        if CAPTCHA_METHOD == 'GEMINI':
            try:
                solver = GeminiCaptchaSolver()
                gemini_code = solver.solve(img_resp)
                print(f"Gemini Predicted: {gemini_code}")
            except Exception as e:
                print(f"Gemini Solver Error/Init failed: {e}")
        elif CAPTCHA_METHOD == 'OCR':
            try:
                solver = DdddOcrCaptchaSolver()
                gemini_code = solver.solve(img_resp)
                print(f"OCR Predicted: {gemini_code}")
            except Exception as e:
                 print(f"OCR Solver Error: {e}")
        else:
            print(f"Automated Solver disabled (Method: {CAPTCHA_METHOD}).")

        # Manual fallback / Confirmation
        final_code = gemini_code
        if not gemini_code:
            print("Opening CAPTCHA image for manual input...")
            image = Image.open(io.BytesIO(img_resp))
            image.show()
            final_code = input("Enter Code: ").strip()
        
        params = {
            'BookingS1Form:hf:0': '',
            'selectStartStation': profile.get('start_station', 2), # Default Taipei
            'selectDestinationStation': profile.get('dest_station', 7), # Default Taichung
            'trainCon:trainRadioGroup': profile.get('car_class', 0), 
            'tripCon:typesoftrip': profile.get('trip_type', 0), 
            'seatCon:seatRadioGroup': profile.get('seat_preference', '0'), 
            'bookingMethod': final_booking_method, 
            'toTimeInputField': target_date.strftime('%Y/%m/%d'),
            'toTimeTable': time_table_input, 
            'toTrainIDInputField': train_no_input,
            'backTimeInputField': target_date.strftime('%Y/%m/%d'),
            'backTimeTable': '',
            'backTrainIDInputField': '',
            'ticketPanel:rows:0:ticketAmount': f"{profile.get('ticket_amount', {}).get('adult', 1)}F", 
            'ticketPanel:rows:1:ticketAmount': f"{profile.get('ticket_amount', {}).get('child', 0)}H",
            'ticketPanel:rows:2:ticketAmount': '0W',
            'ticketPanel:rows:3:ticketAmount': '0E',
            'ticketPanel:rows:4:ticketAmount': '0P',
            'ticketPanel:rows:5:ticketAmount': '0T', 
            'homeCaptcha:securityCode': final_code,
            'agree': 'on'
        }
        
        # Submit
        print(f"Submitting query with code {final_code}...")
        print(f"DEBUG: Params: {params}")
        result_resp = client.submit_booking_form(params)
        
        # Check for specific errors before parsing
        if "檢測碼輸入錯誤" in result_resp.text:
            print("CAPTCHA Error (Verification Code Incorrect). Retrying...")
            continue
            
        try:
            trains = AvailTrains().parse(result_resp.content)
            if not trains:
                # Check for direct confirmation page (Step 3)
                if "BookingS3Form" in result_resp.text:
                    print("Direct confirmation page detected. Parsing single result...")
                    soup_conf = BeautifulSoup(result_resp.content, 'html.parser')
                    try:
                         # Extract info
                         t_id_str = soup_conf.find(id='InfoCode0').text.strip()
                         t_depart = soup_conf.find(id='InfoDeparture0').text.strip()
                         t_arrive = soup_conf.find(id='InfoArrival0').text.strip()
                         t_duration = soup_conf.find(id='InfoEstimatedTime0').text.strip()
                         
                         single_train = Train(
                            id=int(t_id_str),
                            depart=t_depart,
                            arrive=t_arrive,
                            travel_time=t_duration,
                            discount_str="", 
                            form_value="SELECTED" 
                         )
                         return [single_train]
                    except Exception as parse_e:
                        print(f"Failed to parse confirmation page: {parse_e}")

                # Could be other errors or just no trains.
                # If it's an error page without "檢測碼輸入錯誤", we might want to see it.
                if "feedbackPanelERROR" in result_resp.text:
                     print("Unknown Error found in result page.")
                     with open(f"debug_error_attempt_{attempt}.html", "wb") as f:
                        f.write(result_resp.content)
                else:
                     print("No trains parsed (and no obvious error). Saving debug_train_no_fail.html")
                     with open(f"debug_train_no_fail_{attempt}.html", "wb") as f:
                         f.write(result_resp.content)
                
                # If we are sure it's not a temporary glitch, we might break.
                # But let's assume if it failed to parse, we might as well retry if attempts left?
                # No, if params are wrong, retrying won't help. Only retry for CAPTCHA/Connection issues.
                # Let's save debug and return empty list for now.
                pass 
            else:
                return trains
        except Exception as e:
            print(f"Error parsing results: {e}")
            if "驗證碼" in result_resp.text or "檢測碼" in result_resp.text:
                 print("CAPTCHA Error.")
                 continue # Retry
            return []

    print("Max retries reached. Search failed.")
    return []

def main():
    config = load_config()
    if not config:
        return

    # Update global CAPTCHA_METHOD if present
    global CAPTCHA_METHOD
    if 'captcha' in config and 'method' in config['captcha']:
         CAPTCHA_METHOD = config['captcha']['method']
         print(f"CAPTCHA Method set to: {CAPTCHA_METHOD}")

    if 'tickets' not in config:
        print("No tickets found in config.")
        return

    for ticket in config['tickets']:
        print(f"\nProcessing Ticket: {ticket.get('name', 'Unnamed')}")
        
        target_date = parse_schedule(ticket['schedule'])
        
        raw_time = ticket.get('time_preference', '17:30')
        target_time = convert_time_str(raw_time)
        
        train_no = ticket.get('train_no', '')
        
        # Determine search mode based on train_no presence
        if train_no:
            search_mode = 'train_no'
            search_value = train_no
        else:
            # Fallback or error if user insisted on "always search by trainNo"
            # But let's support time search if train_no is missing just in case
            search_mode = 'time'
            search_value = ''
        
        # Mapping logic
        start_st_raw = ticket.get('start_station', 'Taipei')
        dest_st_raw = ticket.get('dest_station', 'Taichung')
        
        # Try to map names first, then integer if possible
        start_station = STATION_MAP.get(start_st_raw)
        if start_station is None and isinstance(start_st_raw, int):
            start_station = start_st_raw
            
        dest_station = STATION_MAP.get(dest_st_raw)
        if dest_station is None and isinstance(dest_st_raw, int):
             dest_station = dest_st_raw
             
        # Fallbacks
        if not start_station: start_station = 2
        if not dest_station: dest_station = 7

        trip_type_raw = ticket.get('trip_type', 'one-way')
        trip_type = TRIP_TYPE_MAP.get(trip_type_raw, 0)
        if isinstance(trip_type_raw, int): trip_type = trip_type_raw

        car_class_raw = ticket.get('car_class', 'standard')
        car_class = CAR_CLASS_MAP.get(car_class_raw, 0)
        if isinstance(car_class_raw, int): car_class = car_class_raw
        
        seat_pref_raw = ticket.get('seat_preference', 'none')
        seat_pref = SEAT_MAP.get(seat_pref_raw, "0")
        if isinstance(seat_pref_raw, (int, str)) and str(seat_pref_raw) in ["0", "1", "2"]:
            seat_pref = str(seat_pref_raw)

        # Construct mapped profile (reuse variable name profile for easier diff, but it represents ticket)
        mapped_profile = ticket.copy()
        mapped_profile['start_station'] = start_station
        mapped_profile['dest_station'] = dest_station
        mapped_profile['trip_type'] = trip_type
        mapped_profile['car_class'] = car_class
        mapped_profile['seat_preference'] = seat_pref
        
        # Pass the whole profile to search_trains to handle stations etc.
        trains = search_trains(search_mode, search_value, target_date, target_time, profile=mapped_profile)

        
        if trains:
             print(f"Found {len(trains)} trains for ticket '{ticket.get('name')}'")
             for t in trains:
                print(f"{t.id:<10} {t.depart:<10} {t.arrive:<10} {t.travel_time:<10} {t.discount_str}")
        else:
             print(f"No trains found for ticket '{ticket.get('name')}'")


if __name__ == "__main__":
    main()
