import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def parse_toonstream_homepage(html, base_url="https://toonstream.us"):
    """ToonStream के होमपेज से एनीमे निकालता है"""
    if not html:
        return []
        
    soup = BeautifulSoup(html, 'html.parser')
    anime_list = []
    
    # ToonStream के कार्ड्स ढूंढो (article tag के अंदर)
    cards = soup.find_all('article', class_=lambda x: x and 'post' in x and ('movies' in x or 'series' in x))
    
    for card in cards:
        try:
            # लिंक निकालो
            link_tag = card.find('a', class_='lnk-blk')
            if not link_tag:
                continue
            url = link_tag.get('href')
            if not url:
                continue
                
            # टाइटल निकालो
            title_tag = card.find('h2') or card.find('h3')
            title = title_tag.text.strip() if title_tag else "Unknown Title"
            
            # इमेज निकालो
            img_tag = card.find('img')
            image = img_tag.get('src') if img_tag else ""
            
            # ID बनाओ (URL के आखिरी हिस्से से)
            anime_id = url.strip('/').split('/')[-1]
            
            anime_list.append({
                'id': anime_id,
                'title': title,
                'url': base_url + url if url.startswith('/') else url,
                'image': image
            })
        except Exception as e:
            continue
            
    return anime_list


def parse_toonstream_episodes(html, base_url="https://toonstream.us"):
    """ToonStream के एनीमे पेज से एपिसोड निकालता है"""
    if not html:
        return []
        
    soup = BeautifulSoup(html, 'html.parser')
    episodes = []
    
    # एपिसोड की लिस्ट ढूंढो (ul id="episode_by_temp")
    episode_list = soup.find('ul', id='episode_by_temp')
    if not episode_list:
        return episodes
        
    for li in episode_list.find_all('li'):
        try:
            # लिंक निकालो
            link_tag = li.find('a', class_='lnk-blk')
            if link_tag and link_tag.get('href'):
                url = link_tag['href']
                if url.startswith('/'):
                    url = base_url + url
                
                # 🚀 यहाँ जादू है: URL से सीजन और एपिसोड नंबर निकालो (जैसे -1x1)
                ep_match = re.search(r'-(\d+)x(\d+)', url)
                if ep_match:
                    ep_num = ep_match.group(2) # सिर्फ एपिसोड नंबर
                    title = f"Episode {ep_num}"
                else:
                    # अगर URL में नंबर न मिले तो पुराना तरीका अपनाओ
                    title_tag = li.find('h3') or li.find('h2') or link_tag
                    title = title_tag.text.strip() if title_tag.text.strip() else url.strip('/').split('/')[-1]
                
                episodes.append({
                    'title': title,
                    'url': url,
                    'video_url': '' # इसे बाद में भरेंगे
                })
        except Exception as e:
            continue
            
    return episodes