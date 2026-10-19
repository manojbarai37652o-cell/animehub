import sys
import os
import time
import json
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from scraper.parser import (parse_season_episodes, parse_video_servers, extract_language_from_detail)

DB_FILE = os.path.join(project_root, 'database', 'storage.json')
FAILED_FILE = os.path.join(project_root, 'database', 'failed_updates.json')

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

def update_anime_servers(page, anime):
    """एक एनीमे/मूवी के सभी सर्वर अपडेट करता है"""
    try:
        page.goto(anime['url'], wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(3000)
        html = page.content()

        updated = False

        # अगर मूवी है
        if anime.get('episodes') and len(anime['episodes']) > 0 and anime['episodes'][0].get('title') == 'Full Movie':
            servers = parse_video_servers(html, anime['url'])
            if servers:
                anime['episodes'][0]['servers'] = servers
                anime['episodes'][0]['video_url'] = servers[0]['url'] if servers else ""
                anime['seasons'][0]['episodes'] = anime['episodes']
                updated = True
                print(f"   🎬 Movie Servers Updated: {len(servers)}")
        
        # अगर सीरीज़ है
        else:
            season_btns = page.query_selector_all('.season-btn')
            if not season_btns:
                # सिंगल सीज़न
                episodes = anime.get('episodes', [])
                for ep in episodes:
                    if not ep.get('servers'): # सिर्फ तभी अपडेट करो जब पहले से न हो
                        try:
                            page.goto(ep['url'], wait_until="domcontentloaded", timeout=60000)
                            page.wait_for_timeout(1500)
                            ep_html = page.content()
                            servers = parse_video_servers(ep_html, ep['url'])
                            ep['servers'] = servers
                            ep['video_url'] = servers[0]['url'] if servers else ""
                            updated = True
                        except: pass
                anime['seasons'][0]['episodes'] = episodes
            else:
                # मल्टीपल सीज़न
                season_nums = sorted(list(set([int(btn.get_attribute('data-season')) for btn in season_btns if btn.get_attribute('data-season')])))
                for season in anime.get('seasons', []):
                    season_num = season['season_number']
                    if season_num in season_nums:
                        btn = page.query_selector(f'.season-btn[data-season="{season_num}"]')
                        if btn:
                            btn.click()
                            page.wait_for_timeout(2000)
                            # यहाँ से हम सीधे डेटाबेस वाले एपिसोड्स को अपडेट करेंगे
                            for ep in season['episodes']:
                                if not ep.get('servers'):
                                    try:
                                        page.goto(ep['url'], wait_until="domcontentloaded", timeout=60000)
                                        page.wait_for_timeout(1500)
                                        ep_html = page.content()
                                        servers = parse_video_servers(ep_html, ep['url'])
                                        ep['servers'] = servers
                                        ep['video_url'] = servers[0]['url'] if servers else ""
                                        updated = True
                                    except: pass
                            
                            # ब्राउज़र को वापस एनीमे पेज पर लाओ ताकि अगला सीज़न क्लिक कर सकें
                            page.goto(anime['url'], wait_until="domcontentloaded", timeout=60000)
                            page.wait_for_timeout(2000)

        return updated

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None # Error

if __name__ == '__main__':
    print("=" * 60)
    print("🔄 SERVER UPDATER: पुराने एनीमे में Server 2 जोड़ रहे हैं...")
    print("🛑 रोकने के लिए Ctrl + C दबाओ")
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
                # अगर पहले से अपडेटेड है तो स्किप करो (चेक करने के लिए पहला एपिसोड देखो)
                first_ep = anime.get('episodes', [{}])[0]
                if first_ep.get('servers') and len(first_ep.get('servers', [])) > 0:
                    continue

                print(f"\n[{idx+1}/{len(anime_list)}] {anime['title']} अपडेट कर रहे हैं...")

                result = None
                for attempt in range(2): # 2 बार ट्राई करो
                    result = update_anime_servers(page, anime)
                    if result is not None:
                        break
                    print(f"   🔄 Retry {attempt+1}/2...")
                    time.sleep(3)

                if result is None:
                    new_failed_ids.append(anime['id'])
                    failed_count += 1
                elif result is True:
                    updated_count += 1
                    db_data['anime_list'] = anime_list
                    save_db(db_data)
                    print(f"   💾 अपडेट हो गया!")
                else:
                    print("   ✅ पहले से अपडेटेड है।")

                if (idx + 1) % 5 == 0:
                    db_data['anime_list'] = anime_list
                    save_db(db_data)
                    time.sleep(2)

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
    print(f"⚠️ {failed_count} एनीमे फेल हुए (अगली बार फिर ट्राई करेंगे)।")
    print("=" * 60)
    sys.exit(0)