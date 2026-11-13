import sys
import os
import time
import json
from playwright.sync_api import sync_playwright

current_dir = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(current_dir, 'database', 'storage.json')
ANIME_SALT_URL = "https://animesalt.cx/mushoku-tensei-jobless-reincarnation/"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f: 
            return json.load(f)
    return {"anime_list": []}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def scrape_mushoku():
    print("🔍 Starting Surgical Scrape for: Mushoku Tensei...")
    db_data = load_db()
    anime_list = db_data.get('anime_list', [])
    
    # 1. Purana data delete karo
    anime_list = [a for a in anime_list if "mushoku tensei" not in a.get('title', '').lower()]
    print("🗑️ Old Mushoku Tensei data removed from memory.")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-ipv6", "--no-sandbox"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        page = context.new_page()
        page.set_default_timeout(60000)
        
        print(f"🌐 Loading Page: {ANIME_SALT_URL}")
        page.goto(ANIME_SALT_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        
        # Base Data nikaalo
        title = "Mushoku Tensei: Jobless Reincarnation"
        image = ""
        try:
            img_tag = page.query_selector('.thumb img') or page.query_selector('meta[property="og:image"]')
            if img_tag:
                image = img_tag.get_attribute('src') or img_tag.get_attribute('content')
        except:
            pass
            
        anime_data = {
            "title": title,
            "url": ANIME_SALT_URL,
            "image": image,
            "type": "Series",
            "language": "Hindi Dub",
            "id": "mushoku-tensei", # Fixed ID for consistency
            "seasons": []
        }
        
        # Season Buttons dhundo
        season_btns = page.query_selector_all('.season-btn')
        if not season_btns:
            print("❌ No season buttons found!")
            browser.close()
            return
            
        season_nums = sorted(list(set([int(btn.get_attribute('data-season')) for btn in season_btns if btn.get_attribute('data-season')])))
        print(f"✅ Found {len(season_nums)} Seasons: {season_nums}")
        
        for season_num in season_nums:
            print(f"🔄 Scraping Season {season_num}...")
            
            # Season button pe click karo
            btn = page.query_selector(f'.season-btn[data-season="{season_num}"]')
            if btn:
                btn.click()
                page.wait_for_timeout(3000) # Wait for AJAX to update episodes
                
                # Episodes ki list dhundo
                episode_links = page.query_selector_all('ul#episode_by_temp a.lnk-blk')
                episodes = []
                
                for idx, ep_link in enumerate(episode_links):
                    ep_num = str(idx + 1)
                    ep_url = ep_link.get_attribute('href')
                    
                    print(f"   📺 Episode {ep_num}...")
                    try:
                        # Episode page pe jao
                        new_page = context.new_page()
                        new_page.goto(ep_url, wait_until="domcontentloaded", timeout=60000)
                        new_page.wait_for_timeout(3000)
                        
                        # Server 2 (Ravok) load karne ke liye changeServer(1) click karo
                        try:
                            server2 = new_page.query_selector("div[onclick='changeServer(1)']")
                            if server2:
                                server2.click(force=True)
                                new_page.wait_for_timeout(3000) # Wait for iframe to load
                        except:
                            pass
                            
                        # Ravok ka iframe dhundo
                        video_url = ""
                        iframe = new_page.query_selector("iframe[src*='ravok.buzz']")
                        if iframe:
                            video_url = iframe.get_attribute('src')
                        else:
                            # Agar iframe na mile toh HTML me regex chalao
                            import re
                            match = re.search(r'(https?://ravok\.buzz/video/[a-zA-Z0-9]+)', new_page.content())
                            if match:
                                video_url = match.group(1)
                                
                        print(f"      ✅ Found: {video_url[:50]}...")
                        
                        episodes.append({
                            "ep_num": ep_num,
                            "title": f"Episode {ep_num}",
                            "video_url": video_url,
                            "servers": [
                                {"name": "Server 1", "url": video_url},
                                {"name": "Server 2", "url": video_url}
                            ]
                        })
                        new_page.close()
                        time.sleep(1) # Thoda gap
                        
                    except Exception as e:
                        print(f"      ❌ Error on Ep {ep_num}: {e}")
                        
                anime_data['seasons'].append({
                    "season_number": season_num,
                    "episodes": episodes
                })
                print(f"   ✅ Season {season_num} done ({len(episodes)} eps).")
                
        browser.close()
        
    # 2. Naya data save karo
    if anime_data['seasons']:
        anime_data['episodes'] = anime_data['seasons'][0]['episodes'] # Fallback for old code
        anime_list.append(anime_data)
        db_data['anime_list'] = anime_list
        save_db(db_data)
        print("🎉 Success! Database updated with fresh Mushoku Tensei data.")
    else:
        print("❌ Scraping failed. No seasons found.")

if __name__ == "__main__":
    scrape_mushoku()