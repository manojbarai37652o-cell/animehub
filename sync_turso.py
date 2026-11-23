import json
import os
import libsql_client
from dotenv import load_dotenv

# .env फाइल से टोकन लोड करो
load_dotenv()

# 🛠️ अब टोकन सीधे .env फाइल से आएगा (सुरक्षित तरीका)
TURSO_URL = os.environ.get('TURSO_DATABASE_URL')
TURSO_TOKEN = os.environ.get('TURSO_AUTH_TOKEN')

# अगर .env में URL नहीं है, तो डिफ़ॉल्ट वाला इस्तेमाल करो
if not TURSO_URL:
    TURSO_URL = "https://animenest-animenest.aws-ap-south-1.turso.io"

if TURSO_URL.startswith("libsql://"):
    TURSO_URL = TURSO_URL.replace("libsql://", "https://")

DB_PATH = os.path.join(os.getcwd(), 'database', 'storage.json')

def sync_to_turso():
    print("🔄 Syncing local storage.json to Turso Cloud...")
    
    if not TURSO_TOKEN:
        print("❌ Error: TURSO_AUTH_TOKEN nahi mila! Check your .env file.")
        return

    if not os.path.exists(DB_PATH):
        print("❌ storage.json not found!")
        return

    with open(DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    json_string = json.dumps(data, ensure_ascii=False)
    
    try:
        client = libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)
        client.execute("CREATE TABLE IF NOT EXISTS animenest_db (id INTEGER PRIMARY KEY, json_data TEXT)")
        client.execute("INSERT OR REPLACE INTO animenest_db (id, json_data) VALUES (1, ?)", [json_string])
        print("✅ Successfully synced to Turso Cloud! Website will update now.")
        client.close()
    except Exception as e:
        print(f"❌ Error syncing: {e}")

if __name__ == "__main__":
    sync_to_turso()