import sys
import io
from PIL import Image
from datetime import date, timedelta
from typing import List

# Ensure project root is in path
sys.path.append("./")

from thsr_ticket.remote.http_request import HTTPRequest
from thsr_ticket.remote.captcha_solver import GeminiCaptchaSolver
from thsr_ticket.view_model.avail_trains import AvailTrains
from thsr_ticket.configs.web.param_schema import BookingModel
from thsr_ticket.configs.web.enums import StationMapping, TicketType

def get_next_friday():
    today = date.today()
    # 0=Mon, 4=Fri, 6=Sun
    # If today is Sunday (6), next Friday is in the next week.
    # Days until next Monday = 0 - 6 + 7 = 1 (Jan 19)
    # Days until next Friday = 4 - 6 + 7 = 5 (Jan 23)
    # Correct logic for "Next Week Friday" (assuming current week ends on Sunday)
    days_ahead = (4 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    # Original Next Friday (Week 1) + 2 weeks = Week 3 ("下下下週五")
    return today + timedelta(days=days_ahead + 14)

def query_trains():
    target_date = get_next_friday()
    # User requested "下下下週五" (Friday after next after next).
    # Current date is 2026-01-18 (Sun). Next week starts 19 (Mon).
    # Friday of next week is Jan 23.
    
    # 17:30 corresponds to '530P' in AVAILABLE_TIME_TABLE
    target_time = "530P" 
    
    print(f"Querying for: {target_date} after 17:30")
    
    client = HTTPRequest()
    
    print("Fetching booking page...")
    resp = client.request_booking_page()
    img_resp = client.request_security_code_img(resp.content).content
    
    print("Solving CAPTCHA...")
    gemini_code = ""
    try:
        solver = GeminiCaptchaSolver()
        gemini_code = solver.solve(img_resp)
        print(f"Gemini Predicted: {gemini_code}")
    except Exception as e:
        print(f"Gemini Solver Error: {e}")

    # Manual Verification / Override
    print("Opening CAPTCHA image...")
    image = Image.open(io.BytesIO(img_resp))
    image.show()
    
    manual_code = input(f"Press Enter to use '{gemini_code}', or type correct code: ").strip()
    final_code = manual_code if manual_code else gemini_code
    print(f"Using Code: {final_code}")

    # Construct Parameters manually as if from form
    # Using the param mapping we validated earlier
    params = {
        'BookingS1Form:hf:0': '',
        'selectStartStation': 2, # Taipei
        'selectDestinationStation': 7, # Taichung
        'trainCon:trainRadioGroup': 0, # Standard Class
        'tripCon:typesoftrip': 0, # One-way
        'seatCon:seatRadioGroup': '0', # No preference
        'bookingMethod': 'radio31', # Time
        'toTimeInputField': target_date.strftime('%Y/%m/%d'),
        'toTimeTable': target_time, 
        'toTrainIDInputField': '',
        'backTimeInputField': target_date.strftime('%Y/%m/%d'),
        'backTimeTable': '',
        'backTrainIDInputField': '',
        'ticketPanel:rows:0:ticketAmount': '1F', # 1 Adult
        'ticketPanel:rows:1:ticketAmount': '0H',
        'ticketPanel:rows:2:ticketAmount': '0W',
        'ticketPanel:rows:3:ticketAmount': '0E',
        'ticketPanel:rows:4:ticketAmount': '0P',
        'ticketPanel:rows:5:ticketAmount': '0T', # Teenager, added based on inspect
        'homeCaptcha:securityCode': final_code,
        'agree': 'on'
    }

    # Submit
    print("Submitting query...")
    result_resp = client.submit_booking_form(params)
    
    # Parse
    print("\nParsing results...")
    try:
        trains = AvailTrains().parse(result_resp.content)
        if not trains:
            print("No trains found or parsing failed.")
            print("Response preview:", result_resp.text[:500])
            with open("debug_response.html", "wb") as f:
                f.write(result_resp.content)
            # Determine if error page
            if "驗證碼" in result_resp.text:
                print("CAPTCHA Error likely.")
            return

        print(f"{'Train ID':<10} {'Depart':<10} {'Arrive':<10} {'Duration':<10} {'Discount'}")
        print("-" * 60)
        count = 0
        for t in trains:
            # Filter: Although we asked for 530P, the system returns trains starting from that time.
            # Convert depart time to comparable if needed, but system usually returns ordered list.
            print(f"{t.id:<10} {t.depart:<10} {t.arrive:<10} {t.travel_time:<10} {t.discount_str}")
            count += 1
            
        print(f"\nTotal trains found: {count}")
            
    except Exception as e:
        print(f"Error parsing: {e}")
        # Debug: save html
        with open("error.html", "wb") as f:
            f.write(result_resp.content)
        print("Saved response to error.html")

if __name__ == "__main__":
    query_trains()
