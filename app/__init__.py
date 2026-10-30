from flask import Flask, render_template, abort, request, redirect, jsonify, send_from_directory, Response
import random
import os
import re
import urllib.parse
from config import Config
from .services.db_manager import (get_all_anime, get_anime_by_id, search_anime,
                                   get_random_anime, get_featured_anime,
                                   get_anime_by_genre, get_single_random_anime,
                                   get_top_anime, get_hero_anime_list)

# 🛠️ स्मार्ट रेटिंग जनरेट करने का फंक्शन
def generate_smart_rating(title):
    if not title: return "8.0"
    total = sum(ord(c) for c in title)
    rating = 7.5 + (total % 24) / 10.0 
    return f"{rating:.1f}"

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.secret_key = app.config['SECRET_KEY']
    
    @app.route('/google284a1cf6abd21b7d.html')
    def google_verification():
        return send_from_directory(app.static_folder, 'google284a1cf6abd21b7d.html')

    @app.route('/sitemap.xml', methods=['GET'])
    def sitemap():
        try:
            all_anime = get_all_anime()
            base_url = request.url_root.rstrip('/')
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            static_pages = ['/', '/trending', '/movies', '/cartoons', '/top-rated', '/popular', '/categories', '/history', '/watchlist']
            for page in static_pages:
                xml += f'  <url>\n    <loc>{base_url}{page}</loc>\n    <changefreq>daily</changefreq>\n    <priority>1.0</priority>\n  </url>\n'
            for anime in all_anime:
                anime_url = f"{base_url}/watch/{anime.get('id', '')}"
                xml += f'  <url>\n    <loc>{anime_url}</loc>\n    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>\n'
            xml += '</urlset>'
            return Response(xml, mimetype='application/xml')
        except Exception as e:
            return Response("Error generating sitemap", status=500)

    def get_filtered_anime():
        all_anime = get_all_anime()
        for anime in all_anime:
            if 'rating' not in anime or anime['rating'] == '8.0' or not anime['rating']:
                anime['rating'] = generate_smart_rating(anime.get('title', ''))

        cartoon_keywords = ['ben 10', 'doraemon', 'shinchan', 'tom and jerry', 'pokemon', 'beyblade', 'barbie', 'spiderman', 'batman']
        movies_list = [a for a in all_anime if a.get('episodes') and len(a['episodes']) > 0 and a['episodes'][0].get('title') == 'Full Movie']
        cartoons_list = [a for a in all_anime if any(k in a['title'].lower() for k in cartoon_keywords)]
        series_list = [a for a in all_anime if a not in movies_list and a not in cartoons_list]
        
        trending_full = sorted(series_list, key=lambda x: float(x.get('rating', 0) or 0), reverse=True)
        popular_full = sorted(series_list, key=lambda x: len(x.get('episodes', [])), reverse=True)
        
        return all_anime, trending_full, popular_full, movies_list, series_list, cartoons_list

    @app.context_processor
    def inject_search_data():
        try:
            all_anime = get_all_anime()
            for anime in all_anime:
                if 'rating' not in anime or anime['rating'] == '8.0' or not anime['rating']:
                    anime['rating'] = generate_smart_rating(anime.get('title', ''))

            popular = sorted(all_anime, key=lambda x: len(x.get('episodes', [])), reverse=True)[:10]
            top_rated = sorted(all_anime, key=lambda x: float(x.get('rating', 0) or 0), reverse=True)[:10]
            trending_searches = [a['title'] for a in popular[:6]] 
            return dict(popular_anime_overlay=popular, top_rated_anime_overlay=top_rated, trending_searches=trending_searches)
        except:
            return dict(popular_anime_overlay=[], top_rated_anime_overlay=[], trending_searches=[])

    # 🛠️ नया सुपरफास्ट Custom Poster (ChatGPT स्टाइल)
    @app.route('/api/custom_poster/<anime_id>')
    def custom_poster(anime_id):
        anime = get_anime_by_id(anime_id)
        if not anime: abort(404)
        
        title = anime.get('title', 'Unknown')
        rating = anime.get('rating', '8.0')
        raw_image_url = anime.get('image', '')
        
        if not rating or rating == '8.0':
            rating = generate_smart_rating(title)
        
        # इमेज लिंक को साफ करो
        image_url = urllib.parse.quote(raw_image_url, safe=':/?&=%') if raw_image_url else ""
        
        short_title = (title[:25] + '...') if len(title) > 25 else title
        total_chars = sum(ord(c) for c in title)
        hue = total_chars % 360
        
        # 🛠️ ChatGPT स्टाइल डिज़ाइन: बैकग्राउंड में असली इमेज, ऊपर डार्क ग्रेडिएंट, और टेक्स्ट
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="450" viewBox="0 0 300 450">
            <defs>
                <!-- डार्क ग्रेडिएंट (नीचे से ऊपर) -->
                <linearGradient id="overlayGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="20%" style="stop-color:rgba(11,15,25,0);stop-opacity:1" />
                    <stop offset="80%" style="stop-color:rgba(11,15,25,0.8);stop-opacity:1" />
                    <stop offset="100%" style="stop-color:rgba(11,15,25,1);stop-opacity:1" />
                </linearGradient>
                
                <!-- अगर इमेज लोड न हो तो यूनिक रंग -->
                <linearGradient id="fallbackGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:hsl({hue}, 50%, 20%);stop-opacity:1" />
                    <stop offset="100%" style="stop-color:hsl({(hue + 60) % 360}, 50%, 10%);stop-opacity:1" />
                </linearGradient>
            </defs>
            
            <!-- फॉलबैक बैकग्राउंड -->
            <rect width="300" height="450" fill="url(#fallbackGrad)" />
            
            <!-- असली एनीमे इमेज -->
            <image href="{image_url}" width="300" height="450" preserveAspectRatio="xMidYMid slice" />
            
            <!-- ऊपर डार्क ग्रेडिएंट -->
            <rect width="300" height="450" fill="url(#overlayGrad)" />
            
            <!-- ऊपर बाईं तरफ AnimeNest बैज -->
            <rect x="10" y="10" width="85" height="22" rx="11" fill="rgba(168, 85, 247, 0.9)" />
            <text x="52" y="25" font-family="Arial, sans-serif" font-weight="bold" font-size="10" fill="#ffffff" text-anchor="middle" dominant-baseline="middle">AnimeNest</text>
            
            <!-- ऊपर दाईं तरफ रेटिंग -->
            <rect x="245" y="10" width="45" height="22" rx="11" fill="rgba(0,0,0,0.6)" />
            <text x="267" y="25" font-family="Arial, sans-serif" font-weight="bold" font-size="10" fill="#f1c40f" text-anchor="middle" dominant-baseline="middle">★ {rating}</text>
            
            <!-- नीचे एनीमे का नाम -->
            <text x="15" y="400" font-family="Arial, sans-serif" font-weight="bold" font-size="18" fill="#ffffff">{short_title}</text>
            <text x="15" y="425" font-family="Arial, sans-serif" font-weight="bold" font-size="10" fill="#a855f7">WATCH FREE ON ANIMENEST</text>
        </svg>'''
        
        return Response(svg, mimetype='image/svg+xml')

    @app.route('/api/recommend')
    def api_recommend():
        genre = request.args.get('genre', 'Action')
        all_anime = get_all_anime()
        
        for anime in all_anime:
            if 'rating' not in anime or anime['rating'] == '8.0' or not anime['rating']:
                anime['rating'] = generate_smart_rating(anime.get('title', ''))

        recommended = []
        for anime in all_anime:
            title_lower = anime['title'].lower()
            if genre.lower() == 'action' and any(k in title_lower for k in ['slayer', 'jujutsu', 'naruto', 'piece', 'leveling', 'titan', 'fight', 'battle', 'action']):
                recommended.append(anime)
            elif genre.lower() == 'romance' and any(k in title_lower for k in ['love', 'romance', 'couple', 'girlfriend', 'kaguya', 'wedding']):
                recommended.append(anime)
            elif genre.lower() == 'fantasy' and any(k in title_lower for k in ['reincarnated', 'isekai', 'magic', 'dungeon', 'king', 'sword', 'fantasy']):
                recommended.append(anime)
            elif genre.lower() == 'comedy' and any(k in title_lower for k in ['comedy', 'life', 'school', 'family', 'spy', 'funny']):
                recommended.append(anime)

        if not recommended:
            recommended = random.sample(all_anime, min(12, len(all_anime)))
        
        random.shuffle(recommended)
        return jsonify(recommended[:12])

    @app.route('/')
    def home():
        all_anime, trending_full, popular_full, movies_full, series_full, cartoons_full = get_filtered_anime()
        trending = random.sample(trending_full[:50], min(len(trending_full[:50]), 12)) if trending_full else []
        popular = random.sample(popular_full[:50], min(len(popular_full[:50]), 12)) if popular_full else []
        movies = movies_full[:12]
        cartoons = cartoons_full[:12]
        hero_anime_list = get_hero_anime_list(5)
        return render_template('index.html', anime_list=all_anime, trending=trending, popular=popular, movies=movies, cartoons=cartoons, hero_anime_list=hero_anime_list, page_title='Home')

    @app.route('/trending')
    def trending_page():
        _, trending_full, _, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=trending_full, page_title="Trending Anime")

    @app.route('/movies')
    def movies_page():
        _, _, _, movies_full, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=movies_full, page_title="Anime Movies")

    @app.route('/cartoons')
    def cartoons_page():
        _, _, _, _, _, cartoons_full = get_filtered_anime()
        return render_template('index.html', anime_list=cartoons_full, page_title="Cartoons")

    @app.route('/categories')
    def categories_page():
        all_anime, _, _, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=all_anime, page_title="All Categories")

    @app.route('/top-rated')
    def top_rated_page():
        all_anime, _, _, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=all_anime, page_title="Top Rated")

    @app.route('/popular')
    def popular_page():
        _, _, popular_full, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=popular_full, page_title="Popular Anime")

    @app.route('/az/<letter>')
    def az_page(letter):
        letter = letter.upper()
        all_anime, _, _, _, _, _ = get_filtered_anime()
        filtered = [a for a in all_anime if a['title'].upper().startswith(letter)]
        filtered.sort(key=lambda x: x['title'].lower())
        return render_template('index.html', anime_list=filtered, page_title=f"Anime starting with '{letter}'")

    @app.route('/search')
    def search():
        query = request.args.get('q', '')
        anime_list = search_anime(query) if query else get_all_anime()
        
        for anime in anime_list:
            if 'rating' not in anime or anime['rating'] == '8.0' or not anime['rating']:
                anime['rating'] = generate_smart_rating(anime.get('title', ''))

        return render_template('index.html', anime_list=anime_list, search_query=query, page_title=f"Search Results")

    @app.route('/random')
    def random_anime():
        anime = get_single_random_anime()
        if anime: return redirect(f"/watch/{anime['id']}")
        return redirect('/')

    @app.route('/history')
    def history():
        return render_template('history.html', page_title='History')

    @app.route('/watchlist')
    def watchlist():
        return render_template('watchlist.html', page_title='Watchlist')

    @app.route('/watch/<anime_id>')
    @app.route('/watch/<anime_id>/<int:season_number>')
    @app.route('/watch/<anime_id>/<int:season_number>/<ep_number>')
    def watch(anime_id, season_number=1, ep_number=None):
        anime = get_anime_by_id(anime_id)
        if not anime: abort(404)
        
        if 'rating' not in anime or anime['rating'] == '8.0' or not anime['rating']:
            anime['rating'] = generate_smart_rating(anime.get('title', ''))

        seasons = anime.get('seasons', [])
        if not seasons:
            episodes = anime.get('episodes', [])
            if episodes:
                seasons = [{"season_number": 1, "episodes": episodes}]
                
        current_season = next((s for s in seasons if s['season_number'] == season_number), None)
        if not current_season and seasons:
            current_season = seasons[0]
            season_number = current_season['season_number']
            
        episodes = current_season['episodes'] if current_season else []
        
        current_ep, current_index = None, 0
        if episodes:
            if ep_number is None:
                current_ep = episodes[0]
                current_index = 0
            else:
                match = re.search(r'(\d+)$', str(ep_number))
                actual_ep_num = match.group(1) if match else str(ep_number)
                for i, ep in enumerate(episodes):
                    if f"Episode {actual_ep_num}" in ep.get('title', '') or str(ep.get('ep_num')) == actual_ep_num:
                        current_ep = ep
                        current_index = i
                        break
            if not current_ep:
                current_ep = episodes[0]
                current_index = 0
                
        prev_ep_num, next_ep_num = None, None
        if episodes:
            if current_index > 0:
                prev_match = episodes[current_index - 1]['title'].split(' ')[-1]
                if prev_match.isdigit(): prev_ep_num = prev_match
            if current_index < len(episodes) - 1:
                next_match = episodes[current_index + 1]['title'].split(' ')[-1]
                if next_match.isdigit(): next_ep_num = next_match
                
        title_lower = anime['title'].lower()
        if any(k in title_lower for k in ['slayer', 'jujutsu', 'naruto', 'piece', 'leveling', 'titan']):
            genres_text = "Action • Adventure • Fantasy"
        elif any(k in title_lower for k in ['love', 'romance', 'couple', 'girlfriend', 'kaguya']):
            genres_text = "Romance • Comedy • Drama"
        elif any(k in title_lower for k in ['reincarnated', 'isekai', 'magic', 'dungeon', 'king']):
            genres_text = "Fantasy • Isekai • Adventure"
        elif any(k in title_lower for k in ['comedy', 'life', 'school', 'family', 'spy']):
            genres_text = "Comedy • Slice of Life • Drama"
        else:
            genres_text = "Action • Adventure • Drama"
            
        description = f"Watch the amazing story of {anime['title']}. An unforgettable journey filled..."
        related_anime = get_random_anime(anime_id, count=4)
        
        return render_template('watch.html', anime=anime, seasons=seasons, current_season=current_season,
                               episodes=episodes, current_ep=current_ep, prev_ep=prev_ep_num, next_ep=next_ep_num,
                               related_anime=related_anime, genres_text=genres_text, description=description,
                               ep_number=ep_number)

    @app.errorhandler(404)
    def page_not_found(e): return render_template('404.html'), 404

    return app