import json
import os

# प्रोजेक्ट रूट सेट करें
current_dir = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(current_dir, 'database', 'storage.json')

def clean_database():
    if not os.path.exists(DB_FILE):
        print(f"❌ Error: {DB_FILE} फाइल नहीं मिली!")
        return

    print("🧹 डेटाबेस साफ़ किया जा रहा है...")

    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            db_data = json.load(f)
    except Exception as e:
        print(f"❌ फाइल पढ़ने में एरर: {e}")
        return

    anime_list = db_data.get('anime_list', [])
    original_count = len(anime_list)
    
    cleaned_list = []
    removed_count = 0

    for anime in anime_list:
        image = anime.get('image', '')
        anime_id = anime.get('id', '')
        title = anime.get('title', 'Unknown')

        # 🛠️ नया कंडीशन: अगर इमेज का URL टूटा हुआ है (जैसे animesalt.cx + tmdb)
        is_broken_url = "animesalt.cx" in image and "tmdb" in image.lower()
        
        # या फिर इमेज खाली है, या 'No Image' लिखा है, या ID नहीं है
        if not image or image.strip() == "" or "No Image" in image or not anime_id or str(anime_id).strip() == "" or is_broken_url:
            print(f"   🗑️ डिलीट किया: {title} (कारण: इमेज या ID गायब/टूटा हुआ है)")
            removed_count += 1
            continue

        cleaned_list.append(anime)

    db_data['anime_list'] = cleaned_list
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db_data, f, indent=4, ensure_ascii=False)

    print("\n" + "=" * 50)
    print(f"📊 कुल एनीमे: {original_count}")
    print(f"🗑️ डिलीट किए गए: {removed_count}")
    print(f"✅ बचे हुए एनीमे: {len(cleaned_list)}")
    print("=" * 50)
    print("🎉 डेटाबेस सफलतापूर्वक साफ़ हो गया!")

if __name__ == "__main__":
    clean_database()