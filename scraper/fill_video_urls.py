import sys
import os
import time
import json
import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from parser import parse_video_link

DB_FILE = os.path.join(project_root, 'database', 'storage.json')

# ✅ हर Season में सिर्फ पहले कितने episodes के link भरने हैं
EPISODES_PER_SEASON = 5


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


if __name__ == '__main__':
    db_data = load_db()
    anime_list = db_data.get('anime_list', [])
    
    print("=" * 60)
    print(f"🔍 कुल {len(anime_list)} एनिमे चेक करने हैं...")
    print(f"📦 हर Season में पहले {EPISODES_PER_SEASON} एपिसोड के वीडियो लिंक भरेंगे")
    print("=" * 60)
    
    total_filled = 0
    
    for a_idx, anime in enumerate(anime_list):
        seasons = anime.get('seasons', [])
        if not seasons:
            continue
        
        # चेक करो कि क्या किसी season में खाली video_url है?
        needs_update = False
        for season in seasons:
            for ep in season['episodes'][:EPISODES_PER_SEASON]:
                if not ep.get('video_url'):
                    needs_update = True
                    break
            if needs_update:
                break
        
        if not needs_update:
            continue
        
        print(f"\n[{a_idx+1}/{len(anime_list)}] {anime['title']}")
        
        anime_filled = 0
        
        for season in seasons:
            season_num = season['season_number']
            episodes = season['episodes']
            
            # सिर्फ पहले कुछ episodes के link भरो
            for ep in episodes[:EPISODES_PER_SEASON]:
                if ep.get('video_url'):
                    continue  # पहले से है तो छोड़ दो
                
                ep_html = fetch_page(ep['url'])
                if ep_html:
                    video_url = parse_video_link(ep_html, ep['url'])
                    if video_url:
                        ep['video_url'] = video_url
                        anime_filled += 1
                time.sleep(0.5)
            
            if anime_filled > 0:
                print(f"   📺 Season {season_num}: {anime_filled} links भरे")
        
        if anime_filled > 0:
            total_filled += anime_filled
            print(f"   ✅ {anime['title']}: {anime_filled} episodes के links भरे")
        
        # हर 3 एनिमे के बाद डेटाबेस सेव करो
        if a_idx % 3 == 0:
            db_data['anime_list'] = anime_list
            save_db(db_data)
            print("   💾 डेटा सेव कर दिया")
    
    db_data['anime_list'] = anime_list
    save_db(db_data)
    
    print("\n" + "=" * 60)
    print(f"🎉 कुल {total_filled} एपिसोड के वीडियो लिंक भर गए!")
    print("=" * 60)