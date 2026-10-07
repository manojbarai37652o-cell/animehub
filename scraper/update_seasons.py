import sys
import os
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from smart_scraper import BrowserFetcher, fetch_season_ajax, load_db, save_db
from parser import parse_post_id, parse_season_episodes, parse_season_ajax, parse_video_link

if __name__ == '__main__':
    db_data = load_db()
    anime_list = db_data.get('anime_list', [])
    
    # ✅ सिर्फ उन्हीं एनिमे को अपडेट करेंगे जिनमें 'seasons' नहीं है
    to_update = [a for a in anime_list if 'seasons' not in a]
    
    print(f"📊 कुल {len(to_update)} पुराने एनिमे अपडेट करने हैं...")
    
    if not to_update:
        print("✅ सारे एनिमे पहले से अपडेटेड हैं!")
        exit()
    
    fetcher = BrowserFetcher()
    fetcher.start()
    
    updated_count = 0
    try:
        for idx, anime in enumerate(to_update):
            print(f"\n[{idx+1}/{len(to_update)}] {anime['title']}")
            
            html = fetcher.fetch(anime['url'])
            if not html:
                print("   ❌ पेज लोड नहीं हुआ")
                continue
            
            post_id = parse_post_id(html)
            if not post_id:
                print("   ❌ Post ID नहीं मिली")
                continue
                
            anime_seasons = []
            season_num = 1
            
            while season_num <= 10:
                if season_num == 1:
                    episodes = parse_season_episodes(html, anime['url'])
                else:
                    season_html = fetch_season_ajax(post_id, season_num)
                    if not season_html or len(season_html.strip()) < 50:
                        break
                    episodes = parse_season_ajax(season_html, anime['url'])
                
                if not episodes:
                    break
                
                # पहले 3 एपिसोड के वीडियो लिंक लो
                for ep in episodes[:3]:
                    ep_html = fetcher.fetch(ep['url'])
                    if ep_html:
                        ep['video_url'] = parse_video_link(ep_html, ep['url'])
                    else:
                        ep['video_url'] = ""
                
                for ep in episodes[3:]:
                    ep['video_url'] = ""
                
                anime_seasons.append({
                    "season_number": season_num,
                    "episodes": episodes
                })
                season_num += 1
                time.sleep(2)
            
            if anime_seasons:
                anime['seasons'] = anime_seasons
                anime['episodes'] = anime_seasons[0]['episodes']
                updated_count += 1
                total_eps = sum(len(s['episodes']) for s in anime_seasons)
                print(f"   ✅ अपडेट! {len(anime_seasons)} Season, {total_eps} Episodes")
            else:
                print("   ⏹️ कोई Season नहीं मिला")
            
            if idx % 5 == 0:
                db_data['anime_list'] = anime_list
                save_db(db_data)
                print("   💾 बीच में सेव कर दिया")
                
            time.sleep(2)
    finally:
        fetcher.close()
        db_data['anime_list'] = anime_list
        save_db(db_data)
        print(f"\n🎉 {updated_count} एनिमे अपडेट हो गए!")