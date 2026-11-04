import os

class Config:
    # ✅ अब सीक्रेट की सिर्फ .env या Render Environment Variables से आएगी
    # अगर ये नहीं मिली, तो ऐप रुक जाएगा (जो कि सिक्योरिटी के लिए सही है)
    SECRET_KEY = os.environ.get('SECRET_KEY') 
    
    # 🔴 सबसे जरूरी: DEBUG को हमेशा False रखेंगे (लाइव साइट पर सुरक्षा के लिए)
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # गूगल लॉगिन (अगर इस्तेमाल करना हो)
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')

    # 🛡️ Rate Limiting (स्पैम रोकने के लिए - 1 मिनट में 200 रिक्वेस्ट)
    RATELIMIT_DEFAULT = "200 per minute"
    RATELIMIT_STORAGE_URI = "memory://"