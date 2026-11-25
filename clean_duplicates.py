import json
import os
import re

# 🛑 यहाँ अपनी storage.json का पाथ डालो
DB_FILE = "database/storage.json"

def clean_title(title):
    """एनीमे के नाम को साफ करके सिर्फ अक्षर और नंबर रखता है"""
    if not title: return ""
    # सारे स्पेशल कैरेक्टर्स हटाओ और सबको lowercase में कर दो
    return re.sub(r'[^a-z0-9]', '', title.lower()).strip()

def remove_duplicates():
    if not os.path.exists(DB_FILE):
        print(f"❌ डेटाबेस फाइल नहीं मिली: {DB_FILE}")
        print("कृपया सुनिश्चित करें कि आप प्रोजेक्ट के मेन फोल्डर से स्क्रिप्ट रन कर रहे हैं।")
        return

    print("🔄 डेटाबेस पढ़ा जा रहा है...")
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    anime_list = data.get('anime_list', [])
    original_count = len(anime_list)

    if original_count == 0:
        print("❌ डेटाबेस खाली है।")
        return

    print(f"📊 कुल एनीमे: {original_count}")
    print("🕵️ डुप्लीकेट्स ढूंढे जा रहे हैं...\n")

    unique_anime = {}
    duplicates_removed = 0

    for anime in anime_list:
        title = anime.get('title', '')
        clean_t = clean_title(title)

        if not clean_t:
            continue # अगर नाम खाली है तो स्किप करो

        if clean_t in unique_anime:
            # 🚨 डुप्लीकेट मिला!
            duplicates_removed += 1
            existing_anime = unique_anime[clean_t]
            
            # स्मार्ट चेक: किसमें ज़्यादा एपिसोड्स हैं?
            existing_eps = len(existing_anime.get('episodes', []))
            current_eps = len(anime.get('episodes', []))

            if current_eps > existing_eps:
                print(f"🗑️ डुप्लीकेट हटाया: '{title}' (नए वाले में ज़्यादा एपिसोड्स थे, इसलिए इसे रखा गया)")
                unique_anime[clean_t] = anime
            else:
                print(f"🗑️ डुप्लीकेट हटाया: '{title}' (पुराने वाले में ज़्यादा या बराबर एपिसोड्स थे, इसलिए इसे रखा गया)")
        else:
            unique_anime[clean_t] = anime

    # डिक्शनरी को वापस लिस्ट में बदलो
    cleaned_list = list(unique_anime.values())
    data['anime_list'] = cleaned_list

    # फाइल में सेव करो
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print("\n" + "="*50)
    print(f"✅ सफाई पूरी हो गई!")
    print(f"📉 हटाए गए डुप्लीकेट्स: {duplicates_removed}")
    print(f"📈 अब डेटाबेस में कुल यूनिक एनीमे: {len(cleaned_list)}")
    print("="*50)
    print("\n⚠️ IMPORTANT: अब तुम्हें अपनी Turso सिंक स्क्रिप्ट (sync_turso.py) रन करनी होगी ताकि लाइव वेबसाइट पर भी ये बदलाव दिखें!")

if __name__ == '__main__':
    remove_duplicates()