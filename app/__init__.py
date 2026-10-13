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
from playwright.sync_api import sync_playwright

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    remember_token = db.Column(db.String(200), nullable=True)

# 🛠️ m3u8 लिंक के लिए कैश (30 मिनट तक सेव रहेगा)
video_cache = {}

def get_fresh_video_url(episode_url):
    """Playwright से लाइव m3u8 लिंक निकालता है (कैश के साथ)"""
    import time
    # कैश चेक करो
    if episode_url in video_cache:
        cached = video_cache[episode_url]
        if time.time() - cached['timestamp'] < 1800: # 30 मिनट
            print(f"✅ Using cached URL for {episode_url[:50]}")
            return cached['url']
    
    print(f"🔍 Playwright started for: {episode_url[:60]}")
    found_video = ""
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-ipv6"])
            page = browser.new_page()
            
            def handle_response(response):
                nonlocal found_video
                if '.m3u8' in response.url and not found_video:
                    found_video = response.url
            
            page.on('response', handle_response)
            page.goto(episode_url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(15000)
            
            # अगर m3u8 नहीं मिला, तो iframe के अंदर जाकर देखो
            if not found_video:
                iframes = page.query_selector_all('iframe')
                for iframe in iframes:
                    src = iframe.get_attribute('src')
                    if src:
                        if src.startswith('//'): src = 'https:' + src
                        if 'ravok' in src or 'video' in src.lower() or 'player' in src.lower():
                            try:
                                inner = browser.new_page()
                                inner.on('response', handle_response)
                                inner.goto(src, timeout=30000, wait_until="domcontentloaded")
                                inner.wait_for_timeout(15000)
                                inner.close()
                            except: pass
                    if found_video: break
            
            # अगर अभी भी नहीं मिला, तो HTML में ढूंढो
            if not found_video:
                content = page.content()
                import re
                match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', content)
                if match: found_video = match.group(1)
            
            browser.close()
    except Exception as e:
        print(f"❌ Playwright Error: {e}")
    
    print(f"🔍 Final found_video: {found_video[:80] if found_video else 'NONE'}")
    
    # कैश में सेव करो
    if found_video:
        video_cache[episode_url] = {'url': found_video, 'timestamp': time.time()}
    
    return found_video


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
        except: db.session.rollback()

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
                response.set_cookie('remember_token', token, max_age=3650*24*60*60, httponly=True, secure=True, samesite='Lax')
            response.set_cookie('saved_email', email, max_age=3650*24*60*60)
            return response
        else:
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

    def get_filtered_anime():
        all_anime = get_all_anime()
        cartoon_keywords = ['ben 10', 'doraemon', 'shinchan', 'tom and jerry', 'pokemon', 'beyblade', 'barbie', 'spiderman', 'batman', 'superman', 'cartoon', 'looney tunes', 'oggy', 'motu patlu', 'chhota bheem', 'ninja hattori', 'perman', 'shin chan']
        movies_list = [a for a in all_anime if not a.get('episodes') or len(a.get('episodes', [])) == 0]
        series_list = [a for a in all_anime if a.get('episodes') and len(a.get('episodes', [])) > 0]
        cartoons_list = [a for a in all_anime if any(k in a['title'].lower() for k in cartoon_keywords)]
        trending = series_list 
        popular = sorted(all_anime, key=lambda x: len(x.get('episodes', [])), reverse=True)
        return all_anime, trending, popular, movies_list, series_list, cartoons_list

    @app.route('/')
    def home():
        if not session.get('user_email'): return render_template('login.html')
        all_anime, trending, popular, movies_list, series_list, cartoons_list = get_filtered_anime()
        hero_anime_list = get_hero_anime_list(5)
        return render_template('index.html', anime_list=all_anime, trending=trending, popular=popular, movies=movies_list, cartoons=cartoons_list, hero_anime_list=hero_anime_list, page_title="Home")

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
        elif any(k in title_lower for k in ['love', 'romance', 'couple', 'girlfriend', 'kaguya']):
            genres_text = "Romance • Comedy • Drama"
        elif any(k in title_lower for k in ['reincarnated', 'isekai', 'magic', 'dungeon', 'king']):
            genres_text = "Fantasy • Isekai • Adventure"
        elif any(k in title_lower for k in ['comedy', 'life', 'school', 'family', 'spy']):
            genres_text = "Comedy • Slice of Life • Drama"
        else:
            genres_text = "Action • Adventure • Drama"
        
        description = f"Watch the amazing story of {anime['title']}. An unforgettable journey filled with action, emotion, and incredible characters!"
        related_anime = get_random_anime(anime_id, count=4)

        return render_template('watch.html', anime=anime, seasons=seasons, current_season=current_season,
                               episodes=episodes, current_ep=current_ep, prev_ep=prev_ep_num, next_ep=next_ep_num,
                               related_anime=related_anime, genres_text=genres_text, description=description)

    # 🛠️ नया API: लाइव m3u8 लिंक निकालेगा
    @app.route('/api/get-video/<anime_id>/<int:season_num>/<int:ep_num>')
    def get_video_api(anime_id, season_num, ep_num):
        print(f"🔥 API HIT: {anime_id} S{season_num}E{ep_num}")
        anime = get_anime_by_id(anime_id)
        if not anime: return jsonify({"video_url": ""})
        
        episode_url = ""
        for season in anime.get('seasons', []):
            if season['season_number'] == season_num:
                for ep in season['episodes']:
                    title = ep.get('title', '')
                    if f"Episode {ep_num}" in title or str(ep_num) in title:
                        episode_url = ep.get('url', '')
                        break
                break
        
        if not episode_url:
            print(f"❌ Episode URL not found for S{season_num}E{ep_num}")
            return jsonify({"video_url": ""})
        
        print(f"🔗 Episode URL found: {episode_url[:60]}")
        fresh_url = get_fresh_video_url(episode_url)
        return jsonify({"video_url": fresh_url})

    @app.errorhandler(404)
    def page_not_found(e): return render_template('404.html'), 404

    return app