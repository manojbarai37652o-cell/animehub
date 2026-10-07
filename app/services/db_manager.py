import json
import os
import random
import requests

# ✅ तुम्हारी GitHub repository का raw link
GITHUB_RAW_URL = "https://raw.githubusercontent.com/manojbarai37652o-cell/animehub/main/database/storage.json"

# ✅ अगर GitHub से डेटा न आए, तो लोकल फाइल का इस्तेमाल करेंगे
DB_PATH = os.path.join(os.getcwd(), 'database', 'storage.json')


def get_all_anime():
    """GitHub से ताज़ा डेटा लाओ, अगर न आए तो लोकल से लो"""
    
    # ✅ पहले GitHub से डेटा उठाओ
    try:
        response = requests.get(GITHUB_RAW_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ GitHub से नया डेटा आ गया!")
            return data.get('anime_list', [])
    except Exception as e:
        print(f"⚠️ GitHub से डेटा नहीं आया: {e}")
    
    # ✅ अगर GitHub से न आए तो लोकल फाइल पढ़ो
    print("📂 लोकल फाइल से डेटा ला रहे हैं...")
    if not os.path.exists(DB_PATH):
        return []
    try:
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('anime_list', [])
    except Exception as e:
        print(f"Database Error: {e}")
        return []


def get_paginated_anime(page=1, per_page=20):
    anime_list = get_all_anime()
    total = len(anime_list)
    start = (page - 1) * per_page
    end = start + per_page
    return anime_list[start:end], total


def get_anime_by_id(anime_id):
    anime_list = get_all_anime()
    for anime in anime_list:
        if anime['id'] == anime_id:
            return anime
    return None


def search_anime(query):
    anime_list = get_all_anime()
    if not query: return anime_list
    query = query.lower()
    return [anime for anime in anime_list if query in anime['title'].lower()]


def get_random_anime(exclude_id, count=6):
    anime_list = get_all_anime()
    filtered = [a for a in anime_list if a['id'] != exclude_id]
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
    action_keywords = ['demon', 'slayer', 'jujutsu', 'hero', 'punch', 'leveling', 'titan', 'hunter', 'blade', 'sword', 'kai', 'dan', 'torch', 'piece', 'naruto', 'clover', 'academia']
    comedy_keywords = ['comedy', 'funny', 'life', 'slice', 'school', 'club', 'kanojo', 'girlfriend', 'dandadan', 'family', 'spy']
    fantasy_keywords = ['fantasy', 'magic', 'isekai', 'reincarnated', 'slime', 'immortal', 'king', 'dungeon', 'adventure']
    romance_keywords = ['romance', 'love', 'romantic', 'heart', 'kiss']
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
    """लोकल फाइल में सेव करो (सिर्फ बैकअप के लिए)"""
    data = {"anime_list": anime_list}
    try:
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"❌ डेटा सेव करने में एरर: {e}")


def update_anime_episodes(anime_id, episodes):
    """अब यह फंक्शन सिर्फ लोकल में सेव करेगा"""
    anime_list = get_all_anime()
    for anime in anime_list:
        if anime['id'] == anime_id:
            anime['episodes'] = episodes
            break
    save_anime_list(anime_list)