import time
import requests
import libsql
import json
import os
from dotenv import load_dotenv  # 🛠️ .env फाइल पढ़ने के लिए

# .env फाइल लोड करो
load_dotenv()

# ==========================================
# 🛠️ अब ये डिटेल्स .env फाइल से आएंगी
# ==========================================
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNEL_ID = '@AnimeNest_Official'
WEBSITE_URL = 'https://animenest-zmbl.onrender.com'

TURSO_URL = "https://animenest-animenest.aws-ap-south-1.turso.io" 
TURSO_AUTH_TOKEN = os.getenv('TURSO_AUTH_TOKEN')

# अगर टोकन नहीं मिला तो स्क्रिप्ट रुक जाएगी
if not BOT_TOKEN or not TURSO_AUTH_TOKEN:
    print("❌ Error: .env file me TELEGRAM_BOT_TOKEN ya TURSO_AUTH_TOKEN nahi mila!")
    exit(1)

PROGRESS_FILE = 'progress.json'

# ==========================================
# 🛑 -1 का मतलब है कि यह प्रोग्रेस फाइल से खुद पढ़ेगा
# ==========================================
MANUAL_START_INDEX = -1 

# ==========================================
# टेलीग्राम पर मैसेज भेजने का फंक्शन
# ==========================================
def send_anime_post(anime):
    try:
        title = anime.get('title', 'Unknown Anime')
        anime_id = anime.get('id', '')
        image_url = anime.get('image', 'https://via.placeholder.com/500x700?text=AnimeNest')
        rating = anime.get('rating', '8.0')
        
        seasons = anime.get('seasons', [])
        
        if seasons and len(seasons) > 0:
            season_no = seasons[0].get('season_number', 1)
            episodes = seasons[0].get('episodes', [])
            total_episodes = len(episodes) if episodes else "N/A"
            
            type_header = f"(S{season_no:02d})"
            details_block = (
                f"• <b>Episode :</b> {total_episodes}\n"
                f"• <b>Season :</b> {season_no:02d}\n"
            )
        else:
            type_header = "(Movie)"
            details_block = ""

        watch_url = f"{WEBSITE_URL}/watch/{anime_id}"

        caption = (
            f"▶️ <b>Name: {title}</b> {type_header}\n"
            f"╭───────────────────────\n"
            f"{details_block}"
            f"• <b>Ratings :</b> {rating} IMDb\n"
            f"• <b>Quality :</b> 480p, 720p, 1080p\n"
            f"• <b>Audio :</b> Hindi\n"
            f"╰───────────────────────\n\n"
            f"👇 <b>Click below to watch now!</b>"
        )

        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "▶️ WATCH NOW ON AnimeNest",
                        "url": watch_url
                    }
                ]
            ]
        }

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {
            'chat_id': CHANNEL_ID,
            'photo': image_url,
            'caption': caption,
            'parse_mode': 'HTML',
            'reply_markup': str(reply_markup).replace("'", '"')
        }

        print(f"⏳ Sending: {title}...")
        response = requests.post(url, data=payload)
        result = response.json()

        if result.get('ok'):
            print(f"✅ Successfully posted: {title}")
            return True
        else:
            print(f"❌ Failed to post {title}. Error: {result.get('description')}")
            return False

    except Exception as e:
        print(f"❌ Error processing {anime.get('title')}: {e}")
        return False

# ==========================================
# Turso से डेटा लाने का फंक्शन
# ==========================================
def fetch_anime_from_turso():
    print("🔄 Turso से डेटा ला रहे हैं...")
    conn = libsql.connect(TURSO_URL, auth_token=TURSO_AUTH_TOKEN)
    cursor = conn.execute("SELECT json_data FROM animenest_db LIMIT 1")
    row = cursor.fetchone()
    
    anime_list = []
    if row and row[0]:
        try:
            data_dict = json.loads(row[0])
            anime_list = data_dict.get('anime_list', [])
        except Exception as e:
            print(f"❌ JSON Parse Error: {e}")
        
    conn.close() 
    return anime_list

# ==========================================
# प्रोग्रेस सेव करने और पढ़ने का फंक्शन
# ==========================================
def load_progress():
    if MANUAL_START_INDEX != -1:
        return MANUAL_START_INDEX
        
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r') as f:
                data = json.load(f)
                return data.get('last_index', 0)
        except:
            return 0
    return 0

def save_progress(index):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({'last_index': index}, f)

# ==========================================
# मेन एक्जीक्यूशन
# ==========================================
def main():
    print("🚀 Starting Telegram Auto-Poster...")
    
    anime_list = fetch_anime_from_turso()
    
    if not anime_list:
        print("❌ Turso में कोई डेटा नहीं मिला।")
        return

    start_index = load_progress()
    print(f"✅ कुल {len(anime_list)} एनीमे मिले।")
    print(f"📍 अब यह {start_index} नंबर के एनीमे से शुरू हो रहा है...")

    if start_index >= len(anime_list):
        print("🎉 सारे एनीमे पहले ही पोस्ट हो चुके हैं!")
        return

    try:
        for i in range(start_index, len(anime_list)):
            anime = anime_list[i]
            
            success = send_anime_post(anime)
            
            if success:
                save_progress(i + 1)
                
            time.sleep(5) 
            
    except KeyboardInterrupt:
        print("\n🛑 स्क्रिप्ट को रोका गया! प्रोग्रेस सेव हो गई है।")
    except Exception as e:
        print(f"\n❌ कुछ गड़बड़ हुई: {e}")
    finally:
        print("👋 बाय भाई!")

if __name__ == '__main__':
    main()