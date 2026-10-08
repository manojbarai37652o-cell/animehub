from flask import Flask, render_template, abort, request, redirect, url_for, session
import random
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

    # Google OAuth Setup
    google_bp = make_google_blueprint(
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        scope=["openid", "email", "profile"],
        redirect_url="/login"
    )
    app.register_blueprint(google_bp, url_prefix="/login")

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
        session['user_pic'] = 'https://ui-avatars.com/api/?name=Guest'
        return redirect(url_for('home'))

    @app.route('/logout')
    def logout():
        session.clear()
        session.pop('google_token', None)
        session.pop('google_oauth_token', None)
        return redirect(url_for('home'))

    @app.route('/')
    def home():
        if not session.get('user_email'):
            return render_template('login.html')

        all_anime = get_all_anime()
        trending = random.sample(all_anime, min(15, len(all_anime))) if len(all_anime) > 15 else all_anime
        popular = sorted(all_anime, key=lambda x: len(x.get('episodes', [])), reverse=True)[:15]

        # Keywords for Genre Classification
        action_keywords = ['demon slayer', 'jujutsu kaisen', 'one punch man', 'attack on titan', 'solo leveling', 'naruto', 'one piece', 'black clover', 'my hero academia', 'hunter x hunter', 'bleach', 'dragon ball', 'chainsaw man', 'tokyo revengers']
        comedy_keywords = ['spy x family', 'grand blue', 'kaguya', 'komi', 'nichijou', 'gintama', 'konosuba', 'daily life', 'horimiya', 'fruits basket', 'science fell in love', 'my dress-up darling', 'toradora', 'love is war']
        fantasy_keywords = ['reincarnated', 'isekai', 'mushoku tensei', 'that time i got', 'overlord', 'slime', 're:zero', 'sword art online', 'fate', 'immortal king', 'daily life of the immortal', 'frontier lord', 'aristoria', 'friren', 'dungeon', 'black torch', 'holy grail']
        romance_keywords = ['horimiya', 'kaguya', 'toradora', 'love is war', 'rent-a-girlfriend', 'my dress-up darling', 'fruits basket', 'your name', 'weathering with you', 'a silent voice', 'i want to eat your pancreas', 'garden of words', 'tomo-chan', 'uzaki', 'quintessential', 'science fell in love']

        action = [a for a in all_anime if any(k in a['title'].lower() for k in action_keywords)][:15]
        comedy = [a for a in all_anime if any(k in a['title'].lower() for k in comedy_keywords)][:15]
        fantasy = [a for a in all_anime if any(k in a['title'].lower() for k in fantasy_keywords)][:15]
        romance = [a for a in all_anime if any(k in a['title'].lower() for k in romance_keywords)][:15]

        hero_anime_list = get_hero_anime_list(5)
        current_genre = request.args.get('genre', 'Popular')

        if current_genre == 'Action': display_list = action
        elif current_genre == 'Comedy': display_list = comedy
        elif current_genre == 'Fantasy': display_list = fantasy
        elif current_genre == 'Romance': display_list = romance
        else: display_list = trending

        return render_template('index.html', 
                               anime_list=all_anime, 
                               hero_anime_list=hero_anime_list, 
                               trending=display_list, 
                               popular=popular, 
                               current_genre=current_genre)

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
        return render_template('search.html', anime_list=anime_list, search_query=query)

    @app.route('/genre/<genre_name>')
    def genre(genre_name):
        if not session.get('user_email'): return render_template('login.html')
        anime_list = get_anime_by_genre(genre_name)
        return render_template('index.html', anime_list=anime_list, search_query=genre_name)

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

    # --- WATCH ROUTE (Master Fix for ToonStream) ---
    @app.route('/watch/<anime_id>')
    @app.route('/watch/<anime_id>/<int:season_number>')
    @app.route('/watch/<anime_id>/<int:season_number>/<int:ep_number>')
    def watch(anime_id, season_number=1, ep_number=None):
        if not session.get('user_email'): return render_template('login.html')
        
        anime = get_anime_by_id(anime_id)
        if not anime: abort(404)

        # 1. Seasons Data Handling (ToonStream Data Structure)
        seasons = anime.get('seasons', [])
        if not seasons:
            episodes_fallback = anime.get('episodes', [])
            if episodes_fallback:
                seasons = [{"season_number": 1, "episodes": episodes_fallback}]
            else:
                seasons = []

        current_season = next((s for s in seasons if s.get('season_number') == season_number), None)
        if not current_season and seasons:
            current_season = seasons[0]
            season_number = current_season.get('season_number', 1)

        # 2. Get Episodes for the current season
        episodes = current_season.get('episodes', []) if current_season else []

        # 3. Current Episode Handling
        current_ep = None
        current_index = 0
        if episodes:
            if ep_number is None:
                current_ep = episodes[0]
                current_index = 0
            else:
                for i, ep in enumerate(episodes):
                    ep_title = str(ep.get('title', ''))
                    if str(ep_number) in ep_title:
                        current_ep = ep
                        current_index = i
                        break
                if not current_ep:
                    current_ep = episodes[0]
                    current_index = 0

        # 4. Prev/Next Episode Handling
        prev_ep_num, next_ep_num = None, None
        if episodes and current_ep:
            if current_index > 0:
                prev_match = str(episodes[current_index - 1].get('title', '')).split(' ')[-1]
                if prev_match.isdigit(): prev_ep_num = int(prev_match)
            
            if current_index < len(episodes) - 1:
                next_match = str(episodes[current_index + 1].get('title', '')).split(' ')[-1]
                if next_match.isdigit(): next_ep_num = int(next_match)

        # 5. Safe Genres and Description Generation (English)
        title_lower = anime.get('title', '').lower()
        if any(k in title_lower for k in ['slayer', 'jujutsu', 'naruto', 'piece', 'hunter', 'titan']):
            genres_text = "Action • Adventure • Fantasy"
            description = f"Dive into the epic world of {anime.get('title', 'Unknown')}! Follow the thrilling journey of powerful characters."
        elif any(k in title_lower for k in ['love', 'romance', 'couple', 'girlfriend', 'kaguya']):
            genres_text = "Romance • Comedy • Drama"
            description = f"Experience the heartwarming tale of {anime.get('title', 'Unknown')}. A beautiful story of love and laughter."
        elif any(k in title_lower for k in ['reincarnated', 'isekai', 'magic', 'dungeon', 'fantasy']):
            genres_text = "Fantasy • Isekai • Adventure"
            description = f"Step into the magical world of {anime.get('title', 'Unknown')}! A thrilling fantasy adventure awaits."
        elif any(k in title_lower for k in ['comedy', 'life', 'school', 'family', 'spy']):
            genres_text = "Comedy • Slice of Life • Drama"
            description = f"Get ready for laughs and heartwarming moments with {anime.get('title', 'Unknown')}."
        else:
            genres_text = "Action • Adventure • Drama"
            description = f"Watch the amazing story of {anime.get('title', 'Unknown')}. An unforgettable journey awaits."

        related_anime = get_random_anime(anime_id, count=6)

        # ✅ सुरक्षा कवच: अगर current_ep None है, तो उसे खाली डिक्शनरी बना दो
        current_ep = current_ep or {}

        return render_template('watch.html', 
                               anime=anime, 
                               seasons=seasons, 
                               current_season=current_season, 
                               episodes=episodes, 
                               current_ep=current_ep, 
                               prev_ep=prev_ep_num, 
                               next_ep=next_ep_num, 
                               related_anime=related_anime, 
                               genres_text=genres_text, 
                               description=description)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    return app