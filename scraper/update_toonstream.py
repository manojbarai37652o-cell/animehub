import os
import json
import time
import re
import gc
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://toonstream.us"
DB_FILE = "database/storage.json"
PROGRESS_FILE = "database/update_toon_progress.json" # नया चेकपॉइंट

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"anime_list": []}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {"completed_ids": []}

def save_progress(data):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(data, f)

def extract_language(soup):
    page_text = soup.get_text(separator=' ').lower()
    if "hindi dub" in page_text or "hindi" in page_text: return "Hindi Dub"
    elif "tamil dub" in page_text or "tamil" in page_text: return "Tamil Dub"
    elif "telugu dub" in page_text or "telugu" in page_text: return "Telugu Dub"
    elif "english dub" in page_text or "english" in page_text: return "English Dub"
    elif "multi audio" in page_text: return "Multi Audio"
    return "Unknown"

if __name__ == '__main__':
    print("=" * 60)
    print("🔄 TOONSTREAM UPDATE LIBRARY (MEGA UPDATE MODE)")
    print("=" * 60)

    db_data = load_db()
    anime_list = db_data.get('anime_list', [])
    progress_data = load_progress()
    completed_ids = set(progress_data.get('completed_ids', []))
    
    # सिर्फ वही एनीमे चुनो जो ToonStream के हैं और जो अभी तक चेक नहीं हुए
    toonstream_animes = [a for a in anime_list if 'toonstream.us' in a.get('url', '') and a.get('id') not in completed_ids]
    
    print(f"📊 कुल {len(anime_list)} एनीमे में से, {len(toonstream_animes)} एनीमे अभी बाकी हैं।")
    print("🔍 अब इन सबको एक-एक करके चेक किया जाएगा...\n")

    updated_count = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--disable-ipv6", "--no-sandbox"])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
            page = context.new_page()
            page.set_default_timeout(60000)

            for index, anime in enumerate(toonstream_animes):
                anime_id = anime.get('id')
                title = anime.get('title', 'Unknown')
                series_url = anime.get('url', '')
                
                if not series_url: continue

                print(f"[{index+1}/{len(toonstream_animes)}] 🔎 चेक कर रहे हैं: {title}")

                try:
                    page.goto(series_url, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(1000)

                    detail_soup = BeautifulSoup(page.content(), 'html.parser')
                    
                    live_episodes = []
                    ep_container = detail_soup.find('ul', id='episode_by_temp')
                    if ep_container:
                        for li in ep_container.find_all('li'):
                            ep_link = li.find('a', class_='lnk-blk') or li.find('a', href=True)
                            if ep_link:
                                ep_title = li.find('h2', class_='entry-title') or li.find('span', class_='num-epi')
                                ep_title_text = ep_title.get_text(strip=True) if ep_title else "Episode"
                                ep_url = BASE_URL + ep_link['href'] if not ep_link['href'].startswith('http') else ep_link['href']
                                
                                existing_ep = next((e for e in anime.get('episodes', []) if e['url'] == ep_url), None)
                                
                                if existing_ep:
                                    live_episodes.append(existing_ep)
                                else:
                                    live_episodes.append({'title': ep_title_text, 'url': ep_url, 'video_url': '', 'servers': []})

                    old_ep_count = len(anime.get('episodes', []))
                    new_ep_count = len(live_episodes)
                    
                    if new_ep_count > old_ep_count:
                        print(f"   🎉 नया एपिसोड मिला! (पहले {old_ep_count} थे, अब {new_ep_count} हैं)")
                        
                        for ep in live_episodes:
                            if ep['video_url'] == '': 
                                page.goto(ep['url'], wait_until="domcontentloaded")
                                page.wait_for_timeout(1500)
                                
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
                                        if len(valid_srcs) >= 2: break 
                                
                                if valid_srcs:
                                    ep['video_url'] = valid_srcs[0] 
                                    ep['servers'] = [{"server": f"Server {j+1}", "url": u} for j, u in enumerate(valid_srcs)]
                        
                        anime['episodes'] = live_episodes
                        if 'seasons' in anime and len(anime['seasons']) > 0:
                            anime['seasons'][0]['episodes'] = live_episodes
                        else:
                            anime['seasons'] = [{"season_number": 1, "episodes": live_episodes}]
                        
                        anime['language'] = extract_language(detail_soup)

                        save_db({"anime_list": anime_list})
                        updated_count += 1
                        print(f"   💾 डेटाबेस अपडेट हो गया!")
                    else:
                        print(f"   ✅ कोई नया एपिसोड नहीं आया।")

                except Exception as e:
                    print(f"   ❌ एरर आया: {e}")
                
                # चेकपॉइंट सेव करो
                completed_ids.add(anime_id)
                progress_data['completed_ids'] = list(completed_ids)
                save_progress(progress_data)

                # 🛠️ हर 50 एनीमे के बाद ब्राउज़र रीस्टार्ट और रैम सफाई
                if (index + 1) % 50 == 0:
                    print("\n   🧹 रैम (RAM) साफ की जा रही है और ब्राउज़र रीस्टार्ट हो रहा है...")
                    context.close()
                    browser.close()
                    gc.collect()
                    time.sleep(2)
                    
                    browser = p.chromium.launch(headless=False, args=["--disable-ipv6", "--no-sandbox"])
                    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
                    page = context.new_page()
                    page.set_default_timeout(60000)
                
                time.sleep(1.5)

            browser.close()

    except KeyboardInterrupt:
        print("\n\n🛑 स्क्रैपिंग यूजर द्वारा रोक दी गई!")

    print("\n" + "=" * 60)
    print(f"🎉 अपडेट प्रोसेस खत्म! कुल {updated_count} एनीमे में नए एपिसोड जोड़े गए।")
    print("=" * 60)