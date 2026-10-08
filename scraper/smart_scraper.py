import sys
import os
import time
import json
from playwright.sync_api import sync_playwright
from parser import (parse_toonstream_homepage, parse_toonstream_episodes)

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

NEW_ANIME_NEEDED = 1  # टेस्टिंग के लिए 1
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
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
            })
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            try:
                page.wait_for_selector('ul#episode_by_temp', timeout=15000)
                print("   ⏳ Episode list loaded successfully.")
            except: pass
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return None

def fetch_episode_video_url(url):
    """Referer हेडर के साथ iframe से m3u8 लिंक निकालता है"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            # 🚀 यहाँ जादू है: Referer सेट करो ताकि rubystm.com को लगे कि हम ToonStream से आए हैं
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 720},
                extra_http_headers={
                    'Referer': 'https://toonstream.us/'
                }
            )
            
            video_url = None
            def handle_response(response):
                nonlocal video_url
                if '.m3u8' in response.url:
                    video_url = response.url
                    print(f"      🎯 Caught video URL: {video_url[:60]}...")
            
            context.on('response', handle_response)
            page = context.new_page()
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            print("      ⏳ Looking for player iframe...")
            try:
                page.wait_for_selector('iframe', timeout=15000)
                iframe = page.query_selector('iframe')
                if iframe:
                    iframe_src = iframe.get_attribute('src')
                    print(f"      ✅ Found iframe: {iframe_src[:60]}...")
                    
                    if iframe_src:
                        print("      ⏳ Navigating to iframe player...")
                        # 🚀 iframe पर जाते समय भी Referer भेजो
                        page.goto(iframe_src, timeout=60000, wait_until="domcontentloaded")
                        page.wait_for_timeout(10000) 
                        
                        try:
                            page.mouse.click(640, 360) 
                            print("      🖱️ Clicked on player area...")
                        except: pass
                        
                        page.wait_for_timeout(15000)
                        
                        # अगर m3u8 नहीं मिला, तो iframe का लिंक ही सेव कर लो
                        if not video_url and iframe_src:
                            video_url = iframe_src
                            print(f"      💾 Using iframe URL as fallback: {video_url[:60]}...")
            except Exception as e:
                print(f"      ⚠️ Iframe Error: {e}")
                
            browser.close()
            return video_url
    except Exception as e:
        print(f"❌ Error fetching video URL for {url}: {e}")
        return None

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 TOONSTREAM MASTER SCRAPER (Referer Bypass)")
    print("=" * 60)

    db_data = load_db()
    skip_data = load_skipped()
    
    existing_anime = db_data.get('anime_list', [])
    existing_ids = set(a['id'] for a in existing_anime)
    skipped_ids = set(skip_data.get('skipped_ids', []))

    print(f"📦 Database में {len(existing_ids)} एनीमे हैं")
    print(f"⏭️ Skip list में {len(skipped_ids)} एनीमे हैं\n")

    print("🔍 ToonStream के Hindi Dub सेक्शन से एनीमे चेक कर रहे हैं...")
    new_anime_list = []
    
    for page_num in [1, 2]: 
        base_url = f"https://toonstream.us/series/hindi-dub/page/{page_num}/" if page_num > 1 else "https://toonstream.us/series/hindi-dub/"
        print(f"  📄 Checking page {page_num}...")
        
        homepage_html = fetch_page(base_url)
        if homepage_html:
            all_anime = parse_toonstream_homepage(homepage_html, "https://toonstream.us")
            print(f"  📄 इस पेज पर कुल {len(all_anime)} एनीमे मिले।")
            
            for a in all_anime:
                if a['id'] not in existing_ids and a['id'] not in skipped_ids:
                    new_anime_list.append(a)
                    if len(new_anime_list) >= NEW_ANIME_NEEDED:
                        break
        if len(new_anime_list) >= NEW_ANIME_NEEDED:
            break

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
            print(f"  📺 {len(episodes)} एपिसोड मिले। अब वीडियो लिंक निकाल रहे हैं...")
            
            for i, ep in enumerate(episodes):
                if i < 1: 
                    print(f"    🎬 Fetching video for Episode {i+1}...")
                    video_url = fetch_episode_video_url(ep['url'])
                    if video_url:
                        ep['video_url'] = video_url
                        print(f"    ✅ Video URL found: {video_url[:50]}...")
                    else:
                        print(f"    ⚠️ Video URL not found for Episode {i+1}.")
                    time.sleep(1)
                else:
                    ep['video_url'] = ""
            
            anime['seasons'] = [{"season_number": 1, "episodes": episodes}]
            anime['episodes'] = episodes
            
            updated_list.append(anime)
            scraped_this_run += 1
            print("  💾 Save (Episodes + Hindi Dub + Video Links)")
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