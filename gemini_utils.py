import os
import google.generativeai as genai
from google.generativeai.client import configure
from google.generativeai.generative_models import GenerativeModel

genai_api_key = os.getenv('GEMINI_API_KEY', 'YOUR_GEMINI_API_KEY')
_model = None

def get_model():
    global _model
    if _model is None:
        configure(api_key=genai_api_key)
        _model = GenerativeModel('gemini-1.5-flash')
    return _model

def generate_gemini_response(prompt):
    model = get_model()
    response = model.generate_content(prompt)
    return response.text.strip() 