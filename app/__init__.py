from flask import Flask, render_template, abort, request, redirect, url_for, session
from config import Config
from .services.db_manager import (get_all_anime, get_anime_by_id, search_anime, 
                                   get_paginated_anime, get_random_anime, 
                                   get_featured_anime, get_anime_by_genre, 
                                   get_single_random_anime, get_top_anime, get_hero_anime_list)
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
        session['user_email'] = 'guest@animehub.com'
        session['user_name'] = 'Guest'
        session['user_pic'] = 'https://ui-avatars.com/api/?name=Guest&background=ff4d4d&color=fff'
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
        
        page = request.args.get('page', 1, type=int)
        anime_list, total = get_paginated_anime(page, per_page=20)
        total_pages = (total + 19) // 20
        featured_anime = get_featured_anime(5)
        top_anime = get_top_anime(10)
        hero_anime_list = get_hero_anime_list(5)
        
        return render_template('index.html', anime_list=anime_list, page=page, total_pages=total_pages, featured_anime=featured_anime, top_anime=top_anime, hero_anime_list=hero_anime_list)

    @app.route('/downloads')
    def downloads():
        if not session.get('user_email'):
            return render_template('login.html')
        return render_template('downloads.html')

    @app.route('/profile')
    def profile():
        if not session.get('user_email'):
            return render_template('login.html')
        return render_template('profile.html')

    @app.route('/settings')
    def settings():
        if not session.get('user_email'):
            return render_template('login.html')
        return render_template('settings.html')

    # ✅ नया रास्ता: Language
    @app.route('/language')
    def language():
        if not session.get('user_email'):
            return render_template('login.html')
        return render_template('language.html')

    @app.route('/search')
    def search():
        if not session.get('user_email'): return render_template('login.html')
        query = request.args.get('q', '')
        anime_list = search_anime(query) if query else get_all_anime()
        return render_template('index.html', anime_list=anime_list, search_query=query, page=1, total_pages=1, featured_anime=[], top_anime=[], hero_anime_list=[])

    @app.route('/genre/<genre_name>')
    def genre(genre_name):
        if not session.get('user_email'): return render_template('login.html')
        anime_list = get_anime_by_genre(genre_name)
        return render_template('index.html', anime_list=anime_list, search_query=genre_name.title() + " Anime", page=1, total_pages=1, featured_anime=[], top_anime=[], hero_anime_list=[])

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
    @app.route('/watch/<anime_id>/<int:ep_number>')
    def watch(anime_id, ep_number=None):
        if not session.get('user_email'): return render_template('login.html')
        anime = get_anime_by_id(anime_id)
        if not anime: abort(404)
        episodes = anime.get('episodes', [])
        current_ep, current_index = None, 0
        if episodes:
            if ep_number is None: current_ep = episodes[0]
            else:
                for i, ep in enumerate(episodes):
                    if f"Episode {ep_number}" in ep.get('title', ''):
                        current_ep, current_index = ep, i
                        break
                if not current_ep: current_ep = episodes[0]
        prev_ep_num, next_ep_num = None, None
        if episodes:
            if current_index > 0:
                prev_match = episodes[current_index - 1]['title'].split(' ')[-1]
                if prev_match.isdigit(): prev_ep_num = prev_match
            if current_index < len(episodes) - 1:
                next_match = episodes[current_index + 1]['title'].split(' ')[-1]
                if next_match.isdigit(): next_ep_num = next_match
        related_anime = get_random_anime(anime_id, count=6)
        return render_template('watch.html', anime=anime, episodes=episodes, current_ep=current_ep, prev_ep=prev_ep_num, next_ep=next_ep_num, related_anime=related_anime)

    @app.errorhandler(404)
    def page_not_found(e): return render_template('404.html'), 404

    return app
    # ✅ DEBUG: Playwright से Letter A का HTML देखने के लिए
if __name__ == '__main__':
    from playwright.sync_api import sync_playwright
    import time
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        print("🌐 Letter A खोल रहे हैं...")
        page.goto("https://animesalt.cx/letter/A/", wait_until='domcontentloaded', timeout=30000)
        time.sleep(5)
        
        html = page.content()
        with open('letter_a_debug.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ File saved! Size: {len(html)} characters")
        
        browser.close()