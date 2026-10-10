import sys
import os
import time
import json
from playwright.sync_api import sync_playwright
from parser import (parse_animixstream_homepage, parse_animixstream_episodes)

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

NEW_ANIME_NEEDED = 1  # सिर्फ 1 एनीमे टेस्ट करेंगे
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

def fetch_page(url, wait_for_selector=None):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
            })
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            if wait_for_selector:
                try:
                    page.wait_for_selector(wait_for_selector, timeout=15000)
                except: pass
            else:
                page.wait_for_timeout(5000)
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return None

def fetch_episode_video_url(url):
    """ब्राउज़र खोलकर, अलग-अलग सर्वर पर क्लिक करके master.m3u8 लिंक पकड़ता है"""
    try:
        with sync_playwright() as p:
            # 🚀 headless=False का मतलब है कि ब्राउज़र दिखेगा
            browser = p.chromium.launch(headless=False) 
            page = browser.new_page()
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
            })
            
            video_url = None
            def handle_response(response):
                nonlocal video_url
                if '.m3u8' in response.url and ('master' in response.url or 'index' in response.url):
                    video_url = response.url
                    print(f"      🎯 Caught video URL: {video_url[:70]}...")
            
            page.on('response', handle_response)
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            print("\n      ⚠️ भाई, ब्राउज़र खुल गया है।")
            print("      ⏳ अब हम अलग-अलग सर्वर पर क्लिक करके देखते हैं...")
            
            # 🚀 अलग-अलग सर्वर पर क्लिक करने की कोशिश करो
            servers = ["Server 1", "Server 2", "Server 3"]
            for server in servers:
                if video_url:
                    break # अगर लिंक मिल गया तो रुक जाओ
                
                try:
                    # सर्वर बटन ढूंढो और क्लिक करो
                    server_btn = page.query_selector(f"text='{server}'")
                    if server_btn:
                        print(f"      🖱️ Clicking on {server}...")
                        server_btn.click()
                        # सर्वर बदलने के बाद वीडियो लोड होने का इंतज़ार करो (10 सेकंड)
                        page.wait_for_timeout(10000)
                        
                        # अगर सर्वर पर क्लिक करने के बाद भी लिंक नहीं मिला, तो प्ले बटन पर क्लिक करो
                        if not video_url:
                            page.mouse.click(640, 360)
                            page.wait_for_timeout(5000)
                except Exception as e:
                    print(f"      ⚠️ Could not click {server}: {e}")
                    continue
            
            browser.close()
            return video_url
    except Exception as e:
        print(f"❌ Error fetching video URL for {url}: {e}")
        return None

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 ANIMIXSTREAM SCRAPER (Multi-Server Video Extraction)")
    print("=" * 60)

    db_data = load_db()
    skip_data = load_skipped()
    
    existing_anime = db_data.get('anime_list', [])
    existing_ids = set(a['id'] for a in existing_anime)
    skipped_ids = set(skip_data.get('skipped_ids', []))

    print(f"📦 Database में {len(existing_ids)} एनीमे हैं\n")

    print("🔍 AnimixStream से नए एनीमे चेक कर रहे हैं...")
    new_anime_list = []
    
    base_url = "https://animixstream.com"
    homepage_html = fetch_page(base_url)
    
    if homepage_html:
        all_anime = parse_animixstream_homepage(homepage_html, base_url)
        print(f"📄 होमपेज पर कुल {len(all_anime)} एनीमे मिले।")
        
        for a in all_anime:
            if a['id'] not in existing_ids and a['id'] not in skipped_ids:
                new_anime_list.append(a)
                if len(new_anime_list) >= NEW_ANIME_NEEDED:
                    break
    else:
        print("❌ AnimixStream का होमपेज लोड नहीं हो पाया।")
        exit()

    if not new_anime_list:
        print("\n😔 भाई, कोई नया एनीमे नहीं मिला।")
        exit()

    print(f"\n📋 इस बार {len(new_anime_list)} नए एनीमे चेक होंगे...\n")

    updated_list = existing_anime.copy()
    scraped_this_run = 0

    for idx, anime in enumerate(new_anime_list):
        print(f"\n[{idx + 1}/{len(new_anime_list)}] {anime['title']}")
        print("  ✅ एपिसोड निकाल रहे हैं...")
        
        anime_html = fetch_page(anime['url'])
        if anime_html:
            episodes = parse_animixstream_episodes(anime_html, base_url)
            print(f"  📺 {len(episodes)} एपिसोड मिले। अब वीडियो लिंक निकाल रहे हैं...")
            
            # सिर्फ पहले 1 एपिसोड के वीडियो लिंक निकालो (टेस्टिंग के लिए)
            for i, ep in enumerate(episodes):
                if i < 1: 
                    print(f"    🎬 Fetching video for Episode {i+1}...")
                    video_url = fetch_episode_video_url(ep['url'])
                    if video_url:
                        ep['video_url'] = video_url
                        print(f"    ✅ Video URL found!")
                    else:
                        print(f"    ⚠️ Video URL not found for Episode {i+1}.")
                    time.sleep(1)
                else:
                    ep['video_url'] = ""
            
            anime['seasons'] = [{"season_number": 1, "episodes": episodes}]
            anime['episodes'] = episodes
            
            updated_list.append(anime)
            scraped_this_run += 1
            print("  💾 Save")
        else:
            print("  ❌ एनीमे का पेज लोड नहीं हो पाया।")
        
        time.sleep(SLEEP_BETWEEN)

    if scraped_this_run > 0:
        db_data['anime_list'] = updated_list
        save_db(db_data)
        skip_data['skipped_ids'] = list(skipped_ids)
        save_skipped(skip_data)
        print(f"\n🎉 इस बार {scraped_this_run} एनीमे सेव हुए!")
    else:
        print("\n😔 इस बार कोई एनीमे नहीं मिला।")
        
    print("=" * 60)