import os
import json

# 🛠️ फाइल का नाम (अगर तुमने मर्ज कर लिया है, तो इसे "database/storage.json" कर देना)
DB_FILE = "toonstream_data.json" 

def clean_movies():
    print("=" * 60)
    print("🗑️ CLEANING MOVIES / 0-EPISODE ANIME FROM TOONSTREAM DATA")
    print("=" * 60)

    if not os.path.exists(DB_FILE):
        print(f"❌ फाइल नहीं मिली: {DB_FILE}")
        return

    with open(DB_FILE, 'r', encoding='utf-8') as f:
        db_data = json.load(f)

    anime_list = db_data.get('anime_list', [])
    original_count = len(anime_list)
    
    clean_list = []
    deleted_count = 0

    for anime in anime_list:
        # अगर लिंक में toonstream है, तो चेक करो कि ये मूवी है या नहीं
        if 'toonstream' in anime.get('url', '').lower():
            # मूवी पहचानने के 3 तरीके:
            # 1. URL में /movies/ हो
            # 2. episodes खाली हो
            # 3. seasons खाली हो या उनमें भी episodes खाली हों
            is_movie = False
            if '/movies/' in anime.get('url', ''):
                is_movie = True
            elif not anime.get('episodes') or len(anime.get('episodes', [])) == 0:
                is_movie = True
            elif not anime.get('seasons') or len(anime.get('seasons', [])) == 0:
                is_movie = True
            elif len(anime.get('seasons', [])) > 0 and len(anime['seasons'][0].get('episodes', [])) == 0:
                is_movie = True

            if is_movie:
                print(f"🗑️ डिलीट किया (मूवी/खाली): {anime.get('title')}")
                deleted_count += 1
                continue # इसे लिस्ट में मत जोड़ो

        # बाकी सब (सही सीरीज़ और AnimeSalt वाले) लिस्ट में जोड़ दो
        clean_list.append(anime)

    # सेव करो
    db_data['anime_list'] = clean_list
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db_data, f, indent=4, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"✅ कुल {deleted_count} मूवीज़/खाली एनीमे डिलीट कर दिए गए हैं।")
    print(f"📊 अब इस फाइल में {len(clean_list)} सही एनीमे बचे हैं।")
    print("=" * 60)

if __name__ == '__main__':
    clean_movies()