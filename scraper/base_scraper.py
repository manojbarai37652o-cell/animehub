import requests
import sys
import os
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from parser import parse_episodes, parse_video_link
from app.services.db_manager import get_all_anime, update_anime_episodes

def fetch_page(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ एरर: {e}")
        return None

if __name__ == '__main__':
    anime_list = get_all_anime()
    print(f"🚀 कुल {len(anime_list)} एनिमे मिले। स्क्रैपिंग शुरू हो रही है...")
    print("⚠️ भाई, इसमें 5-10 मिनट लग सकते हैं क्योंकि अब हम सारे एपिसोड्स के लिंक निकाल रहे हैं।")

    for index, anime in enumerate(anime_list):
        print(f"\n[{index + 1}/{len(anime_list)}] चेक कर रहे हैं: {anime['title']}")
        
        anime_url = anime['url']
        anime_html = fetch_page(anime_url)
        if not anime_html:
            print("   ❌ एनिमे का पेज नहीं खुला।")
            continue

        episodes = parse_episodes(anime_html, anime_url)
        if not episodes:
            print("   ❌ कोई एपिसोड नहीं मिला।")
            continue
        
        print(f"   ✅ {len(episodes)} एपिसोड मिले। अब सभी के वीडियो लिंक निकाले जा रहे हैं...")
        
        # ✅ यहाँ हमने [:3] हटा दिया है, अब पूरे episodes पर लूप चलेगा
        for ep_index, ep in enumerate(episodes):
            # हर 5 एपिसोड के बाद एक बार प्रिंट करें ताकि टर्मिनल भर न जाए
            if ep_index % 5 == 0:
                print(f"      [{ep_index + 1}/{len(episodes)}] {ep['title']} का लिंक...")
                
            ep_html = fetch_page(ep['url'])
            
            if ep_html:
                video_url = parse_video_link(ep_html, ep['url'])
                ep['video_url'] = video_url
            else:
                ep['video_url'] = ""
            
            time.sleep(1) # 1 सेकंड का इंतज़ार ताकि वेबसाइट ब्लॉक न करे

        update_anime_episodes(anime['id'], episodes)
        print(f"   💾 {anime['title']} का पूरा डेटा सेव हो गया!")
        
    print("\n🎉 भाई, सारे एनिमे के सारे एपिसोड्स स्क्रैप हो गए! अब सर्वर चलाओ और वेबसाइट देखो।")