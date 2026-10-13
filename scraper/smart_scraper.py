import sys
import os
import time
import json
import cloudscraper
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from scraper.parser import (parse_anime_homepage, parse_post_id, parse_season_episodes,
                            parse_release_year, extract_language_from_detail)

MIN_YEAR = 2000
BATCH_SIZE = 35
SLEEP_BETWEEN = 1
MAX_PAGES_PER_SECTION = 5

DB_FILE = os.path.join(project_root, 'database', 'storage.json')
scraper = cloudscraper.create_scraper()

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {"anime_list": []}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def fetch_page(url):
    try:
        response = scraper.get(url, timeout=20)
        if response.status_code == 404: return None
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == '__main__':
    print("=" * 60)
    print("📺 SMART SCRAPER (सिर्फ मेटाडेटा सेव करेगा, वीडियो लिंक नहीं)")
    print("=" * 60)

    db_data = load_db()
    existing_anime = db_data.get('anime_list', [])
    existing_ids = set(a['id'] for a in existing_anime)
    updated_list = existing_anime.copy()
    print(f"📊 Database में {len(existing_ids)} एनीमे हैं।\n")

    new_anime = []
    import string
    letters = [''] + list(string.ascii_uppercase)

    for letter in letters:
        if len(new_anime) >= BATCH_SIZE: break
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
                if not homepage_html: break
                all_anime = parse_anime_homepage(homepage_html, "https://animesalt.cx/")
                if not all_anime: break
                page_new_anime = [a for a in all_anime if a['id'] not in existing_ids]
                if not page_new_anime:
                    print(f"   ⏭️ Page {page_num} पर कुछ नया नहीं मिला।")
                    break
                for a in page_new_anime:
                    if a not in new_anime:
                        new_anime.append(a)
                        if len(new_anime) >= BATCH_SIZE: break
                print(f"   📊 Page {page_num} पर {len(page_new_anime)} नए मिले (कुल: {len(new_anime)})")
                if len(new_anime) >= BATCH_SIZE: break
                page_num += 1
                time.sleep(1)
            except Exception as e:
                print(f"   ❌ Page {page_num} पर एरर: {e}.")
                page_num += 1
                continue

    if not new_anime:
        print("\n👋 कोई नया एनीमे नहीं मिला।")
        exit()

    print(f"\n✅ {len(new_anime)} नए एनीमे चेक कर रहे हैं...\n")
    scraped_this_run = 0

    for idx, anime in enumerate(new_anime[:BATCH_SIZE]):
        print(f"\n[{idx + 1}/{min(BATCH_SIZE, len(new_anime))}] {anime['title']}")
        
        anime_html = fetch_page(anime['url'])
        if not anime_html: continue

        language = extract_language_from_detail(anime_html)
        anime['language'] = language
        print(f"   🌐 Language: {language}")

        year = parse_release_year(anime_html)
        if year and year < MIN_YEAR:
            print(f"   ⚠️ बहुत पुराना ({year}), skip")
            continue

        post_id = parse_post_id(anime_html)
        if not post_id: continue
        print(f"   📌 Post ID: {post_id}")

        anime_seasons = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--disable-ipv6"])
                page = browser.new_page()
                page.goto(anime['url'], timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                season_btns = page.query_selector_all('.season-btn')
                
                if not season_btns:
                    episodes = parse_season_episodes(anime_html, anime['url'])
                    if episodes:
                        anime_seasons.append({"season_number": 1, "episodes": episodes})
                        print(f"   📺 Season 1: {len(episodes)} episodes")
                else:
                    print(f"   📺 पाए गए सीज़न: {len(season_btns)}")
                    for btn in season_btns:
                        try:
                            season_num = int(btn.get_attribute('data-season'))
                        except: continue
                        
                        print(f"   ⚙️ Processing Season {season_num}...")
                        btn.click()
                        page.wait_for_timeout(2500)
                        
                        season_html = page.content()
                        episodes = parse_season_episodes(season_html, anime['url'])
                        
                        if episodes:
                            print(f"   📺 Season {season_num}: {len(episodes)} episodes")
                            anime_seasons.append({"season_number": season_num, "episodes": episodes})
                browser.close()
        except Exception as e:
            print(f"   ❌ Playwright Error: {e}")

        if anime_seasons:
            anime['seasons'] = anime_seasons
            anime['episodes'] = anime_seasons[0]['episodes']
            total_eps = sum(len(s['episodes']) for s in anime_seasons)
            print(f"   💾 Save (Series)! {len(anime_seasons)} Season, {total_eps} Episodes")
            updated_list.append(anime)
            scraped_this_run += 1
        else:
            # मूवी लॉजिक (बस URL सेव करो, बाकी कुछ नहीं)
            anime['seasons'] = [{"season_number": 1, "episodes": [{"title": "Full Movie", "ep_num": "1", "url": anime['url']}]}]
            anime['episodes'] = anime['seasons'][0]['episodes']
            print(f"   💾 Save (Movie)!")
            updated_list.append(anime)
            scraped_this_run += 1

        if scraped_this_run % 3 == 0:
            db_data['anime_list'] = updated_list
            save_db(db_data)

        time.sleep(SLEEP_BETWEEN)

    if scraped_this_run > 0:
        db_data['anime_list'] = updated_list
        save_db(db_data)
        print(f"\n🎉 {scraped_this_run} नए एनीमे सेव हुए!")
    else:
        print("\n⚠️ कोई नया एनीमे सेव नहीं हुआ।")
    print("=" * 60)