from flask import Flask, render_template, abort, request, redirect, url_for, session, Response, stream_with_context
import random
import re
import requests
from urllib.parse import urljoin, quote
from config import Config
from .services.db_manager import (get_all_anime, get_anime_by_id, search_anime,
                                   get_random_anime, get_featured_anime,
                                   get_anime_by_genre, get_single_random_anime,
                                   get_top_anime, get_hero_anime_list)
from flask_dance.contrib.google import make_google_blueprint, google

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.secret_key = app.config['SECRET_KEY']

    google_bp = make_google_blueprint(
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        scope=["openid", "email", "profile"],
        redirect_url="/login"
    )
    app.register_blueprint(google_bp, url_prefix="/login")

    # ============================================================
    # 🚀 CORS PROXY ROUTE (सारे वीडियो सेगमेंट्स के लिए)
    # ============================================================
    @app.route('/proxy')
    def proxy():
        target_url = request.args.get('url')
        if not target_url:
            return "Missing URL", 400
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                'Referer': 'https://www.desidubanime.me/',
                'Origin': 'https://www.desidubanime.me'
            }
            resp = requests.get(target_url, headers=headers, timeout=30, stream=True)
            
            if '.m3u8' in target_url or 'mpegurl' in resp.headers.get('Content-Type', ''):
                content = resp.text
                base_url = target_url.rsplit('/', 1)[0] + '/'
                
                lines = content.split('\n')
                new_lines = []
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith('#'):
                        absolute = urljoin(base_url, stripped)
                        new_lines.append(f"/proxy?url={quote(absolute, safe='')}")
                    else:
                        new_lines.append(line)
                
                new_content = '\n'.join(new_lines)
                response = Response(new_content, mimetype='application/vnd.apple.mpegurl')
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response
            else:
                def generate():
                    for chunk in resp.iter_content(chunk_size=8192):
                        yield chunk
                response = Response(stream_with_context(generate()), mimetype=resp.headers.get('Content-Type', 'video/mp2t'))
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response
        except Exception as e:
            print(f"❌ Proxy Error: {e}")
            return f"Proxy error: {e}", 500

    # ============================================================
    # LOGIN / OAUTH
    # ============================================================
    @app.route('/login')
    def login():
        if session.get('user_email'):
            return redirect(url_for('home'))
        if not google.authorized:
            return redirect(url_for("google.login"))
        try:
            resp = google.get("/oauth2/v2/userinfo")
            if resp.ok:
                user_info = resp.json()
                session['user_email'] = user_info['email']
                session['user_name'] = user_info.get('name', 'User')
                session['user_pic'] = user_info.get('picture', '')
                return redirect(url_for('home'))
            else:
                session.clear()
                return render_template('login.html')
        except Exception as e:
            print(f"Error: {e}")
            session.clear()
            return render_template('login.html')

    @app.route('/guest')
    def guest_login():
        session['user_email'] = 'guest@animenest.com'
        session['user_name'] = 'Guest'
        session['user_pic'] = 'https://ui-avatars.com/api/?name=Guest&background=ff4d4d&color=fff'
        return redirect(url_for('home'))

    @app.route('/logout')
    def logout():
        session.clear()
        session.pop('google_token', None)
        session.pop('google_oauth_token', None)
        return redirect(url_for('home'))

    # ============================================================
    # HOME
    # ============================================================
    @app.route('/')
    def home():
        if not session.get('user_email'):
            return render_template('login.html')
        
        all_anime = get_all_anime()
        trending = random.sample(all_anime, min(15, len(all_anime))) if len(all_anime) > 15 else all_anime
        popular = sorted(all_anime, key=lambda x: len(x.get('episodes', [])), reverse=True)[:15]
        
        action_keywords = ['demon slayer', 'jujutsu kaisen', 'one punch man', 'attack on titan', 'solo leveling', 'naruto', 'one piece', 'black clover', 'my hero academia', 'hunter x hunter', 'bleach', 'dragon ball', 'chainsaw man', 'tokyo revengers', 'kaiju no. 8', 'dan da dan', 'vinland saga', 'mob psycho']
        action = [a for a in all_anime if any(k in a['title'].lower() for k in action_keywords)][:15]
        
        comedy_keywords = ['spy x family', 'grand blue', 'kaguya', 'komi', 'nichijou', 'gintama', 'konosuba', 'daily life', 'horimiya', 'fruits basket', 'science fell in love', 'my dress-up darling', 'toradora', 'love is war', 'tomo-chan']
        comedy = [a for a in all_anime if any(k in a['title'].lower() for k in comedy_keywords)][:15]
        
        fantasy_keywords = ['reincarnated', 'isekai', 'mushoku tensei', 'that time i got', 'overlord', 'slime', 're:zero', 'sword art online', 'fate', 'immortal king', 'daily life of the immortal', 'frontier lord', 'wistoria', 'frieren', 'dungeon', 'black torch', 'holy grail']
        fantasy = [a for a in all_anime if any(k in a['title'].lower() for k in fantasy_keywords)][:15]
        
        romance_keywords = ['horimiya', 'kaguya', 'toradora', 'love is war', 'rent-a-girlfriend', 'my dress-up darling', 'fruits basket', 'your name', 'weathering with you', 'a silent voice', 'i want to eat your pancreas', 'garden of words', 'tomo-chan', 'uzaki', 'quintessential', 'science fell in love', 'a couple of cuckoos', 'kanojo', 'lovely complex']
        romance = [a for a in all_anime if any(k in a['title'].lower() for k in romance_keywords)][:15]
        
        hero_anime_list = get_hero_anime_list(5)
        
        return render_template('index.html', anime_list=all_anime, hero_anime_list=hero_anime_list,
                               trending=trending, popular=popular, action=action, comedy=comedy,
                               fantasy=fantasy, romance=romance)

    @app.route('/profile')
    def profile():
        if not session.get('user_email'): return render_template('login.html')
        return render_template('profile.html')

    @app.route('/settings')
    def settings():
        if not session.get('user_email'): return render_template('login.html')
        return render_template('settings.html')

    @app.route('/language')
    def language():
        if not session.get('user_email'): return render_template('login.html')
        return render_template('language.html')

    @app.route('/search')
    def search():
        if not session.get('user_email'): return render_template('login.html')
        query = request.args.get('q', '')
        anime_list = search_anime(query) if query else get_all_anime()
        return render_template('index.html', anime_list=anime_list, search_query=query, hero_anime_list=[], trending=[], popular=[], action=[], comedy=[], fantasy=[], romance=[])

    @app.route('/genre/<genre_name>')
    def genre(genre_name):
        if not session.get('user_email'): return render_template('login.html')
        anime_list = get_anime_by_genre(genre_name)
        return render_template('index.html', anime_list=anime_list, search_query=genre_name.title() + " Anime", hero_anime_list=[], trending=[], popular=[], action=[], comedy=[], fantasy=[], romance=[])

    @app.route('/random')
    def random_anime():
        if not session.get('user_email'): return render_template('login.html')
        anime = get_single_random_anime()
        if anime: return redirect(f"/watch/{anime['id']}")
        return redirect('/')

    @app.route('/watchlist')
    def watchlist():
        if not session.get('user_email'): return render_template('login.html')
        return render_template('watchlist.html')

    # ============================================================
    # WATCH ROUTE
    # ============================================================
    @app.route('/watch/<anime_id>')
    @app.route('/watch/<anime_id>/<int:season_number>')
    @app.route('/watch/<anime_id>/<int:season_number>/<string:ep_number>')
    def watch(anime_id, season_number=1, ep_number=None):
        if not session.get('user_email'): return render_template('login.html')
        
        base_id = re.sub(r'[-_ ]?(episode|ep)[-_ ]?\d+$', '', anime_id, flags=re.IGNORECASE)
        base_id = re.sub(r'[-_ ]?\d+x\d+$', '', base_id)
        
        if ep_number is None:
            ep_match = re.search(r'(?:episode|ep)[-_ ]?(\d+)', anime_id, re.IGNORECASE)
            if ep_match:
                ep_number = ep_match.group(1)
        elif ep_number and not str(ep_number).isdigit():
            num_match = re.search(r'\d+', str(ep_number))
            ep_number = num_match.group(0) if num_match else None
        
        anime = get_anime_by_id(base_id) or get_anime_by_id(anime_id)
        if not anime: 
            print(f"❌ 404 ERROR: Anime not found. Tried ID: '{base_id}' and '{anime_id}'")
            abort(404)
        
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
            else:
                for i, ep in enumerate(episodes):
                    if f"Episode {ep_number}" in ep.get('title', ''):
                        current_ep = ep
                        current_index = i
                        break
                if not current_ep:
                    current_ep = episodes[0]

        prev_ep_num, next_ep_num = None, None
        if episodes:
            if current_index > 0:
                prev_match = episodes[current_index - 1]['title'].split(' ')[-1]
                if prev_match.isdigit(): prev_ep_num = prev_match
            if current_index < len(episodes) - 1:
                next_match = episodes[current_index + 1]['title'].split(' ')[-1]
                if next_match.isdigit(): next_ep_num = next_match

        title_lower = anime['title'].lower()
        if any(k in title_lower for k in ['slayer', 'jujutsu', 'naruto', 'piece', 'leveling', 'titan', 'hunter', 'hero']):
            genres_text = "Action • Adventure • Fantasy"
            description = f"Dive into the epic world of {anime['title']}! Follow the thrilling journey of powerful characters."
        elif any(k in title_lower for k in ['love', 'romance', 'couple', 'girlfriend', 'kaguya']):
            genres_text = "Romance • Comedy • Drama"
            description = f"Experience the heartwarming tale of {anime['title']}. A beautiful story of love and friendship."
        elif any(k in title_lower for k in ['reincarnated', 'isekai', 'magic', 'dungeon', 'king']):
            genres_text = "Fantasy • Isekai • Adventure"
            description = f"Step into the magical world of {anime['title']}! A thrilling fantasy adventure awaits."
        elif any(k in title_lower for k in ['comedy', 'life', 'school', 'family', 'spy']):
            genres_text = "Comedy • Slice of Life • Drama"
            description = f"Get ready for laughs and heartwarming moments with {anime['title']}!"
        else:
            genres_text = "Action • Adventure • Drama"
            description = f"Watch the amazing story of {anime['title']}. An unforgettable journey awaits."

        related_anime = get_random_anime(base_id, count=6)
        
        return render_template('watch.html', anime=anime, seasons=seasons, current_season=current_season, 
                               episodes=episodes, current_ep=current_ep, prev_ep=prev_ep_num, next_ep=next_ep_num, 
                               related_anime=related_anime, genres_text=genres_text, description=description)

    @app.errorhandler(404)
    def page_not_found(e): return render_template('404.html'), 404

    return app