import subprocess
import json
import os
import sys
import time

# 🛑 कॉन्फ़िगरेशन
DATABASE_PATH = "database/storage.json"
MAX_ANIME_LIMIT = 2500  # सर्वर को सुरक्षित रखने के लिए लिमिट 

def get_anime_count():
    """डेटाबेस में मौजूद कुल एनीमे की गिनती करता है"""
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ डेटाबेस फाइल नहीं मिली: {DATABASE_PATH}")
        return 0
    
    try:
        with open(DATABASE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return len(data)
    except Exception as e:
        print(f"⚠️ डेटाबेस पढ़ने में एरर: {e}")
        return 0

def run_scraper(script_path, scraper_name):
    """किसी भी स्क्रिप्ट को एक अलग प्रोसेस में रन करता है"""
    print(f"\n=======================================================")
    print(f"▶️ शुरू कर रहे हैं: {scraper_name}")
    print(f"=======================================================")
    
    start_time = time.time()
    
    try:
        result = subprocess.run([sys.executable, script_path], check=True)
        end_time = time.time()
        minutes = (end_time - start_time) / 60
        print(f"\n✅ {scraper_name} सफलतापूर्वक पूरा हुआ! (समय: {minutes:.2f} मिनट)")
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {scraper_name} में एरर आया! (Error Code: {e.returncode})")
    except FileNotFoundError:
        print(f"\n❌ स्क्रिप्ट नहीं मिली: {script_path}। कृपया पाथ चेक करें।")
    except Exception as e:
        print(f"\n❌ {scraper_name} चलाते समय अज्ञात एरर: {e}")

    print("🧹 RAM और मेमोरी क्लियर की जा रही है...")
    time.sleep(2)

def main():
    print("🤖 THE BOSS FILE: MASTER SCRAPER शुरू हो रहा है...")
    
    # 1. शुरुआती गिनती चेक करो
    current_count = get_anime_count()
    print(f"📊 अभी डेटाबेस में कुल {current_count} एनीमे हैं (लिमिट: {MAX_ANIME_LIMIT})")
    
    if current_count >= MAX_ANIME_LIMIT:
        print(f"🛑 डेटाबेस लिमिट ({MAX_ANIME_LIMIT}) पूरी हो चुकी है! आगे स्क्रैपिंग नहीं होगी।")
        return

    # 2. AnimeSalt स्क्रैपर चलाओ
    if current_count < MAX_ANIME_LIMIT:
        run_scraper("scraper/smart_scraper.py", "AnimeSalt Scraper")
        current_count = get_anime_count()
        print(f"📊 AnimeSalt के बाद डेटाबेस में {current_count} एनीमे हैं।")
        
    # 3. ToonStream स्क्रैपर चलाओ (अगर लिमिट नहीं पहुँची है)
    if current_count < MAX_ANIME_LIMIT:
        run_scraper("scraper/toonstream_scraper.py", "ToonStream Mega Scraper")
    else:
        print("🛑 AnimeSalt के बाद ही लिमिट पूरी हो गई! ToonStream स्किप किया जा रहा है।")

    # 4. फाइनल स्टेटस
    final_count = get_anime_count()
    print(f"\n=======================================================")
    print(f"🎉 ALL SCRAPING DONE! अब डेटाबेस में कुल {final_count} एनीमे हैं।")
    print(f"=======================================================")

    # ==========================================
    # 6. 🚀 ऑटोमैटिक टेलीग्राम पोस्टर (नया जोड़ा गया है)
    # ==========================================
    print("\n📤 अब Telegram पर नए एनीमे पोस्ट किए जा रहे हैं...")
    run_scraper("telegram_poster.py", "Telegram Auto-Poster")

if __name__ == "__main__":
    main()