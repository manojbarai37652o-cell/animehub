import sys
import os
import time
import json
import re
import string
import argparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from scraper.parser import (parse_post_id, parse_season_episodes,
                            parse_video_link, extract_language_from_detail)

DB_FILE = os.path.join(project_root, 'database', 'storage.json')
BASE_URL = "https://animesalt.cx"

# =========================================================
# 🛠️ सेटिंग्स
# =========================================================
MIN_YEAR = 1950
BATCH_SIZE = 999999          
SLEEP_BETWEEN = 3  
MAX_PAGES_PER_SECTION = 100        
MAX_CONSECUTIVE_EMPTY_PAGES = 3  

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {"anime_list": []}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def extract_anime_list_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    anime_list = []
    items = soup.find_all('li', id=re.compile(r'^post-\d+'))
    
    for item in items:
        try:
            title_tag = item.find('h2', class_='entry-title')
            link_tag = item.find('a', class_='lnk-blk')
            if not title_tag or not link_tag: continue
            
            title = title_tag.get_text(strip=True)
            href = link_tag['href']
            if not href.startswith('http'): href = BASE_URL + href
            
            anime_type = "Series"
            if '/movies/' in href: anime_type = "Movie"
            elif '/series/' in href: anime_type = "Series"
            
            img_tag = item.find('img')
            image = ""
            if img_tag:
                image = img_tag.get('data-src') or img_tag.get('src') or ""
                if image.startswith('//'): 
                    image = 'https:' + image
                elif image.startswith('/'): 
                    image = BASE_URL + image
                if 'animesalt.cx' in image and 'tmdb' in image.lower():
                    image = ""

            if not any(a['url'] == href for a in anime_list):
                anime_list.append({'title': title, 'url': href, 'image': image, 'type': anime_type})
        except: continue
    return anime_list

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="AnimeNest Smart Scraper")
    parser.add_argument('--letter', type=str, default='all', help="Letter to scrape (e.g., S, A, B) or 'all'")
    args = parser.parse_args()

    print("=" * 60)
    print("📺 SMART SCRAPER चालू (FULL MASTER MODE)")
    print("🛑 रोकने के लिए Ctrl + C दबाओ")
    print("=" * 60)

    db_data = load_db()
    existing_anime = db_data.get('anime_list', [])
    existing_urls = set(a.get('url', '') for a in existing_anime if a.get('url'))
    updated_list = existing_anime.copy()
    new_anime = []

    try:
        # 🛠️ अब पूरा कोड सिर्फ एक ही Playwright ब्राउज़र के अंदर चलेगा
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--disable-ipv6", "--no-sandbox"])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
            page = context.new_page()
            page.set_default_timeout(90000)

            # --- स्टेप 1: लिस्ट निकालना ---
            if args.letter.lower() == 'all':
                letters = ['home'] + list(string.ascii_uppercase)
            else:
                letters = [args.letter.upper()]

            for letter in letters:
                if len(new_anime) >= BATCH_SIZE: break
                
                if letter == 'home':
                    base_url_pattern = f"{BASE_URL}/page/{{}}/"
                else:
                    base_url_pattern = f"{BASE_URL}/letter/{letter}/page/{{}}/"
                
                print(f"\n🔍 Letter {letter} चेक कर रहे हैं...")
                page_num = 1
                consecutive_empty = 0
                
                while page_num <= MAX_PAGES_PER_SECTION:
                    if letter == 'home' and page_num > 1:
                        print(f"   ✅ होमपेज का सिर्फ 1 पेज होता है, अगले लेटर पर जा रहे हैं।")
                        break

                    base_url = base_url_pattern.format(page_num)
                    try:
                        print(f"   🌐 Loading: {base_url}")
                        response = page.goto(base_url, wait_until="domcontentloaded", timeout=90000)
                        
                        if response and response.status == 404:
                            print(f"   ⚠️ पेज {page_num} मौजूद नहीं है (404 Not Found)।")
                            break

                        try:
                            page.wait_for_selector('li[id^="post-"]', timeout=15000)
                        except:
                            pass

                        page.wait_for_timeout(2000)
                        html = page.content()
                        page_anime = extract_anime_list_from_html(html)
                        
                        if not page_anime:
                            consecutive_empty += 1
                            print(f"   ⚠️ पेज {page_num} खाली है (लगातार {consecutive_empty} पेज खाली)")
                            if consecutive_empty >= MAX_CONSECUTIVE_EMPTY_PAGES: 
                                print(f"   ✅ Letter {letter} के सारे पेज चेक हो गए।")
                                break
                        else:
                            consecutive_empty = 0
                            added_count = 0
                            for a in page_anime:
                                if a['url'] not in existing_urls and a['url'] not in [x['url'] for x in new_anime]:
                                    new_anime.append(a)
                                    added_count += 1
                            print(f"   📊 पेज {page_num} पर {added_count} नए एनीमे मिले (कुल: {len(new_anime)})")
                        
                        page_num += 1
                        time.sleep(SLEEP_BETWEEN)
                    except Exception as e:
                        print(f"   ❌ Page {page_num} एरर: {e}")
                        consecutive_empty += 1
                        if consecutive_empty >= MAX_CONSECUTIVE_EMPTY_PAGES: break
                        page_num += 1

            if not new_anime:
                print("\n👋 कोई नया एनीमे नहीं मिला।")
                browser.close()
                sys.exit(0)

            print(f"\n✅ कुल {len(new_anime)} नए एनीमे मिले। डिटेल निकाल रहे हैं...\n")
            scraped_this_run = 0

            # --- स्टेप 2: डिटेल्स और iframe निकालना (उसी ब्राउज़र का इस्तेमाल करके) ---
            for idx, anime in enumerate(new_anime[:BATCH_SIZE]):
                print(f"\n[{idx + 1}/{len(new_anime)}] {anime['title']} ({anime['type']})")
                
                try:
                    page.goto(anime['url'], wait_until="domcontentloaded", timeout=90000)
                    page.wait_for_timeout(3000)
                    html = page.content()

                    anime['language'] = extract_language_from_detail(html)
                    post_id = parse_post_id(html)
                    anime['id'] = str(post_id) if post_id else str(abs(hash(anime['url'])))
                    print(f"   🌐 Language: {anime['language']} | 📌 ID: {anime['id']}")

                    anime_seasons = []

                    if anime['type'] == 'Series':
                        season_btns = page.query_selector_all('.season-btn')
                        
                        if not season_btns:
                            episodes = parse_season_episodes(html, anime['url'])
                            if episodes:
                                print(f"   📺 Season 1: {len(episodes)} episodes")
                                for ep in episodes:
                                    try:
                                        page.goto(ep['url'], wait_until="domcontentloaded", timeout=90000)
                                        page.wait_for_timeout(1500)
                                        ep['video_url'] = parse_video_link(page.content(), ep['url'])
                                    except: ep['video_url'] = ""
                                anime_seasons.append({"season_number": 1, "episodes": episodes})
                        else:
                            season_nums = sorted(list(set([int(btn.get_attribute('data-season')) for btn in season_btns if btn.get_attribute('data-season')])))
                            print(f"   📺 पाए गए सीज़न: {season_nums}")
                            
                            for season_num in season_nums:
                                btn = page.query_selector(f'.season-btn[data-season="{season_num}"]')
                                if btn:
                                    btn.click()
                                    page.wait_for_timeout(2000)
                                    season_html = page.content()
                                    episodes = parse_season_episodes(season_html, anime['url'])
                                    if episodes:
                                        print(f"   📺 Season {season_num}: {len(episodes)} episodes")
                                        for ep in episodes:
                                            try:
                                                page.goto(ep['url'], wait_until="domcontentloaded", timeout=90000)
                                                page.wait_for_timeout(1500)
                                                ep['video_url'] = parse_video_link(page.content(), ep['url'])
                                            except: ep['video_url'] = ""
                                        anime_seasons.append({"season_number": season_num, "episodes": episodes})
                        
                        if anime_seasons:
                            anime['seasons'] = anime_seasons
                            anime['episodes'] = anime_seasons[0]['episodes']
                            print(f"   💾 Save (Series)!")
                            updated_list.append(anime)
                            scraped_this_run += 1
                        else:
                            continue

                    elif anime['type'] == 'Movie':
                        movie_iframe = ""
                        iframes = page.query_selector_all('iframe')
                        for iframe in iframes:
                            src = iframe.get_attribute('src')
                            if src:
                                if src.startswith('//'): src = 'https:' + src
                                if 'ravok.buzz' in src or 'video' in src.lower() or 'player' in src.lower():
                                    movie_iframe = src
                                    break
                        
                        if movie_iframe:
                            anime['seasons'] = [{"season_number": 1, "episodes": [{"title": "Full Movie", "ep_num": "1", "video_url": movie_iframe}]}]
                            anime['episodes'] = anime['seasons'][0]['episodes']
                            print(f"   💾 Save (Movie)!")
                            updated_list.append(anime)
                            scraped_this_run += 1
                        else:
                            continue

                    db_data['anime_list'] = updated_list
                    save_db(db_data)
                    time.sleep(SLEEP_BETWEEN)
                    
                except Exception as e:
                    print(f"   ❌ एरर: {e}")
                    continue
            
            browser.close()

    except KeyboardInterrupt:
        print("\n\n🛑 स्क्रैपिंग यूजर द्वारा रोक दी गई!")

    db_data['anime_list'] = updated_list
    save_db(db_data)
    print(f"\n🎉 कुल {len(updated_list)} एनीमे डेटाबेस में सेव हैं!")
    print("=" * 60)
    sys.exit(0)