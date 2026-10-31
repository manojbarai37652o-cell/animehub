import json
import os
import random
import requests

# ✅ GitHub से ताजा डेटा
GITHUB_RAW_URL = "https://raw.githubusercontent.com/manojbarai376520-cell/animehub/main/database/storage.json"
DB_PATH = os.path.join(os.getcwd(), 'database', 'storage.json')

# 🛠️ CACHE VARIABLE: यह डेटा को सर्वर की मेमोरी (RAM) में सेव रखेगा
_cached_anime_list = None


# 🛠️ नया फंक्शन: इमेजेस को हल्का (Optimize) करने के लिए
def optimize_image_url(url):
    """TMDB की बड़ी इमेजेस को छोटा करके स्पीड बढ़ाना"""
    if not url: 
        return url
    # अगर इमेज TMDB से है, तो साइज़ कम कर दो
    if 'image.tmdb.org' in url:
        return url.replace('/w500/', '/w300/').replace('/w1280/', '/w780/')
    return url


def get_all_anime():
    """GitHub से ताजा डेटा लाओ (सिर्फ पहली बार, फिर मेमोरी से दो)"""
    global _cached_anime_list
    
    # अगर डेटा पहले से मेमोरी में है, तो सीधे वापस कर दो (बिजली की स्पीड)
    if _cached_anime_list is not None:
        return _cached_anime_list

    # अगर मेमोरी खाली है, तो डेटा लोड करो
    try:
        response = requests.get(GITHUB_RAW_URL, timeout=10)
        if response.status_code == 200:
            data = response.json().get('anime_list', [])
            
            # 🛠️ लोड होते ही सारी इमेजेस को ऑप्टिमाइज़ कर दो
            for anime in data:
                if 'image' in anime:
                    anime['image'] = optimize_image_url(anime['image'])
                    
            _cached_anime_list = data
            return _cached_anime_list
    except Exception as e:
        print(f"⚠️ GitHub fetch error: {e}")
    
    # Fallback: लोकल
    if not os.path.exists(DB_PATH):
        return []
    try:
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f).get('anime_list', [])
            
            # 🛠️ लोकल फाइल से लोड होते ही इमेजेस ऑप्टिमाइज़ कर दो
            for anime in data:
                if 'image' in anime:
                    anime['image'] = optimize_image_url(anime['image'])
                    
            _cached_anime_list = data
            return _cached_anime_list
    except:
        return []


def get_anime_by_id(anime_id):
    """🛠️ FIX: ID को स्ट्रिंग और इंटीजर दोनों तरह से मैच करे (404 एरर खत्म)"""
    anime_id_str = str(anime_id)
    for anime in get_all_anime():
        # दोनों को स्ट्रिंग में बदलकर तुलना करो
        if str(anime.get('id')) == anime_id_str:
            return anime
    return None


def search_anime(query):
    anime_list = get_all_anime()
    if not query: return anime_list
    query = query.lower()
    return [a for a in anime_list if query in a['title'].lower()]


def get_random_anime(exclude_id, count=6):
    anime_list = get_all_anime()
    exclude_id_str = str(exclude_id)
    filtered = [a for a in anime_list if str(a.get('id')) != exclude_id_str]
    if len(filtered) <= count:
        return filtered
    return random.sample(filtered, count)


def get_featured_anime(count=5):
    return get_all_anime()[:count]


def get_top_anime(count=10):
    return get_all_anime()[:count]


def get_hero_anime_list(count=5):
    anime_list = get_all_anime()
    if not anime_list: return []
    top_pool = anime_list[:30]
    if len(top_pool) <= count: return top_pool
    return random.sample(top_pool, count)


def get_anime_by_genre(genre):
    anime_list = get_all_anime()
    if not genre: return anime_list
    genre = genre.lower()
    results = []
    action_keywords = ['demon slayer', 'jujutsu kaisen', 'one punch man', 'attack on titan', 
                      'solo leveling', 'naruto', 'one piece', 'black clover', 'my hero academia',
                      'hunter x hunter', 'bleach', 'dragon ball', 'chainsaw man', 'tokyo revengers']
    comedy_keywords = ['spy x family', 'grand blue', 'kaguya', 'komi', 'nichijou', 
                      'gintama', 'konosuba', 'daily life', 'horimiya', 'fruits basket']
    fantasy_keywords = ['reincarnated', 'isekai', 'mushoku tensei', 'that time i got',
                       'overlord', 'slime', 're:zero', 'sword art online', 'fate',
                       'immortal king', 'frontier lord', 'wistoria', 'frieren', 'dungeon']
    romance_keywords = ['horimiya', 'kaguya', 'toradora', 'love is war', 'rent-a-girlfriend',
                       'my dress-up darling', 'fruits basket', 'tomo-chan', 'uzaki', 'quintessential']
    
    for anime in anime_list:
        title_lower = anime['title'].lower()
        if genre == 'action' and any(k in title_lower for k in action_keywords): results.append(anime)
        elif genre == 'comedy' and any(k in title_lower for k in comedy_keywords): results.append(anime)
        elif genre == 'fantasy' and any(k in title_lower for k in fantasy_keywords): results.append(anime)
        elif genre == 'romance' and any(k in title_lower for k in romance_keywords): results.append(anime)
    if not results:
        results = [a for a in anime_list if genre in a['title'].lower()]
    return results


def get_single_random_anime():
    anime_list = get_all_anime()
    return random.choice(anime_list) if anime_list else None


def save_anime_list(anime_list):
    global _cached_anime_list
    _cached_anime_list = anime_list
    data = {"anime_list": anime_list}
    try:
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Save error: {e}")


def update_anime_episodes(anime_id, episodes):
    anime_list = get_all_anime()
    anime_id_str = str(anime_id)
    for anime in anime_list:
        if str(anime.get('id')) == anime_id_str:
            anime['episodes'] = episodes
            break
    save_anime_list(anime_list)