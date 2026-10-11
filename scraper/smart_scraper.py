import sys
import os
import time
import json
import re
from playwright.sync_api import sync_playwright
from parser import (parse_animostream_homepage, parse_animostream_episodes)

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

NEW_ANIME_NEEDED = 10  # टेस्टिंग के लिए 10
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

def fetch_videos_for_anime(anime_url, episodes):
    """एक ही पेज पर एपिसोड पर क्लिक करके m3u8 या iframe लिंक निकालता है"""
    video_urls = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                viewport={'width': 1366, 'height': 768}
            )
            
            current_m3u8 = None
            def handle_response(response):
                nonlocal current_m3u8
                if '.m3u8' in response.url or 'master' in response.url:
                    current_m3u8 = response.url
                    print(f"      🎯 Caught m3u8: {current_m3u8[:60]}...")
            
            context.on('response', handle_response)
            page = context.new_page()
            page.goto(anime_url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            
            # सिर्फ पहले 2 एपिसोड टेस्ट करेंगे
            for i, ep in enumerate(episodes[:2]):
                ep_num = ep.get('ep_num')
                if not ep_num: continue
                
                print(f"    🖱️ Clicking Episode {ep_num}...")
                current_m3u8 = None
                video_url = None
                
                # 4 बार कोशिश करेंगे
                for attempt in range(4):
                    if video_url:
                        break
                    try:
                        page.locator(f"div.ep:text-is('{ep_num}')").first.click(timeout=10000)
                        page.wait_for_timeout(10000)  # 10 सेकंड का इंतज़ार
                        
                        # Plyr/VJS का प्ले बटन क्लिक करो
                        if not current_m3u8:
                            play_selectors = ['.plyr__control--overlaid', '.vjs-big-play-button', 'video', '.play-button']
                            for sel in play_selectors:
                                btn = page.locator(sel).first
                                if btn.count() > 0:
                                    btn.click(force=True, timeout=5000)
                                    page.wait_for_timeout(5000)
                                    break
                                
                        if current_m3u8:
                            video_url = current_m3u8
                            print(f"    ✅ m3u8 found for Episode {ep_num}!")
                            break
                            
                        # iframe का src निकालो
                        iframes = page.query_selector_all('iframe')
                        for iframe in iframes:
                            src = iframe.get_attribute('src')
                            if src and 'http' in src and 'player' in src.lower() or (src and 'http' in src and 'embed' in src.lower()):
                                video_url = src
                                print(f"    📺 iframe found for Episode {ep_num}!")
                                break
                        
                        if video_url:
                            break
                            
                    except Exception as e:
                        print(f"      ⚠️ Attempt {attempt+1} failed: {e}")
                
                # अगर फिर भी न मिले, तो HTML सोर्स से ढूंढो
                if not video_url:
                    try:
                        content = page.content()
                        m3u8_match = re.search(r'https?://[^"\']+\.m3u8[^"\']*', content)
                        if m3u8_match:
                            video_url = m3u8_match.group(0)
                            print(f"    🎯 Found m3u8 in HTML for Episode {ep_num}!")
                        else:
                            iframe_match = re.search(r'<iframe[^>]+src=["\'](https?://[^"\']+)["\']', content)
                            if iframe_match:
                                video_url = iframe_match.group(1)
                                print(f"    📺 Found iframe in HTML for Episode {ep_num}!")
                    except: pass
                
                if not video_url:
                    print(f"    ⚠️ No video URL found for Episode {ep_num}.")
                video_urls[ep_num] = video_url or ""
            
            browser.close()
    except Exception as e:
        print(f"❌ Error fetching videos for {anime_url}: {e}")
    
    return video_urls

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 ANIMOSTREAM.XYZ SCRAPER (Enhanced Fallback)")
    print("=" * 60)

    db_data = load_db()
    skip_data = load_skipped()
    
    existing_anime = db_data.get('anime_list', [])
    existing_ids = set(a['id'] for a in existing_anime)
    skipped_ids = set(skip_data.get('skipped_ids', []))

    print(f"📦 Database में {len(existing_ids)} एनीमे हैं\n")

    print("🔍 animostream.xyz से नए एनीमे चेक कर रहे हैं...")
    new_anime_list = []
    
    base_url = "https://www.animostream.xyz/"
    homepage_html = fetch_page(base_url, wait_for_selector='div.grid-item')
    
    if homepage_html:
        all_anime = parse_animostream_homepage(homepage_html, "https://www.animostream.xyz")
        print(f"📄 होमपेज पर कुल {len(all_anime)} एनीमे मिले।")
        
        for a in all_anime:
            if a['id'] not in existing_ids and a['id'] not in skipped_ids:
                new_anime_list.append(a)
                if len(new_anime_list) >= NEW_ANIME_NEEDED:
                    break
    else:
        print("❌ animostream.xyz का होमपेज लोड नहीं हो पाया।")
        exit()

    if not new_anime_list:
        print("\n😔 भाई, कोई नया एनीमे नहीं मिला।")
        exit()

    print(f"\n📋 इस बार {len(new_anime_list)} नए एनीमे चेक होंगे...\n")

    updated_list = existing_anime.copy()
    scraped_this_run = 0

    for idx, anime in enumerate(new_anime_list):
        print(f"\n[{idx + 1}/{len(new_anime_list)}] {anime['title']}")
        print("  ✅ एपिसोड की लिस्ट निकाल रहे हैं...")
        
        anime_html = fetch_page(anime['url'], wait_for_selector='div#episodeList')
        if anime_html:
            episodes = parse_animostream_episodes(anime_html, "https://www.animostream.xyz")
            print(f"  📺 {len(episodes)} एपिसोड मिले। अब वीडियो लिंक निकाल रहे हैं...")
            
            video_urls = fetch_videos_for_anime(anime['url'], episodes)
            
            final_episodes = []
            for ep in episodes:
                ep_num = ep.get('ep_num')
                ep['video_url'] = video_urls.get(ep_num, "")
                final_episodes.append(ep)
            
            anime['seasons'] = [{"season_number": 1, "episodes": final_episodes}]
            anime['episodes'] = final_episodes
            
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