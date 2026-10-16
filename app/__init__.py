from flask import Flask, render_template, abort, request, redirect, url_for, session, jsonify, flash
import random
import json
import os
import re
import secrets
from datetime import timedelta, datetime
from config import Config
from .services.db_manager import (get_all_anime, get_anime_by_id, search_anime,
                                   get_random_anime, get_featured_anime,
                                   get_anime_by_genre, get_single_random_anime,
                                   get_top_anime, get_hero_anime_list)
from flask_dance.contrib.google import make_google_blueprint, google
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    remember_token = db.Column(db.String(200), nullable=True)

PROGRESS_FILE = 'database/progress.json'

def load_progress():
    if not os.path.exists(PROGRESS_FILE):
        return {}
    try:
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_progress_data(data):
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.secret_key = app.config['SECRET_KEY']
    
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650)
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        try:
            db.session.execute(db.text('ALTER TABLE user ADD COLUMN remember_token VARCHAR(200)'))
            db.session.commit()
        except Exception:
            db.session.rollback()
            
    google_bp = make_google_blueprint(
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        scope=["openid", "email", "profile"],
        redirect_url="/login"
    )
    app.register_blueprint(google_bp, url_prefix="/login")

    @app.before_request
    def auto_login():
        if not session.get('user_email'):
            token = request.cookies.get('remember_token')
            if token:
                user = User.query.filter_by(remember_token=token).first()
                if user:
                    session['user_email'] = user.email
                    session['user_name'] = user.name
                    session['user_pic'] = f"https://ui-avatars.com/api/?name={user.name}&background=random"
                    session.permanent = True

    @app.route('/login')
    def login():
        if session.get('user_email'):
            return redirect(url_for('home'))
        if not google.authorized:
            return render_template('login.html')
        try:
            resp = google.get('/oauth2/v2/userinfo')
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
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_email'] = user.email
            session['user_name'] = user.name
            session['user_pic'] = f"https://ui-avatars.com/api/?name={user.name}&background=random"
            session.permanent = True
            response = redirect(url_for('home'))
            if remember:
                token = secrets.token_urlsafe(64)
                user.remember_token = token
                db.session.commit()
                response.set_cookie('remember_token', token, max_age=3650*24*60*60, httponly=True)
                response.set_cookie('saved_email', email, max_age=3650*24*60*60)
            return response
        else:
            return render_template('login.html', error="गलत ईमेल या पासवर्ड")

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                return render_template('signup.html', error="यह ईमेल पहले से रजिस्टर्ड है")
            new_user = User(name=name, email=email, password_hash=generate_password_hash(password))
            db.session.add(new_user)
            db.session.commit()
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
        resp = redirect(url_for('home'))
        resp.set_cookie('remember_token', '', expires=0)
        resp.set_cookie('saved_email', '', expires=0)
        return resp

    def get_filtered_anime():
        all_anime = get_all_anime()
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
            popular = sorted(all_anime, key=lambda x: len(x.get('episodes', [])), reverse=True)[:10]
            top_rated = sorted(all_anime, key=lambda x: float(x.get('rating', 0) or 0), reverse=True)[:10]
            trending_searches = [a['title'] for a in popular[:6]] 
            return dict(
                popular_anime_overlay=popular, 
                top_rated_anime_overlay=top_rated,
                trending_searches=trending_searches
            )
        except:
            return dict(popular_anime_overlay=[], top_rated_anime_overlay=[], trending_searches=[])

    @app.route('/api/save_progress', methods=['POST'])
    def api_save_progress():
        if not session.get('user_email'): return jsonify({"status": "error", "message": "Not logged in"}), 401
        
        data = request.json
        user_email = session['user_email']
        
        progress_db = load_progress()
        if user_email not in progress_db:
            progress_db[user_email] = {}
            
        anime_id = str(data.get('anime_id'))
        progress_db[user_email][anime_id] = {
            "season": data.get('season', 1),
            "episode": data.get('episode', 1),
            "timestamp": data.get('timestamp', 0),
            "duration": data.get('duration', 0),
            "updated_at": datetime.now().isoformat()
        }
        
        save_progress_data(progress_db)
        return jsonify({"status": "success"})

    @app.route('/continue-watching')
    def continue_watching_page():
        if not session.get('user_email'): return render_template('login.html')
        
        user_email = session['user_email']
        progress_db = load_progress()
        user_progress = progress_db.get(user_email, {})
        
        continue_list = []
        for anime_id, data in user_progress.items():
            anime_details = get_anime_by_id(anime_id)
            if anime_details:
                duration = data.get('duration', 1)
                timestamp = data.get('timestamp', 0)
                percent = int((timestamp / duration) * 100) if duration > 0 else 0
                
                anime_details['resume_data'] = {
                    'season': data.get('season', 1),
                    'episode': data.get('episode', 1),
                    'percent': min(percent, 100),
                    'timestamp': timestamp
                }
                continue_list.append(anime_details)
                
        continue_list.sort(key=lambda x: user_progress[str(x['id'])].get('updated_at', ''), reverse=True)
        
        return render_template('continue_watching.html', anime_list=continue_list, page_title="Continue Watching")

    # =========================================================
    # 🟢 PUBLIC ROUTES (अब लॉगिन की जरूरत नहीं) 🟢
    # =========================================================
    @app.route('/')
    def home():
        all_anime, trending_full, popular_full, movies_full, series_full, cartoons_full = get_filtered_anime()
        trending = random.sample(trending_full[:50], min(len(trending_full[:50]), 12)) if trending_full else []
        popular = random.sample(popular_full[:50], min(len(popular_full[:50]), 12)) if popular_full else []
        random.shuffle(movies_full)
        movies = movies_full[:12]
        random.shuffle(cartoons_full)
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
        all_anime = get_all_anime()
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

    @app.route('/watch/<anime_id>')
    @app.route('/watch/<anime_id>/<int:season_number>')
    @app.route('/watch/<anime_id>/<int:season_number>/<ep_number>')
    def watch(anime_id, season_number=1, ep_number=None):
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

    # =========================================================
    # 🟢 PROTECTED ROUTES (लॉगिन जरूरी है) 🟢
    # =========================================================
    @app.route('/profile')
    def profile():
        if not session.get('user_email'): return render_template('login.html')
        return render_template('profile.html')

    @app.route('/settings/account')
    def settings_account():
        if not session.get('user_email'): return render_template('login.html')
        return render_template('settings.html', page_title='Account Information')

    @app.route('/settings/playback')
    def settings_playback():
        if not session.get('user_email'): return render_template('login.html')
        return render_template('settings.html', page_title='Playback Settings')

    @app.route('/settings/update_profile', methods=['POST'])
    def update_profile():
        if not session.get('user_email'): return redirect(url_for('login'))
        new_name = request.form.get('name')
        user = User.query.filter_by(email=session['user_email']).first()
        if user and new_name:
            user.name = new_name
            session['user_name'] = new_name
            db.session.commit()
            flash('प्रोफाइल नाम सफलतापूर्वक अपडेट हो गया!', 'success')
        return redirect(url_for('settings_account'))

    @app.route('/settings/update_password', methods=['POST'])
    def update_password():
        if not session.get('user_email'): return redirect(url_for('login'))
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        user = User.query.filter_by(email=session['user_email']).first()
        
        if user and check_password_hash(user.password_hash, current_password):
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('पासवर्ड सफलतापूर्वक बदल दिया गया!', 'success')
        else:
            flash('गलत पुराना पासवर्ड! कृपया पुनः प्रयास करें।', 'error')
        return redirect(url_for('settings_account'))

    @app.route('/watchlist')
    def watchlist():
        if not session.get('user_email'): return render_template('login.html')
        return render_template('watchlist.html')

    @app.errorhandler(404)
    def page_not_found(e): return render_template('404.html'), 404

    return app