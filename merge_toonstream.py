import os
import json
import re

# 🛠️ तुम्हारे प्रोजेक्ट के हिसाब से पाथ (अब ये toonstream_data.json को पढ़ेगा)
LIVE_DB_FILE = "database/storage.json"
TOONSTREAM_DB_FILE = "toonstream_data.json" 
OUTPUT_DB_FILE = "database/storage_new.json" 

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"anime_list": []}

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def clean_title(title):
    if not title: return ""
    title = title.lower()
    title = re.sub(r'[^a-z0-9]', '', title)
    return title.strip()

if __name__ == '__main__':
    print("=" * 60)
    print("🔗 TOONSTREAM SAFE DATA MERGER (FINAL)")
    print("=" * 60)

    # 1. पुराना डेटा और नया डेटा लोड करो
    live_data = load_json(LIVE_DB_FILE)
    test_data = load_json(TOONSTREAM_DB_FILE)

    live_anime_list = live_data.get('anime_list', [])
    test_anime_list = test_data.get('anime_list', [])

    print(f"📊 Live DB में पहले से {len(live_anime_list)} एनीमे हैं।")
    print(f"📊 ToonStream DB में {len(test_anime_list)} नए एनीमे हैं।\n")

    # 2. पुराने एनीमे के टाइटल निकालो (डुप्लीकेट रोकने के लिए)
    existing_titles = set()
    for anime in live_anime_list:
        existing_titles.add(clean_title(anime.get('title', '')))

    new_added_count = 0
    skipped_count = 0

    # 3. मर्जिंग का लॉजिक
    for test_anime in test_anime_list:
        title = test_anime.get('title', '')
        clean_t = clean_title(title)

        if clean_t in existing_titles:
            print(f"⏭️ स्किप (पहले से है): {title}")
            skipped_count += 1
            continue

        # नया एनीमे जोड़ो
        live_anime_list.append(test_anime)
        existing_titles.add(clean_t)
        new_added_count += 1
        print(f"✅ जोड़ दिया गया: {title}")

    # 4. नई फाइल में सेव करो
    if new_added_count > 0:
        live_data['anime_list'] = live_anime_list
        save_json(OUTPUT_DB_FILE, live_data)
        print("\n" + "=" * 60)
        print(f"🎉 सफलतापूर्वक {new_added_count} नए एनीमे मर्ज हो गए!")
        print(f"⏭️ {skipped_count} एनीमे स्किप किए गए (क्योंकि वो पहले से थे)।")
        print(f"💾 नया डेटा यहाँ सेव हुआ है: {OUTPUT_DB_FILE}")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("⚠️ कोई नया एनीमे नहीं मिला। सब पहले से डेटाबेस में मौजूद हैं।")
        print("=" * 60)