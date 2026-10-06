import requests
import sys
import os
import time
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from parser import (parse_anime_homepage, parse_post_id, parse_season_ajax,
                    parse_video_link, parse_release_year, parse_season_episodes)

from playwright.sync_api import sync_playwright

MIN_YEAR = 2010
BATCH_SIZE = 10
SLEEP_BETWEEN = 2
LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["#"]
MAX_PAGES_PER_LETTER = 30

PROGRESS_FILE = os.path.join(project_root, 'database', 'progress.json')
DB_FILE = os.path.join(project_root, 'database', 'storage.json')


class BrowserFetcher:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    def start(self):
        print("🌐 Browser शुरू हो रहा है...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.page = self.browser.new_page()
        self.page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def fetch(self, url):
        try:
            # ✅ domcontentloaded = जल्दी, फिर 5 सेकंड का इंतज़ार JS के लिए
            self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(5)  # JavaScript को load होने का इंतज़ार
            
            # Check for 404
            title = self.page.title()
            if '404' in title or 'Not Found' in title:
                return None
            
            return self.page.content()
        except Exception as e:
            print(f"   ❌ Browser fetch error: {e}")
            return None

    def close(self):
        if self.browser: self.browser.close()
        if self.playwright: self.playwright.stop()


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except: pass
    return {"current_letter_index": 0, "current_page": 1, "total_scraped": 0}


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
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return None


def fetch_season_ajax(post_id, season_num):
    ajax_url = f"https://animesalt.cx/wp-admin/admin-ajax.php?action=action_select_season&season={season_num}&post={post_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://animesalt.cx/'
    }
    try:
        response = requests.get(ajax_url, headers=headers, timeout=15)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"   ❌ AJAX Error Season {season_num}: {e}")
        return None


if __name__ == '__main__':
    print("=" * 60)
    print("🤖 A-TO-Z SCRAPER (JavaScript Enabled)")
    print(f"📅 सिर्फ {MIN_YEAR} साल या उसके बाद के एनिमे")
    print("=" * 60)
    
    progress = load_progress()
    letter_idx = progress.get('current_letter_index', 0)
    page_num = progress.get('current_page', 1)
    
    print(f"\n📍 Letter '{LETTERS[letter_idx]}' के Page {page_num} पर")
    print(f"📊 Total scraped: {progress['total_scraped']}")
    
    db_data = load_db()
    existing_anime = db_data.get('anime_list', [])
    existing_ids = set(a['id'] for a in existing_anime)
    print(f"💾 Database में अभी {len(existing_ids)} एनिमे\n")
    
    fetcher = BrowserFetcher()
    fetcher.start()
    
    new_anime = []
    found_new = False
    
    try:
        while letter_idx < len(LETTERS):
            letter = LETTERS[letter_idx]
            
            while page_num <= MAX_PAGES_PER_LETTER:
                if page_num == 1:
                    url = f"https://animesalt.cx/letter/{letter}/"
                else:
                    url = f"https://animesalt.cx/letter/{letter}/?page={page_num}"
                
                print(f"\n🔍 Letter '{letter}' Page {page_num}...")
                
                html = fetcher.fetch(url)
                
                if not html:
                    print(f"   ⏹️ Letter '{letter}' के पेज खत्म")
                    break
                
                all_from_page = parse_anime_homepage(html, "https://animesalt.cx/")
                print(f"   🔍 मिले {len(all_from_page)} एनिमे")
                
                if not all_from_page:
                    print(f"   ⏹️ इस पेज पर कोई एनिमे नहीं")
                    break
                
                new_from_page = [a for a in all_from_page if a['id'] not in existing_ids]
                print(f"   🆕 इनमें से {len(new_from_page)} नए हैं")
                
                if new_from_page:
                    new_anime.extend(new_from_page)
                    if len(new_anime) >= BATCH_SIZE:
                        found_new = True
                        break
                
                page_num += 1
                progress['current_letter_index'] = letter_idx
                progress['current_page'] = page_num
                save_progress(progress)
                time.sleep(1)
            
            if found_new:
                break
            
            letter_idx += 1
            page_num = 1
            progress['current_letter_index'] = letter_idx
            progress['current_page'] = 1
            save_progress(progress)
            
            if letter_idx < len(LETTERS):
                print(f"\n➡️ Letter '{letter}' पूरा, अब '{LETTERS[letter_idx]}' पर")
    finally:
        fetcher.close()
    
    if not found_new:
        print("\n🎉 A से Z तक सब चेक हो गया!")
        exit()
    
    print(f"\n📦 {min(BATCH_SIZE, len(new_anime))} एनिमे स्क्रैप होंगे\n")
    
    scraped_this_run = 0
    updated_list = existing_anime.copy()
    
    for anime in new_anime[:BATCH_SIZE]:
        print(f"\n[{scraped_this_run + 1}/{min(BATCH_SIZE, len(new_anime))}] {anime['title']}")
        
        anime_html = fetch_page(anime['url'])
        if not anime_html:
            print("   ❌ Page load fail")
            continue
        
        year = parse_release_year(anime_html)
        if year:
            print(f"   📅 Release Year: {year}")
            if year < MIN_YEAR:
                print(f"   ⏭️ Skip")
                time.sleep(SLEEP_BETWEEN)
                continue
        else:
            print("   ❓ Year नहीं मिला, accept")
        
        post_id = parse_post_id(anime_html)
        if not post_id:
            print("   ❌ Post ID नहीं मिली")
            time.sleep(SLEEP_BETWEEN)
            continue
        print(f"   🆔 Post ID: {post_id}")
        
        anime_seasons = []
        season_num = 1
        
        while season_num <= 10:
            print(f"   📺 Season {season_num}...")
            
            if season_num == 1:
                episodes = parse_season_episodes(anime_html, anime['url'])
            else:
                season_html = fetch_season_ajax(post_id, season_num)
                if not season_html or len(season_html.strip()) < 50:
                    print(f"      ⏹️ Season {season_num} नहीं मिला")
                    break
                episodes = parse_season_ajax(season_html, anime['url'])
            
            if not episodes:
                print(f"      ⏹️ कोई एपिसोड नहीं")
                break
            
            print(f"      ✅ {len(episodes)} एपिसोड")
            
            for ep_idx, ep in enumerate(episodes[:3]):
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
            time.sleep(SLEEP_BETWEEN)
        
        if not anime_seasons:
            continue
        
        anime['seasons'] = anime_seasons
        anime['episodes'] = anime_seasons[0]['episodes']
        updated_list.append(anime)
        scraped_this_run += 1
        
        total_eps = sum(len(s['episodes']) for s in anime_seasons)
        print(f"   💾 Save! {len(anime_seasons)} Season, {total_eps} Episodes")
        time.sleep(SLEEP_BETWEEN)
    
    if scraped_this_run > 0:
        db_data['anime_list'] = updated_list
        save_db(db_data)
        progress['total_scraped'] += scraped_this_run
        save_progress(progress)
        print(f"\n🎉 {scraped_this_run} एनिमे स्क्रैप हुए!")
        print(f"📊 Total Database: {len(updated_list)} एनिमे")
    
    print("=" * 60)