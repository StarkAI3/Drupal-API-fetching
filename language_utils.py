import re

def detect_language(text):
    # Marathi Unicode range: \u0900-\u097F
    if re.search(r'[\u0900-\u097F]', text):
        return 'mr'
    return 'en' 