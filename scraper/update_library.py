import sys
import os
import time
import json
import cloudscraper
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from scraper.parser import (parse_season_episodes, parse_video_link,
                            extract_language_from_detail)

DB_FILE = os.path.join(project_root, 'database', 'storage.json')
FAILED_FILE = os.path.join(project_root, 'database', 'failed_updates.json')
scraper = cloudscraper.create_scraper()

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

def fetch_page(url):
    try:
        response = scraper.get(url, timeout=20)
        if response.status_code == 404: return None
        response.raise_for_status()
        return response.text
    except: return None


def check_anime_for_updates(anime):
    """एक एनीमे को चेक करता है और नया सीज़न/एपिसोड मिलने पर True return करता है"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-ipv6"])
            page = browser.new_page()
            page.goto(anime['url'], timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            season_btns = page.query_selector_all('.season-btn')
            existing_seasons = anime.get('seasons', [])
            existing_season_nums = [s['season_number'] for s in existing_seasons]

            website_season_nums = []
            for btn in season_btns:
                try:
                    sn = int(btn.get_attribute('data-season'))
                    if sn not in website_season_nums:
                        website_season_nums.append(sn)
                except: pass
            website_season_nums.sort()

            new_found = False

            # 1. नया सीज़न चेक करो
            for season_num in website_season_nums:
                if season_num not in existing_season_nums:
                    print(f"   🆕 नया सीज़न मिला: Season {season_num}")
                    btn = page.query_selector(f'.season-btn[data-season="{season_num}"]')
                    if btn:
                        btn.click()
                        page.wait_for_timeout(3000)
                        season_html = page.content()
                        episodes = parse_season_episodes(season_html, anime['url'])
                        if episodes:
                            print(f"   📺 Season {season_num}: {len(episodes)} episodes")
                            for ep in episodes:
                                ep_html = fetch_page(ep['url'])
                                ep['video_url'] = parse_video_link(ep_html, ep['url']) if ep_html else ""
                                time.sleep(1)
                            anime['seasons'].append({"season_number": season_num, "episodes": episodes})
                            new_found = True

            # 2. पुराने सीज़न में नए एपिसोड चेक करो
            for season in anime.get('seasons', []):
                season_num = season['season_number']
                try:
                    btn = page.query_selector(f'.season-btn[data-season="{season_num}"]')
                    if btn:
                        btn.click()
                        page.wait_for_timeout(2500)
                        season_html = page.content()
                        website_episodes = parse_season_episodes(season_html, anime['url'])
                        if website_episodes:
                            existing_ep_urls = set(ep['url'] for ep in season['episodes'])
                            new_eps = [ep for ep in website_episodes if ep['url'] not in existing_ep_urls]
                            if new_eps:
                                print(f"   🆕 Season {season_num} में {len(new_eps)} नए एपिसोड मिले!")
                                for ep in new_eps:
                                    ep_html = fetch_page(ep['url'])
                                    ep['video_url'] = parse_video_link(ep_html, ep['url']) if ep_html else ""
                                    time.sleep(1)
                                    season['episodes'].append(ep)
                                new_found = True
                except: pass

            browser.close()
            return new_found

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None  # None means FAILED (error), True means new found, False means nothing new


if __name__ == '__main__':
    print("=" * 60)
    print("🔄 UPDATE LIBRARY: पुराने एनीमे में नया सीज़न/एपिसोड चेक कर रहे हैं...")
    print("=" * 60)

    db_data = load_db()
    anime_list = db_data.get('anime_list', [])
    failed_data = load_failed()
    failed_ids = failed_data.get('failed_ids', [])

    print(f"📊 Database में {len(anime_list)} एनीमे हैं।")
    print(f"⚠️ पिछली बार {len(failed_ids)} एनीमे फेल हुए थे।\n")

    updated_count = 0
    failed_count = 0
    new_failed_ids = []

    for idx, anime in enumerate(anime_list):
        # मूवीज़ को स्किप करो
        if anime.get('episodes') and len(anime['episodes']) > 0 and anime['episodes'][0].get('title') == 'Full Movie':
            continue

        print(f"\n[{idx+1}/{len(anime_list)}] {anime['title']}...")

        # 3 बार रीट्राई करो
        result = None
        for attempt in range(3):
            result = check_anime_for_updates(anime)
            if result is not None:  # अगर सफल हुआ (error नहीं आया)
                break
            print(f"   🔄 Retry {attempt+1}/3...")
            time.sleep(3)

        if result is None:
            # तीनों बार फेल हुआ
            print(f"   ❌ तीनों बार फेल हुआ, बाद के लिए रख रहे हैं।")
            new_failed_ids.append(anime['id'])
            failed_count += 1
        elif result is True:
            # नया मिला
            updated_count += 1
            print(f"   💾 {anime['title']} अपडेट हो गया!")
            # 🛠️ हर अपडेट के बाद डेटाबेस सेव करो
            db_data['anime_list'] = anime_list
            save_db(db_data)
        else:
            print("   ✅ कोई नया नहीं मिला।")

        # 🛠️ हर 5 एनीमे के बाद डेटाबेस सेव करो और थोड़ा रुको
        if (idx + 1) % 5 == 0:
            db_data['anime_list'] = anime_list
            save_db(db_data)
            print("   💾 (Incremental save)")
            time.sleep(5)

        time.sleep(1)

    # फाइनल सेव
    db_data['anime_list'] = anime_list
    save_db(db_data)
    failed_data['failed_ids'] = new_failed_ids
    save_failed(failed_data)

    print("\n" + "=" * 60)
    print(f"🎉 कुल {updated_count} एनीमे अपडेट हुए!")
    print(f"⚠️ {failed_count} एनीमे फेल हुए (next run में retry होंगे)।")
    print("=" * 60)