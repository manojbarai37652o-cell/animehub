import sys
import os
import time
import json
import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from parser import parse_post_id, parse_season_episodes, parse_season_ajax

DB_FILE = os.path.join(project_root, 'database', 'storage.json')


def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
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
        print(f"   ❌ Error: {e}")
        return None


def fetch_season_ajax(post_id, season_num):
    # ✅ यहाँ सही किया गया है: 'action_select_season'
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
        print(f"   ❌ AJAX Error: {e}")
        return None


if __name__ == '__main__':
    db_data = load_db()
    anime_list = db_data.get('anime_list', [])
    
    # ✅ सिर्फ उन्हीं एनिमे को अपडेट करेंगे जिनमें 'seasons' नहीं है
    to_update = [a for a in anime_list if 'seasons' not in a]
    
    print("=" * 60)
    print(f"📊 कुल {len(to_update)} पुराने एनिमे अपडेट करने हैं...")
    print("⚡ तेज़ मोड: सिर्फ सीज़न और एपिसोड लिस्ट")
    print("=" * 60)
    
    if not to_update:
        print("✅ सारे एनिमे पहले से अपडेटेड हैं!")
        exit()
    
    updated_count = 0
    
    for idx, anime in enumerate(to_update):
        print(f"\n[{idx+1}/{len(to_update)}] {anime['title']}")
        
        # ✅ सीधे requests से पेज लोड (Playwright नहीं, इसलिए तेज़)
        html = fetch_page(anime['url'])
        if not html:
            print("   ❌ पेज लोड नहीं हुआ")
            continue
        
        post_id = parse_post_id(html)
        if not post_id:
            print("   ❌ Post ID नहीं मिली")
            continue
        
        print(f"   🆔 Post ID: {post_id}")
        
        anime_seasons = []
        season_num = 1
        
        while season_num <= 15:
            if season_num == 1:
                episodes = parse_season_episodes(html, anime['url'])
            else:
                season_html = fetch_season_ajax(post_id, season_num)
                if not season_html or len(season_html.strip()) < 50:
                    break
                episodes = parse_season_ajax(season_html, anime['url'])
            
            if not episodes:
                break
            
            print(f"   📺 Season {season_num}: {len(episodes)} एपिसोड ✅")
            
            # ✅ वीडियो लिंक अभी नहीं निकल रहे, सिर्फ लिस्ट
            for ep in episodes:
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
            updated_count += 1
            total_eps = sum(len(s['episodes']) for s in anime_seasons)
            print(f"   ✅ अपडेट! {len(anime_seasons)} Season, {total_eps} Episodes")
        else:
            print("   ⏹️ कोई Season नहीं मिला")
        
        # हर 3 एनिमे के बाद डेटाबेस सेव करो
        if idx % 3 == 0:
            db_data['anime_list'] = anime_list
            save_db(db_data)
        
        time.sleep(1)
    
    db_data['anime_list'] = anime_list
    save_db(db_data)
    print("\n" + "=" * 60)
    print(f"🎉 {updated_count} एनिमे अपडेट हो गए!")
    print("=" * 60)