import sys
import os
import time
import json
import cloudscraper
from parser import (parse_anime_homepage, parse_post_id, parse_season_ajax,
                     parse_video_link, parse_release_year, parse_season_episodes,
                     has_hindi_dub)

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

MIN_YEAR = 2010
NEW_ANIME_NEEDED = 20  # कितने नए एनीमे चाहिए
OLD_ANIME_NEEDED = 20  # कितने पुराने एनीमे चाहिए
SLEEP_BETWEEN = 2
MAX_PAGES_TO_CHECK = 500

PROGRESS_FILE = os.path.join(project_root, 'database', 'progress.json')
DB_FILE = os.path.join(project_root, 'database', 'storage.json')
SKIP_FILE = os.path.join(project_root, 'database', 'skipped.json')

# ✅ Cloudscraper का इस्तेमाल करें (Cloudflare बायपास के लिए)
scraper = cloudscraper.create_scraper()

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except: pass
    return {"last_page": 10, "total_scraped": 0} # पुराने एनीमे के लिए शुरुआती पेज 10 से

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
        response = scraper.get(url, timeout=20)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return None

def fetch_season_ajax(post_id, season_num):
    ajax_url = f"https://animesalt.cx/wp-admin/admin-ajax.php?action=action_select_season&post_id={post_id}&season={season_num}"
    try:
        response = scraper.get(ajax_url, timeout=20)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ AJAX Error Season {season_num}: {e}")
        return None

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 SMART SCRAPER (हिंदी डब, Cloudscraper के साथ)")
    print("=" * 60)

    progress = load_progress()
    db_data = load_db()
    skip_data = load_skipped()
    
    existing_anime = db_data.get('anime_list', [])
    existing_ids = set(a['id'] for a in existing_anime)
    skipped_ids = set(skip_data.get('skipped_ids', []))

    print(f"📦 Database में {len(existing_ids)} एनीमे हैं")
    print(f"⏭️ Skip list में {len(skipped_ids)} एनीमे हैं\n")

    # --- भाग 1: 5 नए एनीमे ढूंढें (पेज 1 से 3 तक) ---
    print("🔍 नए एनीमे के लिए पेज 1 से 3 चेक कर रहे हैं...")
    new_anime_list = []
    for page in range(1, 4):
        base_url = f"https://animesalt.cx/?page={page}"
        homepage_html = fetch_page(base_url)
        if not homepage_html:
            break
            
        all_anime = parse_anime_homepage(homepage_html, "https://animesalt.cx/")
        # सिर्फ वही लो जो पहले से डेटाबेस में नहीं हैं और स्किप लिस्ट में नहीं हैं
        fresh_anime = [a for a in all_anime if a['id'] not in existing_ids and a['id'] not in skipped_ids]
        
        for a in fresh_anime:
            if a['id'] not in [x['id'] for x in new_anime_list]:
                new_anime_list.append(a)
                if len(new_anime_list) >= NEW_ANIME_NEEDED:
                    break
        
        if len(new_anime_list) >= NEW_ANIME_NEEDED:
            break
        time.sleep(1)

    # --- भाग 2: 5 पुराने एनीमे ढूंढें (last_page से शुरू करके) ---
    print(f"\n📚 पुराने एनीमे के लिए पेज {progress.get('last_page', 10)} से शुरू कर रहे हैं...")
    old_anime_list = []
    page_num = progress.get('last_page', 10)
    
    while page_num <= progress.get('last_page', 10) + MAX_PAGES_TO_CHECK:
        base_url = f"https://animesalt.cx/?page={page_num}"
        homepage_html = fetch_page(base_url)
        if not homepage_html:
            break
            
        all_anime = parse_anime_homepage(homepage_html, "https://animesalt.cx/")
        fresh_anime = [a for a in all_anime if a['id'] not in existing_ids and a['id'] not in skipped_ids]
        
        for a in fresh_anime:
            if a['id'] not in [x['id'] for x in new_anime_list + old_anime_list]:
                old_anime_list.append(a)
                if len(old_anime_list) >= OLD_ANIME_NEEDED:
                    break
        
        if len(old_anime_list) >= OLD_ANIME_NEEDED:
            break
            
        page_num += 1
        progress['last_page'] = page_num
        save_progress(progress)
        time.sleep(1)

    # --- भाग 3: दोनों को मिलाकर प्रोसेस करें ---
    all_to_check = new_anime_list + old_anime_list
    
    if not all_to_check:
        print("\n😔 भाई, कोई नया एनीमे नहीं मिला।")
        exit()

    print(f"\n📋 इस बार {len(all_to_check)} एनीमे चेक होंगे ({len(new_anime_list)} नए + {len(old_anime_list)} पुराने)\n")

    scraped_this_run = 0
    updated_list = existing_anime.copy()

    for idx, anime in enumerate(all_to_check):
        print(f"\n[{idx + 1}/{len(all_to_check)}] {anime['title']}")
        
        anime_html = fetch_page(anime['url'])
        if not anime_html:
            print("  ❌ Page load fail")
            continue

        # ✅ हिंदी डब चेक (अगर नहीं है, तो सिर्फ इस बार स्किप करो, हमेशा के लिए नहीं)
        if not has_hindi_dub(anime_html):
            print("  ⏭️ हिंदी डब नहीं है, अगली बार फिर चेक करेंगे।")
            time.sleep(1)
            continue

        print("  ✅ हिंदी डब है!")

        year = parse_release_year(anime_html)
        if year and year < MIN_YEAR:
            print(f"  ⏭️ Skip (पुराना एनीमे: {year})")
            time.sleep(1)
            continue
        elif not year:
            print("  ❓ Year नहीं मिला, accept कर रहे हैं।")

        post_id = parse_post_id(anime_html)
        if not post_id:
            print("  ❌ Post ID नहीं मिली")
            time.sleep(1)
            continue

        print(f"  🆔 Post ID: {post_id}")

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

            print(f"     📺 Season {season_num}: {len(episodes)} एपिसोड")
            
            # पहले 3 एपिसोड के वीडियो लिंक निकालें
            for ep in episodes[:3]:
                ep_html = fetch_page(ep['url'])
                if ep_html:
                    ep['video_url'] = parse_video_link(ep_html, ep['url'])
                else:
                    ep['video_url'] = ""
                time.sleep(1)
            
            # बाकी एपिसोड के वीडियो लिंक खाली रखें (बाद में भरेंगे)
            for ep in episodes[3:]:
                ep['video_url'] = ""

            anime_seasons.append({
                "season_number": season_num,
                "episodes": episodes
            })
            season_num += 1
            time.sleep(1)

        if not anime_seasons:
            continue

        anime['seasons'] = anime_seasons
        anime['episodes'] = anime_seasons[0]['episodes']
        updated_list.append(anime)
        scraped_this_run += 1

        total_eps = sum(len(s['episodes']) for s in anime_seasons)
        print(f"  💾 Save! {len(anime_seasons)} Season, {total_eps} Episodes")

        # हर 3 एनीमे के बाद डेटा सेव करें
        if scraped_this_run % 3 == 0:
            db_data['anime_list'] = updated_list
            save_db(db_data)
            print("  💾 बीच में सेव कर दिया")

        time.sleep(SLEEP_BETWEEN)

    # अंत में डेटा सेव करें
    if scraped_this_run > 0:
        db_data['anime_list'] = updated_list
        save_db(db_data)
        progress['total_scraped'] += scraped_this_run
        save_progress(progress)
        print(f"\n🎉 इस बार {scraped_this_run} हिंदी एनीमे सेव हुए!")
    
    print("=" * 60)