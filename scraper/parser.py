import re
import base64
import urllib.parse
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def parse_anime_homepage(html_content, base_url):
    if not html_content: return []
    soup = BeautifulSoup(html_content, 'html.parser')
    items = []
    seen_urls = set()
    for article in soup.find_all('article'):
        link_tag = article.find('a', class_='lnk-blk')
        if not link_tag:
            link_tag = article.find('a', href=re.compile(r'/series/|/anime/|/movies/'))
        if not link_tag or not link_tag.get('href'): continue
        anime_url = urljoin(base_url, link_tag['href'])
        if anime_url in seen_urls: continue
        seen_urls.add(anime_url)
        title_tag = article.find('h2', class_='entry-title')
        title = title_tag.get_text(strip=True) if title_tag else ""
        img_tag = article.find('img')
        if not title and img_tag and img_tag.get('alt'):
            title = img_tag['alt'].replace("Image ", "").strip()
        if not title or len(title) < 2: continue
        image_url = ""
        if img_tag:
            image_url = (img_tag.get('data-src') or img_tag.get('data-lazy-src') or img_tag.get('src') or "")
            if image_url.startswith('//'): image_url = 'https:' + image_url
            if image_url.startswith('data:'): image_url = ""
        url_parts = anime_url.rstrip('/').split('/')
        anime_id = url_parts[-1] if url_parts else title.lower().replace(' ', '-')
        items.append({"id": anime_id, "title": title, "url": anime_url, "image": image_url})
    return items

def parse_post_id(html_content):
    if not html_content: return None
    soup = BeautifulSoup(html_content, 'html.parser')
    
    match = re.search(r'let postID = "(\d+)"', html_content)
    if match: return str(match.group(1))
    
    body = soup.find('body')
    if body and body.get('class'):
        for cls in body.get('class'):
            if cls.startswith('postid-') or cls.startswith('post-'):
                try: return str(cls.split('-')[-1])
                except: pass
    
    for tag in soup.find_all(attrs={'data-post-id': True}):
        try: return str(tag['data-post-id'])
        except: pass
        
    return None

def extract_seasons_from_html(html_content):
    if not html_content: return []
    soup = BeautifulSoup(html_content, 'html.parser')
    seasons = []
    seen = set()
    season_buttons = soup.find_all('a', class_='season-btn')
    for btn in season_buttons:
        season_num = btn.get('data-season')
        if season_num:
            try:
                season_num = int(season_num)
                if season_num not in seen:
                    seen.add(season_num)
                    seasons.append(season_num)
            except: pass
    seasons.sort()
    return seasons

def parse_season_episodes(html_content, base_url):
    if not html_content: return []
    soup = BeautifulSoup(html_content, 'html.parser')
    episodes = []
    
    ul = soup.find('ul', id='episode_by_temp')
    if not ul:
        return episodes
    
    for li in ul.find_all('li'):
        article = li.find('article')
        if not article: continue
        
        title_tag = article.find('h2', class_='entry-title')
        num_tag = article.find('span', class_='num-epi')
        link_tag = article.find('a', class_='lnk-blk')
        
        if not title_tag or not link_tag: continue
        
        title = title_tag.get_text(strip=True)
        ep_num = num_tag.get_text(strip=True) if num_tag else str(len(episodes) + 1)
        href = link_tag['href']
        
        if not href.startswith('http'):
            href = urljoin(base_url, href)
        
        if not any(e['url'] == href for e in episodes):
            episodes.append({
                "title": title,
                "ep_num": ep_num,
                "url": href,
                "video_url": "",
                "servers": [] # 🛠️ नया फील्ड
            })
    return episodes

def parse_video_servers(html_content, base_url):
    """🛠️ नया फंक्शन: सारे सर्वर (iframes) निकालने के लिए"""
    if not html_content: return []
    soup = BeautifulSoup(html_content, 'html.parser')
    servers = []
    
    # वेबसाइट के हिसाब से iframes की लिस्ट
    iframes = soup.find_all('iframe')
    for i, iframe in enumerate(iframes):
        src = iframe.get('src') or iframe.get('data-src')
        if src:
            if src.startswith('//'): src = 'https:' + src
            servers.append({
                "name": f"Server {i+1}",
                "url": src
            })
            
    return servers

def parse_release_year(html_content):
    if not html_content: return None
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text()
    patterns = [r'(?:Aired|Release|Year|Premiered)[\s:]*(\d{4})', r'(\d{4})\s*(?:-|–)?\s*(?:\d{4}|ongoing)?']
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            year = int(match.group(1))
            if 1960 <= year <= 2030: return year
    return None

def extract_language_from_detail(detail_html):
    if not detail_html: return "Unknown"
    
    match = re.search(r'data-src="[^"]*?data=([^"&]+)"', detail_html)
    if match:
        try:
            decoded = base64.b64decode(urllib.parse.unquote(match.group(1))).decode('utf-8')
            langs = re.findall(r'"language":"([^"]+)"', decoded)
            if langs:
                return "Multi Audio" if len(langs) > 1 else f"{langs[0]} Dub"
        except: pass
    
    soup = BeautifulSoup(detail_html, 'html.parser')
    full_text = soup.get_text(separator=' ', strip=True).lower()
    languages_dict = {
        'Hindi': ['hindi', 'hin'], 'English': ['english', 'eng'], 'Tamil': ['tamil', 'tam'],
        'Telugu': ['telugu', 'tel'], 'Malayalam': ['malayalam', 'mal'], 'Kannada': ['kannada', 'kan'],
        'Bengali': ['bengali', 'ben'], 'Marathi': ['marathi', 'mar'], 'Punjabi': ['punjabi', 'pun'],
        'Japanese': ['japanese', 'jap'], 'Korean': ['korean', 'kor'],
    }
    found_languages = []
    for lang_name, keywords in languages_dict.items():
        for kw in keywords:
            if re.search(r'\b' + kw + r'\b', full_text):
                found_languages.append(lang_name)
                break 
    if len(found_languages) > 1: return "Multi Audio"
    elif len(found_languages) == 1: return f"{found_languages[0]} Dub"
    if 'dubbed' in full_text or 'dub' in full_text: return "Dubbed"
    return "Unknown"