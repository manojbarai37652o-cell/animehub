import sys
import os
import time
import json
import cloudscraper

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from parser import (parse_anime_homepage, parse_post_id, parse_season_ajax,
                    parse_video_link, parse_release_year, parse_season_episodes)

MIN_YEAR = 2000
BATCH_SIZE = 35
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
    """AJAX call से Season 2, 3, 4... के episodes लाता है"""
    ajax_url = f"https://animesalt.cx/wp-admin/admin-ajax.php?action=action_select_season&season={season_num}&post={post_id}"
    try:
        response = scraper.get(ajax_url, timeout=20)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"   ❌ AJAX Error: {e}")
        return None


if __name__ == '__main__':
    print("=" * 60)
    print("📺 SCRAPER चालू (सारे anime - हर भाषा)")
    print("=" * 60)

    progress = load_progress()
    start_page = progress.get('last_page', 1)
    print(f"\n📌 Page {start_page} से शुरू")

    db_data = load_db()
    existing_anime = db_data.get('anime_list', [])
    existing_ids = set(a['id'] for a in existing_anime)

    print(f"📊 Database: {len(existing_ids)} anime\n")

    new_anime = []
    page_num = start_page
    pages_checked = 0
    
    # 🛠️ FIX 1: हम तब तक पेज चेक करेंगे जब तक 35 नए एनीमे नहीं मिल जाते
    MAX_PAGES_TO_CHECK = 500 
    
    while len(new_anime) < BATCH_SIZE and pages_checked < MAX_PAGES_TO_CHECK:
        base_url = f"https://animesalt.cx/?page={page_num}"
        print(f"\n🔍 Page {page_num}...")

        try:
            homepage_html = fetch_page(base_url)
            if not homepage_html:
                # 🛠️ FIX 2: 504 एरर आने पर रुकना नहीं है, अगले पेज पर जाना है
                print(f"⚠️ Page {page_num} लोड नहीं हुआ (शायद 504 एरर)। अगले पेज पर जा रहे हैं...")
                page_num += 1
                pages_checked += 1
                continue

            all_anime = parse_anime_homepage(homepage_html, "https://animesalt.cx/")
            page_new_anime = [a for a in all_anime if a['id'] not in existing_ids]
            
            for a in page_new_anime:
                if a not in new_anime:
                    new_anime.append(a)
                    if len(new_anime) >= BATCH_SIZE:
                        break
            
            print(f"   📊 इस पेज पर {len(page_new_anime)} नए आइटम मिले (कुल जुटाए: {len(new_anime)})")

            page_num += 1
            progress['last_page'] = page_num
            save_progress(progress)
            pages_checked += 1
            time.sleep(1) # सर्वर पर लोड कम करने के लिए
            
        except Exception as e:
            print(f"❌ Page {page_num} पर एरर: {e}. अगले पेज पर जा रहे हैं...")
            page_num += 1
            pages_checked += 1
            continue

    if not new_anime:
        print("\n👋 सारे पेज खत्म! कोई नया आइटम नहीं मिला।")
        exit()

    print(f"\n✅ {len(new_anime)} एनीमे चेक कर रहे हैं...\n")

    scraped_this_run = 0
    updated_list = existing_anime.copy()

    # 🛠️ FIX 3: अब हम 35 एनीमे (सीरीज़ या मूवी) को प्रोसेस करेंगे
    for idx, anime in enumerate(new_anime[:BATCH_SIZE]):
        print(f"\n[{idx + 1}/{min(BATCH_SIZE, len(new_anime))}] {anime['title']}")
        
        anime_html = fetch_page(anime['url'])
        if not anime_html:
            continue

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

        # 🛠️ FIX 4: मूवीज़ को स्किप मत करो। अगर सीज़न नहीं हैं, तो खाली लिस्ट सेव करो।
        if anime_seasons:
            anime['seasons'] = anime_seasons
            anime['episodes'] = anime_seasons[0]['episodes']
            total_eps = sum(len(s['episodes']) for s in anime_seasons)
            print(f"   💾 Save (Series)! {len(anime_seasons)} Season, {total_eps} Episodes")
        else:
            anime['seasons'] = []
            anime['episodes'] = []
            print(f"   💾 Save (Movie)! कोई सीज़न नहीं मिला, मूवी के रूप में सेव कर रहे हैं।")

        updated_list.append(anime)
        scraped_this_run += 1

        # हर 3 एनीमे के बाद डेटाबेस में सेव करो
        if scraped_this_run % 3 == 0:
            db_data['anime_list'] = updated_list
            save_db(db_data)

        time.sleep(SLEEP_BETWEEN)

    # 🛠️ FIX 5: आखिर में सेव करो और अगली बार के लिए पेज 1 पर रीसेट कर दो
    if scraped_this_run > 0:
        db_data['anime_list'] = updated_list
        save_db(db_data)
        progress['total_scraped'] += scraped_this_run
        
        # यही तुम्हारे सवाल का जवाब है! अगली बार फिर से पेज 1 से शुरू करने के लिए
        progress['last_page'] = 1 
        save_progress(progress)
        
        print(f"\n🎉 {scraped_this_run} anime saved! अगली बार फिर से Page 1 से शुरू होगा।")
    else:
        print("\n⚠️ कोई नया एनीमे सेव नहीं हुआ।")

    print("=" * 60)