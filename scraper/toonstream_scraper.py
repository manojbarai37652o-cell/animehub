import os
import json
import time
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://toonstream.us" 
HOME_URL = "https://toonstream.us/home"

DB_FILE = "toonstream_data.json" 
LIVE_DB_FILE = "database/storage.json" # 🛠️ लाइव डेटाबेस (ताकि पुराने एनीमे स्किप हों)

# 🛑 एक बार में सिर्फ 200 नए एनीमे स्क्रैप होंगे
MAX_ANIME_TO_TEST = 200 
MAX_EPISODES_TO_CHECK = 9999 

# 🚫 BLACKLIST: यहाँ उन सर्वर्स के नाम लिखो जो बहुत ज्यादा ऐड दिखाते हैं या रीडायरेक्ट करते हैं
BAD_SERVERS = [
    "ravok.buzz",
    "rubystm.com",
    "filesforever.link"
]

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

def parse_episodes_from_current_page(page):
    episodes = []
    detail_soup = BeautifulSoup(page.content(), 'html.parser')
    ep_container = detail_soup.find('ul', id='episode_by_temp')
    
    if ep_container:
        for li in ep_container.find_all('li'):
            ep_link = li.find('a', class_='lnk-blk') or li.find('a', href=True)
            if ep_link:
                ep_title = li.find('h2', class_='entry-title') or li.find('span', class_='num-epi')
                ep_title_text = ep_title.get_text(strip=True) if ep_title else "Episode"
                ep_url = BASE_URL + ep_link['href'] if not ep_link['href'].startswith('http') else ep_link['href']
                episodes.append({'title': ep_title_text, 'url': ep_url, 'video_url': '', 'servers': []})
                
    if len(episodes) == 0:
        for a_tag in detail_soup.find_all('a', href=True):
            if '/episode/' in a_tag['href']:
                ep_title = a_tag.get_text(strip=True) or a_tag['href'].split('/')[-2]
                ep_url = a_tag['href'] if a_tag['href'].startswith('http') else BASE_URL + a_tag['href']
                if not any(ep['url'] == ep_url for ep in episodes):
                    episodes.append({'title': ep_title, 'url': ep_url, 'video_url': '', 'servers': []})
    return episodes

def process_anime_card(page, card, existing_titles, anime_list):
    try:
        title_tag = card.find('h2', class_='entry-title') or card.find('h2')
        link_tag = card.find('a', class_='lnk-blk') or card.find('a', href=True)
        if not title_tag or not link_tag: return 0
        
        title = title_tag.get_text(strip=True)
        clean_t = clean_title(title)
        
        # 🛑 अगर एनीमे पहले से toonstream_data.json या storage.json में है, तो स्किप करो
        if clean_t in existing_titles:
            print(f"   ⏭️ स्किप (पहले से है): {title}")
            return 0
        
        original_href = link_tag['href']
        if not original_href.startswith('http'):
            original_href = BASE_URL + original_href if original_href.startswith('/') else BASE_URL + '/' + original_href
        
        img_tag = card.find('img')
        image = img_tag.get('src') if img_tag else ""
        if image.startswith('//'): image = 'https:' + image
        elif image.startswith('/'): image = BASE_URL + image

        # ==========================================
        # 🎬 मूवी का लॉजिक (अगर URL में /movies/ है)
        # ==========================================
        if '/movies/' in original_href or '/movie/' in original_href:
            print(f"\n   🎬 नई मूवी मिली: {title}")
            page.goto(original_href, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            
            detail_soup = BeautifulSoup(page.content(), 'html.parser')
            language = extract_language(detail_soup)
            description = extract_description(detail_soup)
            
            valid_srcs = []
            player_area = detail_soup.find('aside', id='aa-options') or detail_soup
            for iframe in player_area.find_all('iframe'):
                src = iframe.get('data-src') or iframe.get('src')
                if src and not src.startswith('javascript:'):
                    if src.startswith('//'): src = 'https:' + src
                    elif src.startswith('/'): src = BASE_URL + src
                    
                    # 🚫 खराब सर्वर चेक
                    if any(bad in src for bad in BAD_SERVERS):
                        print(f"         ❌ बैड सर्वर स्किप: {src[:40]}...")
                        continue
                        
                    if src not in valid_srcs:
                        valid_srcs.append(src)
                    if len(valid_srcs) >= 2: break # सिर्फ 2 सर्वर
            
            servers = [{"server": f"Server {j+1}", "url": u} for j, u in enumerate(valid_srcs)]
            print(f"      🌐 Audio: {language} | ✅ {len(servers)} साफ iframe मिले")
            
            movie_episode = {
                'title': 'Full Movie',
                'url': original_href,
                'video_url': servers[0]['url'] if servers else "",
                'servers': servers
            }
            
            new_anime_data = {
                'title': title, 
                'url': original_href, 
                'image': image, 
                'id': str(abs(hash(original_href))),
                'language': language, 
                'description': description,
                'seasons': [{"season_number": 1, "episodes": [movie_episode]}], 
                'episodes': [movie_episode]
            }
            
            anime_list.append(new_anime_data)
            existing_titles.add(clean_t)
            print(f"      💾 मूवी सेव हो गई!")
            return 1

        # ==========================================
        # 📺 सीरीज़ का लॉजिक
        # ==========================================
        print(f"\n   🆕 नया एनीमे: {title}")
        
        href = original_href
        if '/episode/' in original_href:
            page.goto(original_href, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            ep_page_soup = BeautifulSoup(page.content(), 'html.parser')
            series_link_tag = ep_page_soup.find('a', href=re.compile(r'/series/'))
            if series_link_tag:
                href = series_link_tag['href']
                if not href.startswith('http'):
                    href = BASE_URL + href if href.startswith('/') else BASE_URL + '/' + href

        page.goto(href, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000) 
        
        detail_soup = BeautifulSoup(page.content(), 'html.parser')
        language = extract_language(detail_soup)
        description = extract_description(detail_soup)
        print(f"      🌐 Audio: {language}")
        
        seasons_dict = {}
        season_btns = page.query_selector_all('.season-btn')
        
        if season_btns:
            season_nums = []
            for btn in season_btns:
                try:
                    sn = int(btn.get_attribute('data-season'))
                    if sn not in season_nums:
                        season_nums.append(sn)
                except:
                    pass
            
            print(f"      🔄 इस एनीमे में {len(season_nums)} सीज़न मिले हैं। सभी को स्क्रैप कर रहे हैं...")
            
            for sn in season_nums:
                try:
                    # 🛠️ FIX: क्लिक करने से पहले पारदर्शी परत (overlay) को हटाओ
                    page.evaluate("""() => {
                        const overlay = document.getElementById('dontfoid');
                        if (overlay) overlay.remove();
                    }""")
                    
                    # अब बटन को क्लिक करो
                    btn_to_click = page.query_selector(f'.season-btn[data-season="{sn}"]')
                    if btn_to_click:
                        btn_to_click.click()
                        page.wait_for_timeout(2500) # सर्वर से एपिसोड लोड होने का इंतज़ार
                    
                    season_eps = parse_episodes_from_current_page(page)
                    if season_eps:
                        seasons_dict[sn] = season_eps
                        print(f"         📺 Season {sn} में {len(season_eps)} एपिसोड मिले।")
                except Exception as e:
                    print(f"         ⚠️ सीज़न {sn} बटन क्लिक करने में दिक्कत: {e}")
        else:
            season_eps = parse_episodes_from_current_page(page)
            if season_eps:
                seasons_dict[1] = season_eps
                print(f"      📺 Season 1 में {len(season_eps)} एपिसोड मिले।")

        final_seasons = []
        all_episodes_flat = []
        
        for s_num in sorted(seasons_dict.keys()):
            eps = seasons_dict[s_num]
            for ep in eps[:MAX_EPISODES_TO_CHECK]:
                print(f"         🎬 चेक: {ep['title']}")
                try:
                    page.goto(ep['url'], wait_until="domcontentloaded")
                    page.wait_for_timeout(2000) 
                    ep_soup = BeautifulSoup(page.content(), 'html.parser')
                    valid_srcs = []
                    player_area = ep_soup.find('aside', id='aa-options') or ep_soup
                    for iframe in player_area.find_all('iframe'):
                        src = iframe.get('data-src') or iframe.get('src')
                        if src and not src.startswith('javascript:'):
                            if src.startswith('//'): src = 'https:' + src
                            elif src.startswith('/'): src = BASE_URL + src
                            
                            # 🚫 खराब सर्वर चेक (सीरीज़ के लिए)
                            if any(bad in src for bad in BAD_SERVERS):
                                print(f"            ❌ बैड सर्वर स्किप: {src[:40]}...")
                                continue
                                
                            if src not in valid_srcs:
                                valid_srcs.append(src)
                            if len(valid_srcs) >= 2: break # सिर्फ 2 सर्वर
                    
                    if valid_srcs:
                        ep['video_url'] = valid_srcs[0] 
                        ep['servers'] = [{"server": f"Server {j+1}", "url": u} for j, u in enumerate(valid_srcs)]
                        print(f"            ✅ {len(valid_srcs)} साफ सर्वर मिले")
                except Exception as e:
                    pass
            
            final_seasons.append({"season_number": s_num, "episodes": eps})
            all_episodes_flat.extend(eps)

        new_anime_data = {
            'title': title, 
            'url': href, 
            'image': image, 
            'id': str(abs(hash(href))),
            'language': language, 
            'description': description,
            'seasons': final_seasons, 
            'episodes': all_episodes_flat
        }
        
        anime_list.append(new_anime_data)
        existing_titles.add(clean_t)
        print(f"      💾 सेव हो गया! (कुल {len(final_seasons)} सीज़न पूरी तरह स्क्रैप हुए)")
        return 1
    except Exception as e:
        print(f"   ❌ एरर: {e}")
        return 0

if __name__ == '__main__':
    print("=" * 60)
    print("🔥 TOONSTREAM SCRAPER (100 ANIME PER RUN + CORRECT A-Z + BAD SERVER FILTER)")
    print("=" * 60)

    db_data = load_db()
    live_db_data = load_live_db() # 🛠️ लाइव डेटा लोड करो

    anime_list = db_data.get('anime_list', [])
    
    # 🛠️ FIX: दोनों डेटाबेस से टाइटल इकट्ठा करो (ताकि जो पहले से वेबसाइट पर है, वो दोबारा स्क्रैप न हो)
    existing_titles = set(clean_title(anime.get('title', '')) for anime in anime_list)
    existing_titles.update(set(clean_title(anime.get('title', '')) for anime in live_db_data.get('anime_list', [])))
    
    print(f"📊 टोटल स्किप लिस्ट (ToonStream + Live DB) में {len(existing_titles)} एनीमे हैं।\n")
    print(f"🎯 इस रन में सिर्फ {MAX_ANIME_TO_TEST} नए एनीमे स्क्रैप होंगे।\n")
    new_anime_added = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--disable-ipv6", "--no-sandbox"])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
            page = context.new_page()
            page.set_default_timeout(60000)

            # ==========================================
            # चरण 1: होम पेज स्क्रैपिंग
            # ==========================================
            print(f"🌐 होमपेज: {HOME_URL}")
            page.goto(HOME_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(4000) 
            
            soup = BeautifulSoup(page.content(), 'html.parser')
            cards = soup.find_all('article', class_='post') or soup.find_all('li', id=re.compile(r'^post-\d+'))
            
            for card in cards:
                if new_anime_added >= MAX_ANIME_TO_TEST: break
                added = process_anime_card(page, card, existing_titles, anime_list)
                if added:
                    new_anime_added += added
                    save_db({"anime_list": anime_list})
                    time.sleep(1)

            # ==========================================
            # चरण 2: A से Z तक (हर लेटर के 18 पेज तक) स्क्रैपिंग
            # ==========================================
            if new_anime_added < MAX_ANIME_TO_TEST:
                print("\n" + "=" * 60)
                print("🔤 अब A से Z तक के पेज (हर लेटर के 18 पेज) स्क्रैप कर रहे हैं...")
                print("=" * 60)

                for letter in "abcdefghijklmnopqrstuvwxyz":
                    if new_anime_added >= MAX_ANIME_TO_TEST: break
                    
                    # 🛠️ FIX: पेज 1 से शुरू करके 18 तक जाएगा
                    for page_num in range(1, 19):
                        if new_anime_added >= MAX_ANIME_TO_TEST: break
                        
                        # 🛠️ FIX: सही URL /letter/A/ और पेजिनेशन /letter/A/page/2/
                        az_url = f"{BASE_URL}/letter/{letter.upper()}/" if page_num == 1 else f"{BASE_URL}/letter/{letter.upper()}/page/{page_num}/"
                        
                        print(f"\n🌐 लेटर '{letter.upper()}' - पेज {page_num} पर जा रहे हैं: {az_url}")
                        
                        try:
                            page.goto(az_url, wait_until="domcontentloaded")
                            page.wait_for_timeout(3000)
                            
                            az_soup = BeautifulSoup(page.content(), 'html.parser')
                            az_cards = az_soup.find_all('article', class_='post') or az_soup.find_all('li', id=re.compile(r'^post-\d+'))
                            
                            if not az_cards:
                                print(f"   ⚠️ पेज {page_num} पर कोई कार्ड नहीं मिला (पेज खत्म)। अगले लेटर पर जा रहे हैं।")
                                break # बाहर निकलो, अगले लेटर पर जाओ
                                
                            print(f"   🔍 पेज {page_num} पर {len(az_cards)} कार्ड्स मिले।")
                            
                            for card in az_cards:
                                if new_anime_added >= MAX_ANIME_TO_TEST: break
                                added = process_anime_card(page, card, existing_titles, anime_list)
                                if added:
                                    new_anime_added += added
                                    save_db({"anime_list": anime_list})
                                    time.sleep(1)
                                    
                        except Exception as e:
                            print(f"   ❌ लेटर {letter.upper()} - पेज {page_num} पर एरर: {e}")
                            break # एरर आने पर अगले लेटर पर जाओ

            browser.close()
    except KeyboardInterrupt:
        print("\n🛑 रोक दिया गया!")

    save_db({"anime_list": anime_list})
    print(f"\n🎉 स्क्रैपिंग पूरी! कुल {new_anime_added} नए एनीमे/मूवी सेव हुए।")