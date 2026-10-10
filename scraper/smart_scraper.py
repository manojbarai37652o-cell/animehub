import sys
import os
import time
import json
from playwright.sync_api import sync_playwright
from parser import (parse_desidubanime_homepage, parse_desidubanime_episodes)

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

NEW_ANIME_NEEDED = 5  # टेस्टिंग के लिए 5
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

def fetch_episode_video_url(episode_url):
    """एपिसोड पेज से असली m3u8 लिंक निकालता है (iframe के अंदर जाकर)"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
            })
            
            video_url = None
            def handle_response(response):
                nonlocal video_url
                if '.m3u8' in response.url:
                    video_url = response.url
                    print(f"      🎯 Caught m3u8: {video_url[:60]}...")
            
            page.on('response', handle_response)
            page.goto(episode_url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            
            # iframe ढूंढो
            iframe_url = None
            iframes = page.query_selector_all('iframe')
            for iframe in iframes:
                src = iframe.get_attribute('src')
                if src and 'http' in src and ('filesforever' in src or 'embed' in src or 'player' in src):
                    iframe_url = src
                    break
            
            if iframe_url:
                print(f"      🔄 Found iframe. Navigating inside: {iframe_url[:50]}...")
                # iframe के अंदर जाओ
                page.goto(iframe_url, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(10000) # वीडियो लोड होने का इंतज़ार
                
                # अगर फिर भी न मिले, तो बीच में क्लिक करो
                if not video_url:
                    page.mouse.click(640, 360)
                    page.wait_for_timeout(8000)
            else:
                print("      ⚠️ No suitable iframe found, clicking main player area...")
                page.mouse.click(640, 360)
                page.wait_for_timeout(10000)

            browser.close()
            return video_url
    except Exception as e:
        print(f"❌ Error fetching video for {episode_url}: {e}")
        return None

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 DESIDUBANIME MASTER SCRAPER (Deep m3u8 Extraction)")
    print("=" * 60)

    db_data = load_db()
    skip_data = load_skipped()
    
    existing_anime = db_data.get('anime_list', [])
    existing_ids = set(a['id'] for a in existing_anime)
    skipped_ids = set(skip_data.get('skipped_ids', []))

    print(f"📦 Database में {len(existing_ids)} एनीमे हैं\n")

    print("🔍 DesiDubAnime से नए एनीमे चेक कर रहे हैं...")
    new_anime_list = []
    
    base_url = "https://www.desidubanime.me"
    homepage_html = fetch_page(base_url, wait_for_selector='article.anime-card')
    
    if homepage_html:
        all_anime = parse_desidubanime_homepage(homepage_html, base_url)
        print(f"📄 होमपेज पर कुल {len(all_anime)} एनीमे मिले।")
        
        for a in all_anime:
            if a['id'] not in existing_ids and a['id'] not in skipped_ids:
                new_anime_list.append(a)
                if len(new_anime_list) >= NEW_ANIME_NEEDED:
                    break
    else:
        print("❌ DesiDubAnime का होमपेज लोड नहीं हो पाया।")
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
        
        anime_html = fetch_page(anime['url'], wait_for_selector='a[href*="/episode/"]')
        if anime_html:
            episodes = parse_desidubanime_episodes(anime_html, base_url)
            print(f"  📺 {len(episodes)} एपिसोड मिले। अब असली m3u8 लिंक निकाल रहे हैं...")
            
            for i, ep in enumerate(episodes):
                if i < 2: # टेस्टिंग के लिए पहले 2 एपिसोड
                    print(f"    🎬 Fetching video for Episode {i+1}...")
                    video_url = fetch_episode_video_url(ep['url'])
                    if video_url:
                        ep['video_url'] = video_url
                        print(f"    ✅ Real m3u8 URL found!")
                    else:
                        print(f"    ⚠️ Real m3u8 URL not found.")
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