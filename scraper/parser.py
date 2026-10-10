import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def parse_desidubanime_homepage(html, base_url="https://www.desidubanime.me"):
    """DesiDubAnime के होमपेज से एनीमे निकालता है"""
    if not html:
        return []
        
    soup = BeautifulSoup(html, 'html.parser')
    anime_list = []
    
    # DesiDubAnime के कार्ड्स ढूंढो (article class="anime-card")
    articles = soup.find_all('article', class_='anime-card')
    
    for article in articles:
        try:
            # लिंक और टाइटल निकालो
            link_tag = article.find('a')
            if not link_tag: continue
            
            url = link_tag.get('href')
            if not url: continue
            
            # टाइटल 'title' attribute में या text में हो सकता है
            title = link_tag.get('title') or link_tag.text.strip()
            
            # अगर टाइटल खाली है, तो इमेज के alt से निकालो
            if not title or len(title) < 2:
                img_tag = article.find('img')
                if img_tag:
                    title = img_tag.get('alt', '').replace('poster', '').strip()
            
            # इमेज निकालो
            img_tag = article.find('img')
            image = img_tag.get('src') if img_tag else ""
            
            # ID बनाओ (URL के आखिरी हिस्से से)
            anime_id = url.strip('/').split('/')[-1]
            
            anime_list.append({
                'id': anime_id,
                'title': title,
                'url': urljoin(base_url, url) if url.startswith('/') else url,
                'image': image
            })
        except Exception as e:
            continue
            
    return anime_list

def parse_desidubanime_episodes(html, base_url="https://www.desidubanime.me"):
    """DesiDubAnime के एनीमे पेज से एपिसोड निकालता है"""
    if not html:
        return []
        
    soup = BeautifulSoup(html, 'html.parser')
    episodes = []
    
    # एपिसोड की लिस्ट ढूंढो (आमतौर पर 'episode' या 'ep' लिंक में होती है)
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if '/episode/' in href or '/watch/' in href:
            url = urljoin(base_url, href)
            title = link.text.strip() or href.strip('/').split('/')[-1]
            
            if url not in [e['url'] for e in episodes]:
                episodes.append({
                    'title': title,
                    'url': url,
                    'video_url': ''
                })
    
    return episodes