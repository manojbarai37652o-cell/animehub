import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def parse_animixstream_homepage(html, base_url="https://animixstream.com"):
    """AnimixStream के होमपेज से एनीमे निकालता है"""
    if not html:
        return []
        
    soup = BeautifulSoup(html, 'html.parser')
    anime_list = []
    
    # AnimixStream के कार्ड्स ढूंढो (<a class="card">)
    cards = soup.find_all('a', class_='card')
    
    for card in cards:
        try:
            url = card.get('href')
            if not url: continue
            
            # नाम निकालो (card-body के अंदर)
            title_tag = card.find('div', class_='card-body')
            if title_tag:
                name_tag = title_tag.find('h3') or title_tag.find('h4') or title_tag
                title = name_tag.text.strip()
            else:
                title = "Unknown Title"
            
            # इमेज निकालो (imgwrap के अंदर)
            img_tag = card.find('div', class_='imgwrap')
            image = ""
            if img_tag:
                img = img_tag.find('img')
                if img:
                    image = img.get('src', '')
            
            anime_id = url.strip('/').split('/')[-1]
            
            if anime_id.isdigit():
                anime_list.append({
                    'id': anime_id,
                    'title': title,
                    'url': base_url + url if url.startswith('/') else url,
                    'image': image
                })
        except Exception as e:
            continue
            
    return anime_list


def parse_animixstream_episodes(html, base_url="https://animixstream.com"):
    """AnimixStream के एनीमे पेज से एपिसोड निकालता है"""
    if not html:
        return []
        
    soup = BeautifulSoup(html, 'html.parser')
    episodes = []
    
    # AnimixStream में एपिसोड की लिस्ट 'ep-list' या 'episodes' क्लास में हो सकती है
    # पहले सारे <a> टैग ढूंढो जिनमें 'ep' या 'episode' लिखा हो
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if '/ep/' in href or 'episode' in href.lower() or 'watch' in href.lower():
            url = base_url + href if href.startswith('/') else href
            title = link.text.strip() or href.strip('/').split('/')[-1]
            
            if url not in [e['url'] for e in episodes]:
                episodes.append({
                    'title': title,
                    'url': url,
                    'video_url': ''
                })
    
    return episodes