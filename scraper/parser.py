import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def parse_anime_homepage(html_content, base_url):
    if not html_content:
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    items = []
    seen_urls = set()

    for article in soup.find_all('article'):
        anime_url = ""
        link_tag = article.find('a', class_='lnk-blk')
        if not link_tag:
            link_tag = article.find('a', href=re.compile(r'/series/|/anime/'))
        
        if not link_tag or not link_tag.get('href'):
            continue
        
        anime_url = urljoin(base_url, link_tag['href'])
        
        if anime_url in seen_urls:
            continue
        seen_urls.add(anime_url)
        
        title_tag = article.find('h2', class_='entry-title')
        title = ""
        if title_tag:
            title = title_tag.get_text(strip=True)
        
        img_tag = article.find('img')
        if not title and img_tag and img_tag.get('alt'):
            title = img_tag['alt'].replace("Image ", "").strip()
        
        if not title or len(title) < 2:
            continue
        
        image_url = ""
        if img_tag:
            image_url = (img_tag.get('data-src') or 
                         img_tag.get('data-lazy-src') or 
                         img_tag.get('src') or "")
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            if image_url.startswith('data:'):
                image_url = ""
        
        url_parts = anime_url.rstrip('/').split('/')
        anime_id = url_parts[-1] if url_parts else title.lower().replace(" ", "-")
        
        items.append({
            "id": anime_id,
            "title": title,
            "url": anime_url,
            "image": image_url
        })
    
    return items


def parse_episodes(html_content, base_url):
    if not html_content: return []
    soup = BeautifulSoup(html_content, 'html.parser')
    episodes = []
    seen_urls = set()
    for link in soup.find_all('a', href=True):
        ep_url = urljoin(base_url, link['href'])
        if '/episode/' in ep_url or '/episodes/' in ep_url:
            if ep_url in seen_urls: continue
            ep_title = "Episode"
            match = re.search(r'(\d+)x(\d+)', ep_url)
            if match:
                ep_title = f"Episode {match.group(2)}"
            else:
                num_match = re.search(r'(\d+)', ep_url.rstrip('/').split('-')[-1])
                if num_match: ep_title = f"Episode {num_match.group(1)}"
            episodes.append({"title": ep_title, "url": ep_url})
            seen_urls.add(ep_url)
    def get_ep_num(ep):
        m = re.search(r'(\d+)', ep['title'])
        return int(m.group(1)) if m else 999
    episodes.sort(key=get_ep_num)
    return episodes


def parse_season_episodes(html_content, base_url):
    return parse_episodes(html_content, base_url)


def parse_seasons(html_content, base_url):
    if not html_content: return []
    soup = BeautifulSoup(html_content, 'html.parser')
    seasons = []
    seen = set()
    for tag in soup.find_all(['a', 'button'], string=re.compile(r'Season\s*\d+', re.IGNORECASE)):
        text = tag.get_text(strip=True)
        season_num = None
        match = re.search(r'Season\s*(\d+)', text, re.IGNORECASE)
        if match:
            season_num = int(match.group(1))
        if not season_num or season_num in seen: continue
        season_url = base_url
        if tag.name == 'a' and tag.get('href'):
            season_url = urljoin(base_url, tag['href'])
        seasons.append({
            "season_number": season_num,
            "season_label": text,
            "url": season_url
        })
        seen.add(season_num)
    seasons.sort(key=lambda x: x['season_number'])
    return seasons


def parse_season_ajax(html_content, base_url):
    if not html_content: return []
    soup = BeautifulSoup(html_content, 'html.parser')
    episodes = []
    seen_urls = set()
    for article in soup.find_all('article'):
        title_tag = article.find('h2', class_='entry-title')
        ep_title = title_tag.get_text(strip=True) if title_tag else "Episode"
        num_tag = article.find('span', class_='num-epi')
        ep_num = num_tag.get_text(strip=True) if num_tag else "?"
        link_tag = article.find('a', href=True)
        ep_url = ""
        if link_tag:
            ep_url = urljoin(base_url, link_tag['href'])
            if ep_url in seen_urls: continue
            seen_urls.add(ep_url)
        if ep_url:
            episodes.append({
                "title": f"Episode {ep_num}",
                "episode_name": ep_title,
                "url": ep_url
            })
    def get_ep_num(ep):
        m = re.search(r'(\d+)', ep['title'])
        return int(m.group(1)) if m else 999
    episodes.sort(key=get_ep_num)
    return episodes


def parse_video_link(html_content, base_url):
    if not html_content: return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    iframe = soup.find('iframe')
    if iframe and iframe.get('src'):
        v = iframe['src']
        if v.startswith('//'): v = 'https:' + v
        return v
    video = soup.find('video')
    if video and video.get('src'):
        v = video['src']
        if v.startswith('//'): v = 'https:' + v
        return v
    match = re.search(r'(https?://[^\s"\']+\.(m3u8|mp4))', html_content)
    if match: return match.group(1)
    return ""


def parse_release_year(html_content):
    if not html_content: return None
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text()
    patterns = [
        r'(?:Aired|Release|Year|Premiered)[\s:]*(\d{4})',
        r'(\d{4})\s*(?:-\s*(?:\d{4}|ongoing))?',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            year = int(match.group(1))
            if 1960 <= year <= 2030:
                return year
    return None


def parse_post_id(html_content):
    if not html_content: return None
    soup = BeautifulSoup(html_content, 'html.parser')
    body = soup.find('body')
    if body and body.get('class'):
        for cls in body.get('class'):
            if cls.startswith('postid-'):
                try:
                    return int(cls.replace('postid-', ''))
                except: pass
    for tag in soup.find_all(attrs={'data-post-id': True}):
        try:
            return int(tag['data-post-id'])
        except: pass
    match = re.search(r'"post_id"\s*:\s*(\d+)', html_content)
    if match:
        return int(match.group(1))
    match = re.search(r'postid-(\d+)', html_content)
    if match:
        return int(match.group(1))
    return None


# ✅ नया फंक्शन: जाँचो कि एनिमे में हिंदी डब है या नहीं
def has_hindi_dub(html_content):
    """अगर एनिमे के पेज पर 'category-hindi' मिले, तो True लौटाओ"""
    if not html_content:
        return False
    
    # तरीका 1: class="category-hindi" ढूँढो
    if 'category-hindi' in html_content:
        return True
    
    # तरीका 2: Languages सेक्शन में "Hindi" ढूँढो
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup.find_all(['a', 'span', 'li'], string=re.compile(r'^\s*Hindi\s*$', re.IGNORECASE)):
        return True
    
    return False