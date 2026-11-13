import json
import os
import libsql_client

# ⚠️ YAHAN RENDER WALA TURSO URL AUR TOKEN DAALNA
TURSO_URL = "https://animenest-animenest.aws-ap-south-1.turso.io" # Apna URL daalo
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTQxNDMzODgsImlkIjoiMDFhMWJiNDQtM2MwMS03ZjRiLTlmYzQtY2RhODc4NTdjZGViIiwia2lkIjoic0RfVWxIcE1mMDk3d25UemNHdHJTd3R6RjdseXFLbU1pekhTMDZFQkNtWSIsInJpZCI6ImE0ZTFiNzYyLTliMTYtNDY3YS05OTQwLWZjMWJjNmE0NDJkNSJ9.03Cqd1MRuAMJgfXnjUbi9X9a8EmGhnrMGmPBFADI6CuzMqOJMkh2FmtMXYO63Ak2Z5ry-kY0y31JJL0CnnWiBA" # Apna lamba wala token daalo

if TURSO_URL.startswith("libsql://"):
    TURSO_URL = TURSO_URL.replace("libsql://", "https://")

DB_PATH = os.path.join(os.getcwd(), 'database', 'storage.json')

def sync_to_turso():
    print("🔄 Syncing local storage.json to Turso Cloud...")
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