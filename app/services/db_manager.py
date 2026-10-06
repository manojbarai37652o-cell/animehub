import json
import os
import random

DB_PATH = os.path.join(os.getcwd(), 'database', 'storage.json')

def get_all_anime():
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
    return random.sample(filtered, min(count, len(filtered))) if filtered else []

def get_featured_anime(count=5):
    return get_all_anime()[:count]

def get_top_anime(count=10):
    return get_all_anime()[:count]

# ✅ नया फंक्शन: 5 रैंडम एनिमे निकालने के लिए (Hero Slider के लिए)
def get_hero_anime_list(count=5):
    anime_list = get_all_anime()
    if not anime_list: return []
    # हम पहले 30 में से 5 रैंडम एनिमे उठाएंगे, ताकि बैनर बदलता रहे
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
    data = {"anime_list": anime_list}
    try:
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"✅ डेटाबेस में {len(anime_list)} एनिमे सफलतापूर्वक सेव हो गए!")
    except Exception as e:
        print(f"❌ डेटा सेव करने में एरर: {e}")

def update_anime_episodes(anime_id, episodes):
    anime_list = get_all_anime()
    updated = False
    for anime in anime_list:
        if anime['id'] == anime_id:
            anime['episodes'] = episodes
            updated = True
            break
    if updated: save_anime_list(anime_list)