import sys
import os
import time
import json
from playwright.sync_api import sync_playwright
from parser import (parse_desidubanime_homepage, parse_desidubanime_anime_detail)

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

NEW_ANIME_NEEDED = 5  # टेस्टिंग के लिए 5 (बाद में 50 कर देंगे)
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

def fetch_video_url(episode_url):
    """एपिसोड पेज से वीडियो लिंक (iframe या m3u8) निकालता है, और ऐड्स ब्लॉक करता है"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 720}
            )
            
            # 🚀 ऐड्स और पॉपअप को तुरंत बंद करो
            context.on("page", lambda page: page.close() if page != context.pages[0] else None)
            
            # 🚀 ऐड डोमेन को ब्लॉक करो
            ad_domains = ['doubleclick', 'popads', 'propellerads', 'adcash', 'exoclick', 'popcash', 'adsterra']
            def block_ads(route):
                if any(ad_domain in route.request.url for ad_domain in ad_domains):
                    route.abort()
                else:
                    route.continue_()
            context.route("**/*", block_ads)
            
            video_url = None
            def handle_response(response):
                nonlocal video_url
                if '.m3u8' in response.url:
                    video_url = response.url
                    print(f"      🎯 Caught m3u8: {video_url[:60]}...")
            
            context.on('response', handle_response)
            page = context.new_page()
            
            page.goto(episode_url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(15000) # 15 सेकंड का इंतज़ार
            
            if not video_url:
                try:
                    iframe = page.query_selector('iframe')
                    if iframe:
                        iframe_src = iframe.get_attribute('src')
                        if iframe_src and 'http' in iframe_src:
                            video_url = iframe_src
                            print(f"      💾 Using iframe URL: {video_url[:60]}...")
                except: pass
            
            browser.close()
            return video_url
    except Exception as e:
        print(f"❌ Error fetching video URL for {episode_url}: {e}")
        return None

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 DESIDUBANIME MASTER SCRAPER (Full Details)")
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
        print("  ✅ डिटेल्स और एपिसोड निकाल रहे हैं...")
        
        anime_html = fetch_page(anime['url'], wait_for_selector='a[href*="/episode/"]')
        if anime_html:
            detail = parse_desidubanime_anime_detail(anime_html, base_url)
            episodes = detail.get('episodes', [])
            anime['description'] = detail.get('description', 'No description available.')
            anime['genres'] = detail.get('genres', [])
            
            print(f"  📝 Description: {'Found' if anime['description'] != 'No description available.' else 'Not found'}")
            print(f"  🏷️ Genres: {', '.join(anime['genres']) if anime['genres'] else 'Not found'}")
            print(f"  📺 {len(episodes)} एपिसोड मिले। अब वीडियो लिंक निकाल रहे हैं...")
            
            for i, ep in enumerate(episodes):
                if i < 2:  # टेस्टिंग के लिए पहले 2 एपिसोड
                    print(f"    🎬 Fetching video for Episode {i+1}...")
                    video_url = fetch_video_url(ep['url'])
                    if video_url:
                        ep['video_url'] = video_url
                        print(f"    ✅ Video URL found!")
                    else:
                        print(f"    ⚠️ Video URL not found.")
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