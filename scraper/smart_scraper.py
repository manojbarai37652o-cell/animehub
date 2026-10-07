import requests
import sys
import os
import time
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from parser import (parse_anime_homepage, parse_post_id, parse_season_ajax,
                    parse_video_link, parse_release_year, parse_season_episodes,
                    has_hindi_dub)

MIN_YEAR = 2010
BATCH_SIZE = 10
SLEEP_BETWEEN = 2
MAX_PAGES_TO_CHECK = 500

PROGRESS_FILE = os.path.join(project_root, 'database', 'progress.json')
DB_FILE = os.path.join(project_root, 'database', 'storage.json')
SKIP_FILE = os.path.join(project_root, 'database', 'skipped.json')


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


def load_skipped():
    """जो एनिमे हिंदी में नहीं हैं, उनकी लिस्ट"""
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
    print("🤖 SMART SCRAPER (सिर्फ हिंदी डब एनिमे)")
    print(f"📅 सिर्फ {MIN_YEAR} साल या उसके बाद के एनिमे")
    print(f"📦 हर बार {BATCH_SIZE} एनिमे")
    print("=" * 60)
    
    progress = load_progress()
    start_page = progress.get('last_page', 1)
    print(f"\n📍 अभी Page {start_page} से शुरू कर रहे हैं। Total scraped: {progress['total_scraped']}")
    
    db_data = load_db()
    existing_anime = db_data.get('anime_list', [])
    existing_ids = set(a['id'] for a in existing_anime)
    
    skip_data = load_skipped()
    skipped_ids = set(skip_data.get('skipped_ids', []))
    
    print(f"💾 Database में {len(existing_ids)} एनिमे हैं")
    print(f"⏭️ Skip list में {len(skipped_ids)} एनिमे हैं (हिंदी नहीं)\n")
    
    found_new = False
    page_num = start_page
    new_anime = []
    
    while page_num <= start_page + MAX_PAGES_TO_CHECK:
        base_url = f"https://animesalt.cx/?page={page_num}"
        print(f"\n🔍 Page {page_num} खोला जा रहा है...")
        
        homepage_html = fetch_page(base_url)
        if not homepage_html:
            print(f"❌ Page {page_num} load नहीं हुआ।")
            break
        
        all_anime = parse_anime_homepage(homepage_html, "https://animesalt.cx/")
        print(f"🔍 इस पेज पर मिले {len(all_anime)} एनिमे")
        
        # ✅ जो पहले से DB में हैं या skip हो चुके हैं, उन्हें छोड़ दो
        new_anime = [a for a in all_anime if a['id'] not in existing_ids and a['id'] not in skipped_ids]
        print(f"🆕 इनमें से {len(new_anime)} नए हैं")
        
        if not new_anime:
            print(f"   ⏭️ Page {page_num} के सारे एनिमे चेक हो चुके हैं, अगले पेज पर")
            page_num += 1
            progress['last_page'] = page_num
            save_progress(progress)
            time.sleep(1)
            continue
        else:
            print(f"   ✅ {len(new_anime)} नए एनिमे मिले!")
            found_new = True
            break
    
    if not found_new:
        print("\n🎉 भाई, सारे पेज खत्म हो गए!")
        exit()
    
    print(f"\n📦 इस बार {min(BATCH_SIZE, len(new_anime))} एनिमे चेक होंगे\n")
    
    scraped_this_run = 0
    skipped_this_run = 0
    updated_list = existing_anime.copy()
    
    for anime in new_anime[:BATCH_SIZE]:
        print(f"\n[{scraped_this_run + 1}/{min(BATCH_SIZE, len(new_anime))}] {anime['title']}")
        
        anime_html = fetch_page(anime['url'])
        if not anime_html:
            print("   ❌ Page load fail")
            continue
        
        # ✅ पहले हिंदी चेक करो
        if not has_hindi_dub(anime_html):
            print("   ⏭️ हिंदी डब नहीं है, Skip कर रहे हैं")
            skipped_ids.add(anime['id'])
            skipped_this_run += 1
            time.sleep(1)
            continue
        
        print("   ✅ हिंदी डब है!")
        
        # फिर Year चेक करो
        year = parse_release_year(anime_html)
        if year:
            print(f"   📅 Release Year: {year}")
            if year < MIN_YEAR:
                print(f"   ⏭️ Skip (before {MIN_YEAR})")
                skipped_ids.add(anime['id'])
                skipped_this_run += 1
                time.sleep(1)
                continue
        else:
            print("   ❓ Year नहीं मिला, accept कर रहे हैं")
        
        post_id = parse_post_id(anime_html)
        if not post_id:
            print("   ❌ Post ID नहीं मिली")
            time.sleep(1)
            continue
        print(f"   🆔 Post ID: {post_id}")
        
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
            
            print(f"   📺 Season {season_num}: {len(episodes)} एपिसोड")
            
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
        
        if not anime_seasons:
            continue
        
        anime['seasons'] = anime_seasons
        anime['episodes'] = anime_seasons[0]['episodes']
        updated_list.append(anime)
        scraped_this_run += 1
        
        total_eps = sum(len(s['episodes']) for s in anime_seasons)
        print(f"   💾 Save! {len(anime_seasons)} Season, {total_eps} Episodes")
        
        # हर 3 एनिमे के बाद डेटा सेव करो
        if scraped_this_run % 3 == 0:
            db_data['anime_list'] = updated_list
            save_db(db_data)
            skip_data['skipped_ids'] = list(skipped_ids)
            save_skipped(skip_data)
            print("   💾 बीच में सेव कर दिया")
        
        time.sleep(SLEEP_BETWEEN)
    
    # अंत में सब सेव करो
    if scraped_this_run > 0:
        db_data['anime_list'] = updated_list
        save_db(db_data)
        progress['total_scraped'] += scraped_this_run
        save_progress(progress)
        print(f"\n🎉 इस बार {scraped_this_run} हिंदी एनिमे स्क्रैप हुए!")
        print(f"📊 Total Database: {len(updated_list)} एनिमे")
    
    if skipped_this_run > 0:
        skip_data['skipped_ids'] = list(skipped_ids)
        save_skipped(skip_data)
        print(f"⏭️ {skipped_this_run} एनिमे skip किए (हिंदी नहीं या पुराने)")
    
    print("=" * 60)