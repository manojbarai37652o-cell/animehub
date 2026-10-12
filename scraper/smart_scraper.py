import sys
import os
import time
import json
import cloudscraper
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright # 🛠️ मूवी के m3u8 लिंक के लिए

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from parser import (parse_anime_homepage, parse_post_id, parse_season_ajax,
                    parse_video_link, parse_release_year, parse_season_episodes,
                    extract_language_from_detail)

MIN_YEAR = 2000
BATCH_SIZE = 50
SLEEP_BETWEEN = 2
MAX_PAGES_TO_CHECK = 500

PROGRESS_FILE = os.path.join(project_root, 'database', 'progress.json')
DB_FILE = os.path.join(project_root, 'database', 'storage.json')

# Cloudflare bypass
scraper = cloudscraper.create_scraper()

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except: pass
    return {"last_page": 1, "total_scraped": 0}

def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=4)

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

def fetch_page(url):
    try:
        response = scraper.get(url, timeout=20)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def fetch_season_ajax(post_id, season_num):
    """AJAX call से Season 2, 3, 4... के episodes निकालता है"""
    ajax_url = f"https://animesalt.cx/wp-admin/admin-ajax.php?action=action_select_season&season={season_num}&post_id={post_id}"
    try:
        response = scraper.get(ajax_url, timeout=20)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"   ❌ AJAX Error: {e}")
        return None

# 🛠️ FIX: ये नया फंक्शन मूवी का m3u8 लिंक निकालेगा (iframe के अंदर तक जाकर)
def fetch_movie_video_with_playwright(url):
    """Playwright का इस्तेमाल करके मूवी का m3u8 वीडियो लिंक निकालता है"""
    print(f"   🎬 Playwright से मूवी वीडियो लिंक ढूंढ रहे हैं...")
    found_video = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-ipv6"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = context.new_page()
            
            # हर रिक्वेस्ट को चेक करो
            def handle_response(response):
                nonlocal found_video
                if '.m3u8' in response.url and not found_video:
                    found_video = response.url
                    print(f"   🎯 Caught m3u8: {found_video[:70]}...")

            page.on('response', handle_response)
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            # 10 सेकंड का इंतज़ार करो ताकि iframe और उसके अंदर के एड्स लोड हो जाएं
            page.wait_for_timeout(10000)
            
            # अगर अभी तक नहीं मिला, तो iframes में जाकर देखो
            if not found_video:
                iframes = page.query_selector_all('iframe')
                for iframe in iframes:
                    src = iframe.get_attribute('src')
                    if src and ('ravok' in src or 'player' in src or 'video' in src or 'embed' in src):
                        print(f"   🌐 Iframe मिला, उसके अंदर जा रहे हैं: {src[:50]}...")
                        try:
                            # नए पेज में iframe का URL खोलो
                            iframe_page = context.new_page()
                            iframe_page.on('response', handle_response)
                            iframe_page.goto(src, timeout=30000, wait_until="domcontentloaded")
                            iframe_page.wait_for_timeout(8000)
                            
                            # अगर अभी भी नहीं मिला, तो iframe के अंदर Play बटन दबाओ
                            if not found_video:
                                try:
                                    iframe_page.locator('video, .play-btn, .vjs-big-play-button, button:has-text("Play")').first.click(timeout=3000)
                                    iframe_page.wait_for_timeout(5000)
                                except: pass
                            iframe_page.close()
                        except Exception as e:
                            print(f"   ❌ Iframe Error: {e}")
                    if found_video: break

            # आखिरी कोशिश: HTML में सीधा m3u8 ढूंढो
            if not found_video:
                content = page.content()
                import re
                match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', content)
                if match:
                    found_video = match.group(1)
                    print(f"   🎯 Caught m3u8 from HTML: {found_video[:70]}...")

            browser.close()
    except Exception as e:
        print(f"   ❌ Playwright Error: {e}")
        
    return found_video


if __name__ == '__main__':
    print("=" * 60)
    print("📺 SCRAPER चालू (होमपेज + A-Z लेटर)")
    print("=" * 60)

    db_data = load_db()
    existing_anime = db_data.get('anime_list', [])
    existing_ids = set(a['id'] for a in existing_anime)

    print(f"📊 Database: {len(existing_ids)} anime\n")

    new_anime = []
    scraped_this_run = 0
    updated_list = existing_anime.copy()
    
    # 🛠️ FIX: पहले होमपेज चेक करेंगे, फिर A-Z लेटर
    import string
    letters = [''] + list(string.ascii_uppercase) 
    
    MAX_PAGES_PER_SECTION = 5 

    for letter in letters:
        if len(new_anime) >= BATCH_SIZE:
            break
            
        if letter == '':
            print(f"\n🏠 होमपेज चेक कर रहे हैं...")
            base_url_pattern = "https://animesalt.cx/?page={}"
        else:
            print(f"\n🔍 Letter {letter} चेक कर रहे हैं...")
            base_url_pattern = f"https://animesalt.cx/letter/{letter}/?page={{}}"
        
        page_num = 1
        while page_num <= MAX_PAGES_PER_SECTION:
            base_url = base_url_pattern.format(page_num)
            
            try:
                homepage_html = fetch_page(base_url)
                if not homepage_html:
                    break

                all_anime = parse_anime_homepage(homepage_html, "https://animesalt.cx/")
                if not all_anime:
                    break

                page_new_anime = [a for a in all_anime if a['id'] not in existing_ids]
                
                if not page_new_anime:
                    print(f"   ⏭️ Page {page_num} पर कुछ नया नहीं मिला। अगले लेटर पर जा रहे हैं।")
                    break
                
                for a in page_new_anime:
                    if a not in new_anime:
                        new_anime.append(a)
                        if len(new_anime) >= BATCH_SIZE:
                            break
                
                print(f"   📊 Page {page_num} पर {len(page_new_anime)} नए आइटम मिले (कुल जुटाए: {len(new_anime)})")

                if len(new_anime) >= BATCH_SIZE:
                    break

                page_num += 1
                time.sleep(1) 
                
            except Exception as e:
                print(f"   ❌ Page {page_num} पर एरर: {e}. अगले पेज पर जा रहे हैं...")
                page_num += 1
                continue

        if len(new_anime) >= BATCH_SIZE:
            print(f"\n🎯 हमें {BATCH_SIZE} नए एनीमे मिल गए! अब इन्हें प्रोसेस करते हैं।")
            break

    if not new_anime:
        print("\n👋 सारे लेटर चेक हो गए! कोई नया आइटम नहीं मिला।")
        exit()

    print(f"\n✅ {len(new_anime)} एनीमे चेक कर रहे हैं...\n")

    for idx, anime in enumerate(new_anime[:BATCH_SIZE]):
        print(f"\n[{idx + 1}/{min(BATCH_SIZE, len(new_anime))}] {anime['title']}")
        
        anime_html = fetch_page(anime['url'])
        if not anime_html:
            continue

        language = extract_language_from_detail(anime_html)
        anime['language'] = language
        print(f"   🌐 Language: {language}")

        year = parse_release_year(anime_html)
        if year and year < MIN_YEAR:
            print(f"   ⚠️ बहुत पुराना ({year}), skip")
            continue

        post_id = parse_post_id(anime_html)
        if not post_id:
            continue

        print(f"   📌 Post ID: {post_id}")

        anime_seasons = []
        season_num = 1

        while season_num <= 15:
            if season_num == 1:
                episodes = parse_season_episodes(anime_html, anime['url'])
            else:
                season_html = fetch_season_ajax(post_id, season_num)
                if not season_html or len(season_html.strip()) < 50:
                    break
                episodes = parse_season_ajax(season_html, anime['url'])

            if not episodes:
                break

            print(f"   📺 Season {season_num}: {len(episodes)} episodes")

            for ep in episodes[:3]:
                ep_html = fetch_page(ep['url'])
                if ep_html:
                    ep['video_url'] = parse_video_link(ep_html, ep['url'])
                else:
                    ep['video_url'] = ""
                time.sleep(1)

            for ep in episodes[3:]:
                ep['video_url'] = ""

            anime_seasons.append({
                "season_number": season_num,
                "episodes": episodes
            })
            season_num += 1
            time.sleep(1)

        if anime_seasons:
            anime['seasons'] = anime_seasons
            anime['episodes'] = anime_seasons[0]['episodes']
            total_eps = sum(len(s['episodes']) for s in anime_seasons)
            print(f"   💾 Save (Series)! {len(anime_seasons)} Season, {total_eps} Episodes")
        else:
            # 🛠️ FIX: ये मूवी है! Playwright से सीधा m3u8 लिंक निकालो
            movie_video = fetch_movie_video_with_playwright(anime['url'])
            
            anime['seasons'] = [{
                "season_number": 1,
                "episodes": [{
                    "title": "Full Movie",
                    "ep_num": "1",
                    "video_url": movie_video
                }]
            }]
            anime['episodes'] = anime['seasons'][0]['episodes']
            
            if movie_video:
                print(f"   💾 Save (Movie)! वीडियो लिंक के साथ सेव कर रहे हैं।")
            else:
                print(f"   ⚠️ Save (Movie) without video link. (Video nahi mila)")

        updated_list.append(anime)
        scraped_this_run += 1

        if scraped_this_run % 3 == 0:
            db_data['anime_list'] = updated_list
            save_db(db_data)

        time.sleep(SLEEP_BETWEEN)

    if scraped_this_run > 0:
        db_data['anime_list'] = updated_list
        save_db(db_data)
        print(f"\n🎉 {scraped_this_run} anime saved!")
    else:
        print("\n⚠️ कोई नया एनीमे सेव नहीं हुआ।")

    print("=" * 60)