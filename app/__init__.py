from flask import Flask, render_template, abort, request, redirect, jsonify, send_from_directory, Response
import random
import os
import re
import json
import requests
from datetime import datetime
from config import Config
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import libsql_client

from .services.db_manager import (get_all_anime, get_anime_by_id, search_anime,
                                   get_random_anime, get_featured_anime,
                                   get_anime_by_genre, get_single_random_anime,
                                   get_top_anime, get_hero_anime_list)

TURSO_URL = os.environ.get('TURSO_DATABASE_URL')
TURSO_TOKEN = os.environ.get('TURSO_AUTH_TOKEN')

if TURSO_URL and TURSO_URL.startswith("libsql://"):
    TURSO_URL = TURSO_URL.replace("libsql://", "https://", 1)

COMMENTS_FILE = os.path.join(os.getcwd(), 'database', 'comments.json')

def get_turso_client():
    if not TURSO_URL or not TURSO_TOKEN:
        return None
    try:
        return libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)
    except Exception as e:
        print(f"Turso Comments Client Error: {e}")
        return None

def get_comments_data(anime_id):
    anime_id_str = str(anime_id)
    client = get_turso_client()
    if client:
        try:
            client.execute("CREATE TABLE IF NOT EXISTS comments (anime_id TEXT PRIMARY KEY, data TEXT)")
            res = client.execute("SELECT data FROM comments WHERE anime_id = ?", [anime_id_str])
            if res.rows and len(res.rows) > 0:
                return json.loads(res.rows[0][0])
        except Exception as e:
            print(f"Turso Comments Fetch Error: {e}")
        finally:
            client.close()
    
    if not os.path.exists(COMMENTS_FILE):
        return []
    try:
        with open(COMMENTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get(anime_id_str, [])
    except:
        return []

def save_comment_data(anime_id, new_comment):
    anime_id_str = str(anime_id)
    comments = get_comments_data(anime_id)
    if 'anime_id' in new_comment: del new_comment['anime_id']
    comments.insert(0, new_comment)
    comments = comments[:500] 
    
    client = get_turso_client()
    turso_success = False
    if client:
        try:
            client.execute("CREATE TABLE IF NOT EXISTS comments (anime_id TEXT PRIMARY KEY, data TEXT)")
            client.execute("INSERT OR REPLACE INTO comments (anime_id, data) VALUES (?, ?)", [anime_id_str, json.dumps(comments, ensure_ascii=False)])
            turso_success = True
        except Exception as e:
            print(f"Turso Comments Save Error: {e}")
        finally:
            client.close()
            
    data = {}
    if os.path.exists(COMMENTS_FILE):
        try:
            with open(COMMENTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            pass
    data[anime_id_str] = comments
    try:
        os.makedirs(os.path.dirname(COMMENTS_FILE), exist_ok=True)
        with open(COMMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except:
        pass

    return True if (turso_success or data) else False

def generate_smart_rating(title):
    if not title: return "8.0"
    total = sum(ord(c) for c in title)
    rating = 7.5 + (total % 24) / 10.0 
    return f"{rating:.1f}"

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.secret_key = app.config['SECRET_KEY']
    
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[app.config.get("RATELIMIT_DEFAULT", "200 per minute")],
        storage_uri=app.config.get("RATELIMIT_STORAGE_URI", "memory://")
    )

    @app.after_request
    def add_security_headers(response):
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.route('/api/comments/<anime_id>', methods=['GET', 'POST'])
    def handle_comments(anime_id):
        if request.method == 'GET':
            return jsonify(get_comments_data(anime_id))
        
        elif request.method == 'POST':
            req_data = request.get_json()
            text = req_data.get('text', '').strip()
            username = req_data.get('username', 'Guest')
            avatar_color = req_data.get('avatar_color', 'a855f7')
            
            if not text:
                return jsonify({'error': 'Comment cannot be empty'}), 400
                
            new_comment = {
                'id': str(datetime.now().timestamp()),
                'username': username,
                'text': text,
                'timestamp': datetime.now().strftime("%d/%m/%Y, %I:%M %p"),
                'timestamp_raw': datetime.now().timestamp(),
                'likes': 0,
                'avatar_color': avatar_color
            }
            
            if save_comment_data(anime_id, new_comment):
                return jsonify(new_comment), 201
            return jsonify({'error': 'Failed to save comment'}), 500

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
                xml += f'  <url>\n    <loc>{base_url}/watch/{anime.get("id", "")}</loc>\n    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>\n'
            xml += '</urlset>'
            return Response(xml, mimetype='application/xml')
        except Exception as e:
            return Response("Error", status=500)

    _cached_filtered_data = None
    _cached_inject_data = None

    def get_filtered_anime():
        nonlocal _cached_filtered_data
        if _cached_filtered_data is not None:
            return _cached_filtered_data

        all_anime = get_all_anime()
        for anime in all_anime:
            if 'rating' not in anime or anime['rating'] == '8.0' or not anime['rating']:
                anime['rating'] = generate_smart_rating(anime.get('title', ''))

        cartoon_keywords = ['ben 10', 'tom and jerry', 'tom & jerry', 'scooby', 'looney tunes', 'popeye', 'pink panther', 'mr bean', 'oggy', 'zig & sharko', 'grizzy', 'ed edd', 'ed, edd n eddy', 'johnny test', 'powerpuff', 'dexter', 'courage', 'cow and chicken', 'adventure time', 'regular show', 'gumball', 'rick and morty', 'simpsons', 'family guy', 'spongebob', 'avatar', 'teen titans', 'justice league', 'x-men', 'ninja turtles', 'transformers', 'my little pony', 'care bears', 'johnny bravo', 'fosters home', 'chowder', 'steven universe', 'gravity falls', 'phineas and ferb', 'kim possible', 'danny phantom', 'fairly oddparents', 'jimmy neutron', 'rugrats', 'hey arnold', 'catdog', 'rockos modern life', 'ren and stimpy', 'animaniacs', 'tale spin', 'duck tales', 'darkwing duck', 'chip n dale', 'aladdin', 'hercules', 'tarzan', 'lilo and stitch', 'doraemon', 'shinchan', 'shin chan', 'kiteretsu', 'perman', 'ninja hattori', 'chhota bheem', 'motu patlu', 'pokemon', 'pokémon', 'beyblade', 'bakugan', 'digimon', 'yugioh', 'cardcaptor', 'roll no 21', 'keymon', 'vir the robot boy', 'rudra', 'gaju bhai', 'barbie', 'chikame', 'kochikame', 'sgt. frog', 'sgt frog', 'kiteretsu', 'ninja hattori', 'perman', 'tensai bakabon', 'chibi maruko', 'spiderman', 'spider-man', 'batman', 'superman', 'marvel', 'avengers', 'iron man', 'hulk', 'captain america', 'thor', 'doctor strange', 'flash', 'green lantern', 'aquaman', 'wonder woman', 'toy story', 'finding nemo', 'frozen', 'shrek', 'madagascar', 'kung fu panda', 'how to train your dragon', 'princess and the frog', '1001 nights', 'hotel transylvania', 'despicable me', 'minions', 'ice age', 'cars', 'moana', 'coco', 'up', 'wall-e', 'ratatouille', 'the incredibles', 'zootopia', 'big hero 6', 'encanto', 'brave', 'tangled', 'wreck-it ralph', 'mulan', 'pocahontas', 'beauty and the beast', 'the lion king', 'the little mermaid', 'peter pan', 'pinocchio', 'bambi', 'dumbo']
        anime_blacklist = ['cuckoos', 'kamen rider', 'tokusatsu', 'anime', 'senpai']

        cartoon_regex = re.compile(r'\b(' + '|'.join(map(re.escape, cartoon_keywords)) + r')\b', re.IGNORECASE)
        blacklist_regex = re.compile(r'\b(' + '|'.join(map(re.escape, anime_blacklist)) + r')\b', re.IGNORECASE)

        cartoons_list = []
        movies_list = []
        series_list = []

        for a in all_anime:
            title = a['title']
            
            is_cartoon = bool(cartoon_regex.search(title))
            if is_cartoon and blacklist_regex.search(title):
                is_cartoon = False

            is_movie = False
            if a.get('episodes') and len(a['episodes']) > 0:
                first_ep_title = a['episodes'][0].get('title', '').lower()
                if 'full movie' in first_ep_title or 'movie' in first_ep_title:
                    is_movie = True

            if is_movie:
                movies_list.append(a)
            elif is_cartoon:
                cartoons_list.append(a)
            else:
                series_list.append(a)
        
        trending_full = sorted(series_list, key=lambda x: float(x.get('rating', 0) or 0), reverse=True)
        popular_full = sorted(series_list, key=lambda x: len(x.get('episodes', [])), reverse=True)
        
        _cached_filtered_data = (all_anime, trending_full, popular_full, movies_list, series_list, cartoons_list)
        return _cached_filtered_data

    @app.context_processor
    def inject_search_data():
        nonlocal _cached_inject_data
        if _cached_inject_data is not None:
            return _cached_inject_data
            
        try:
            all_anime = get_all_anime()
            for anime in all_anime:
                if 'rating' not in anime or anime['rating'] == '8.0' or not anime['rating']:
                    anime['rating'] = generate_smart_rating(anime.get('title', ''))

            popular = sorted(all_anime, key=lambda x: len(x.get('episodes', [])), reverse=True)[:10]
            top_rated = sorted(all_anime, key=lambda x: float(x.get('rating', 0) or 0), reverse=True)[:10]
            trending_searches = [a['title'] for a in popular[:6]] 
            
            _cached_inject_data = dict(popular_anime_overlay=popular, top_rated_anime_overlay=top_rated, trending_searches=trending_searches)
            return _cached_inject_data
        except:
            return dict(popular_anime_overlay=[], top_rated_anime_overlay=[], trending_searches=[])

    @app.route('/api/recommend')
    @limiter.limit("60 per minute")
    def api_recommend():
        genres_param = request.args.get('genres', 'Action')
        user_genres = [g.strip().lower() for g in genres_param.split(',') if g.strip()]
        all_anime = get_all_anime()
        
        recommended = []
        genre_keywords = {
            'action': ['slayer', 'jujutsu', 'naruto', 'piece', 'leveling', 'titan', 'fight', 'battle', 'action', 'hero', 'hunter'],
            'romance': ['love', 'romance', 'couple', 'girlfriend', 'kaguya', 'wedding', 'darling', 'horimiya'],
            'fantasy': ['reincarnated', 'isekai', 'magic', 'dungeon', 'king', 'sword', 'fantasy', 'witch', 'demon'],
            'comedy': ['comedy', 'life', 'school', 'family', 'spy', 'funny', 'slice', 'club']
        }
        for anime in all_anime:
            title_lower = anime['title'].lower()
            for g in user_genres:
                if g in genre_keywords:
                    if any(k in title_lower for k in genre_keywords[g]):
                        recommended.append(anime)
                        break
        if not recommended:
            recommended = random.sample(all_anime, min(12, len(all_anime)))
        else:
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
        random_series = random.sample(series_full, min(len(series_full), 10)) if series_full else []
        random_movies = random.sample(movies_full, min(len(movies_full), 10)) if movies_full else []

        return render_template('index.html', trending=trending, popular=popular, movies=movies, cartoons=cartoons, 
                               hero_anime_list=hero_anime_list, random_series=random_series, random_movies=random_movies, page_title='Home')

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
        
        season_number_str = str(season_number)
        current_season = next((s for s in seasons if str(s.get('season_number')) == season_number_str), None)
        
        if not current_season and seasons:
            current_season = seasons[0]
            season_number = current_season.get('season_number', 1)
            
        episodes = current_season.get('episodes', []) if current_season else []
        
        # 🛠️ FIX: Details page will only show if ep_number is None
        current_ep, current_index = None, 0
        if episodes and ep_number is not None:
            ep_number_str = str(ep_number)
            for i, ep in enumerate(episodes):
                ep_num_db = str(ep.get('ep_num', ''))
                ep_title = ep.get('title', '').lower()
                if ep_num_db == ep_number_str or f"episode {ep_number_str}" in ep_title or ep_title == ep_number_str:
                    current_ep = ep
                    current_index = i
                    break
                    
            if not current_ep:
                current_ep = episodes[0]
                current_index = 0
                ep_number = current_ep.get('ep_num', 1)
                
        prev_ep_num, next_ep_num = None, None
        if episodes and current_ep is not None:
            if current_index > 0: prev_ep_num = episodes[current_index - 1].get('ep_num', current_index)
            if current_index < len(episodes) - 1: next_ep_num = episodes[current_index + 1].get('ep_num', current_index + 2)
                
        title_lower = anime['title'].lower()
        if any(k in title_lower for k in ['slayer', 'jujutsu', 'naruto', 'piece', 'leveling', 'titan']): genres_text = "Action • Adventure • Fantasy"
        elif any(k in title_lower for k in ['love', 'romance', 'couple', 'girlfriend', 'kaguya']): genres_text = "Romance • Comedy • Drama"
        elif any(k in title_lower for k in ['reincarnated', 'isekai', 'magic', 'dungeon', 'king']): genres_text = "Fantasy • Isekai • Adventure"
        elif any(k in title_lower for k in ['comedy', 'life', 'school', 'family', 'spy']): genres_text = "Comedy • Slice of Life • Drama"
        else: genres_text = "Action • Adventure • Drama"
            
        description = f"Watch the amazing story of {anime['title']}. An unforgettable journey filled..."
        related_anime = get_random_anime(anime_id, count=4)
        
        return render_template('watch.html', anime=anime, seasons=seasons, current_season=current_season,
                               episodes=episodes, current_ep=current_ep, prev_ep=prev_ep_num, next_ep=next_ep_num,
                               related_anime=related_anime, genres_text=genres_text, description=description,
                               ep_number=ep_number)

    @app.errorhandler(404)
    def page_not_found(e): return render_template('404.html'), 404

    return app