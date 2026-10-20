import os
import json

# 🛠️ फाइलों के पाथ
DB_FILE = "database/storage.json"
TOONSTREAM_TEMP_FILE = "toonstream_data.json"

def delete_toonstream_data():
    print("=" * 60)
    print("🗑️ TOONSTREAM DATA DELETER (सिर्फ ToonStream वाले डिलीट होंगे)")
    print("=" * 60)

    if not os.path.exists(DB_FILE):
        print("❌ storage.json नहीं मिली!")
        return

    # 1. असली डेटाबेस लोड करो
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        db_data = json.load(f)

    anime_list = db_data.get('anime_list', [])
    original_count = len(anime_list)

    # 2. सिर्फ वो एनीमे रखो जिनके URL में 'toonstream' नहीं है (यानी AnimeSalt वाले)
    new_anime_list = [a for a in anime_list if 'toonstream' not in a.get('url', '').lower()]

    # 3. कितने डिलीट हुए, उसका हिसाब
    deleted_count = original_count - len(new_anime_list)

    # 4. डेटाबेस अपडेट करो
    db_data['anime_list'] = new_anime_list

    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db_data, f, indent=4, ensure_ascii=False)

    print(f"✅ कुल {deleted_count} ToonStream एनीमे असली डेटाबेस से डिलीट कर दिए गए हैं।")
    print(f"📊 अब डेटाबेस में {len(new_anime_list)} एनीमे बचे हैं (सिर्फ AnimeSalt वाले)।")

    # 5. स्क्रैपर की टेस्ट फाइल (toonstream_data.json) को भी डिलीट कर दो
    if os.path.exists(TOONSTREAM_TEMP_FILE):
        os.remove(TOONSTREAM_TEMP_FILE)
        print(f"✅ {TOONSTREAM_TEMP_FILE} भी डिलीट कर दी गई है (नए सिरे से स्क्रैपिंग के लिए)।")
    else:
        print(f"ℹ️ {TOONSTREAM_TEMP_FILE} पहले से ही मौजूद नहीं है।")

    print("=" * 60)

if __name__ == '__main__':
    delete_toonstream_data()