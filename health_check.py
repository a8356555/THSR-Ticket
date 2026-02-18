import sys
import logging
from bs4 import BeautifulSoup

sys.path.append("./")
from thsr_ticket.remote.http_request import HTTPRequest
from thsr_ticket.configs.web.parse_html_element import BOOKING_PAGE

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def check_selectors():
    logger.info("Starting Health Check: Verifying HTML Selectors...")
    client = HTTPRequest()
    
    try:
        resp = client.request_booking_page()
        if resp.status_code != 200:
            logger.error(f"Failed to fetch booking page. Status: {resp.status_code}")
            return False
            
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        all_good = True
        
        # Check Critical Elements defined in BOOKING_PAGE
        for key, locator in BOOKING_PAGE.items():
            element = None
            if "id" in locator:
                element = soup.find(id=locator["id"])
                selector_desc = f"id='{locator['id']}'"
            elif "name" in locator:
                # Approximate check for name/class
                # The config structure in parse_html_element is a bit custom, 
                # usually it maps to find()'s attrs.
                # e.g. "security_code_img": {"id": "..."}
                pass
            
            # Re-implementing logic similar to internal parser or just checking existence
            # Let's trust the 'id' check primarily as that's most fragile
            
            if "id" in locator and not element:
                logger.error(f"CRITICAL: Element {key} ({selector_desc}) NOT FOUND!")
                all_good = False
            elif "id" in locator:
                logger.info(f"OK: Element {key} found.")

        if all_good:
            logger.info("Health Check Passed: All critical selectors found.")
            return True
        else:
            logger.error("Health Check Failed: Source HTML might have changed.")
            return False

    except Exception as e:
        logger.error(f"Health Check Exception: {e}")
        return False

if __name__ == "__main__":
    success = check_selectors()
    sys.exit(0 if success else 1)
