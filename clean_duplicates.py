import json
import os

DB_PATH = os.path.join(os.getcwd(), 'database', 'storage.json')

def clean_duplicate_videos():
    print("🔍 Checking database for duplicate video links...")
    if not os.path.exists(DB_PATH):
        print("❌ storage.json not found!")
        return

    with open(DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    anime_list = data.get('anime_list', [])
    total_removed = 0

    for anime in anime_list:
        seasons = anime.get('seasons', [])
        if not seasons:
            continue

        seen_urls = set()

        for season in seasons:
            episodes = season.get('episodes', [])
            valid_episodes = []
            
            for ep in episodes:
                video_url = ep.get('video_url')
                
                # Agar video_url pehle se dekh chuke hain, toh isko skip kar do
                if video_url and video_url in seen_urls:
                    print(f"🗑️ Removed duplicate video from {anime['title']} (Season {season.get('season_number')}, Ep {ep.get('ep_num')})")
                    total_removed += 1
                else:
                    if video_url:
                        seen_urls.add(video_url)
                    valid_episodes.append(ep)
            
            # Update the episodes list without duplicates
            season['episodes'] = valid_episodes

    # Save back to database
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    print(f"✅ Cleaning complete! Total duplicates removed: {total_removed}")

if __name__ == "__main__":
    clean_duplicate_videos()