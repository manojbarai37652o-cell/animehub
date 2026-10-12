import os
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
DB_FILE = os.path.join(project_root, 'database', 'storage.json')

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {"anime_list": []}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    print("=" * 60)
    print("🧹 डेटाबेस से सिर्फ मूवीज़ डिलीट कर रहे हैं...")
    print("=" * 60)

    db_data = load_db()
    anime_list = db_data.get("anime_list", [])
    
    series_list = []
    movies_deleted = 0
    
    for anime in anime_list:
        # 🛠️ मूवी की पहचान: अगर episodes खाली हैं, या पहला episode "Full Movie" है
        episodes = anime.get('episodes', [])
        is_movie = False
        
        if not episodes or len(episodes) == 0:
            is_movie = True
        elif episodes[0].get('title') == 'Full Movie':
            is_movie = True
            
        if is_movie:
            movies_deleted += 1
            print(f"❌ मूवी डिलीट की: {anime['title']}")
        else:
            series_list.append(anime)

    # अब डेटाबेस में सिर्फ सीरीज़ बची हैं
    db_data['anime_list'] = series_list
    save_db(db_data)
    
    print(f"\n🎉 काम खत्म! कुल {movies_deleted} मूवीज़ डिलीट हो गईं।")
    print(f"✅ अब डेटाबेस में सिर्फ {len(series_list)} सीरीज़ बची हैं।")
    print("=" * 60)