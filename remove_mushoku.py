import json
import os

DB_PATH = os.path.join(os.getcwd(), 'database', 'storage.json')

def remove_mushoku():
    print("🔍 Searching for Mushoku Tensei to delete...")
    if not os.path.exists(DB_PATH):
        print("❌ storage.json not found!")
        return

    # 1. Load Database
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    anime_list = data.get('anime_list', [])
    original_count = len(anime_list)

    # 2. Filter out Mushoku Tensei
    new_anime_list = []
    deleted = False
    
    for anime in anime_list:
        if "mushoku tensei" in anime.get('title', '').lower():
            print(f"🗑️ Deleting: {anime.get('title')}")
            deleted = True
        else:
            new_anime_list.append(anime)

    # 3. Save back to storage.json
    if deleted:
        data['anime_list'] = new_anime_list
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"✅ Success! Removed {original_count - len(new_anime_list)} entry from database.")
    else:
        print("⚠️ Mushoku Tensei was not found in the database.")

if __name__ == "__main__":
    remove_mushoku()