import json
import os
import random
import requests
import libsql_client # 🛠️ Turso ke liye zaroori hai

# ✅ Turso (libSQL) Credentials - Render Environment Variables se aayenge
TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

# ✅ GitHub से ताजा डेटा (Fallback ke liye)
GITHUB_RAW_URL = "https://raw.githubusercontent.com/manojbarai376520-cell/animehub/main/database/storage.json"
DB_PATH = os.path.join(os.getcwd(), 'database', 'storage.json')

# 🛠️ CACHE VARIABLE: यह डेटा को सर्वर की मेमोरी (RAM) में सेव रखेगा
_cached_anime_list = None

# 🛠️ Turso Client banane ka function
def get_turso_client():
    if not TURSO_URL or not TURSO_TOKEN:
        print("⚠️ Turso URL or Token missing in Environment Variables!")
        return None
    try:
        return libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)
    except Exception as e:
        print(f"⚠️ Turso Client Error: {e}")
        return None

# 🛠️ नया फंक्शन: इमेजेस को हल्का (Optimize) करने के लिए
def optimize_image_url(url):
    """TMDB की बड़ी इमेजेस को छोटा करके स्पीड बढ़ाना"""
    if not url: 
        return url
    if 'image.tmdb.org' in url:
        return url.replace('/w500/', '/w300/').replace('/w1280/', '/w780/')
    return url

# 🛠️ NEW FUNCTION: डेटाबेस की गलत भाषा (Language) को ठीक करने के लिए
def fix_language_data(anime):
    """टाइटल के हिसाब से भाषा को सही करना (Auto-Fix Database)"""
    title = anime.get('title', '').lower()
    current_lang = str(anime.get('language', '')).lower()

    if 'english' in title:
        anime['language'] = 'English Dub'
    elif 'hindi' in title:
        anime['language'] = 'Hindi Dub'
    elif 'tamil' in title:
        anime['language'] = 'Tamil Dub'
    elif 'telugu' in title:
        anime['language'] = 'Telugu Dub'
    elif 'japanese' in title:
        anime['language'] = 'Japanese'
    else:
        if not current_lang or current_lang == 'unknown':
            anime['language'] = 'Multi Audio'
        elif current_lang == 'hindi dub' and 'hindi' not in title:
            anime['language'] = 'Multi Audio'


def get_all_anime():
    """Turso se data lao, agar nahi mile toh GitHub/Local se laakar Turso me save karo"""
    global _cached_anime_list
    
    # 1. Agar RAM me data hai, toh seedha do (Fastest)
    if _cached_anime_list is not None:
        return _cached_anime_list

    # 2. Turso se data fetch karne ki koshish karo
    client = get_turso_client()
    if client:
        try:
            # Table banado agar pehle se nahi hai
            client.execute("CREATE TABLE IF NOT EXISTS animenest_db (id INTEGER PRIMARY KEY, json_data TEXT)")
            # Data fetch karo
            result = client.execute("SELECT json_data FROM animenest_db WHERE id = 1")
            
            if result.rows and len(result.rows) > 0:
                data = json.loads(result.rows[0][0]).get('anime_list', [])
                for anime in data:
                    if 'image' in anime:
                        anime['image'] = optimize_image_url(anime['image'])
                    fix_language_data(anime)
                _cached_anime_list = data
                print("✅ Data successfully loaded from Turso Cloud!")
                return _cached_anime_list
        except Exception as e:
            print(f"⚠️ Turso Fetch Error: {e}")

    # 3. Agar Turso me data nahi mila, toh GitHub se lao
    print("🔄 Turso empty or failed. Fetching from GitHub...")
    try:
        response = requests.get(GITHUB_RAW_URL, timeout=10)
        if response.status_code == 200:
            data = response.json().get('anime_list', [])
            
            for anime in data:
                if 'image' in anime:
                    anime['image'] = optimize_image_url(anime['image'])
                fix_language_data(anime)
                    
            _cached_anime_list = data
            
            # 👇 Turso me save kar do taaki agli baar seedha wahi se mile
            save_anime_list(_cached_anime_list) 
            return _cached_anime_list
    except Exception as e:
        print(f"⚠️ GitHub fetch error: {e}")
    
    # 4. Agar sab fail ho jaye, toh Local file padho
    if not os.path.exists(DB_PATH):
        return []
    try:
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f).get('anime_list', [])
            
            for anime in data:
                if 'image' in anime:
                    anime['image'] = optimize_image_url(anime['image'])
                fix_language_data(anime)
                    
            _cached_anime_list = data
            save_anime_list(_cached_anime_list) # Turso me save karo
            return _cached_anime_list
    except:
        return []


def get_anime_by_id(anime_id):
    """🛠️ FIX: ID को स्ट्रिंग और इंटीजर दोनों तरह से मैच करे"""
    anime_id_str = str(anime_id)
    for anime in get_all_anime():
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
    """Data ko RAM, Turso Cloud aur Local file teeno jagah save karega"""
    global _cached_anime_list
    _cached_anime_list = anime_list
    data = {"anime_list": anime_list}
    json_string = json.dumps(data, ensure_ascii=False)
    
    # 1. Turso Cloud me save karo
    client = get_turso_client()
    if client:
        try:
            client.execute("CREATE TABLE IF NOT EXISTS animenest_db (id INTEGER PRIMARY KEY, json_data TEXT)")
            # id = 1 par poora data save/replace kar do
            client.execute("INSERT OR REPLACE INTO animenest_db (id, json_data) VALUES (1, ?)", [json_string])
            print("✅ Data saved to Turso Cloud successfully!")
        except Exception as e:
            print(f"⚠️ Turso Save Error: {e}")
            
    # 2. Local file me backup ke liye save karo
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            f.write(json_string)
    except Exception as e:
        print(f"❌ Local Save error: {e}")


def update_anime_episodes(anime_id, episodes):
    anime_list = get_all_anime()
    anime_id_str = str(anime_id)
    for anime in anime_list:
        if str(anime.get('id')) == anime_id_str:
            anime['episodes'] = episodes
            break
    save_anime_list(anime_list)