import sys
import os
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(current_dir, 'database', 'storage.json')

def remove_animesalt_mushoku():
    print("🔍 Mushoku Tensei (AnimeSalt) को डिलीट करने की प्रक्रिया शुरू...")
    
    if not os.path.exists(DB_FILE):
        print(f"❌ डेटाबेस फाइल नहीं मिली: {DB_FILE}")
        return

    with open(DB_FILE, 'r', encoding='utf-8') as f: 
        db_data = json.load(f)
        
    anime_list = db_data.get('anime_list', [])
    original_count = len(anime_list)
    
    cleaned_list = []
    deleted_count = 0
    
    for anime in anime_list:
        title = anime.get('title', '').lower()
        url = anime.get('url', '').lower()
        
        # 🛑 शर्त: अगर नाम में mushoku tensei है और URL में animesalt है, तो इसे डिलीट कर दो
        if "mushoku tensei" in title and "animesalt" in url:
            print(f"🗑️ हटाया गया: {anime.get('title')} | URL: {url}")
            deleted_count += 1
        else:
            # बाकी सारे एनीमे (जैसे ToonStream वाला Mushoku) सेफ रहेंगे
            cleaned_list.append(anime)
            
    if deleted_count > 0:
        db_data['anime_list'] = cleaned_list
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db_data, f, indent=4, ensure_ascii=False)
            
        print("\n" + "="*50)
        print(f"✅ सफलतापूर्वक {deleted_count} AnimeSalt वाले 'Mushoku Tensei' डिलीट हो गए!")
        print(f"📈 अब डेटाबेस में कुल एनीमे: {len(cleaned_list)}")
        print("="*50)
        print("\n⚠️ IMPORTANT: अब लाइव साइट पर अपडेट करने के लिए 'python sync_turso.py' ज़रूर रन करना!")
    else:
        print("\n⚠️ डेटाबेस में AnimeSalt वाला 'Mushoku Tensei' नहीं मिला। (शायद पहले ही हट चुका है)")

if __name__ == "__main__":
    remove_animesalt_mushoku()