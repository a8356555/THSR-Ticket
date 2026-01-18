import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

class GeminiCaptchaSolver:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables or .env file.")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-flash-latest')

    def solve(self, image_bytes: bytes) -> str:
        """
        Solves the CAPTCHA using Gemini Flash model.
        Returns the 4-character alphanumeric code.
        """
        prompt = "This is a CAPTCHA image with 4 alphanumeric characters. Output ONLY the characters in the image, without spaces or special characters."
        
        response = self.model.generate_content([
            {'mime_type': 'image/jpeg', 'data': image_bytes},
            prompt
        ])
        
        # Simple cleanup: remove whitespace and potential markdown formatting
        text = response.text.strip().replace(" ", "").replace("\n", "").replace("`", "")
        
        # Use regex to find the first sequence of 4 alphanumeric characters
        match = re.search(r'[A-Za-z0-9]{4}', text)
        if match:
            return match.group(0)
        return text
