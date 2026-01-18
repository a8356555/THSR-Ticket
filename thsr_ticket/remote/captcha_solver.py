import os
import re
import google.generativeai as genai
import ddddocr
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
        if match:
            return match.group(0)
        return text

class DdddOcrCaptchaSolver:
    def __init__(self):
        self.ocr = ddddocr.DdddOcr()

    def solve(self, image_bytes: bytes) -> str:
        """
        Solves the CAPTCHA using ddddocr.
        Returns the alphanumeric code.
        """
        res = self.ocr.classification(image_bytes)
        return res

class HybridCaptchaSolver:
    """
    OCR first then Gemini
    Lazy load Gemini to avoid API costs or initialization errors until absolutely necessary
    """
    def __init__(self):
        self.ocr_solver = DdddOcrCaptchaSolver()
        self.gemini_solver = None
        
    def _get_gemini_solver(self):
        if not self.gemini_solver:
            self.gemini_solver = GeminiCaptchaSolver()
        return self.gemini_solver
    
    def solve_ocr(self, image_bytes: bytes) -> str:
        return self.ocr_solver.solve(image_bytes)

    def solve_gemini(self, image_bytes: bytes) -> str:
        return self._get_gemini_solver().solve(image_bytes)


