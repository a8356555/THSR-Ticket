import sys
from bs4 import BeautifulSoup

# Ensure project root is in path
sys.path.append("./")

from thsr_ticket.remote.http_request import HTTPRequest
from thsr_ticket.configs.web.parse_html_element import BOOKING_PAGE

def inspect():
    print("Fetching booking page...")
    client = HTTPRequest()
    resp = client.request_booking_page()
    soup = BeautifulSoup(resp.content, 'html.parser')

    print("\n--- Dumping ALL Inputs ---")
    tags = soup.find_all(['input', 'select'])
    for i in tags:
        name = i.get('name')
        val = i.get('value')
        id_attr = i.get('id')
        type_attr = i.get('type', i.name) # Use tag name if type is missing (for select)
        
        # Try to find context (parent text)
        parent = i.parent
        parent_text = parent.text.strip().replace('\n', ' ')[:50] if parent else "No Parent"
        
        # For select, print options
        options_str = ""
        if i.name == 'select':
            opts = [f"{o.get('value')}:{o.text.strip()}" for o in i.find_all('option')]
            options_str = f" Options: {opts}"

        print(f"Tag: {i.name}, Type: {type_attr}, Name: {name}, ID: {id_attr}, Value: {val}, Context: {parent_text}{options_str}")

if __name__ == "__main__":
    inspect()
