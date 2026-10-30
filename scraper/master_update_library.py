import subprocess
import sys
import time
import os
import gc

# 🛑 कॉन्फ़िगरेशन (स्क्रिप्ट्स के पाथ)
# सुनिश्चित करें कि ये फाइलें तुम्हारे scraper फोल्डर में मौजूद हैं
SEASONS_FIXER_SCRIPT = "scraper/update_seasons.py"
ANIMESALT_SCRIPT = "scraper/update_library.py"
TOONSTREAM_SCRIPT = "scraper/update_toonstream.py"

def run_script(script_path, script_name):
    """किसी भी स्क्रिप्ट को एक अलग प्रोसेस में रन करता है ताकि RAM क्लियर हो जाए"""
    print(f"\n=======================================================")
    print(f"🔄 शुरू कर रहे हैं: {script_name}")
    print(f"=======================================================")
    
    if not os.path.exists(script_path):
        print(f"❌ स्क्रिप्ट नहीं मिली: {script_path}। कृपया पाथ चेक करें।")
        return False

    start_time = time.time()
    
    try:
        # sys.executable का इस्तेमाल करने से वही पायथन वर्ज़न चलेगा जो सिस्टम में है
        subprocess.run([sys.executable, script_path], check=True)
        
        end_time = time.time()
        minutes = (end_time - start_time) / 60
        
        print(f"\n✅ {script_name} सफलतापूर्वक पूरा हुआ! (समय: {minutes:.2f} मिनट)")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {script_name} में एरर आया! (Error Code: {e.returncode})")
    except Exception as e:
        print(f"\n❌ {script_name} चलाते समय अज्ञात एरर: {e}")

    return False

def clean_ram():
    """RAM और मेमोरी साफ करने का फंक्शन"""
    print("🧹 RAM और मेमोरी क्लियर की जा रही है...")
    gc.collect() 
    time.sleep(3) 

def main():
    print("🤖 THE BOSS FILE: MASTER UPDATE LIBRARY शुरू हो रहा है...")
    print("⚠️ नोट: यह स्क्रिप्ट सारे पुराने एनीमे के नए एपिसोड्स चेक करेगी। इसमें घंटों लग सकते हैं।")
    
    # 1. सबसे पहले पुराने डेटा (सीज़न मिसिंग) को फिक्स करो
    # (यह सबसे तेज़ है क्योंकि इसमें requests का इस्तेमाल होता है)
    run_script(SEASONS_FIXER_SCRIPT, "Seasons Fixer (Legacy Data)")
    clean_ram()
    
    # 2. फिर AnimeSalt अपडेटर चलाओ
    run_script(ANIMESALT_SCRIPT, "AnimeSalt Updater")
    clean_ram()
    
    # 3. फिर ToonStream अपडेटर चलाओ
    run_script(TOONSTREAM_SCRIPT, "ToonStream Updater")
    clean_ram()

    print(f"\n=======================================================")
    print(f"🎉 सभी अपडेट प्रोसेस खत्म हो गए!")
    print("👉 अब आप अपना अपडेटेड डेटाबेस Git पर पुश कर सकते हैं।")
    print(f"=======================================================")

if __name__ == "__main__":
    main()