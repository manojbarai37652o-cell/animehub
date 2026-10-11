import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def parse_animostream_homepage(html, base_url="https://www.animostream.xyz"):
    """animostream.xyz के होमपेज से एनीमे निकालता है"""
    if not html:
        return []
        
    soup = BeautifulSoup(html, 'html.parser')
    anime_list = []
    
    # 🚀 कार्ड्स 'grid-item' क्लास में हैं
    items = soup.find_all('div', class_='grid-item')
    
    for item in items:
        try:
            link_tag = item.find('a', class_='entry-image-wrap')
            if not link_tag:
                link_tag = item.find('a', href=True)
            if not link_tag: continue
            
            url = link_tag.get('href')
            if not url: continue
            
            title = link_tag.get('title')
            if not title:
                header = item.find('div', class_='entry-header')
                if header:
                    title = header.text.strip()
            if not title:
                title = f"Anime {len(anime_list) + 1}"
            
            # इमेज 'data-image' या 'style' attribute में छिपी है
            image = ""
            thumb_span = item.find('span', class_='entry-thumb')
            if thumb_span:
                image = thumb_span.get('data-image', '')
                if not image and thumb_span.get('style'):
                    match = re.search(r"url\(['\"]?(.*?)['\"]?\)", thumb_span.get('style'))
                    if match:
                        image = match.group(1)
            
            anime_id = url.strip('/').split('/')[-1].replace('.html', '')
            
            anime_list.append({
                'id': anime_id,
                'title': title,
                'url': url if url.startswith('http') else urljoin(base_url, url),
                'image': image
            })
        except Exception as e:
            continue
            
    return anime_list


def parse_animostream_episodes(html, base_url="https://www.animostream.xyz"):
    """animostream.xyz के एनीमे पेज से एपिसोड नंबर निकालता है"""
    if not html:
        return []
        
    soup = BeautifulSoup(html, 'html.parser')
    episodes = []
    
    # 🚀 स्क्रीनशॉट के मुताबिक एपिसोड 'episodeList' के अंदर 'ep' क्लास में हैं
    ep_list = soup.find('div', id='episodeList')
    if not ep_list:
        return episodes
        
    for div in ep_list.find_all('div', class_='ep'):
        num = div.text.strip()
        if num:
            episodes.append({
                'title': f"Episode {num}",
                'ep_num': num  # हम सिर्फ एपिसोड नंबर सेव करेंगे
            })
    
    return episodes