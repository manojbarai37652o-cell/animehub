import os

print("🚀 भाई, प्रोजेक्ट स्ट्रक्चर बनाना शुरू हो रहा है...")

# 1. सारे फोल्डर्स की लिस्ट
folders = [
    "app",
    "app/routes",
    "app/services",
    "app/static",
    "app/static/css",
    "app/static/js",
    "app/static/images",
    "app/templates",
    "scraper",
    "database",
    "tests"
]

# 2. सारी खाली फाइलों की लिस्ट
files = [
    ".env",
    ".gitignore",
    "requirements.txt",
    "run.py",
    "config.py",
    "app/__init__.py",
    "app/routes/__init__.py",
    "app/routes/main.py",
    "app/routes/anime.py",
    "app/services/__init__.py",
    "app/services/db_manager.py",
    "app/services/ai_helper.py",
    "app/static/css/style.css",
    "app/static/js/main.js",
    "app/static/images/logo.png",
    "app/templates/base.html",
    "app/templates/index.html",
    "app/templates/watch.html",
    "scraper/__init__.py",
    "scraper/base_scraper.py",
    "scraper/parser.py",
    "scraper/downloader.py",
    "database/storage.json",
    "tests/__init__.py",
    "tests/test_db.py",
    "tests/test_scraper.py"
]

# 3. फोल्डर्स बनाना
for folder in folders:
    os.makedirs(folder, exist_ok=True)
    print(f"📁 फोल्डर तैयार: {folder}")

# 4. खाली फाइलें बनाना
for file in files:
    # अगर फाइल पहले से नहीं है, तो बनाओ
    if not os.path.exists(file):
        with open(file, 'w', encoding='utf-8') as f:
            pass  # खाली फाइल बनाएगा
        print(f"📄 फाइल तैयार: {file}")

print("\n✅ भाई, पूरा स्ट्रक्चर एकदम तैयार है! अब आगे बढ़ते हैं।")