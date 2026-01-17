import sys
import io
from PIL import Image

# Ensure project root is in path
sys.path.append("./")

from thsr_ticket.remote.http_request import HTTPRequest
from thsr_ticket.remote.captcha_solver import GeminiCaptchaSolver

def test_captcha():
    print("Initializing HTTP Client...")
    client = HTTPRequest()
    
    print("Requesting booking page...")
    book_page_resp = client.request_booking_page()
    book_page = book_page_resp.content
    
    print("Downloading CAPTCHA image...")
    img_resp = client.request_security_code_img(book_page).content
    
    print("Initializing Gemini Solver...")
    try:
        solver = GeminiCaptchaSolver()
    except ValueError as e:
        print(f"Error: {e}")
        print("Please export GEMINI_API_KEY='your_key' or check .env file.")
        return

    print("Solving CAPTCHA...")
    try:
        code = solver.solve(img_resp)
        print(f"\n--- Result ---")
        print(f"Gemini Predicted Code: {code}")
        
        # Show image for manual verification
        print("Opening image for manual verification...")
        image = Image.open(io.BytesIO(img_resp))
        image.show()
    except Exception as e:
        print(f"Failed to solve CAPTCHA: {e}")

if __name__ == "__main__":
    test_captcha()
