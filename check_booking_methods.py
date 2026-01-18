import sys
import requests
from bs4 import BeautifulSoup

# Ensure project root is in path
sys.path.append("./")

from thsr_ticket.remote.http_request import HTTPRequest

def check_booking_methods():
    client = HTTPRequest()
    print("Fetching booking page...")
    resp = client.request_booking_page()
    
    soup = BeautifulSoup(resp.content, 'html.parser')
    
    # Find all inputs with name="bookingMethod"
    methods = soup.find_all('input', {'name': 'bookingMethod'})
    
    print("\nAvailable Booking Methods:")
    print(f"{'Value':<15} {'Label'}")
    print("-" * 30)
    
    for method in methods:
        print(method)
        value = method.get('value')
        # Try to find the label text. usually it's the parent label text or next sibling
        # In the provided HTML debug:
        # <label><input ...> 時間 </label>
        
        label_text = "Unknown"
        parent = method.find_parent('label')
        if parent:
            label_text = parent.get_text(strip=True)
            
        print(f"{value:<15} {label_text}")

if __name__ == "__main__":
    check_booking_methods()
