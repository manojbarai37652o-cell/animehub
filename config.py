import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'animehub-super-secret-key-2026'
    DEBUG = True
    # ✅ अब सीक्रेट कोड में नहीं, बल्कि अलग फाइल में रहेगा
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')