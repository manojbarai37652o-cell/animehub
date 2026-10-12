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

    db_data = load_db()
    existing_anime = db_data.get('anime_list', [])
    existing_ids = set(a['id'] for a in existing_anime)

    print(f"📊 Database: {len(existing_ids)} anime\n")

    new_anime = []
    scraped_this_run = 0
    updated_list = existing_anime.copy()

    # 🛠️ FIX: A से Z तक जाएंगे ताकि नए एनीमे कभी मिस न हों
    import string
    letters = string.ascii_uppercase
    MAX_PAGES_PER_LETTER = 20

    for letter in letters:
        if len(new_anime) >= BATCH_SIZE:
            break
            
        print(f"\n🔍 Letter {letter} चेक कर रहे हैं...")
        page_num = 1
        
        while page_num <= MAX_PAGES_PER_LETTER:
            base_url = f"https://animesalt.cx/letter/{letter}/?page={page_num}"
            
            try:
                homepage_html = fetch_page(base_url)
                if not homepage_html:
                    print(f"   ⚠️ Page {page_num} लोड नहीं हुआ। इस लेटर को छोड़ रहे हैं।")
                    break

                all_anime = parse_anime_homepage(homepage_html, "https://animesalt.cx/")
                if not all_anime:
                    print(f"   ⏭️ इस पेज पर कोई एनीमे नहीं मिला। अगले लेटर पर जा रहे हैं।")
                    break

                page_new_anime = [a for a in all_anime if a['id'] not in existing_ids]
                
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

        # 🛠️ FIX: यहाँ भाषा निकालो और सेव करो
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

            # सिर्फ पहले 3 एपिसोड के वीडियो लिंक निकालेंगे (स्पीड के लिए)
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
            anime['seasons'] = []
            anime['episodes'] = []
            print(f"   💾 Save (Movie)! कोई सीज़न नहीं मिला, मूवी के रूप में सेव कर रहे हैं।")

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