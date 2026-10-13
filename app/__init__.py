from flask import Flask, render_template, abort, request, redirect, url_for, session, jsonify
import random
import json
import os
import secrets
from datetime import timedelta
from config import Config
from .services.db_manager import (get_all_anime, get_anime_by_id, search_anime,
                                  get_random_anime, get_featured_anime,
                                  get_anime_by_genre, get_single_random_anime,
                                  get_top_anime, get_hero_anime_list)
from flask_dance.contrib.google import make_google_blueprint, google
from scraper.smart_scraper import (fetch_movie_video_with_playwright, fetch_page, 
                                   parse_video_link, parse_post_id, fetch_season_ajax, 
                                   parse_season_ajax)

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    remember_token = db.Column(db.String(200), nullable=True) # 🛠️ परमानेंट लॉगिन के लिए

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.secret_key = app.config['SECRET_KEY']

    # 🛠️ PostgreSQL डेटाबेस (Render पर) और SQLite (लोकल पर)
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 🛠️ सेशन को 10 साल का बनाओ (Crunchyroll Style)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650)
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    db.init_app(app)

    with app.app_context():
        db.create_all()
        # 🛠️ FIX: अगर पुराने टेबल में remember_token कॉलम नहीं है, तो उसे जोड़ो
        try:
            db.session.execute(db.text('ALTER TABLE user ADD COLUMN remember_token VARCHAR(200)'))
            db.session.commit()
            print("✅ remember_token कॉलम जोड़ दिया गया।")
        except Exception:
            db.session.rollback() 

    google_bp = make_google_blueprint(
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        scope=["openid", "email", "profile"],
        redirect_url="/login"
    )
    app.register_blueprint(google_bp, url_prefix="/login")

    # 🛠️ ऑटो-लॉगिन (हर बार पेज लोड होने से पहले चेक करेगा)
    @app.before_request
    def auto_login():
        if not session.get('user_email'):
            token = request.cookies.get('remember_token')
            if token:
                user = User.query.filter_by(remember_token=token).first()
                if user:
                    session['user_email'] = user.email
                    session['user_name'] = user.name
                    session['user_pic'] = f"https://ui-avatars.com/api/?name={user.name}&background=a371f7&color=fff"
                    session.permanent = True

    @app.route('/login')
    def login():
        if session.get('user_email'):
            session.permanent = True
            return redirect(url_for('home'))
        if not google.authorized:
            return render_template('login.html')
        try:
            resp = google.get("/oauth2/v2/userinfo")
            if resp.ok:
                user_info = resp.json()
                session['user_email'] = user_info['email']
                session['user_name'] = user_info.get('name', 'User')
                session['user_pic'] = user_info.get('picture', '')
                session.permanent = True
                return redirect(url_for('home'))
            else:
                session.clear()
                return render_template('login.html')
        except Exception as e:
            print(f"Error: {e}")
            session.clear()
            return render_template('login.html')

    @app.route('/login/google')
    def login_google():
        if not google.authorized:
            return redirect(url_for("google.login"))
        return redirect(url_for('login'))

    @app.route('/login/email', methods=['POST'])
    def login_email():
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember')
        
        print(f"🔍 Login attempt: {email}")
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_email'] = user.email
            session['user_name'] = user.name
            session['user_pic'] = f"https://ui-avatars.com/api/?name={user.name}&background=a371f7&color=fff"
            session.permanent = True
            
            response = redirect(url_for('home'))
            if remember:
                token = secrets.token_urlsafe(64)
                user.remember_token = token
                db.session.commit()
                # 🛠️ 10 साल की कुकी सेट करो
                response.set_cookie('remember_token', token, max_age=3650*24*60*60, httponly=True, secure=True, samesite='Lax')
            
            response.set_cookie('saved_email', email, max_age=3650*24*60*60)
            print(f"✅ Login successful: {email}")
            return response
        else:
            print(f"❌ Login failed for: {email}")
            return render_template('login.html', error="गलत ईमेल या पासवर्ड!")

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                return render_template('signup.html', error="यह ईमेल पहले से रजिस्टर्ड है!")
            
            new_user = User(
                name=name,
                email=email,
                password_hash=generate_password_hash(password)
            )
            db.session.add(new_user)
            db.session.commit()
            print(f"✅ New user created: {email}")
            return redirect(url_for('login'))
        return render_template('signup.html')

    @app.route('/guest')
    def guest_login():
        session['user_email'] = 'guest@animenest.com'
        session['user_name'] = 'Guest'
        session['user_pic'] = 'https://ui-avatars.com/api/?name=Guest&background=ff4d4d&color=fff'
        session.permanent = True
        return redirect(url_for('home'))

    @app.route('/logout')
    def logout():
        token = request.cookies.get('remember_token')
        if token:
            user = User.query.filter_by(remember_token=token).first()
            if user:
                user.remember_token = None
                db.session.commit()
        
        session.clear()
        session.pop('google_token', None)
        session.pop('google_oauth_token', None)
        
        resp = redirect(url_for('login'))
        resp.set_cookie('remember_token', '', expires=0)
        resp.set_cookie('saved_email', '', expires=0)
        return resp

    def get_filtered_anime():
        all_anime = get_all_anime()
        cartoon_keywords = ['ben 10', 'doraemon', 'shinchan', 'tom and jerry', 'pokemon', 'beyblade', 'barbie', 'spiderman', 'batman', 'superman', 'cartoon', 'looney tunes', 'oggy', 'motu patlu', 'chhota bheem', 'ninja hattori', 'perman', 'shin chan']
        action_keywords = ['demon slayer', 'jujutsu kaisen', 'one punch man', 'attack on titan', 'solo leveling', 'naruto', 'one piece', 'black clover', 'my hero academia', 'hunter x hunter', 'bleach', 'dragon ball', 'chainsaw man', 'tokyo revengers', 'kaiju no. 8', 'dan da dan', 'vinland saga', 'mob psycho']
        comedy_keywords = ['spy x family', 'grand blue', 'kaguya', 'komi', 'nichijou', 'gintama', 'konosuba', 'daily life', 'horimiya', 'fruits basket', 'science fell in love', 'my dress-up darling', 'toradora', 'love is war', 'a couple of cuckoos', 'kanojo', 'lovely complex']
        fantasy_keywords = ['reincarnated', 'isekai', 'mushoku tensei', 'that time i got', 'overlord', 'slime', 're:zero', 'sword art online', 'fate', 'immortal king', 'daily life of the immortal', 'frontier lord', 'wistoria', 'frieren', 'dungeon', 'black torch', 'holy grail']
        romance_keywords = ['horimiya', 'kaguya', 'toradora', 'love is war', 'rent-a-girlfriend', 'my dress-up darling', 'fruits basket', 'your name', 'weathering with you', 'a silent voice', 'i want to eat your pancreas', 'garden of words', 'tomo-chan', 'uzaki', 'quintessential', 'science fell in love', 'a couple of cuckoos', 'kanojo', 'lovely complex']

        movies_list = [a for a in all_anime if not a.get('episodes') or len(a.get('episodes', [])) == 0]
        series_list = [a for a in all_anime if a.get('episodes') and len(a.get('episodes', [])) > 0]
        cartoons_list = [a for a in all_anime if any(k in a['title'].lower() for k in cartoon_keywords)]
        action = [a for a in all_anime if any(k in a['title'].lower() for k in action_keywords)]
        comedy = [a for a in all_anime if any(k in a['title'].lower() for k in comedy_keywords)]
        fantasy = [a for a in all_anime if any(k in a['title'].lower() for k in fantasy_keywords)]
        romance = [a for a in all_anime if any(k in a['title'].lower() for k in romance_keywords)]
        
        trending = series_list 
        popular = sorted(all_anime, key=lambda x: len(x.get('episodes', [])), reverse=True)
        
        return all_anime, trending, popular, movies_list, series_list, cartoons_list, action, comedy, fantasy, romance

    @app.route('/')
    def home():
        if not session.get('user_email'):
            return render_template('login.html')
        all_anime, trending, popular, movies_list, series_list, cartoons_list, action, comedy, fantasy, romance = get_filtered_anime()
        hero_anime_list = get_hero_anime_list(5)
        return render_template('index.html', anime_list=all_anime, trending=trending, popular=popular, movies=movies_list, cartoons=cartoons_list, series=series_list, hero_anime_list=hero_anime_list, action=action, comedy=comedy, fantasy=fantasy, romance=romance, page_title="Home")

    @app.route('/trending')
    def trending_page():
        if not session.get('user_email'): return render_template('login.html')
        _, trending, _, _, _, _, _, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=trending, page_title="Trending Anime")

    @app.route('/popular')
    def popular_page():
        if not session.get('user_email'): return render_template('login.html')
        _, _, popular, _, _, _, _, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=popular, page_title="Popular Anime")

    @app.route('/movies')
    def movies_page():
        if not session.get('user_email'): return render_template('login.html')
        _, _, _, movies_list, _, _, _, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=movies_list, page_title="Anime Movies")

    @app.route('/cartoons')
    def cartoons_page():
        if not session.get('user_email'): return render_template('login.html')
        _, _, _, _, _, cartoons_list, _, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=cartoons_list, page_title="Cartoons")

    @app.route('/series')
    def series_page():
        if not session.get('user_email'): return render_template('login.html')
        _, _, _, _, series_list, _, _, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=series_list, page_title="Anime Series")

    @app.route('/top-rated')
    def top_rated_page():
        if not session.get('user_email'): return render_template('login.html')
        all_anime, _, _, _, _, _, _, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=all_anime, page_title="Top Rated")

    @app.route('/categories')
    def categories_page():
        if not session.get('user_email'): return render_template('login.html')
        all_anime, _, _, _, _, _, _, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=all_anime, page_title="All Categories")

    @app.route('/profile')
    def profile():
        if not session.get('user_email'): return render_template('login.html')
        return render_template('profile.html')

    @app.route('/search')
    def search():
        if not session.get('user_email'): return render_template('login.html')
        query = request.args.get('q', '')
        anime_list = search_anime(query) if query else get_all_anime()
        return render_template('index.html', anime_list=anime_list, search_query=query, page_title=f"Search: {query}")

    @app.route('/genre/<genre_name>')
    def genre(genre_name):
        if not session.get('user_email'): return render_template('login.html')
        anime_list = get_anime_by_genre(genre_name)
        return render_template('index.html', anime_list=anime_list, search_query=genre_name, page_title=f"Genre: {genre_name}")

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

    @app.route('/watch/<anime_id>')
    @app.route('/watch/<anime_id>/<int:season_number>')
    @app.route('/watch/<anime_id>/<int:season_number>/<int:ep_number>')
    def watch(anime_id, season_number=1, ep_number=None):
        if not session.get('user_email'): return render_template('login.html')
        anime = get_anime_by_id(anime_id)
        if not anime: abort(404)

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
                for i, ep in enumerate(episodes):
                    if f"Episode {ep_number}" in ep.get('title', ''):
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
        if any(k in title_lower for k in ['slayer', 'jujutsu', 'naruto', 'piece', 'leveling', 'titan', 'hunter', 'hero']):
            genres_text = "Action • Adventure • Fantasy"
            description = f"Dive into the epic world of {anime['title']}! Follow the thrilling journey of powerful characters."
        elif any(k in title_lower for k in ['love', 'romance', 'couple', 'girlfriend', 'kaguya']):
            genres_text = "Romance • Comedy • Drama"
            description = f"Experience the heartwarming tale of {anime['title']}. A beautiful story of love, friendship, and emotions."
        elif any(k in title_lower for k in ['reincarnated', 'isekai', 'magic', 'dungeon', 'king']):
            genres_text = "Fantasy • Isekai • Adventure"
            description = f"Step into the magical world of {anime['title']}! A thrilling fantasy adventure filled with magic and monsters."
        elif any(k in title_lower for k in ['comedy', 'life', 'school', 'family', 'spy']):
            genres_text = "Comedy • Slice of Life • Drama"
            description = f"Get ready for laughs and heartwarming moments with {anime['title']}! A delightful story filled with humor."
        else:
            genres_text = "Action • Adventure • Drama"
            description = f"Watch the amazing story of {anime['title']}. An unforgettable journey filled with action, emotion, and incredible characters!"

        related_anime = get_random_anime(anime_id, count=4)

        return render_template('watch.html', anime=anime, seasons=seasons, current_season=current_season,
                               episodes=episodes, current_ep=current_ep, prev_ep=prev_ep_num, next_ep=next_ep_num,
                               related_anime=related_anime, genres_text=genres_text, description=description)

    @app.route('/api/get-video/<anime_id>/<int:season_num>/<int:ep_num>')
    def get_video_api(anime_id, season_num, ep_num):
        anime = get_anime_by_id(anime_id)
        if not anime:
            return jsonify({"video_url": ""})
        
        if anime.get('episodes') and len(anime['episodes']) > 0 and anime['episodes'][0].get('title') == 'Full Movie':
            fresh_link = fetch_movie_video_with_playwright(anime['url'])
            return jsonify({"video_url": fresh_link})
        else:
            if not anime.get('seasons'):
                return jsonify({"video_url": ""})
            current_season = next((s for s in anime['seasons'] if s['season_number'] == season_num), None)
            if not current_season:
                return jsonify({"video_url": ""})
            current_ep = next((e for e in current_season['episodes'] if str(e.get('ep_num')) == str(ep_num)), None)
            if not current_ep:
                return jsonify({"video_url": ""})
            ep_html = fetch_page(current_ep['url'])
            if ep_html:
                video_url = parse_video_link(ep_html, current_ep['url'])
                return jsonify({"video_url": video_url})
        return jsonify({"video_url": ""})

    @app.errorhandler(404)
    def page_not_found(e): return render_template('404.html'), 404

    return app