import sys
import os
import time
import json
import cloudscraper
from parser import (parse_toonstream_homepage)

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

NEW_ANIME_NEEDED = 20  # एक बार में 20 नए एनीमे लाएंगे
SLEEP_BETWEEN = 2

DB_FILE = os.path.join(project_root, 'database', 'storage.json')
SKIP_FILE = os.path.join(project_root, 'database', 'skipped.json')

scraper = cloudscraper.create_scraper()

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {"anime_list": []}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_skipped():
    if os.path.exists(SKIP_FILE):
        try:
            with open(SKIP_FILE, 'r') as f:
                return json.load(f)
        except: pass
    return {"skipped_ids": []}

def fetch_page(url):
    try:
        response = scraper.get(url, timeout=20)
        if response.status_code == 404: return None
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return None

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 TOONSTREAM SCRAPER (सिर्फ नए एनीमे के लिए)")
    print("=" * 60)

    db_data = load_db()
    skip_data = load_skipped()
    
    existing_anime = db_data.get('anime_list', [])
    existing_ids = set(a['id'] for a in existing_anime)
    skipped_ids = set(skip_data.get('skipped_ids', []))

    print(f"📦 Database में {len(existing_ids)} एनीमे हैं\n")

    # --- ToonStream से नए एनीमे ढूंढें ---
    print("🔍 ToonStream होमपेज से नए एनीमे चेक कर रहे हैं...")
    new_anime_list = []
    
    base_url = "https://toonstream.us/home"
    homepage_html = fetch_page(base_url)
    
    if homepage_html:
        all_anime = parse_toonstream_homepage(homepage_html, "https://toonstream.us")
        print(f"📄 होमपेज पर कुल {len(all_anime)} एनीमे मिले।")
        
        # सिर्फ वही लो जो पहले से डेटाबेस में नहीं हैं
        for a in all_anime:
            if a['id'] not in existing_ids and a['id'] not in skipped_ids:
                new_anime_list.append(a)
                if len(new_anime_list) >= NEW_ANIME_NEEDED:
                    break
    else:
        print("❌ ToonStream का होमपेज लोड नहीं हो पाया।")

    if not new_anime_list:
        print("\n😔 भाई, कोई नया एनीमे नहीं मिला।")
        exit()

    print(f"\n📋 इस बार {len(new_anime_list)} नए एनीमे मिले। इन्हें सेव कर रहे हैं...\n")

    updated_list = existing_anime.copy()

    for idx, anime in enumerate(new_anime_list):
        print(f"[{idx + 1}/{len(new_anime_list)}] {anime['title']}")
        
        # अभी हम सिर्फ बेसिक जानकारी सेव कर रहे हैं (टाइटल, इमेज, लिंक)
        # एपिसोड और हिंदी डब का काम हम अगले स्टेप में करेंगे।
        anime['seasons'] = []
        anime['episodes'] = []
        
        updated_list.append(anime)
        print("  💾 Save (Basic Info)")

    # डेटा सेव करें
    db_data['anime_list'] = updated_list
    save_db(db_data)
    print(f"\n🎉 इस बार {len(new_anime_list)} नए एनीमे सेव हुए!")
    print("=" * 60)