import os
import json
import time
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://toonstream.us" 
HOME_URL = "https://toonstream.us/home"

# 🛑 यहाँ हम 'test_storage' की जगह 'toonstream_data.json' बना रहे हैं 
# ताकि तुम्हारे असली डेटा के साथ कोई गड़बड़ न हो।
DB_FILE = "toonstream_data.json" 

MAX_ANIME_TO_TEST = 20  # जितने एनीमे चाहिए उतने यहाँ डालो
MAX_EPISODES_TO_CHECK = 9999 

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
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

def process_anime_card(page, card, existing_titles, anime_list):
    try:
        title_tag = card.find('h2', class_='entry-title') or card.find('h2')
        link_tag = card.find('a', class_='lnk-blk') or card.find('a', href=True)
        if not title_tag or not link_tag: return 0
        
        title = title_tag.get_text(strip=True)
        clean_t = clean_title(title)
        
        if clean_t in existing_titles:
            print(f"   ⏭️ स्किप: {title}")
            return 0
        
        original_href = link_tag['href']
        if not original_href.startswith('http'):
            original_href = BASE_URL + original_href if original_href.startswith('/') else BASE_URL + '/' + original_href
        
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
        
        img_tag = card.find('img')
        image = img_tag.get('src') if img_tag else ""
        if image.startswith('//'): image = 'https:' + image
        elif image.startswith('/'): image = BASE_URL + image

        page.goto(href, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000) 
        
        detail_soup = BeautifulSoup(page.content(), 'html.parser')
        language = extract_language(detail_soup)
        description = extract_description(detail_soup)
        print(f"      🌐 Audio: {language}")
        
        episodes = []
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
        
        print(f"      📺 कुल {len(episodes)} एपिसोड मिले।")

        for ep in episodes[:MAX_EPISODES_TO_CHECK]:
            print(f"      🎬 चेक: {ep['title']}")
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
                        if src not in valid_srcs:
                            valid_srcs.append(src)
                        if len(valid_srcs) >= 2: break # सिर्फ 2 सर्वर
                
                if valid_srcs:
                    ep['video_url'] = valid_srcs[0] 
                    ep['servers'] = [{"server": f"Server {j+1}", "url": u} for j, u in enumerate(valid_srcs)]
                    print(f"         ✅ {len(valid_srcs)} iframe मिले।")
            except Exception as e:
                pass

        new_anime_data = {
            'title': title, 'url': href, 'image': image, 'id': str(abs(hash(href))),
            'language': language, 'description': description,
            'seasons': [{"season_number": 1, "episodes": episodes}], 'episodes': episodes
        }
        
        anime_list.append(new_anime_data)
        existing_titles.add(clean_t)
        print(f"      💾 सेव हो गया!")
        return 1
    except Exception as e:
        print(f"   ❌ एरर: {e}")
        return 0

if __name__ == '__main__':
    print("=" * 60)
    print("🔥 TOONSTREAM DEDICATED SCRAPER (कोई खिचड़ी नहीं)")
    print("=" * 60)

    db_data = load_db()
    anime_list = db_data.get('anime_list', [])
    existing_titles = set(clean_title(anime.get('title', '')) for anime in anime_list)
    print(f"📊 DB में पहले से {len(existing_titles)} एनीमे हैं।\n")
    new_anime_added = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--disable-ipv6", "--no-sandbox"])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
            page = context.new_page()
            page.set_default_timeout(60000)

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

            browser.close()
    except KeyboardInterrupt:
        print("\n🛑 रोक दिया गया!")

    save_db({"anime_list": anime_list})
    print(f"\n🎉 स्क्रैपिंग पूरी! कुल {new_anime_added} नए एनीमे सेव हुए।")