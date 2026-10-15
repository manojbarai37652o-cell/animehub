from flask import Flask, render_template, abort, request, redirect, url_for, session
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
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    remember_token = db.Column(db.String(200), nullable=True)

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
            session.permanent = True
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
        resp = redirect(url_for('login'))
        resp.set_cookie('remember_token', '', expires=0)
        resp.set_cookie('saved_email', '', expires=0)
        return resp

    # =========================================================
    # 🟢 FIXED: YAHAN HAI ASLI FILTERING LOGIC 🟢
    # =========================================================
    def get_filtered_anime():
        all_anime = get_all_anime()
        
        # 1. Cartoon Keywords (In titles mein ye words honge to wo Cartoon hain)
        cartoon_keywords = ['ben 10', 'doraemon', 'shinchan', 'tom and jerry', 'pokemon', 'beyblade', 'barbie', 'spiderman', 'batman']
        
        # 2. Movies List (Sirf wo anime jinka pehla episode 'Full Movie' hai)
        movies_list = [a for a in all_anime if a.get('episodes') and len(a['episodes']) > 0 and a['episodes'][0].get('title') == 'Full Movie']
        
        # 3. Cartoons List (Jinke title mein cartoon_keywords hain)
        cartoons_list = [a for a in all_anime if any(k in a['title'].lower() for k in cartoon_keywords)]
        
        # 4. Series List (Bache hue saare anime jo na Movie hain, na Cartoon)
        series_list = [a for a in all_anime if a not in movies_list and a not in cartoons_list]
        
        # 5. Trending (Top 12 Series - Rating ke hisaab se)
        trending = sorted(series_list, key=lambda x: float(x.get('rating', 0) or 0), reverse=True)[:12]
        
        # 6. Popular (Top 12 Series - Episodes ki sankhya ke hisaab se)
        popular = sorted(series_list, key=lambda x: len(x.get('episodes', [])), reverse=True)[:12]
        
        # Debugging ke liye print (Render logs me dikhega)
        print(f"Total Anime: {len(all_anime)}, Series: {len(series_list)}, Movies: {len(movies_list)}, Cartoons: {len(cartoons_list)}")
        
        return all_anime, trending, popular, movies_list, series_list, cartoons_list
    # =========================================================

    @app.route('/')
    def home():
        if not session.get('user_email'): return render_template('login.html')
        all_anime, trending, popular, movies_list, series_list, cartoons_list = get_filtered_anime()
        hero_anime_list = get_hero_anime_list(5)
        return render_template('index.html', anime_list=all_anime, trending=trending, popular=popular, movies=movies_list, cartoons=cartoons_list, hero_anime_list=hero_anime_list, page_title='Home')

    @app.route('/trending')
    def trending_page():
        if not session.get('user_email'): return render_template('login.html')
        _, trending, _, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=trending, page_title="Trending Anime")

    @app.route('/movies')
    def movies_page():
        if not session.get('user_email'): return render_template('login.html')
        _, _, _, movies_list, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=movies_list, page_title="Anime Movies")

    @app.route('/cartoons')
    def cartoons_page():
        if not session.get('user_email'): return render_template('login.html')
        _, _, _, _, _, cartoons_list = get_filtered_anime()
        return render_template('index.html', anime_list=cartoons_list, page_title="Cartoons")

    @app.route('/categories')
    def categories_page():
        if not session.get('user_email'): return render_template('login.html')
        all_anime, _, _, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=all_anime, page_title="All Categories")

    @app.route('/top-rated')
    def top_rated_page():
        if not session.get('user_email'): return render_template('login.html')
        all_anime, _, _, _, _, _ = get_filtered_anime()
        return render_template('index.html', anime_list=all_anime, page_title="Top Rated")

    # 🔠 A-Z Browse Route
    @app.route('/az/<letter>')
    def az_page(letter):
        if not session.get('user_email'): return render_template('login.html')
        letter = letter.upper()
        all_anime = get_all_anime()
        filtered = [a for a in all_anime if a['title'].upper().startswith(letter)]
        filtered.sort(key=lambda x: x['title'].lower())
        return render_template('index.html', anime_list=filtered, page_title=f"Anime starting with '{letter}'")

    @app.route('/profile')
    def profile():
        if not session.get('user_email'): return render_template('login.html')
        return render_template('profile.html')

    @app.route('/search')
    def search():
        if not session.get('user_email'): return render_template('login.html')
        query = request.args.get('q', '')
        anime_list = search_anime(query) if query else get_all_anime()
        return render_template('index.html', anime_list=anime_list, search_query=query, page_title=f"Search Results")

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