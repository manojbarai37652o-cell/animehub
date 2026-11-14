import json
import os

DB_PATH = os.path.join(os.getcwd(), 'database', 'storage.json')

# 🖼️ Mushoku Tensei ka ekdum saaf HD Poster link
NEW_POSTER_URL = "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx108465-p1l80V1Rk29D.jpg"

def fix_image():
    print("🔍 Updating poster for Mushoku Tensei...")
    
    if not os.path.exists(DB_PATH):
        print("❌ storage.json not found!")
        return

    with open(DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated = False
    for anime in data.get('anime_list', []):
        if "mushoku" in anime.get('title', '').lower():
            anime['image'] = NEW_POSTER_URL
            updated = True
            print(f"✅ Poster updated for: {anime['title']}")
            break

    if updated:
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print("🎉 Database updated successfully!")
    else:
        print("⚠️ Mushoku Tensei not found in database.")

if __name__ == "__main__":
    fix_image()