import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def parse_anime_homepage(html_content, base_url):
    if not html_content: return []
    soup = BeautifulSoup(html_content, 'html.parser')
    items = []
    seen_urls = set()
    for article in soup.find_all('article'):
        anime_url = ""
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
    body = soup.find('body')
    if body and body.get('class'):
        for cls in body.get('class'):
            if cls.startswith('postid-'):
                try: return int(cls.replace('postid-', ''))
                except: pass
    for tag in soup.find_all(attrs={'data-post-id': True}):
        try: return int(tag['data-post-id'])
        except: pass
    match = re.search(r'"post_id"\s*:\s*(\d+)', html_content)
    if match: return int(match.group(1))
    return None

def parse_season_episodes(html_content, base_url):
    """ये फंक्शन किसी भी सीज़न के HTML से episodes के लिंक निकालेगा"""
    if not html_content: return []
    soup = BeautifulSoup(html_content, 'html.parser')
    episodes = []
    seen_urls = set()
    for link in soup.find_all('a', href=True):
        ep_url = urljoin(base_url, link['href'])
        if '/episode/' in ep_url or '/episodes/' in ep_url:
            if ep_url in seen_urls: continue
            seen_urls.add(ep_url)
            ep_title = "Episode"
            match = re.search(r'(\d+)x(\d+)', ep_url)
            if match:
                ep_title = f"Episode {match.group(2)}"
            else:
                num_match = re.search(r'(\d+)', ep_url.rstrip('/').split('-')[-1])
                if num_match: ep_title = f"Episode {num_match.group(1)}"
            episodes.append({"title": ep_title, "url": ep_url})
    def get_ep_num(ep):
        m = re.search(r'(\d+)', ep['title'])
        return int(m.group(1)) if m else 999
    episodes.sort(key=get_ep_num)
    return episodes

def parse_video_link(html_content, base_url):
    """एपिसोड/मूवी के पेज से वीडियो iframe/m3u8 लिंक निकालता है"""
    if not html_content: return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    iframes = soup.find_all('iframe')
    for iframe in iframes:
        src = iframe.get('src') or iframe.get('data-src')
        if src:
            if src.startswith('//'): src = 'https:' + src
            if 'http' in src: return src
    video = soup.find('video')
    if video and video.get('src'):
        src = video['src']
        if src.startswith('//'): src = 'https:' + src
        return src
    match = re.search(r'(https?://[^\s"\']+\.(m3u8|mp4))', html_content)
    if match: return match.group(1)
    return ""

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