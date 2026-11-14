import json
import os
import re

DB_PATH = os.path.join(os.getcwd(), 'database', 'storage.json')

def clean_title(title):
    """नाम से सारे स्पेशल कैरेक्टर और स्पेस हटाकर सिर्फ अक्षर और नंबर रखेगा"""
    if not title: return ""
    return re.sub(r'[^a-z0-9]', '', title.lower()).strip()

def clean_all_duplicates():
    print("🔍 Checking for ALL duplicate anime (Smart Match)...")
    if not os.path.exists(DB_PATH):
        print("❌ storage.json not found!")
        return

    with open(DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    anime_list = data.get('anime_list', [])
    unique_anime_dict = {}
    removed_count = 0

    for anime in anime_list:
        raw_title = anime.get('title', '')
        # स्मार्ट नाम बनाओ (जैसे "Naruto (Hindi)" -> "narutohindi")
        smart_key = clean_title(raw_title)
        
        if not smart_key:
            continue

        if smart_key in unique_anime_dict:
            # अगर डुप्लीकेट मिला, तो देखो किसमें ज्यादा एपिसोड हैं
            existing_anime = unique_anime_dict[smart_key]
            
            # एपिसोड्स की संख्या चेक करो
            existing_eps = sum(len(s.get('episodes', [])) for s in existing_anime.get('seasons', []))
            if existing_eps == 0 and existing_anime.get('episodes'):
                existing_eps = len(existing_anime.get('episodes', []))

            new_eps = sum(len(s.get('episodes', [])) for s in anime.get('seasons', []))
            if new_eps == 0 and anime.get('episodes'):
                new_eps = len(anime.get('episodes', []))

            # अगर नए वाले में ज्यादा एपिसोड हैं, तो पुराने को हटाकर नया रखो
            if new_eps > existing_eps:
                print(f"🔄 Replaced: '{existing_anime.get('title')}' with better version '{raw_title}'")
                unique_anime_dict[smart_key] = anime
            else:
                print(f"🗑️ Removed duplicate: '{raw_title}' (Kept: '{existing_anime.get('title')}')")
            
            removed_count += 1
        else:
            unique_anime_dict[smart_key] = anime

    # डेटाबेस को अपडेट करो
    data['anime_list'] = list(unique_anime_dict.values())
    
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
    print(f"\n✅ Cleaning complete! Total duplicate anime removed: {removed_count}")
    print(f"🎉 Total unique anime remaining: {len(data['anime_list'])}")

if __name__ == "__main__":
    clean_all_duplicates()