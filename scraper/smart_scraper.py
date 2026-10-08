import sys
import os
import time
import json
from playwright.sync_api import sync_playwright
from parser import (parse_toonstream_homepage, parse_toonstream_episodes)

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

NEW_ANIME_NEEDED = 50  # एक बार में 50 एनीमे चेक करेंगे
SLEEP_BETWEEN = 2

DB_FILE = os.path.join(project_root, 'database', 'storage.json')
SKIP_FILE = os.path.join(project_root, 'database', 'skipped.json')

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

def save_skipped(data):
    with open(SKIP_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def fetch_page(url):
    """Playwright का उपयोग करके पेज लोड करता है और एपिसोड लिस्ट का इंतज़ार करता है"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
            })
            
            # पेज पर जाओ
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            # 🚀 यहाँ जादू है: एपिसोड की लिस्ट लोड होने तक 15 सेकंड तक इंतज़ार करो
            try:
                page.wait_for_selector('ul#episode_by_temp', timeout=15000)
                print("   ⏳ Episode list loaded successfully.")
            except Exception as e:
                print(f"   ⚠️ Warning: Episode list selector not found or timed out.")
            
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return None

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 TOONSTREAM MASTER SCRAPER (Episode Loader Fixed)")
    print("=" * 60)

    db_data = load_db()
    skip_data = load_skipped()
    
    existing_anime = db_data.get('anime_list', [])
    existing_ids = set(a['id'] for a in existing_anime)
    skipped_ids = set(skip_data.get('skipped_ids', []))

    print(f"📦 Database में {len(existing_ids)} एनीमे हैं")
    print(f"⏭️ Skip list में {len(skipped_ids)} एनीमे हैं\n")

    # --- सीधे ToonStream के Hindi Dub सेक्शन पर जाओ ---
    print("🔍 ToonStream के Hindi Dub सेक्शन से एनीमे चेक कर रहे हैं...")
    new_anime_list = []
    
    base_url = "https://toonstream.us/series/hindi-dub/" 
    
    homepage_html = fetch_page(base_url)
    
    if homepage_html:
        all_anime = parse_toonstream_homepage(homepage_html, "https://toonstream.us")
        print(f"📄 इस पेज पर कुल {len(all_anime)} एनीमे मिले।")
        
        for a in all_anime:
            if a['id'] not in existing_ids and a['id'] not in skipped_ids:
                new_anime_list.append(a)
                if len(new_anime_list) >= NEW_ANIME_NEEDED:
                    break
    else:
        print("❌ Hindi Dub पेज लोड नहीं हो पाया।")
        exit()

    if not new_anime_list:
        print("\n😔 भाई, कोई नया हिंदी एनीमे नहीं मिला।")
        exit()

    print(f"\n📋 इस बार {len(new_anime_list)} नए हिंदी एनीमे चेक होंगे...\n")

    updated_list = existing_anime.copy()
    scraped_this_run = 0

    for idx, anime in enumerate(new_anime_list):
        print(f"\n[{idx + 1}/{len(new_anime_list)}] {anime['title']}")
        print("  ✅ हिंदी डब है! एपिसोड निकाल रहे हैं...")
        
        anime_html = fetch_page(anime['url'])
        if anime_html:
            episodes = parse_toonstream_episodes(anime_html, "https://toonstream.us")
            print(f"  📺 {len(episodes)} एपिसोड मिले।")
            
            anime['seasons'] = [{"season_number": 1, "episodes": episodes}]
            anime['episodes'] = episodes
            
            updated_list.append(anime)
            scraped_this_run += 1
            print("  💾 Save (Episodes + Hindi Dub)")
        else:
            print("  ❌ एनीमे का पेज लोड नहीं हो पाया।")
        
        time.sleep(SLEEP_BETWEEN)

    if scraped_this_run > 0:
        db_data['anime_list'] = updated_list
        save_db(db_data)
        skip_data['skipped_ids'] = list(skipped_ids)
        save_skipped(skip_data)
        print(f"\n🎉 इस बार {scraped_this_run} हिंदी एनीमे सेव हुए!")
    else:
        print("\n😔 इस बार कोई हिंदी डब एनीमे नहीं मिला।")
        
    print("=" * 60)