import sys
import os
import time
import json
import gc
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from scraper.parser import (parse_season_episodes, parse_video_servers)

DB_FILE = os.path.join(project_root, 'database', 'storage.json')
FAILED_FILE = os.path.join(project_root, 'database', 'failed_updates.json')

# =========================================================
# 🛠️ SKIP LIST: यहाँ उन एनीमे के नाम लिखो जिन्हें स्किप करना है
# =========================================================
SKIP_ANIME_TITLES = [           
     "cartoon",           
     "Power rangers",     
]
# =========================================================

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {"anime_list": []}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_failed():
    if os.path.exists(FAILED_FILE):
        try:
            with open(FAILED_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"failed_ids": []}

def save_failed(data):
    with open(FAILED_FILE, 'w') as f:
        json.dump(data, f, indent=4)


def check_anime_updates(page, anime):
    """एक एनीमे में नया सीज़न/एपिसोड या गायब सर्वर चेक करता है"""
    try:
        page.goto(anime['url'], wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(1000) 
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')

        updated = False

        # अगर मूवी है
        if anime.get('episodes') and len(anime['episodes']) > 0 and anime['episodes'][0].get('title') == 'Full Movie':
            if not anime['episodes'][0].get('servers'):
                servers = parse_video_servers(html, anime['url'])
                if servers:
                    anime['episodes'][0]['servers'] = servers
                    anime['episodes'][0]['video_url'] = servers[0]['url'] if servers else ""
                    anime['seasons'][0]['episodes'] = anime['episodes']
                    updated = True
        
        # अगर सीरीज़ है
        else:
            season_btns = page.query_selector_all('.season-btn')
            
            # 1. वेबसाइट से मौजूदा सीज़न की लिस्ट निकालो
            website_seasons = []
            if season_btns:
                for btn in season_btns:
                    try:
                        sn = int(btn.get_attribute('data-season'))
                        if sn not in website_seasons:
                            website_seasons.append(sn)
                    except: pass
                website_seasons.sort()
            else:
                website_seasons = [1] # सिंगल सीज़न

            existing_seasons = anime.get('seasons', [])
            existing_season_nums = [s['season_number'] for s in existing_seasons]

            # 2. नया सीज़न चेक करो
            for sn in website_seasons:
                if sn not in existing_season_nums:
                    print(f"      🆕 नया सीज़न मिला: Season {sn}")
                    if season_btns:
                        btn = page.query_selector(f'.season-btn[data-season="{sn}"]')
                        if btn:
                            btn.click()
                            page.wait_for_timeout(2000)
                            season_html = page.content()
                    else:
                        season_html = html

                    episodes = parse_season_episodes(season_html, anime['url'])
                    if episodes:
                        for ep in episodes:
                            try:
                                page.goto(ep['url'], wait_until="domcontentloaded", timeout=60000)
                                page.wait_for_timeout(500)
                                ep['servers'] = parse_video_servers(page.content(), ep['url'])
                                ep['video_url'] = ep['servers'][0]['url'] if ep['servers'] else ""
                            except: ep['video_url'] = ""
                        anime['seasons'].append({"season_number": sn, "episodes": episodes})
                        updated = True
                    
                    # वापस एनीमे पेज पर आओ
                    page.goto(anime['url'], wait_until="domcontentloaded", timeout=90000)
                    page.wait_for_timeout(1000)

            # 3. पुराने सीज़न में नया एपिसोड या गायब सर्वर चेक करो
            for season in anime.get('seasons', []):
                sn = season['season_number']
                if sn in website_seasons:
                    # वेबसाइट से उस सीज़न के ताज़ा एपिसोड निकालो
                    if season_btns:
                        btn = page.query_selector(f'.season-btn[data-season="{sn}"]')
                        if btn:
                            btn.click()
                            page.wait_for_timeout(2000)
                            season_html = page.content()
                    else:
                        season_html = html
                        
                    website_episodes = parse_season_episodes(season_html, anime['url'])
                    existing_ep_urls = set(ep['url'] for ep in season['episodes'])

                    # नए एपिसोड ढूंढो
                    new_eps = [ep for ep in website_episodes if ep['url'] not in existing_ep_urls]
                    
                    if new_eps:
                        print(f"      🆕 Season {sn} में {len(new_eps)} नए एपिसोड मिले!")
                        for ep in new_eps:
                            try:
                                page.goto(ep['url'], wait_until="domcontentloaded", timeout=60000)
                                page.wait_for_timeout(500)
                                ep['servers'] = parse_video_servers(page.content(), ep['url'])
                                ep['video_url'] = ep['servers'][0]['url'] if ep['servers'] else ""
                            except: ep['video_url'] = ""
                            season['episodes'].append(ep)
                        updated = True
                    
                    # गायब सर्वर अपडेट करो (पुराने एपिसोड के लिए)
                    for ep in season['episodes']:
                        if not ep.get('servers'):
                            try:
                                page.goto(ep['url'], wait_until="domcontentloaded", timeout=60000)
                                page.wait_for_timeout(500)
                                ep['servers'] = parse_video_servers(page.content(), ep['url'])
                                ep['video_url'] = ep['servers'][0]['url'] if ep['servers'] else ""
                                updated = True
                            except: pass
                            
                    if season_btns:
                        page.goto(anime['url'], wait_until="domcontentloaded", timeout=90000)
                        page.wait_for_timeout(1000)

        return updated
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None 


if __name__ == '__main__':
    print("=" * 60)
    print("🔄 UPDATE LIBRARY: नया सीज़न/एपिसोड चेक कर रहे हैं...")
    print("🛑 रोकने के लिए Ctrl + C दबाओ (डेटा सुरक्षित रहेगा)")
    print("=" * 60)

    db_data = load_db()
    anime_list = db_data.get('anime_list', [])
    failed_data = load_failed()
    failed_ids = failed_data.get('failed_ids', [])

    print(f"📊 Database में {len(anime_list)} एनीमे हैं।\n")

    updated_count = 0
    failed_count = 0
    new_failed_ids = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--disable-ipv6", "--no-sandbox"])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
            page = context.new_page()
            page.set_default_timeout(90000)

            for idx, anime in enumerate(anime_list):
                # 1. SKIP LIST CHECK
                if any(skip_title.lower() in anime['title'].lower() for skip_title in SKIP_ANIME_TITLES):
                    print(f"\n[{idx+1}/{len(anime_list)}] {anime['title']} -> ⏭️ SKIPPED (Skip list में है)")
                    continue

                print(f"\n[{idx+1}/{len(anime_list)}] {anime['title']} चेक कर रहे हैं...")

                result = None
                for attempt in range(2): 
                    result = check_anime_updates(page, anime)
                    if result is not None:
                        break
                    print(f"   🔄 Retry {attempt+1}/2...")
                    time.sleep(1) 

                if result is None:
                    new_failed_ids.append(anime['id'])
                    failed_count += 1
                elif result is True:
                    updated_count += 1
                    db_data['anime_list'] = anime_list
                    save_db(db_data)
                    print(f"   💾 अपडेट हो गया!")
                else:
                    print("   ✅ कोई नया नहीं मिला।")

                # 2. RAM MANAGEMENT (हर 5 एनीमे के बाद रैम साफ करो)
                if (idx + 1) % 5 == 0:
                    db_data['anime_list'] = anime_list
                    save_db(db_data)
                    gc.collect()  
                    time.sleep(1) 

            try: browser.close()
            except: pass

    except KeyboardInterrupt:
        print("\n\n🛑 स्क्रैपिंग यूजर द्वारा रोक दी गई!")

    db_data['anime_list'] = anime_list
    save_db(db_data)
    failed_data['failed_ids'] = new_failed_ids
    save_failed(failed_data)

    print("\n" + "=" * 60)
    print(f"🎉 कुल {updated_count} एनीमे अपडेट हुए!")
    print(f"⚠️ {failed_count} एनीमे फेल हुए।")
    print("=" * 60)
    sys.exit(0)