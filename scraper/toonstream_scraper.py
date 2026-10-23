import os
import json
import time
import re
import gc
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://toonstream.us" 
HOME_URL = "https://toonstream.us/home"

DB_FILE = "toonstream_data.json" 
LIVE_DB_FILE = "database/storage.json"
LINK_CACHE_FILE = "toonstream_links_cache.json" # 🛠️ सारे लिंक यहाँ सेव होंगे

# 🛑 अब कोई लिमिट नहीं (हज़ारों एनीमे स्क्रैप करने के लिए 99999)
MAX_ANIME_TO_TEST = 99999 
MAX_EPISODES_TO_CHECK = 9999 

BAD_SERVERS = ["ravok.buzz", "rubystm.com", "filesforever.link"]

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"anime_list": []}

def load_live_db():
    if os.path.exists(LIVE_DB_FILE):
        with open(LIVE_DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"anime_list": []}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def clean_title(title):
    if not title: return ""
    return re.sub(r'[^a-z0-9]', '', title.lower()).strip()

def extract_language(soup):
    page_text = soup.get_text(separator=' ').lower()
    if "hindi dub" in page_text or "hindi" in page_text: return "Hindi Dub"
    elif "tamil dub" in page_text or "tamil" in page_text: return "Tamil Dub"
    elif "telugu dub" in page_text or "telugu" in page_text: return "Telugu Dub"
    elif "english dub" in page_text or "english" in page_text: return "English Dub"
    elif "multi audio" in page_text: return "Multi Audio"
    return "Unknown"

def extract_description(soup):
    desc_tag = soup.find('div', class_='description') or soup.find('div', class_='entry-content') or soup.find('div', class_='wp-content')
    if desc_tag: return desc_tag.get_text(strip=True)
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc: return meta_desc.get('content')
    return "No description available."

# ==========================================
# 🛠️ MASTER FIX 1: सारे लिंक इकट्ठे करने वाला फंक्शन
# ==========================================
def collect_all_links(page):
    all_links = set()
    
    # अगर पहले से लिंक कैश में सेव हैं, तो उन्हें लोड करो
    if os.path.exists(LINK_CACHE_FILE):
        with open(LINK_CACHE_FILE, 'r', encoding='utf-8') as f:
            all_links.update(json.load(f))
        print(f"✅ पुराने कैश से {len(all_links)} लिंक मिल गए।")

    print("🔍 नए लिंक ढूंढ रहे हैं (Sitemap & A-Z)...")
    
    # तरीका 1: Sitemap से लिंक उठाओ
    try:
        res = requests.get(f"{BASE_URL}/sitemap.xml", timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'xml')
            for loc in soup.find_all('loc'):
                link = loc.text
                if '/series/' in link or '/movies/' in link:
                    all_links.add(link)
    except: pass

    # तरीका 2: A-Z से गहराई तक लिंक उठाओ (अब unlimited pages)
    print("🔄 अब A-Z पेजों से लिंक उठा रहे हैं (ये थोड़ा टाइम लेगा)...")
    for letter in "abcdefghijklmnopqrstuvwxyz":
        page_num = 1
        while True:
            az_url = f"{BASE_URL}/letter/{letter.upper()}/" if page_num == 1 else f"{BASE_URL}/letter/{letter.upper()}/page/{page_num}/"
            try:
                page.goto(az_url, wait_until="domcontentloaded")
                page.wait_for_timeout(1500)
                soup = BeautifulSoup(page.content(), 'html.parser')
                cards = soup.find_all('article', class_='post') or soup.find_all('li', id=re.compile(r'^post-\d+'))
                
                if not cards: 
                    break # पेज खत्म हो गया, अगले लेटर पर जाओ
                
                for card in cards:
                    link_tag = card.find('a', href=True)
                    if link_tag:
                        href = link_tag['href']
                        if not href.startswith('http'): href = BASE_URL + href
                        if '/episode/' in href:
                            href = re.sub(r'/episode/(.*?)-\d+x\d+/?.*', r'/series/\1', href)
                        all_links.add(href)
                print(f"   लेटर {letter.upper()} - पेज {page_num}: कुल {len(all_links)} लिंक मिले")
                page_num += 1
            except Exception as e:
                break # एरर आने पर अगले लेटर पर जाओ
            
    # लिंक कैश में सेव करो
    with open(LINK_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(all_links), f, indent=4)
        
    return list(all_links)

# ==========================================
# 🛠️ MASTER FIX 2: डायरेक्ट URL से एनीमे स्क्रैप करना
# ==========================================
def scrape_anime_by_url(page, url, existing_titles, anime_list):
    try:
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)
        
        detail_soup = BeautifulSoup(page.content(), 'html.parser')
        
        title_tag = detail_soup.find('h1', class_='entry-title') or detail_soup.find('h1')
        if not title_tag: return 0
        title = title_tag.get_text(strip=True)
        clean_t = clean_title(title)
        
        if clean_t in existing_titles:
            return 0 # स्किप
            
        img_tag = detail_soup.find('img', class_='wp-post-image') or detail_soup.find('div', class_='post-thumbnail').find('img') if detail_soup.find('div', class_='post-thumbnail') else detail_soup.find('img')
        image = img_tag.get('src') if img_tag else ""
        if image.startswith('//'): image = 'https:' + image
        elif image.startswith('/'): image = BASE_URL + image
        
        language = extract_language(detail_soup)
        description = extract_description(detail_soup)
        
        # मूवी लॉजिक
        if '/movies/' in url or '/movie/' in url:
            valid_srcs = []
            player_area = detail_soup.find('aside', id='aa-options') or detail_soup
            for iframe in player_area.find_all('iframe'):
                src = iframe.get('data-src') or iframe.get('src')
                if src and not src.startswith('javascript:'):
                    if src.startswith('//'): src = 'https:' + src
                    elif src.startswith('/'): src = BASE_URL + src
                    if any(bad in src for bad in BAD_SERVERS): continue
                    if src not in valid_srcs: valid_srcs.append(src)
                    if len(valid_srcs) >= 2: break
            
            servers = [{"server": f"Server {j+1}", "url": u} for j, u in enumerate(valid_srcs)]
            movie_episode = {'title': 'Full Movie', 'url': url, 'video_url': servers[0]['url'] if servers else "", 'servers': servers}
            
            anime_list.append({
                'title': title, 'url': url, 'image': image, 'id': str(abs(hash(url))),
                'language': language, 'description': description,
                'seasons': [{"season_number": 1, "episodes": [movie_episode]}], 'episodes': [movie_episode]
            })
            existing_titles.add(clean_t)
            print(f"      ✅ मूवी सेव हो गई!")
            return 1

        # सीरीज़ लॉजिक
        seasons_dict = {}
        season_btns = page.query_selector_all('.season-btn')
        
        if season_btns:
            season_nums = []
            for btn in season_btns:
                try:
                    sn = int(btn.get_attribute('data-season'))
                    if sn not in season_nums: season_nums.append(sn)
                except: pass
            
            for sn in season_nums:
                page.evaluate("() => { const o = document.getElementById('dontfoid'); if(o) o.remove(); }")
                btn_to_click = page.query_selector(f'.season-btn[data-season="{sn}"]')
                if btn_to_click:
                    btn_to_click.click()
                    page.wait_for_timeout(1500)
                    season_soup = BeautifulSoup(page.content(), 'html.parser')
                    eps = []
                    ep_container = season_soup.find('ul', id='episode_by_temp')
                    if ep_container:
                        for li in ep_container.find_all('li'):
                            ep_link = li.find('a', href=True)
                            if ep_link:
                                ep_title = li.find('h2', class_='entry-title') or li.find('span', class_='num-epi')
                                ep_url = BASE_URL + ep_link['href'] if not ep_link['href'].startswith('http') else ep_link['href']
                                eps.append({'title': ep_title.get_text(strip=True) if ep_title else "Episode", 'url': ep_url, 'video_url': '', 'servers': []})
                    if eps: seasons_dict[sn] = eps
        else:
            eps = []
            ep_container = detail_soup.find('ul', id='episode_by_temp')
            if ep_container:
                for li in ep_container.find_all('li'):
                    ep_link = li.find('a', href=True)
                    if ep_link:
                        ep_title = li.find('h2', class_='entry-title') or li.find('span', class_='num-epi')
                        ep_url = BASE_URL + ep_link['href'] if not ep_link['href'].startswith('http') else ep_link['href']
                        eps.append({'title': ep_title.get_text(strip=True) if ep_title else "Episode", 'url': ep_url, 'video_url': '', 'servers': []})
            if eps: seasons_dict[1] = eps

        final_seasons = []
        all_episodes_flat = []
        
        for s_num in sorted(seasons_dict.keys()):
            eps = seasons_dict[s_num]
            print(f"      📺 Season {s_num}: {len(eps)} एपिसोड मिले")
            for ep in eps:
                try:
                    page.goto(ep['url'], wait_until="domcontentloaded")
                    page.wait_for_timeout(1200) 
                    ep_soup = BeautifulSoup(page.content(), 'html.parser')
                    valid_srcs = []
                    player_area = ep_soup.find('aside', id='aa-options') or ep_soup
                    for iframe in player_area.find_all('iframe'):
                        src = iframe.get('data-src') or iframe.get('src')
                        if src and not src.startswith('javascript:'):
                            if src.startswith('//'): src = 'https:' + src
                            elif src.startswith('/'): src = BASE_URL + src
                            if any(bad in src for bad in BAD_SERVERS): continue
                            if src not in valid_srcs: valid_srcs.append(src)
                            if len(valid_srcs) >= 2: break
                    
                    if valid_srcs:
                        ep['video_url'] = valid_srcs[0] 
                        ep['servers'] = [{"server": f"Server {j+1}", "url": u} for j, u in enumerate(valid_srcs)]
                except: pass
            
            final_seasons.append({"season_number": s_num, "episodes": eps})
            all_episodes_flat.extend(eps)

        anime_list.append({
            'title': title, 'url': url, 'image': image, 'id': str(abs(hash(url))),
            'language': language, 'description': description,
            'seasons': final_seasons, 'episodes': all_episodes_flat
        })
        existing_titles.add(clean_t)
        print(f"      💾 सेव हो गया! (कुल {len(final_seasons)} सीज़न)")
        return 1
    except Exception as e:
        print(f"   ❌ एरर: {e}")
        return 0

if __name__ == '__main__':
    print("=" * 60)
    print("🔥 TOONSTREAM MEGA SCRAPER (A TO Z - NO LIMITS)")
    print("=" * 60)

    db_data = load_db()
    live_db_data = load_live_db() 

    anime_list = db_data.get('anime_list', [])
    
    existing_titles = set(clean_title(anime.get('title', '')) for anime in anime_list)
    existing_titles.update(set(clean_title(anime.get('title', '')) for anime in live_db_data.get('anime_list', [])))
    
    print(f"📊 पहले से {len(existing_titles)} एनीमे डेटाबेस में हैं।\n")
    new_anime_added = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--disable-ipv6", "--no-sandbox"])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
            page = context.new_page()
            page.set_default_timeout(60000)

            # चरण 1: सारे लिंक इकट्ठे करो
            all_links = collect_all_links(page)
            print(f"\n🎯 कुल {len(all_links)} लिंक मिले। अब स्क्रैपिंग शुरू...")

            # चरण 2: लिंक्स को स्क्रैप करो
            for index, link in enumerate(all_links):
                if new_anime_added >= MAX_ANIME_TO_TEST: break
                
                print(f"\n[{index+1}/{len(all_links)}] 🔎 चेक कर रहे हैं: {link}")
                added = scrape_anime_by_url(page, link, existing_titles, anime_list)
                
                if added:
                    new_anime_added += 1
                    save_db({"anime_list": anime_list})
                    time.sleep(1)

                # ==========================================
                # 🛡️ RAM MANAGEMENT (हर 50 एनीमे के बाद)
                # ==========================================
                if (index + 1) % 50 == 0:
                    print("\n   🧹 रैम (RAM) साफ की जा रही है और ब्राउज़र रीस्टार्ट हो रहा है...")
                    context.close()
                    browser.close()
                    gc.collect()
                    time.sleep(2)
                    
                    # ब्राउज़र को फिर से चालू करो
                    browser = p.chromium.launch(headless=False, args=["--disable-ipv6", "--no-sandbox"])
                    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
                    page = context.new_page()
                    page.set_default_timeout(60000)

            browser.close()
    except KeyboardInterrupt:
        print("\n🛑 रोक दिया गया!")

    save_db({"anime_list": anime_list})
    print(f"\n🎉 स्क्रैपिंग पूरी! कुल {new_anime_added} नए एनीमे/मूवी सेव हुए।")