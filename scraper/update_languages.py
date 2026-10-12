import os
import json
import time
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from parser import extract_language_from_detail
# smart_scraper.py से fetch_page फंक्शन इम्पोर्ट कर रहे हैं
from smart_scraper import fetch_page 

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
    print("🌐 पुराने एनीमे की भाषा अपडेट कर रहे हैं...")
    print("=" * 60)

    db_data = load_db()
    anime_list = db_data.get("anime_list", [])
    
    total = len(anime_list)
    updated_count = 0
    
    print(f"📊 कुल {total} एनीमे मिले।\n")

    for idx, anime in enumerate(anime_list):
        # अगर पहले से भाषा है और Unknown नहीं है, तो स्किप कर दो
        if anime.get('language') and anime.get('language') != 'Unknown':
            print(f"[{idx+1}/{total}] {anime['title']} -> भाषा पहले से है: {anime['language']}")
            continue

        print(f"[{idx+1}/{total}] {anime['title']} की भाषा ढूंढ रहे हैं...")
        
        anime_html = fetch_page(anime['url'])
        if not anime_html:
            print(f"   ❌ पेज लोड नहीं हुआ। स्किप कर रहे हैं।")
            anime['language'] = "Unknown"
            continue

        language = extract_language_from_detail(anime_html)
        anime['language'] = language
        print(f"   🌐 भाषा मिली: {language}")
        
        updated_count += 1
        
        # हर 5 एनीमे के बाद डेटाबेस सेव कर दो (ताकि बीच में क्रैश होने पर डेटा न उड़े)
        if updated_count % 5 == 0:
            db_data['anime_list'] = anime_list
            save_db(db_data)
            print("   💾 डेटाबेस सेव कर दिया (बैकअप के लिए)।")

        time.sleep(1.5) # सर्वर पर लोड कम करने के लिए

    # आखिर में पूरा डेटाबेस सेव कर दो
    db_data['anime_list'] = anime_list
    save_db(db_data)
    
    print(f"\n🎉 काम खत्म! कुल {updated_count} एनीमे की भाषा अपडेट हो गई।")
    print("=" * 60)