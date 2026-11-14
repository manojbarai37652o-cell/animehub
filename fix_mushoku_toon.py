import os
import json
import time
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://toonstream.us" 
TOONSTREAM_URL = "https://toonstream.us/series/mushoku-tensei-jobless-reincarnation/" 
DB_FILE = os.path.join(os.getcwd(), 'database', 'storage.json')

BAD_SERVERS = ["ravok.buzz", "rubystm.com", "filesforever.link"]

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"anime_list": []}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def handle_access_gateway(page):
    try:
        page.wait_for_timeout(1500)
        if page.query_selector('#continueGo'):
            print("            🔓 Access Gateway bypass...")
            page.evaluate("document.getElementById('continueGo').click()")
            page.wait_for_timeout(4000)
    except Exception:
        pass

def fix_mushoku_toonstream():
    print("🔥 Scraping Mushoku Tensei via TOONSTREAM...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-ipv6", "--no-sandbox"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        page.set_default_timeout(60000)

        print(f"🌐 Loading ToonStream URL...")
        page.goto(TOONSTREAM_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        
        handle_access_gateway(page)
        detail_soup = BeautifulSoup(page.content(), 'html.parser')
        
        title = "Mushoku Tensei: Jobless Reincarnation"
        language = "Hindi Dub"
        description = "A 34-year-old underachiever gets run over by a truck, but his story doesn’t end there. Reincarnated in a new world as an infant, Rudeus will seize every opportunity to live the life he’s always wanted."
        
        image = ""
        img_tag = detail_soup.find('meta', property='og:image')
        if img_tag and img_tag.get('content'):
            image = img_tag.get('content')
        else:
            for img in detail_soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src and 'image.tmdb.org' in src:
                    image = src
                    break
        
        if image:
            image = image.replace('/w780/', '/original/').replace('/w500/', '/original/').replace('/w300/', '/original/')
            
        print(f"🖼️ Poster Link: {image}")

        seasons_dict = {}
        season_btns = page.query_selector_all('.season-btn')

        if season_btns:
            season_nums = []
            for btn in season_btns:
                try:
                    sn = int(btn.get_attribute('data-season'))
                    if sn not in season_nums: season_nums.append(sn)
                except: pass
            
            print(f"🔄 Found {len(season_nums)} Seasons. Scraping...")

            for sn in season_nums:
                print(f"   📺 Scraping Season {sn}...")
                episodes = []
                try:
                    page.evaluate("""() => { const overlay = document.getElementById('dontfoid'); if (overlay) overlay.remove(); }""")
                    btn_to_click = page.query_selector(f'.season-btn[data-season="{sn}"]')
                    if btn_to_click:
                        btn_to_click.click()
                        page.wait_for_timeout(3000)
                    
                    ep_soup = BeautifulSoup(page.content(), 'html.parser')
                    ep_container = ep_soup.find('ul', id='episode_by_temp')
                    
                    if ep_container:
                        for idx, li in enumerate(ep_container.find_all('li')):
                            ep_link = li.find('a', class_='lnk-blk') or li.find('a', href=True)
                            if ep_link:
                                ep_num = str(idx + 1)
                                ep_url = BASE_URL + ep_link['href'] if not ep_link['href'].startswith('http') else ep_link['href']
                                
                                print(f"      🎬 Checking Ep {ep_num}...")
                                new_page = context.new_page()
                                
                                # 🛠️ EPISODE LEVEL TRY-EXCEPT
                                try:
                                    new_page.goto(ep_url, wait_until="domcontentloaded", timeout=30000)
                                    new_page.wait_for_timeout(2000)
                                    handle_access_gateway(new_page)
                                    
                                    video_soup = BeautifulSoup(new_page.content(), 'html.parser')
                                    valid_srcs = []
                                    player_area = video_soup.find('aside', id='aa-options') or video_soup
                                    
                                    for iframe in player_area.find_all('iframe'):
                                        src = iframe.get('data-src') or iframe.get('src')
                                        if src and not src.startswith('javascript:'):
                                            if src.startswith('//'): src = 'https:' + src
                                            elif src.startswith('/'): src = BASE_URL + src
                                            
                                            if any(bad in src for bad in BAD_SERVERS): continue
                                            
                                            if src not in valid_srcs: valid_srcs.append(src)
                                            if len(valid_srcs) >= 2: break
                                    
                                    ep_data = {
                                        "ep_num": ep_num,
                                        "title": f"Episode {ep_num}",
                                        "video_url": valid_srcs[0] if valid_srcs else "",
                                        "servers": [{"server": f"Server {j+1}", "url": u} for j, u in enumerate(valid_srcs)]
                                    }
                                    episodes.append(ep_data)
                                    
                                except Exception as e:
                                    print(f"      ❌ Error on Ep {ep_num} (Skipping): {e}")
                                    # Agar error aaye toh khali episode save karo taaki list na ruke
                                    episodes.append({
                                        "ep_num": ep_num,
                                        "title": f"Episode {ep_num}",
                                        "video_url": "",
                                        "servers": []
                                    })
                                finally:
                                    new_page.close()
                                
                    seasons_dict[sn] = episodes
                    print(f"   ✅ Season {sn} done.")
                except Exception as e:
                    print(f"   ❌ Major Error on Season {sn}: {e}")

        print("💾 Saving to database...")
        db_data = load_db()
        anime_list = [a for a in db_data.get('anime_list', []) if "mushoku" not in a.get('title', '').lower()]
        
        final_seasons = [{"season_number": s, "episodes": eps} for s, eps in sorted(seasons_dict.items())]
        all_episodes = [ep for s in final_seasons for ep in s['episodes']]
        
        new_anime = {
            "title": title,
            "url": TOONSTREAM_URL,
            "image": image,
            "id": "mushoku-tensei-toon",
            "language": language,
            "description": description,
            "seasons": final_seasons,
            "episodes": all_episodes
        }
        
        anime_list.append(new_anime)
        db_data['anime_list'] = anime_list
        save_db(db_data)
        
        print("🎉 Mushoku Tensei saved via ToonStream!")
        browser.close()

if __name__ == "__main__":
    fix_mushoku_toonstream()