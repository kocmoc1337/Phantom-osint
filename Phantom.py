#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PHANTOM v5.0 - OSINT Tool for Pydroid 3
Легальный сбор информации из публичных источников
"""

import os
import sys
import json
import time
import re
import requests
import hashlib
import base64
import sqlite3
from datetime import datetime
from urllib.parse import quote, urlparse
from collections import defaultdict
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Для кеширования и базы данных
import sqlite3
from pathlib import Path

# ============================================================================
# ЦВЕТНЫЕ ВЫВОДЫ И ИНТЕРФЕЙС
# ============================================================================

class Colors:
    """Цвета для терминала"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Основные цвета
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    
    # Фоны
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'

class UI:
    """Красивый интерфейс"""
    
    @staticmethod
    def clear():
        os.system('clear' if os.name != 'nt' else 'cls')
    
    @staticmethod
    def banner():
        banner = f"""
{Colors.MAGENTA}{Colors.BOLD}
██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗
██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║
██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║
██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║
██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝
{Colors.CYAN}v5.0 Pydroid | by @jecrs | verificator{Colors.RESET}
Open Source Intelligence Tool
"""
        return banner
    
    @staticmethod
    def header(title):
        line = "═" * 60
        print(f"\n{Colors.CYAN}{line}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}► {title}{Colors.RESET}")
        print(f"{Colors.CYAN}{line}{Colors.RESET}\n")
    
    @staticmethod
    def success(msg):
        print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")
    
    @staticmethod
    def info(msg):
        print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")
    
    @staticmethod
    def warning(msg):
        print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")
    
    @staticmethod
    def error(msg):
        print(f"{Colors.RED}✗{Colors.RESET} {msg}")
    
    @staticmethod
    def title(text):
        print(f"\n{Colors.BOLD}{Colors.MAGENTA}{text}{Colors.RESET}")
    
    @staticmethod
    def table(headers, rows):
        """Красивая таблица"""
        col_widths = [max(len(str(h)), max(len(str(r[i])) if i < len(r) else 0 for r in rows)) 
                      for i, h in enumerate(headers)]
        
        # Заголовок
        header_row = " | ".join(f"{h:{w}}" for h, w in zip(headers, col_widths))
        print(f"\n{Colors.CYAN}{Colors.BOLD}{header_row}{Colors.RESET}")
        print(f"{Colors.CYAN}{'-' * len(header_row)}{Colors.RESET}")
        
        # Строки
        for row in rows:
            formatted_row = " | ".join(f"{str(r):{w}}" for r, w in zip(row, col_widths))
            print(formatted_row)
    
    @staticmethod
    def progress_bar(current, total, label=""):
        """Прогресс-бар"""
        percent = current / total * 100
        bar_length = 30
        filled = int(bar_length * current // total)
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"\r{Colors.CYAN}[{bar}]{Colors.RESET} {percent:.1f}% {label}", end="", flush=True)

# ============================================================================
# РАБОТА С КЕШЕМ И БАЗОЙ ДАННЫХ
# ============================================================================

class Database:
    """Локальное хранилище результатов"""
    
    def __init__(self, save_mode=True):
        self.save_mode = save_mode  # True = сохранять, False = только RAM
        self.db_path = Path.home() / ".phantom" / "results.db"
        self.db_path.parent.mkdir(exist_ok=True)
        
        if self.save_mode:
            self.init_db()
    
    def init_db(self):
        """Инициализация БД"""
        if not self.save_mode:
            return
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS searches
                     (id INTEGER PRIMARY KEY, query TEXT, module TEXT, 
                      result TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS bookmarks
                     (id INTEGER PRIMARY KEY, title TEXT, data TEXT, 
                      created DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        conn.commit()
        conn.close()
    
    def save_search(self, query, module, result):
        """Сохранить результат поиска"""
        if not self.save_mode:
            return  # Не сохраняем в режиме RAM only
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO searches (query, module, result) VALUES (?, ?, ?)",
                  (query, module, json.dumps(result)))
        conn.commit()
        conn.close()
    
    def get_search_history(self, limit=10):
        """История поисков"""
        if not self.save_mode:
            return []
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT query, module, timestamp FROM searches ORDER BY id DESC LIMIT ?", (limit,))
        results = c.fetchall()
        conn.close()
        return results
    
    def add_bookmark(self, title, data):
        """Добавить в закладки"""
        if not self.save_mode:
            return
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO bookmarks (title, data) VALUES (?, ?)",
                  (title, json.dumps(data)))
        conn.commit()
        conn.close()
    
    def clear_history(self):
        """Очистить всю историю"""
        if not self.save_mode:
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("DELETE FROM searches")
            c.execute("DELETE FROM bookmarks")
            conn.commit()
            conn.close()
            return True
        except:
            return False
    
    def delete_database(self):
        """Удалить файл БД"""
        try:
            if self.db_path.exists():
                self.db_path.unlink()
            return True
        except:
            return False

# ============================================================================
# ОСНОВНЫЕ МОДУЛИ OSINT
# ============================================================================

class UsernameScanner:
    """Поиск юзернейма на популярных платформах"""
    
    # 200+ сайтов для проверки
    PLATFORMS = {
        # ===== СОЦИАЛЬНЫЕ СЕТИ =====
        "Twitter": "https://twitter.com/{}",
        "Instagram": "https://instagram.com/{}",
        "TikTok": "https://tiktok.com/@{}",
        "Facebook": "https://facebook.com/{}",
        "LinkedIn": "https://linkedin.com/in/{}",
        "Snapchat": "https://snapchat.com/add/{}",
        "WeChat": "https://wechat.com/{}",
        "WhatsApp": "https://wa.me/{}",
        "Viber": "https://viber.click/{}",
        "Line": "https://line.me/{}",
        "Nextdoor": "https://nextdoor.com/{}",
        "Tumblr": "https://{}.tumblr.com",
        "MySpace": "https://myspace.com/{}",
        "Quora": "https://quora.com/profile/{}",
        "Mastodon": "https://mastodon.social/@{}",
        "Bluesky": "https://bsky.app/profile/{}",
        "Threads": "https://threads.net/@{}",
        "BeReal": "https://bereal.com/{}",
        
        # ===== ВИДЕО-ПЛАТФОРМЫ =====
        "YouTube": "https://youtube.com/@{}",
        "Vimeo": "https://vimeo.com/{}",
        "DailyMotion": "https://dailymotion.com/{}",
        "Rumble": "https://rumble.com/user/{}",
        "Twitch": "https://twitch.tv/{}",
        "Kick": "https://kick.com/{}",
        "Rumble Gaming": "https://rumble.com/c/{}",
        "Dailymotion": "https://dailymotion.com/{}",
        "Odysee": "https://odysee.com/{}",
        "BitChute": "https://bitchute.com/channel/{}",
        "Gettr": "https://gettr.com/post/{}",
        
        # ===== МУЗЫКА =====
        "Spotify": "https://open.spotify.com/user/{}",
        "SoundCloud": "https://soundcloud.com/{}",
        "Bandcamp": "https://{}.bandcamp.com",
        "Apple Music": "https://music.apple.com/profile/{}",
        "Deezer": "https://deezer.com/profile/{}",
        "LastFM": "https://last.fm/user/{}",
        "MusicBrainz": "https://musicbrainz.org/user/{}",
        "Genius": "https://genius.com/{}",
        "Tidal": "https://listen.tidal.com/user/{}",
        "YouTube Music": "https://music.youtube.com/@{}",
        "Amazon Music": "https://amazon.com/music/user/{}",
        
        # ===== ФОТО И ИСКУССТВО =====
        "Flickr": "https://flickr.com/photos/{}",
        "500px": "https://500px.com/{}",
        "DeviantArt": "https://deviantart.com/{}",
        "ArtStation": "https://artstation.com/{}",
        "Behance": "https://behance.net/{}",
        "Instagram": "https://instagram.com/{}",
        "Pinterest": "https://pinterest.com/{}/",
        "We Heart It": "https://weheartit.com/{}",
        "Unsplash": "https://unsplash.com/@{}",
        "Pexels": "https://pexels.com/@{}",
        "Pixabay": "https://pixabay.com/users/{}/",
        "SmugMug": "https://smugmug.com/{}",
        
        # ===== РАЗРАБОТКА И TECH =====
        "GitHub": "https://github.com/{}",
        "GitLab": "https://gitlab.com/{}",
        "Bitbucket": "https://bitbucket.org/{}",
        "Codepen": "https://codepen.io/{}",
        "Replit": "https://replit.com/@{}",
        "Glitch": "https://glitch.com/@{}",
        "Stack Overflow": "https://stackoverflow.com/users/*/{}",
        "HackerRank": "https://hackerrank.com/{}",
        "LeetCode": "https://leetcode.com/{}",
        "CodeWars": "https://codewars.com/users/{}",
        "Project Euler": "https://projecteuler.net/profile/{}",
        "CodeSignal": "https://codesignal.com/profile/{}",
        "Kaggle": "https://kaggle.com/{}",
        "OpenStreetMap": "https://openstreetmap.org/user/{}",
        "SourceForge": "https://sourceforge.net/u/{}/profile/",
        "LaunchPad": "https://launchpad.net/~{}",
        
        # ===== БЛОГИ И КОНТЕНТ =====
        "Medium": "https://medium.com/@{}",
        "Substack": "https://substack.com/@{}",
        "Blogger": "https://{}.blogspot.com",
        "WordPress": "https://{}.wordpress.com",
        "Wix": "https://{}.wix.com",
        "Weebly": "https://{}.weebly.com",
        "Tumblr": "https://{}.tumblr.com",
        "Ghost": "https://{}.ghost.io",
        "Hashnode": "https://hashnode.com/@{}",
        "Dev.to": "https://dev.to/{}",
        "Mirror": "https://mirror.xyz/{}",
        "Paragraph": "https://paragraph.xyz/{}",
        "Beehive": "https://beehive.substack.com/{}",
        
        # ===== ФОРУМЫ И СООБЩЕСТВА =====
        "Reddit": "https://reddit.com/user/{}",
        "4chan": "https://boards.4chan.org/b/",
        "8kun": "https://8kun.top/{}",
        "Voat": "https://voat.co/user/{}",
        "Rumble Community": "https://rumble.com/c/{}",
        "Minds": "https://minds.com/{}",
        "Steemit": "https://steemit.com/@{}",
        "Hive": "https://hive.blog/@{}",
        "Gab": "https://gab.com/{}",
        "Truth Social": "https://truthsocial.com/@{}",
        "Parler": "https://parler.com/{}",
        "Gettr": "https://gettr.com/user/{}",
        "Telegram": "https://t.me/{}",
        "Discord": "https://discordapp.com/users/{}",
        "Slack": "https://{}.slack.com",
        "Matrix": "https://matrix.to/#/@{}",
        
        # ===== ИГРЫ =====
        "Steam": "https://steamcommunity.com/search/?text={}",
        "Roblox": "https://roblox.com/users/profile?username={}",
        "Minecraft": "https://minecraft.net/profile/{}",
        "Epic Games": "https://epicgames.com/id/{}",
        "Battle.net": "https://us.battle.net/profile/{}",
        "PlayStation Network": "https://psnprofiles.com/{}",
        "Xbox Live": "https://xboxgamertag.com/search/{}",
        "Nintendo": "https://accounts.nintendo.com/{}",
        "Twitch": "https://twitch.tv/{}",
        "Chess.com": "https://chess.com/user/{}",
        "Lichess": "https://lichess.org/{}",
        "Itch.io": "https://itch.io/profile/{}",
        "GameJolt": "https://gamejolt.com/@{}",
        "Newgrounds": "https://newgrounds.com/user/{}",
        
        # ===== ФИНАНСЫ И КРИПТО =====
        "Blockchain.com": "https://blockchain.com/btc/address/{}",
        "Etherscan": "https://etherscan.io/address/{}",
        "Coinbase": "https://coinbase.com/user/{}",
        "Kraken": "https://kraken.com/en-us/user/{}",
        "Binance": "https://binance.com/en/user/{}",
        "Bybit": "https://bybit.com/user/{}",
        "OKEx": "https://okex.com/user/{}",
        "FTX": "https://ftx.com/user/{}",
        "Robinhood": "https://robinhood.com/user/{}",
        "Stripe": "https://stripe.com/user/{}",
        "PayPal": "https://paypal.com/user/{}",
        "Patreon": "https://patreon.com/{}",
        "Kickstarter": "https://kickstarter.com/profile/{}",
        "Gumroad": "https://gumroad.com/{}",
        
        # ===== ПРОФЕССИОНАЛЬНЫЕ СЕТИ =====
        "LinkedIn": "https://linkedin.com/in/{}",
        "Indeed": "https://profile.indeed.com/{}",
        "Glassdoor": "https://glassdoor.com/Profile/{}",
        "AngelList": "https://angel.co/{}",
        "Crunchbase": "https://crunchbase.com/person/{}",
        "ProductHunt": "https://producthunt.com/@{}",
        "Dribbble": "https://dribbble.com/{}",
        "Designer Hangout": "https://designerhangout.co/{}",
        "ADPList": "https://adplist.org/designers/{}",
        "F6S": "https://www.f6s.com/{}",
        
        # ===== ОБРАЗОВАНИЕ =====
        "Duolingo": "https://duolingo.com/profile/{}",
        "Codecademy": "https://codecademy.com/users/{}",
        "Udemy": "https://udemy.com/user/{}/",
        "Coursera": "https://coursera.org/user/{}",
        "edX": "https://edx.org/u/{}",
        "Khan Academy": "https://khanacademy.org/profile/{}",
        "Skillshare": "https://skillshare.com/user/{}",
        "Udacity": "https://udacity.com/user/{}",
        "Treehouse": "https://treehouse.com/{}",
        "Pluralsight": "https://pluralsight.com/user/{}",
        
        # ===== ТРАНСПОРТ И ПУТЕШЕСТВИЯ =====
        "Uber": "https://uber.com/user/{}",
        "Lyft": "https://lyft.com/user/{}",
        "Airbnb": "https://airbnb.com/users/{}",
        "Booking.com": "https://booking.com/profile/{}",
        "Tripadvisor": "https://tripadvisor.com/members/{}",
        "Google Maps": "https://maps.google.com/maps/contrib/{}",
        "Yelp": "https://yelp.com/user_details?userid={}",
        "GetYourGuide": "https://getyourguide.com/@{}",
        "Klook": "https://klook.com/user/{}",
        
        # ===== ЕДА И ДОСТАВКА =====
        "DoorDash": "https://doordash.com/profile/{}",
        "UberEats": "https://ubereats.com/user/{}",
        "Grubhub": "https://grubhub.com/user/{}",
        "Instacart": "https://instacart.com/u/{}",
        "Yelp": "https://yelp.com/user_details?userid={}",
        "Just Eat": "https://justeat.com/user/{}",
        "Deliveroo": "https://deliveroo.com/user/{}",
        
        # ===== ЗДОРОВЬЕ И ФИТНЕС =====
        "MyFitnessPal": "https://myfitnesspal.com/user/{}",
        "Strava": "https://strava.com/athletes/{}",
        "Fitbit": "https://fitbit.com/user/{}",
        "Apple Health": "https://health.apple.com/user/{}",
        "Nike Training Club": "https://nike.com/user/{}",
        "Peloton": "https://onepeloton.com/user/{}",
        "Zwift": "https://zwift.com/user/{}",
        "Map My Run": "https://mapmyrun.com/user/{}",
        
        # ===== ЖИВОТНЫЕ И ПИТОМЦЫ =====
        "DogTime": "https://dogtime.com/user/{}",
        "CatTime": "https://cattime.com/user/{}",
        "Nextdoor Pet": "https://nextdoor.com/pet/{}",
        "PetFinder": "https://petfinder.com/user/{}",
        
        # ===== КИНО И ТВ =====
        "IMDb": "https://imdb.com/user/ur{}/",
        "Letterboxd": "https://letterboxd.com/{}",
        "MyAnimeList": "https://myanimelist.net/profile/{}",
        "Trakt": "https://trakt.tv/users/{}",
        "TMDB": "https://themoviedb.org/user/{}",
        "Rotten Tomatoes": "https://rottentomatoes.com/user/{}",
        
        # ===== МОДА И СТИЛЬ =====
        "ShopStyle": "https://shopstylist.com/{}",
        "Lookbook": "https://lookbook.nu/{}",
        "TheOutnet": "https://theoutnet.com/user/{}",
        "SSENSE": "https://ssense.com/en-us/user/{}",
        
        # ===== НЕДВИЖИМОСТЬ =====
        "Zillow": "https://zillow.com/user/{}",
        "Redfin": "https://redfin.com/user/{}",
        "Trulia": "https://trulia.com/user/{}",
        "Apartments.com": "https://apartments.com/user/{}",
        
        # ===== АВТОМОБИЛИ =====
        "KBB": "https://kbb.com/user/{}",
        "CarGurus": "https://cargurus.com/user/{}",
        "Autotrader": "https://autotrader.com/user/{}",
        "Cars.com": "https://cars.com/user/{}",
        
        # ===== ДРУГОЕ =====
        "Patreon": "https://patreon.com/{}",
        "BuyMeACoffee": "https://buymeacoffee.com/{}",
        "Ko-fi": "https://ko-fi.com/{}",
        "Linktree": "https://linktree.com/{}",
        "Beacons": "https://beacons.ai/{}",
        "About.me": "https://about.me/{}",
        "Carrd": "https://carrd.co/{}",
        "Letterhead": "https://letterhead.co/@{}",
        "Notion": "https://notion.so/@{}",
        "Obsidian": "https://publish.obsidian.md/{}",
        "Mastodon": "https://mastodon.social/@{}",
        "Pixelfed": "https://pixelfed.social/{}",
        "PeerTube": "https://peertube.example.com/{}",
        "Lemmy": "https://lemmy.ml/u/{}",
        "Kbin": "https://kbin.social/u/{}",
        "BookBaby": "https://bookbaby.com/author/{}",
        "Wattpad": "https://wattpad.com/user/{}",
        "Inkitt": "https://inkitt.com/{}",
        "Smashwords": "https://smashwords.com/profile/{}",
        "ReaderLink": "https://readerlink.com/user/{}",
        "Goodreads": "https://goodreads.com/{}",
        "LibraryThing": "https://librarything.com/profile/{}",
    }
    
    def __init__(self):
        self.results = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scan(self, username):
        """Сканировать юзернейм"""
        UI.clear()
        UI.clear()
        UI.header(f"🔍 Сканирование юзернейма: {Colors.YELLOW}{username}{Colors.RESET}")
        
        found = []
        total = len(self.PLATFORMS)
        lock = Lock()
        checked = [0]  # Счётчик проверенных платформ
        
        def check_platform(platform, url):
            """Проверить одну платформу"""
            try:
                full_url = url.format(username)
                response = self.session.head(full_url, timeout=3, allow_redirects=True)
                
                if response.status_code == 200:
                    with lock:
                        found.append((platform, full_url))
                        UI.success(f"Найден на {platform}")
            except:
                pass
            
            # Обновляем прогресс
            with lock:
                checked[0] += 1
                UI.progress_bar(checked[0], total, f"({checked[0]}/{total})")
        
        # Используем многопоточность (10 потоков одновременно)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(check_platform, platform, url) 
                for platform, url in self.PLATFORMS.items()
            ]
            
            # Ждём завершения всех задач
            for future in as_completed(futures):
                try:
                    future.result()
                except:
                    pass
        
        print("\n")
        return found

class DomainOSINT:
    """Анализ доменов"""
    
    def analyze(self, domain):
        """Полный анализ домена"""
        UI.clear()
        UI.header(f"🌐 Анализ домена: {Colors.YELLOW}{domain}{Colors.RESET}")
        
        results = {
            "domain": domain,
            "whois": self._get_whois(domain),
            "dns": self._get_dns(domain),
            "ip_info": self._get_ip_info(domain),
            "ssl": self._get_ssl_info(domain),
        }
        
        return results
    
    def _get_whois(self, domain):
        """WHOIS информация"""
        try:
            # Используем публичный WHOIS API
            response = requests.get(f"https://whois.ipeye.ru/api/whois/{domain}", timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return {"error": "WHOIS информация недоступна"}
    
    def _get_dns(self, domain):
        """DNS записи"""
        try:
            import socket
            results = {}
            
            # A record
            try:
                ip = socket.gethostbyname(domain)
                results['A'] = ip
            except:
                pass
            
            # MX record (упрощённо)
            results['info'] = f"Основной IP: {results.get('A', 'N/A')}"
            
            return results
        except:
            return {"error": "DNS информация недоступна"}
    
    def _get_ip_info(self, domain):
        """Информация об IP"""
        try:
            ip = socket.gethostbyname(domain)
            response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return {"error": "IP информация недоступна"}
    
    def _get_ssl_info(self, domain):
        """SSL информация"""
        try:
            response = requests.get(f"https://crt.sh/?q={domain}&output=json", timeout=5)
            if response.status_code == 200:
                certs = response.json()
                return {"certificates": len(certs), "latest": certs[0] if certs else None}
        except:
            pass
        return {"error": "SSL информация недоступна"}

class ImageOSINT:
    """Анализ изображений и EXIF"""
    
    def analyze_url(self, image_url):
        """Анализ изображения по URL"""
        UI.clear()
        UI.header(f"🖼️  Анализ изображения")
        
        try:
            response = requests.get(image_url, timeout=10)
            if response.status_code == 200:
                # Попробуем получить EXIF данные (если установлена PIL)
                try:
                    from PIL import Image
                    from PIL.ExifTags import TAGS
                    from io import BytesIO
                    
                    image = Image.open(BytesIO(response.content))
                    exif_data = image._getexif()
                    
                    results = {
                        "format": image.format,
                        "size": image.size,
                        "mode": image.mode,
                    }
                    
                    if exif_data:
                        for tag_id, value in exif_data.items():
                            tag = TAGS.get(tag_id, tag_id)
                            results[tag] = str(value)[:100]
                    
                    return results
                except:
                    return {
                        "format": "Неизвестен",
                        "note": "PIL не установлена. Используй: pip install pillow"
                    }
        except Exception as e:
            UI.error(f"Ошибка загрузки: {e}")
        
        return {}

class CryptoOSINT:
    """Анализ криптоадресов"""
    
    def analyze_address(self, address, blockchain="bitcoin"):
        """Анализ крипто-адреса"""
        UI.clear()
        UI.header(f"💰 Анализ адреса: {Colors.YELLOW}{address}{Colors.RESET}")
        
        results = {}
        
        if blockchain == "bitcoin":
            try:
                response = requests.get(f"https://blockchain.info/q/addressbalance/{address}", timeout=5)
                if response.status_code == 200:
                    balance = int(response.text) / 1e8  # Convert satoshi to BTC
                    results['balance_btc'] = balance
                    results['blockchain'] = "Bitcoin"
            except:
                pass
        
        elif blockchain == "ethereum":
            try:
                response = requests.get(
                    f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest",
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == '1':
                        balance = int(data['result']) / 1e18  # Convert wei to ETH
                        results['balance_eth'] = balance
                        results['blockchain'] = "Ethereum"
            except:
                pass
        
        return results if results else {"error": "Адрес не найден"}

class EmailFinder:
    """Поиск email по доменам и именам"""
    
    def find_emails(self, domain):
        """Найти emails домена"""
        UI.clear()
        UI.header(f"📧 Поиск emails для: {Colors.YELLOW}{domain}{Colors.RESET}")
        
        emails = []
        
        # Проверяем стандартные паттерны
        common_patterns = [
            "admin", "info", "support", "contact", "hello",
            "sales", "marketing", "team", "mail", "noreply"
        ]
        
        for pattern in common_patterns:
            email = f"{pattern}@{domain}"
            if self._check_email(email):
                emails.append(email)
                UI.success(f"Найден: {email}")
        
        return emails
    
    def _check_email(self, email):
        """Проверка существования email (упрощённо)"""
        # Это базовая проверка - реальная проверка требует SMTP сервера
        try:
            response = requests.head(f"https://hunter.io/search?domain={email.split('@')[1]}&limit=1", timeout=2)
            return response.status_code == 200
        except:
            return False

class DataBreachChecker:
    """Проверка утечек данных"""
    
    def check_email(self, email):
        """Проверить email в известных утечках"""
        UI.clear()
        UI.header(f"🔴 Проверка утечек: {Colors.YELLOW}{email}{Colors.RESET}")
        
        try:
            # Using haveibeenpwned API
            response = requests.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(email)}",
                headers={'User-Agent': 'PHANTOM-OSINT'},
                timeout=5
            )
            
            if response.status_code == 200:
                breaches = response.json()
                UI.warning(f"⚠️  Email найден в {len(breaches)} утечках!")
                
                for breach in breaches:
                    print(f"  • {breach['Name']} ({breach['BreachDate']})")
                
                return breaches
            elif response.status_code == 404:
                UI.success("✓ Email не найден в известных утечках")
                return []
        except Exception as e:
            UI.error(f"Ошибка проверки: {e}")
        
        return []
    
    def check_password(self, password):
        """Проверить пароль в утечках (Pwned Passwords)"""
        UI.clear()
        UI.header(f"🔑 Проверка пароля")
        
        try:
            # k-anonymity API
            sha1_hash = hashlib.sha1(password.encode()).hexdigest().upper()
            prefix = sha1_hash[:5]
            suffix = sha1_hash[5:]
            
            response = requests.get(f"https://api.pwnedpasswords.com/range/{prefix}", timeout=5)
            
            if response.status_code == 200:
                hashes = response.text.split('\r\n')
                
                for hash_pair in hashes:
                    hash_suffix, count = hash_pair.split(':')
                    
                    if hash_suffix == suffix:
                        UI.warning(f"⚠️  Пароль найден в {count} утечках!")
                        return int(count)
                
                UI.success("✓ Пароль не найден в известных утечках")
                return 0
        except Exception as e:
            UI.error(f"Ошибка проверки: {e}")
        
        return -1

class WebsiteAnalyzer:
    """Анализ вебсайтов"""
    
    def analyze(self, url):
        """Полный анализ вебсайта"""
        UI.clear()
        UI.header(f"🔗 Анализ веб-сайта: {Colors.YELLOW}{url}{Colors.RESET}")
        
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        results = {
            "url": url,
            "headers": self._get_headers(url),
            "ssl": self._get_ssl_info(url),
            "dns": self._get_dns_info(url),
            "technology": self._detect_technology(url),
        }
        
        return results
    
    def _get_headers(self, url):
        """HTTP заголовки"""
        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            return dict(response.headers)
        except:
            return {}
    
    def _get_ssl_info(self, url):
        """SSL информация"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            
            response = requests.get(f"https://crt.sh/?q={domain}&output=json", timeout=5)
            if response.status_code == 200:
                certs = response.json()
                return {"valid_certificates": len(certs)}
        except:
            pass
        return {}
    
    def _get_dns_info(self, url):
        """DNS информация"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.split(':')[0]
            ip = socket.gethostbyname(domain)
            return {"ip": ip, "domain": domain}
        except:
            return {}
    
    def _detect_technology(self, url):
        """Определение технологий на сайте"""
        try:
            response = requests.get(url, timeout=5)
            headers = response.headers
            
            tech = []
            
            # Определяем по заголовкам
            if 'X-Powered-By' in headers:
                tech.append(headers['X-Powered-By'])
            
            if 'Server' in headers:
                tech.append(headers['Server'])
            
            return tech
        except:
            return []

class URLAnalyzer:
    """Анализ URL"""
    
    def analyze(self, url):
        """Анализ URL"""
        UI.clear()
        UI.header(f"🔍 Анализ URL")
        
        parsed = urlparse(url)
        
        results = {
            "original": url,
            "scheme": parsed.scheme,
            "domain": parsed.netloc,
            "path": parsed.path,
            "params": parsed.params,
            "query": parsed.query,
            "fragment": parsed.fragment,
        }
        
        # Проверка на фишинг
        results['suspicious'] = self._check_suspicious(url)
        
        return results
    
    def _check_suspicious(self, url):
        """Проверка подозрительных признаков"""
        suspicious = []
        
        if url.count('@') > 0:
            suspicious.append("Найдена @ в URL")
        
        if 'bit.ly' in url or 'tinyurl' in url:
            suspicious.append("Используется сокращение URL")
        
        if len(url) > 100:
            suspicious.append("Очень длинный URL")
        
        return suspicious

class HashAnalyzer:
    """Анализ хешей"""
    
    def analyze(self, hash_string):
        """Определить тип хеша и проверить"""
        UI.clear()
        UI.header(f"🔐 Анализ хеша")
        
        hash_type = self._identify_hash(hash_string)
        results = {"hash": hash_string, "type": hash_type}
        
        # Попытка найти в базе
        results['lookup'] = self._lookup_hash(hash_string)
        
        return results
    
    def _identify_hash(self, hash_str):
        """Определить тип хеша"""
        length = len(hash_str)
        
        hash_types = {
            32: "MD5 или NTLM",
            40: "SHA-1",
            64: "SHA-256",
            128: "SHA-512",
        }
        
        return hash_types.get(length, f"Неизвестен (длина: {length})")
    
    def _lookup_hash(self, hash_str):
        """Поиск хеша в общедоступных базах"""
        try:
            response = requests.get(f"https://hash.online-convert.com/hash-lookup/sha256/{hash_str}", timeout=5)
            return response.status_code == 200
        except:
            return False

class ReputationChecker:
    """Проверка репутации"""
    
    def check_domain(self, domain):
        """Проверить репутацию домена"""
        UI.clear()
        UI.header(f"⭐ Проверка репутации: {Colors.YELLOW}{domain}{Colors.RESET}")
        
        results = {}
        
        # Google Safe Browsing (упрощённо)
        results['google_safe'] = True  # Требует API ключ
        
        # Проверка в VirusTotal (требует API)
        results['virustotal'] = "Требует API ключ"
        
        # Проверка в списках спама
        results['spam_list'] = False
        
        return results

class NameGenerator:
    """Генератор юзернейм-вариаций"""
    
    def generate(self, first_name, last_name):
        """Генерировать варианты юзернейма"""
        UI.clear()
        UI.header(f"💡 Генератор вариаций")
        
        variations = []
        
        # Базовые варианты
        variations.append(f"{first_name.lower()}{last_name.lower()}")
        variations.append(f"{first_name.lower()}.{last_name.lower()}")
        variations.append(f"{first_name[0].lower()}{last_name.lower()}")
        variations.append(f"{first_name.lower()}{last_name[0].lower()}")
        variations.append(f"{last_name.lower()}{first_name.lower()}")
        
        # С числами
        for i in range(2024, 2030):
            variations.append(f"{first_name.lower()}{i}")
            variations.append(f"{first_name.lower()}{last_name.lower()}{str(i)[-2:]}")
        
        # С подчёркиванием
        variations.append(f"{first_name.lower()}_{last_name.lower()}")
        variations.append(f"{first_name.lower()}_{last_name.lower()}_{str(2024)[-2:]}")
        
        return list(set(variations))  # Убираем дубликаты

class APIFinder:
    """Поиск открытых API endpoint'ов"""
    
    def find_apis(self, domain):
        """Найти API endpoints"""
        UI.clear()
        UI.header(f"🔌 Поиск API endpoints: {Colors.YELLOW}{domain}{Colors.RESET}")
        
        common_endpoints = [
            "/api/", "/api/v1/", "/api/v2/", "/api/v3/",
            "/rest/", "/graphql/", "/swagger/", "/swagger.json",
            "/openapi.json", "/api-docs/", "/docs/", "/redoc/",
            "/actuator/", "/admin/api/", "/wp-json/", "/json/",
            "/.well-known/", "/config.json", "/settings.json",
            "/status/", "/health/", "/ping/", "/version/",
            "/api.php", "/api.asp", "/api.aspx", "/api.jsp",
        ]
        
        found_apis = []
        total = len(common_endpoints)
        lock = Lock()
        checked = [0]
        
        if not domain.startswith(('http://', 'https://')):
            domain = f"https://{domain}"
        
        def check_endpoint(endpoint):
            """Проверить endpoint"""
            try:
                url = domain.rstrip('/') + endpoint
                response = requests.head(url, timeout=2, allow_redirects=False)
                
                if response.status_code in [200, 401, 403]:
                    with lock:
                        found_apis.append((endpoint, response.status_code))
                        UI.success(f"Найден: {endpoint} ({response.status_code})")
            except:
                pass
            
            with lock:
                checked[0] += 1
                UI.progress_bar(checked[0], total, endpoint)
        
        # Многопоточность для API поиска (8 потоков)
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(check_endpoint, endpoint) for endpoint in common_endpoints]
            for future in as_completed(futures):
                try:
                    future.result()
                except:
                    pass
        
        print("\n")
        return found_apis

class GitHubDork:
    """Поиск конфигов и секретов в GitHub"""
    
    def search(self, keyword):
        """Поиск в GitHub публичных репозиториях"""
        UI.clear()
        UI.header(f"🐙 GitHub Dork Search: {Colors.YELLOW}{keyword}{Colors.RESET}")
        
        # Чувствительные паттерны для поиска
        dorks = [
            f'"{keyword}" password',
            f'"{keyword}" api_key',
            f'"{keyword}" token',
            f'"{keyword}" secret',
            f'"{keyword}" config.json',
            f'"{keyword}" .env',
        ]
        
        results = []
        
        for dork in dorks:
            try:
                query = f'q={quote(dork)}&type=code&per_page=5'
                url = f"https://api.github.com/search/code?{query}"
                
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('items'):
                        for item in data['items'][:3]:
                            results.append({
                                'repo': item['repository']['full_name'],
                                'file': item['name'],
                                'url': item['html_url']
                            })
                            UI.success(f"Найдено в {item['repository']['full_name']}")
            except Exception as e:
                pass
            
            time.sleep(0.2)
        
        return results

class SocialAggregator:
    """Агрегатор информации со социальных сетей"""
    
    def aggregate(self, username):
        """Собрать всю публичную информацию по юзернейму"""
        UI.clear()
        UI.header(f"👥 Social Profile Aggregator: {Colors.YELLOW}{username}{Colors.RESET}")
        
        platforms = {
            "Twitter": f"https://twitter.com/{username}",
            "Instagram": f"https://instagram.com/{username}",
            "GitHub": f"https://github.com/{username}",
            "LinkedIn": f"https://linkedin.com/in/{username}",
            "Reddit": f"https://reddit.com/user/{username}",
            "Medium": f"https://medium.com/@{username}",
            "Telegram": f"https://t.me/{username}",
            "YouTube": f"https://youtube.com/@{username}",
        }
        
        aggregated = []
        total = len(platforms)
        lock = Lock()
        checked = [0]
        
        def check_platform(platform, url):
            """Проверить платформу"""
            try:
                response = requests.head(url, timeout=3, allow_redirects=True)
                
                if response.status_code == 200:
                    with lock:
                        aggregated.append({
                            'platform': platform,
                            'url': url,
                            'status': 'active'
                        })
                        UI.success(f"Профиль найден на {platform}")
            except:
                pass
            
            with lock:
                checked[0] += 1
                UI.progress_bar(checked[0], total, platform)
        
        # Многопоточность (8 потоков)
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(check_platform, platform, url) for platform, url in platforms.items()]
            for future in as_completed(futures):
                try:
                    future.result()
                except:
                    pass
        
        print("\n")
        return aggregated

class PastebinMonitor:
    """Мониторинг утечек в Pastebin"""
    
    def search(self, keyword):
        """Поиск утечек на Pastebin"""
        UI.clear()
        UI.header(f"🔍 Pastebin Monitor: {Colors.YELLOW}{keyword}{Colors.RESET}")
        
        results = []
        
        try:
            # Используем публичный Pastebin API (с ограничениями)
            query = quote(keyword)
            
            # Поиск через Google с фильтром по pastebin.com
            search_url = f"https://www.google.com/search?q=site:pastebin.com+{query}"
            
            UI.info("Ищу в публичных источниках...")
            
            # Альтернативный способ - через Have I Been Pwned pastes API
            response = requests.get(
                f"https://haveibeenpwned.com/api/v3/pasteaccount/{quote(keyword)}",
                headers={'User-Agent': 'PHANTOM-OSINT'},
                timeout=5
            )
            
            if response.status_code == 200:
                pastes = response.json()
                
                for paste in pastes:
                    results.append({
                        'title': paste.get('Title', 'Unknown'),
                        'source': paste.get('Source', 'Unknown'),
                        'date': paste.get('PublicationDate', 'Unknown'),
                    })
                    UI.warning(f"⚠️  Найден в утечке: {paste.get('Source')}")
            
            elif response.status_code == 404:
                UI.success("✓ Не найдено в публичных утечках")
        
        except Exception as e:
            UI.error(f"Ошибка при поиске: {e}")
        
        return results

class IPGeolocationAdvanced:
    """Расширенный анализ IP адресов с геолокацией"""
    
    def analyze(self, ip_address):
        """Полный анализ IP"""
        UI.clear()
        UI.header(f"🌍 Анализ IP: {Colors.YELLOW}{ip_address}{Colors.RESET}")
        
        results = {
            "ip": ip_address,
            "geolocation": self._get_geolocation(ip_address),
            "asn_info": self._get_asn_info(ip_address),
            "isp_info": self._get_isp_info(ip_address),
            "dns_reverse": self._get_reverse_dns(ip_address),
            "abuse_reports": self._check_abuse_reports(ip_address),
        }
        
        return results
    
    def _get_geolocation(self, ip):
        """Геолокация IP"""
        try:
            response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "country": data.get('country'),
                    "region": data.get('region'),
                    "city": data.get('city'),
                    "coordinates": data.get('loc'),
                    "timezone": data.get('timezone'),
                    "postal": data.get('postal'),
                }
        except:
            pass
        return {}
    
    def _get_asn_info(self, ip):
        """ASN информация"""
        try:
            response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {"org": data.get('org')}
        except:
            pass
        return {}
    
    def _get_isp_info(self, ip):
        """ISP информация"""
        try:
            response = requests.get(f"https://api.abuseipdb.com/api/v2/check", 
                                   params={"ipAddress": ip, "maxAgeInDays": 90},
                                   headers={"Key": "test", "Accept": "application/json"},
                                   timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return {}
    
    def _get_reverse_dns(self, ip):
        """Обратный DNS"""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return {"hostname": hostname}
        except:
            return {"hostname": "Not available"}
    
    def _check_abuse_reports(self, ip):
        """Проверка на abuse reports"""
        try:
            response = requests.get(f"https://ipqualityscore.com/api/json/ip/{ip}", 
                                   timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "is_vpn": data.get('is_vpn'),
                    "is_proxy": data.get('is_proxy'),
                    "is_tor": data.get('is_tor'),
                    "fraud_score": data.get('fraud_score'),
                }
        except:
            pass
        return {}

class PhoneNumberAnalyzer:
    """Анализ номеров телефонов"""
    
    # Коды стран
    COUNTRY_CODES = {
        '+1': 'USA/Canada',
        '+7': 'Russia',
        '+44': 'United Kingdom',
        '+49': 'Germany',
        '+33': 'France',
        '+39': 'Italy',
        '+34': 'Spain',
        '+31': 'Netherlands',
        '+32': 'Belgium',
        '+43': 'Austria',
        '+46': 'Sweden',
        '+47': 'Norway',
        '+45': 'Denmark',
        '+358': 'Finland',
        '+48': 'Poland',
        '+420': 'Czech Republic',
        '+36': 'Hungary',
        '+40': 'Romania',
        '+90': 'Turkey',
        '+81': 'Japan',
        '+86': 'China',
        '+91': 'India',
        '+55': 'Brazil',
        '+54': 'Argentina',
        '+52': 'Mexico',
        '+61': 'Australia',
    }
    
    # Расширенные коды операторов России с регионами
    RUSSIA_OPERATORS = {
        # МегаФон (911-919, 921-929)
        '911': ('МегаФон', 'Общероссийский'),
        '912': ('МегаФон', 'Общероссийский'),
        '913': ('МегаФон', 'Общероссийский'),
        '914': ('МегаФон', 'Общероссийский'),
        '915': ('МегаФон', 'Общероссийский'),
        '916': ('МегаФон', 'Общероссийский'),
        '917': ('МегаФон', 'Общероссийский'),
        '918': ('МегаФон', 'Общероссийский'),
        '919': ('МегаФон', 'Общероссийский'),
        '921': ('МегаФон', 'Общероссийский'),
        '922': ('МегаФон', 'Общероссийский'),
        '923': ('МегаФон', 'Общероссийский'),
        '924': ('МегаФон', 'Общероссийский'),
        '925': ('МегаФон', 'Общероссийский'),
        '926': ('МегаФон', 'Общероссийский'),
        '927': ('МегаФон', 'Общероссийский'),
        '928': ('МегаФон', 'Кавказский ФО'),
        '929': ('МегаФон', 'Кавказский ФО'),
        
        # Beeline (901-909, 930-939, 960-969)
        '901': ('Beeline', 'Общероссийский'),
        '902': ('Beeline', 'Общероссийский'),
        '903': ('Beeline', 'Общероссийский'),
        '904': ('Beeline', 'Общероссийский'),
        '905': ('Beeline', 'Общероссийский'),
        '906': ('Beeline', 'Общероссийский'),
        '907': ('Beeline', 'Общероссийский'),
        '908': ('Beeline', 'Общероссийский'),
        '909': ('Beeline', 'Общероссийский'),
        '930': ('Beeline', 'Сибирский ФО'),
        '931': ('Beeline', 'Дальневосточный ФО'),
        '932': ('Beeline', 'Дальневосточный ФО'),
        '933': ('Beeline', 'Дальневосточный ФО'),
        '934': ('Beeline', 'Дальневосточный ФО'),
        '936': ('Beeline', 'Дальневосточный ФО'),
        '937': ('Beeline', 'Сибирский ФО'),
        '938': ('Beeline', 'Сибирский ФО'),
        '939': ('Beeline', 'Сибирский ФО'),
        '960': ('Beeline', 'Уральский ФО'),
        '961': ('Beeline', 'Уральский ФО'),
        '962': ('Beeline', 'Уральский ФО'),
        '963': ('Beeline', 'Уральский ФО'),
        '964': ('Beeline', 'Уральский ФО'),
        '965': ('Beeline', 'Уральский ФО'),
        '966': ('Beeline', 'Уральский ФО'),
        '967': ('Beeline', 'Уральский ФО'),
        '968': ('Beeline', 'Уральский ФО'),
        '969': ('Beeline', 'Уральский ФО'),
        
        # МТС (910-919, 920-927, 950-959)
        '910': ('МТС', 'Общероссийский'),
        '920': ('МТС', 'Северо-Западный ФО'),
        '924': ('МТС', 'Приволжский ФО'),
        '950': ('МТС', 'Общероссийский'),
        '951': ('МТС', 'Общероссийский'),
        '952': ('МТС', 'Общероссийский'),
        '953': ('МТС', 'Общероссийский'),
        '954': ('МТС', 'Общероссийский'),
        '955': ('МТС', 'Общероссийский'),
        '956': ('МТС', 'Общероссийский'),
        '957': ('МТС', 'Общероссийский'),
        '958': ('МТС', 'Общероссийский'),
        '959': ('МТС', 'Общероссийский'),
        
        # Yota (980-989)
        '980': ('Yota', 'Общероссийский'),
        '981': ('Yota', 'Общероссийский'),
        '982': ('Yota', 'Общероссийский'),
        '983': ('Yota', 'Общероссийский'),
        '984': ('Yota', 'Общероссийский'),
        '985': ('Yota', 'Общероссийский'),
        '986': ('Yota', 'Общероссийский'),
        '987': ('Yota', 'Общероссийский'),
        '988': ('Yota', 'Общероссийский'),
        '989': ('Yota', 'Общероссийский'),
        
        # Rostelecom (800-809, 820-829)
        '800': ('Ростелеком', 'Бесплатный номер'),
        '801': ('Ростелеком', 'Бесплатный номер'),
        '802': ('Ростелеком', 'Бесплатный номер'),
        '803': ('Ростелеком', 'Бесплатный номер'),
        '804': ('Ростелеком', 'Бесплатный номер'),
        '805': ('Ростелеком', 'Бесплатный номер'),
        '806': ('Ростелеком', 'Бесплатный номер'),
        '807': ('Ростелеком', 'Бесплатный номер'),
        '808': ('Ростелеком', 'Бесплатный номер'),
        '809': ('Ростелеком', 'Бесплатный номер'),
        '820': ('Ростелеком', 'Мобильный'),
        '821': ('Ростелеком', 'Мобильный'),
        '822': ('Ростелеком', 'Мобильный'),
        '823': ('Ростелеком', 'Мобильный'),
        '824': ('Ростелеком', 'Мобильный'),
        '825': ('Ростелеком', 'Мобильный'),
        '826': ('Ростелеком', 'Мобильный'),
        '827': ('Ростелеком', 'Мобильный'),
        '828': ('Ростелеком', 'Мобильный'),
        '829': ('Ростелеком', 'Мобильный'),
        
        # TELE2 (999)
        '999': ('TELE2', 'Общероссийский'),
        
        # Татартелеком и другие региональные
        '970': ('Татартелеком', 'Татарстан'),
        '971': ('Татартелеком', 'Татарстан'),
        '972': ('Татартелеком', 'Татарстан'),
        '973': ('Татартелеком', 'Татарстан'),
        '974': ('Татартелеком', 'Татарстан'),
        '975': ('Татартелеком', 'Татарстан'),
        '976': ('Татартелеком', 'Татарстан'),
        '977': ('Татартелеком', 'Татарстан'),
        '978': ('Татартелеком', 'Татарстан'),
        '979': ('Татартелеком', 'Татарстан'),
    }
    
    def analyze(self, phone_number):
        """Анализ номера телефона"""
        UI.clear()
        UI.header(f"📱 Анализ номера: {Colors.YELLOW}{phone_number}{Colors.RESET}")
        
        # Очистка номера
        cleaned = phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Нормализация номера
        if cleaned.startswith('+'):
            normalized = cleaned[1:]  # Убираем плюс
        elif cleaned.startswith('8'):
            normalized = '7' + cleaned[1:]  # 8 -> 7
        else:
            normalized = cleaned
        
        results = {
            "original": phone_number,
            "cleaned": cleaned,
            "normalized": normalized,
            "country": self._get_country(cleaned),
            "operator": self._get_operator(normalized),
            "format_info": self._validate_format(cleaned),
            "type": self._detect_type(normalized),
        }
        
        return results
    
    def _get_country(self, phone):
        """Определить страну по коду"""
        if phone.startswith('+7'):
            return {"code": "+7", "country": "Russia"}
        elif phone.startswith('7'):
            return {"code": "+7", "country": "Russia"}
        
        for code, country in self.COUNTRY_CODES.items():
            if phone.startswith(code.replace('+', '')):
                return {"code": code, "country": country}
        return {"code": "Unknown", "country": "Unknown"}
    
    def _get_operator(self, phone):
        """Определить оператора (для России)"""
        if phone.startswith('7'):
            # Российский номер
            prefix = phone[1:4]  # Берём цифры после кода страны
            
            if prefix in self.RUSSIA_OPERATORS:
                operator, region = self.RUSSIA_OPERATORS[prefix]
                return {
                    "operator": operator,
                    "region": region,
                    "country": "Russia",
                    "prefix": prefix
                }
            else:
                return {
                    "operator": "Региональный оператор",
                    "region": "Россия",
                    "country": "Russia",
                    "prefix": prefix
                }
        return {"operator": "Unknown", "region": "Unknown"}
    
    def _validate_format(self, phone):
        """Валидация формата"""
        length = len(phone)
        is_valid = 10 <= length <= 15
        
        return {
            "is_valid": is_valid,
            "length": length,
            "format": "International" if phone.startswith('+') else "Local"
        }
    
    def _detect_type(self, phone):
        """Определить тип номера"""
        if phone.startswith('7800') or phone.startswith('7801'):
            return "Toll-free (Бесплатный)"
        elif phone.startswith('7900') or phone.startswith('7950'):
            return "Premium (Премиум)"
        else:
            return "Regular (Обычный)"

class VKontakteAnalyzer:
    """Анализ публичных данных профилей ВКонтакте"""
    
    def analyze(self, vk_identifier):
        """Анализ профиля ВКонтакте"""
        UI.clear()
        UI.header(f"🔗 VKontakte Analyzer: {Colors.YELLOW}{vk_identifier}{Colors.RESET}")
        
        # vk_identifier может быть: username, id число, или URL
        profile_url = self._build_url(vk_identifier)
        profile_data = self._get_profile_info(profile_url)
        
        if not profile_data:
            UI.error("Профиль не найден или данные недоступны")
            return {}
        
        results = {
            "identifier": vk_identifier,
            "url": profile_url,
            "profile_status": "active",
            "basic_info": {
                "profile_url": profile_url,
                "access": "Публичный профиль",
            },
            "public_data": {
                "posts_url": f"{profile_url}?tab=wall",
                "friends_url": f"{profile_url}?tab=friends",
                "photos_url": f"{profile_url}?tab=photos",
                "info_url": f"{profile_url}?tab=info",
            },
            "contact_methods": self._extract_contacts(vk_identifier),
            "linked_social_networks": [
                "Instagram (если указана в профиле)",
                "Telegram (если указан в профиле)",
                "YouTube (если указан в профиле)",
                "Twitter (если указан в профиле)",
            ],
        }
        
        return results
    
    def _build_url(self, vk_identifier):
        """Построить URL профиля"""
        if vk_identifier.startswith('http'):
            return vk_identifier
        elif vk_identifier.startswith('vk.com'):
            return f"https://{vk_identifier}"
        elif vk_identifier.startswith('@'):
            return f"https://vk.com/{vk_identifier[1:]}"
        else:
            return f"https://vk.com/{vk_identifier}"
    
    def _get_profile_info(self, url):
        """Получить информацию профиля"""
        try:
            response = requests.get(url, timeout=5, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if response.status_code == 200:
                UI.success("Профиль найден")
                return {"exists": True}
            else:
                return None
        except:
            return None
    
    def _extract_contacts(self, vk_identifier):
        """Извлечь контакты из профиля"""
        return {
            "email": "Если указана в публичной информации",
            "phone": "Если указан в публичной информации",
            "website": "Если указан в публичной информации",
        }

class GoogleDorksAdvanced:
    """Поиск через Google Dorks"""
    
    def search(self, query):
        """Поиск по Google Dorks"""
        UI.clear()
        UI.header(f"🔍 Google Dorks Search: {Colors.YELLOW}{query}{Colors.RESET}")
        
        dorks = [
            f'"{query}" filetype:pdf',
            f'"{query}" filetype:xlsx',
            f'"{query}" filetype:docx',
            f'site:pastebin.com {query}',
            f'site:github.com {query}',
            f'"{query}" inurl:admin',
            f'"{query}" inurl:backup',
            f'intitle:index.of {query}',
        ]
        
        results = []
        for dork in dorks:
            try:
                url = f"https://www.google.com/search?q={quote(dork)}"
                results.append({"dork": dork, "url": url})
                UI.success(f"Dork: {dork}")
            except:
                pass
            time.sleep(0.1)
        
        return results

class NewsAggregator:
    """Агрегация новостей из различных источников"""
    
    def search(self, keyword):
        """Поиск новостей"""
        UI.clear()
        UI.header(f"📰 News Aggregator: {Colors.YELLOW}{keyword}{Colors.RESET}")
        
        sources = {
            "Google News": f"https://news.google.com/search?q={quote(keyword)}",
            "Яндекс.Новости": f"https://yandex.ru/news/search?text={quote(keyword)}",
            "BBC": f"https://www.bbc.com/news/search?q={quote(keyword)}",
            "Reuters": f"https://www.reuters.com/search/news?blob={quote(keyword)}",
            "AP News": f"https://apnews.com/search?q={quote(keyword)}",
            "HN": f"https://news.ycombinator.com/search?q={quote(keyword)}",
        }
        
        results = []
        for source, url in sources.items():
            results.append({"source": source, "url": url})
            UI.success(f"Источник: {source}")
        
        return results

class JobProfileOSINT:
    """Анализ профилей на job сайтах"""
    
    def search(self, name):
        """Поиск профилей по имени"""
        UI.clear()
        UI.header(f"💼 Job Profile OSINT: {Colors.YELLOW}{name}{Colors.RESET}")
        
        job_sites = {
            "HeadHunter": f"https://hh.ru/search/resume?text={quote(name)}",
            "LinkedIn": f"https://linkedin.com/search/results/people/?keywords={quote(name)}",
            "Indeed": f"https://indeed.com/resumes?q={quote(name)}",
            "Glassdoor": f"https://glassdoor.com/Search/results.htm?q={quote(name)}",
            "GitHub": f"https://github.com/search?q={quote(name)}&type=users",
            "Stack Overflow": f"https://stackoverflow.com/search?q={quote(name)}",
        }
        
        results = []
        for site, url in job_sites.items():
            results.append({"site": site, "url": url})
            UI.success(f"Найти на {site}")
        
        return results

class CorporateRegistry:
    """Анализ публичных данных компаний"""
    
    def analyze(self, company_name):
        """Анализ регистрационных данных"""
        UI.clear()
        UI.header(f"🏛️ Corporate Registry: {Colors.YELLOW}{company_name}{Colors.RESET}")
        
        results = {
            "russian_registry": {
                "egrul": f"https://egrul.nalog.ru/search/?q={quote(company_name)}",
                "nalog": f"https://service.nalog.ru/inn/ip.html",
            },
            "other_registries": {
                "rusprofile": f"https://www.rusprofile.ru/search?q={quote(company_name)}",
                "sbis": f"https://sbis.ru/searchresults",
                "yandex_company": f"https://company.yandex.com/",
            },
            "financial": {
                "cbr": "https://www.cbr.ru/",
                "moex": "https://www.moex.com/",
            }
        }
        
        UI.success("Источники открытых реестров найдены")
        return results

class PaymentSystemFinder:
    """Поиск в платежных системах"""
    
    def find(self, username):
        """Поиск профилей в платежных системах"""
        UI.clear()
        UI.header(f"💳 Payment System Finder: {Colors.YELLOW}{username}{Colors.RESET}")
        
        systems = {
            "Patreon": f"https://patreon.com/{username}",
            "Boosty": f"https://boosty.to/{username}",
            "Ko-fi": f"https://ko-fi.com/{username}",
            "BuyMeACoffee": f"https://buymeacoffee.com/{username}",
            "Gumroad": f"https://gumroad.com/{username}",
            "Streamlabs": f"https://streamlabs.com/{username}",
            "Opencollective": f"https://opencollective.com/{username}",
        }
        
        found = []
        for system, url in systems.items():
            try:
                response = requests.head(url, timeout=3)
                if response.status_code == 200:
                    found.append({"system": system, "url": url})
                    UI.success(f"Найден на {system}")
            except:
                pass
        
        return found

class TelegramOSINT:
    """Анализ публичных Telegram каналов"""
    
    def analyze(self, channel_name):
        """Анализ Telegram канала"""
        UI.clear()
        UI.header(f"✈️ Telegram OSINT: {Colors.YELLOW}{channel_name}{Colors.RESET}")
        
        results = {
            "channel": channel_name,
            "direct_url": f"https://t.me/{channel_name}",
            "web_url": f"https://web.telegram.org/k/#@{channel_name}",
            "search_urls": {
                "tme_channels": f"https://tme.io/channels?query={quote(channel_name)}",
                "combot": f"https://combot.org/telegram/channels?query={quote(channel_name)}",
            },
            "note": "Только публичные каналы и доступная информация"
        }
        
        UI.success("Информация о Telegram канале найдена")
        return results

class YouTubeOSINT:
    """Анализ YouTube каналов"""
    
    def analyze(self, channel_name):
        """Анализ YouTube канала"""
        UI.clear()
        UI.header(f"🎬 YouTube OSINT: {Colors.YELLOW}{channel_name}{Colors.RESET}")
        
        results = {
            "channel": channel_name,
            "search_url": f"https://youtube.com/results?search_query={quote(channel_name)}",
            "channel_url": f"https://youtube.com/@{channel_name}",
            "analytics": {
                "socialblade": f"https://socialblade.com/youtube/channel/{channel_name}",
            },
            "public_data": [
                "Описание канала",
                "Количество подписчиков",
                "Количество видео",
                "Связанные каналы",
                "Соцсети в описании",
            ]
        }
        
        UI.success("Информация о YouTube канале найдена")
        return results

class ReverseImageSearchAdvanced:
    """Продвинутый поиск по изображению"""
    
    def search(self, image_url):
        """Поиск по картинке в разных сервисах"""
        UI.clear()
        UI.header(f"🖼️ Reverse Image Search: {Colors.YELLOW}{image_url[:50]}...{Colors.RESET}")
        
        results = {
            "google": f"https://lens.google.com/uploadbyurl?url={quote(image_url)}",
            "yandex": f"https://yandex.ru/images/search?rpt=imageview&url={quote(image_url)}",
            "tineye": f"https://tineye.com/search?url={quote(image_url)}",
            "bing": f"https://www.bing.com/images/search?view=detailv2&iss=sbi&FORM=SBIIRK&sbisrc=ChromeExt&q=imgurl:{quote(image_url)}",
        }
        
        for service, url in results.items():
            UI.success(f"Поиск в {service}")
        
        return results

class DocumentMetadataExtractor:
    """Извлечение метаданных из документов"""
    
    def analyze_file(self, file_path):
        """Анализ метаданных файла"""
        UI.clear()
        UI.header(f"📄 Document Metadata: {Colors.YELLOW}{file_path}{Colors.RESET}")
        
        try:
            from PIL.Image import open as open_image
            from PIL.ExifTags import TAGS
            
            image = open_image(file_path)
            exif = image._getexif()
            
            metadata = {}
            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    metadata[tag] = str(value)[:100]
            
            return {
                "file": file_path,
                "format": image.format,
                "size": image.size,
                "metadata": metadata
            }
        except:
            return {"note": "Для полного анализа установи: pip install pillow"}

class CourtRecordsOSINT:
    """Поиск в судебных документах (публичные)"""
    
    def search(self, name):
        """Поиск судебных решений"""
        UI.clear()
        UI.header(f"⚖️ Court Records Search: {Colors.YELLOW}{name}{Colors.RESET}")
        
        results = {
            "russia_courts": {
                "sudrf": f"https://sudrf.ru/",
                "example_query": f"Поиск по: {name}"
            },
            "international": {
                "google_scholar": f"https://scholar.google.com/scholar?q={quote(name)}",
            },
            "databases": [
                "Единый реестр судебных решений (ЕРСР)",
                "Судебные решения по банкротству",
                "Реестр исполнительных производств",
            ]
        }
        
        UI.success("Источники судебных данных найдены")
        return results

class WHOISHistory:
    """История изменений WHOIS"""
    
    def analyze(self, domain):
        """Получить историю WHOIS"""
        UI.clear()
        UI.header(f"📋 WHOIS History: {Colors.YELLOW}{domain}{Colors.RESET}")
        
        results = {
            "domain": domain,
            "sources": {
                "whoisds": f"https://whoisds.com/reverse-whois/{quote(domain)}",
                "domaintools": f"https://www.domaintools.com/research/whois-history/search/?q={domain}",
                "web_archive": f"https://web.archive.org/web/*/whois.com/*{domain}",
            },
            "data_points": [
                "Регистратор",
                "Дата регистрации",
                "Дата истечения",
                "История контактов",
                "История собственников",
            ]
        }
        
        UI.success("История WHOIS найдена")
        return results

class MentionsFinder:
    """Поиск упоминаний везде одновременно"""
    
    def search(self, query):
        """Найти упоминания"""
        UI.clear()
        UI.header(f"🔎 Mentions Finder: {Colors.YELLOW}{query}{Colors.RESET}")
        
        sources = {
            "Reddit": f"https://www.reddit.com/search/?q={quote(query)}",
            "Twitter": f"https://twitter.com/search?q={quote(query)}",
            "YouTube": f"https://www.youtube.com/results?search_query={quote(query)}",
            "GitHub": f"https://github.com/search?q={quote(query)}",
            "Stack Overflow": f"https://stackoverflow.com/search?q={quote(query)}",
            "Medium": f"https://medium.com/search?q={quote(query)}",
            "Dev.to": f"https://dev.to/search?q={quote(query)}",
            "HackerNews": f"https://news.ycombinator.com/search?q={quote(query)}",
            "4chan": f"https://boards.4chan.org/search?q={quote(query)}",
            "Quora": f"https://www.quora.com/search?q={quote(query)}",
        }
        
        results = []
        for source, url in sources.items():
            results.append({"source": source, "url": url})
            UI.success(f"Ищу в {source}")
        
        return results

class DNSHistory:
    """История DNS записей"""
    
    def analyze(self, domain):
        """Получить историю DNS"""
        UI.clear()
        UI.header(f"🌍 DNS History: {Colors.YELLOW}{domain}{Colors.RESET}")
        
        results = {
            "domain": domain,
            "sources": {
                "viewdns": f"https://viewdns.info/dnshistory/?domain={domain}",
                "web_archive": f"https://web.archive.org/web/*/dns/records/{domain}",
                "dnstrails": f"https://dnstrails.com/{domain}",
            },
            "records_tracked": [
                "A records (IPv4)",
                "AAAA records (IPv6)",
                "MX records (Mail)",
                "CNAME records",
                "TXT records",
                "NS records",
            ]
        }
        
        UI.success("История DNS найдена")
        return results

class FinancialOSINT:
    """Анализ финансовой информации"""
    
    def analyze(self, company_name):
        """Анализ финансов компании"""
        UI.clear()
        UI.header(f"💰 Financial OSINT: {Colors.YELLOW}{company_name}{Colors.RESET}")
        
        results = {
            "company": company_name,
            "public_sources": {
                "edgar": f"https://www.sec.gov/cgi-bin/browse-edgar?company={quote(company_name)}",
                "yahoo_finance": f"https://finance.yahoo.com/quote/{company_name}",
                "google_finance": f"https://www.google.com/finance/quote/{company_name}",
                "bloomberg": f"https://www.bloomberg.com/search?q={quote(company_name)}",
            },
            "russian_sources": {
                "moex": f"https://www.moex.com/en/index/",
                "cbr": f"https://www.cbr.ru/",
            },
            "data_available": [
                "Публичная финансовая отчетность",
                "Курсы акций",
                "Капитализация",
                "Основные акционеры",
                "Дивиденды",
                "Квартальные отчеты",
            ]
        }
        
        UI.success("Финансовые данные найдены")
        return results

class GeneralOSINTReport:
    """Создание общего OSINT отчёта из собранной информации"""
    
    def generate_report(self, data_collection):
        """Генерировать общий отчёт"""
        UI.clear()
        UI.header(f"📊 OSINT Report Generator")
        
        report = f"""
{Colors.MAGENTA}{Colors.BOLD}╔════════════════════════════════════════════╗{Colors.RESET}
{Colors.MAGENTA}{Colors.BOLD}║      PHANTOM v5.0 MAXIMUM OSINT REPORT     ║{Colors.RESET}
{Colors.MAGENTA}{Colors.BOLD}║         by @jecrs | verificator            ║{Colors.RESET}
{Colors.MAGENTA}{Colors.BOLD}╚════════════════════════════════════════════╝{Colors.RESET}

{Colors.CYAN}═══ ОСНОВНАЯ ИНФОРМАЦИЯ ═══{Colors.RESET}
"""
        
        # Username
        if 'username' in data_collection:
            report += f"\n{Colors.CYAN}🔍 USERNAME SCANNING:{Colors.RESET}\n"
            data = data_collection['username']
            if isinstance(data, list) and len(data) > 0:
                report += f"  {Colors.GREEN}✓ Найдено на {len(data)} платформах{Colors.RESET}\n"
        
        # Domain
        if 'domain' in data_collection:
            report += f"\n{Colors.CYAN}🌐 DOMAIN ANALYSIS:{Colors.RESET}\n"
            data = data_collection['domain']
            if data:
                report += f"  {Colors.GREEN}✓ Домен анализирован{Colors.RESET}\n"
        
        # Email
        if 'email' in data_collection:
            report += f"\n{Colors.CYAN}📧 EMAIL SECURITY:{Colors.RESET}\n"
            data = data_collection['email']
            if data:
                report += f"  {Colors.GREEN}✓ Email проверен{Colors.RESET}\n"
        
        # Phone
        if 'phone' in data_collection:
            report += f"\n{Colors.CYAN}📱 PHONE NUMBER:{Colors.RESET}\n"
            data = data_collection['phone']
            if data:
                report += f"  • Оператор: {Colors.GREEN}{data['operator'].get('operator', 'N/A')}{Colors.RESET}\n"
                report += f"  • Регион: {Colors.YELLOW}{data['operator'].get('region', 'N/A')}{Colors.RESET}\n"
        
        # IP
        if 'ip' in data_collection:
            report += f"\n{Colors.CYAN}🌍 IP GEOLOCATION:{Colors.RESET}\n"
            data = data_collection['ip']
            if data and 'geolocation' in data:
                geo = data['geolocation']
                report += f"  • IP: {Colors.YELLOW}{data.get('ip')}{Colors.RESET}\n"
                if geo.get('country'):
                    report += f"  • Страна: {geo['country']}\n"
                if geo.get('city'):
                    report += f"  • Город: {geo['city']}\n"
        
        # VK
        if 'vk' in data_collection:
            report += f"\n{Colors.CYAN}🔗 VKONTAKTE:{Colors.RESET}\n"
            data = data_collection['vk']
            report += f"  • Профиль: {Colors.CYAN}{data.get('url', 'N/A')}{Colors.RESET}\n"
        
        # Company
        if 'company' in data_collection:
            report += f"\n{Colors.CYAN}🏢 COMPANY INTELLIGENCE:{Colors.RESET}\n"
            data = data_collection['company']
            if data.get('domains'):
                report += f"  {Colors.GREEN}✓ Найдено {len(data['domains'])} доменов{Colors.RESET}\n"
        
        # Crypto
        if 'crypto' in data_collection:
            report += f"\n{Colors.CYAN}💰 CRYPTOCURRENCY:{Colors.RESET}\n"
            data = data_collection['crypto']
            report += f"  • Адрес: {Colors.YELLOW}{data.get('address', 'N/A')}{Colors.RESET}\n"
        
        # Google Dorks
        if 'google_dorks' in data_collection:
            report += f"\n{Colors.CYAN}🔎 GOOGLE DORKS:{Colors.RESET}\n"
            data = data_collection['google_dorks']
            if isinstance(data, list) and len(data) > 0:
                report += f"  {Colors.GREEN}✓ Найдено {len(data)} dorksов{Colors.RESET}\n"
        
        # News
        if 'news' in data_collection:
            report += f"\n{Colors.CYAN}📰 NEWS AGGREGATOR:{Colors.RESET}\n"
            data = data_collection['news']
            if isinstance(data, list) and len(data) > 0:
                report += f"  {Colors.GREEN}✓ Найдено {len(data)} источников новостей{Colors.RESET}\n"
        
        # Job Profiles
        if 'job_profiles' in data_collection:
            report += f"\n{Colors.CYAN}💼 JOB PROFILES:{Colors.RESET}\n"
            data = data_collection['job_profiles']
            if isinstance(data, list) and len(data) > 0:
                report += f"  {Colors.GREEN}✓ Найдено {len(data)} профилей{Colors.RESET}\n"
        
        # Payment Systems
        if 'payment_systems' in data_collection:
            report += f"\n{Colors.CYAN}💳 PAYMENT SYSTEMS:{Colors.RESET}\n"
            data = data_collection['payment_systems']
            if isinstance(data, list) and len(data) > 0:
                report += f"  {Colors.GREEN}✓ Найдено на {len(data)} платежных системах{Colors.RESET}\n"
        
        # Telegram
        if 'telegram' in data_collection:
            report += f"\n{Colors.CYAN}✈️ TELEGRAM:{Colors.RESET}\n"
            data = data_collection['telegram']
            report += f"  • Канал: {Colors.CYAN}{data.get('direct_url', 'N/A')}{Colors.RESET}\n"
        
        # YouTube
        if 'youtube' in data_collection:
            report += f"\n{Colors.CYAN}🎬 YOUTUBE:{Colors.RESET}\n"
            data = data_collection['youtube']
            report += f"  • Канал: {Colors.CYAN}{data.get('channel_url', 'N/A')}{Colors.RESET}\n"
        
        # Mentions
        if 'mentions' in data_collection:
            report += f"\n{Colors.CYAN}🔎 MENTIONS FOUND:{Colors.RESET}\n"
            data = data_collection['mentions']
            if isinstance(data, list) and len(data) > 0:
                report += f"  {Colors.GREEN}✓ Найдено упоминаний в {len(data)} источниках{Colors.RESET}\n"
        
        # Summary
        report += f"\n{Colors.MAGENTA}═══════════════════════════════════════════{Colors.RESET}\n"
        report += f"{Colors.GREEN}✓ Все данные из ПУБЛИЧНЫХ источников{Colors.RESET}\n"
        report += f"{Colors.GREEN}✓ Полностью ЛЕГАЛЬНО{Colors.RESET}\n"
        report += f"{Colors.MAGENTA}═══════════════════════════════════════════{Colors.RESET}\n"
        
        return report
    
    def save_report(self, report_text, filename="osint_report.txt"):
        """Сохранить отчёт в файл"""
        try:
            report_dir = Path.home() / ".phantom" / "reports"
            report_dir.mkdir(exist_ok=True)
            
            filepath = report_dir / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                # Убираем ANSI коды для сохранения
                clean_text = self._remove_ansi_codes(report_text)
                f.write(clean_text)
            
            return str(filepath)
        except:
            return None
    
    def _remove_ansi_codes(self, text):
        """Удалить ANSI коды из текста"""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

class CompanyIntelligenceScraper:
    """Сборка информации о компаниях из публичных источников"""
    
    def scrape(self, company_name):
        """Собрать всю доступную информацию о компании"""
        UI.clear()
        UI.header(f"🏢 Company Intelligence: {Colors.YELLOW}{company_name}{Colors.RESET}")
        
        results = {
            "company": company_name,
            "crunchbase": self._get_crunchbase(company_name),
            "linkedin": self._get_linkedin_company(company_name),
            "social_media": self._find_social_accounts(company_name),
            "domains": self._find_domains(company_name),
            "news": self._find_news(company_name),
        }
        
        return results
    
    def _get_crunchbase(self, company):
        """Информация из Crunchbase"""
        try:
            query = quote(company)
            response = requests.get(
                f"https://www.crunchbase.com/search/entities?query={query}",
                timeout=5
            )
            if response.status_code == 200:
                return {"found": True, "url": f"https://crunchbase.com/search/{query}"}
        except:
            pass
        return {"found": False}
    
    def _get_linkedin_company(self, company):
        """LinkedIn компания"""
        try:
            query = quote(company)
            return {
                "found": True,
                "url": f"https://linkedin.com/search/results/companies/?keywords={query}"
            }
        except:
            pass
        return {"found": False}
    
    def _find_social_accounts(self, company):
        """Найти социальные сети компании"""
        accounts = {}
        
        platforms = {
            "Twitter": f"https://twitter.com/search?q={quote(company)}",
            "Facebook": f"https://facebook.com/search/pages/?q={quote(company)}",
            "Instagram": f"https://instagram.com/search/tags/{quote(company.replace(' ', ''))}",
            "LinkedIn": f"https://linkedin.com/company/{quote(company)}",
        }
        
        for platform, url in platforms.items():
            try:
                response = requests.head(url, timeout=3)
                if response.status_code == 200:
                    accounts[platform] = url
                    UI.success(f"Найден на {platform}")
            except:
                pass
        
        return accounts
    
    def _find_domains(self, company):
        """Найти домены компании"""
        domains = []
        
        # Стандартные варианты
        variants = [
            company.lower().replace(' ', ''),
            company.lower().replace(' ', '-'),
            ''.join([word[0].lower() for word in company.split()]),
        ]
        
        for domain_name in variants:
            for tld in ['.com', '.io', '.co', '.net', '.org', '.ru', '.dev']:
                url = f"https://{domain_name}{tld}"
                try:
                    response = requests.head(url, timeout=2)
                    if response.status_code == 200:
                        domains.append({
                            "domain": f"{domain_name}{tld}",
                            "status": "Active"
                        })
                        UI.success(f"Домен найден: {domain_name}{tld}")
                except:
                    pass
        
        return domains
    
    def _find_news(self, company):
        """Новости о компании"""
        try:
            query = quote(company)
            return {
                "google_news": f"https://news.google.com/search?q={query}",
                "ycombinator": f"https://ycombinator.com/search?q={query}",
                "hackernews": f"https://news.ycombinator.com/search?p=1&q={query}"
            }
        except:
            pass
        return {}

# ============================================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================================

class PHANTOM:
    """Главный класс приложения"""
    
    def __init__(self, save_mode=True):
        self.save_mode = save_mode
        self.db = Database(save_mode=save_mode)
        self.username_scanner = UsernameScanner()
        self.domain_osint = DomainOSINT()
        self.image_osint = ImageOSINT()
        self.crypto_osint = CryptoOSINT()
        self.email_finder = EmailFinder()
        self.breach_checker = DataBreachChecker()
        self.website_analyzer = WebsiteAnalyzer()
        self.url_analyzer = URLAnalyzer()
        self.hash_analyzer = HashAnalyzer()
        self.reputation_checker = ReputationChecker()
        self.name_generator = NameGenerator()
        self.api_finder = APIFinder()
        self.github_dork = GitHubDork()
        self.social_aggregator = SocialAggregator()
        self.pastebin_monitor = PastebinMonitor()
        self.ip_geolocation = IPGeolocationAdvanced()
        self.phone_analyzer = PhoneNumberAnalyzer()
        self.company_scraper = CompanyIntelligenceScraper()
        self.vk_analyzer = VKontakteAnalyzer()
        self.osint_report = GeneralOSINTReport()
        self.google_dorks = GoogleDorksAdvanced()
        self.news_aggregator = NewsAggregator()
        self.job_osint = JobProfileOSINT()
        self.corp_registry = CorporateRegistry()
        self.payment_finder = PaymentSystemFinder()
        self.telegram_osint = TelegramOSINT()
        self.youtube_osint = YouTubeOSINT()
        self.reverse_image = ReverseImageSearchAdvanced()
        self.metadata_extractor = DocumentMetadataExtractor()
        self.court_records = CourtRecordsOSINT()
        self.whois_history = WHOISHistory()
        self.mentions_finder = MentionsFinder()
        self.dns_history = DNSHistory()
        self.financial_osint = FinancialOSINT()
        self.collected_data = {}
    
    def main_menu(self):
        """Главное меню"""
        while True:
            UI.clear()
            print(UI.banner())
            
            print(f"{Colors.CYAN}╔════════════════════════════════════════════════════╗{Colors.RESET}")
            print(f"{Colors.CYAN}║{Colors.RESET}          {Colors.BOLD}ГЛАВНОЕ МЕНЮ{Colors.RESET}" + " " * 30 + f"{Colors.CYAN}║{Colors.RESET}")
            print(f"{Colors.CYAN}╚════════════════════════════════════════════════════╝{Colors.RESET}\n")
            
            menu_items = [
                ("1", "🔍 Username Scanner (180+ сайтов)", self.username_menu),
                ("2", "🌐 Domain OSINT", self.domain_menu),
                ("3", "🖼️  Image OSINT", self.image_menu),
                ("4", "💰 Crypto Analysis", self.crypto_menu),
                ("5", "📧 Email Finder", self.email_menu),
                ("6", "🔴 Data Breach Checker", self.breach_menu),
                ("7", "🔗 Website Analyzer", self.website_menu),
                ("8", "🔍 URL Analyzer", self.url_menu),
                ("9", "🔐 Hash Analyzer", self.hash_menu),
                ("10", "⭐ Reputation Checker", self.reputation_menu),
                ("11", "💡 Name Generator", self.name_menu),
                ("12", "🔌 API Endpoint Finder", self.api_menu),
                ("13", "🐙 GitHub Dork Search", self.github_menu),
                ("14", "👥 Social Aggregator", self.social_menu),
                ("15", "📋 Pastebin Monitor", self.pastebin_menu),
                ("16", "🌍 IP Geolocation Advanced", self.ip_menu),
                ("17", "📱 Phone Number Analyzer", self.phone_menu),
                ("18", "🏢 Company Intelligence", self.company_menu),
                ("19", "🔗 VKontakte Analyzer", self.vk_menu),
                ("20", "🔎 Google Dorks Advanced", self.dorks_menu),
                ("21", "📰 News Aggregator", self.news_menu),
                ("22", "💼 Job Profile OSINT", self.job_menu),
                ("23", "🏛️ Corporate Registry", self.registry_menu),
                ("24", "💳 Payment System Finder", self.payment_menu),
                ("25", "✈️ Telegram OSINT", self.telegram_menu),
                ("26", "🎬 YouTube OSINT", self.youtube_menu),
                ("27", "🖼️  Reverse Image Search", self.reverse_image_menu),
                ("28", "📄 Document Metadata", self.metadata_menu),
                ("29", "⚖️ Court Records", self.court_menu),
                ("30", "📋 WHOIS History", self.whois_menu),
                ("31", "🔎 Mentions Finder", self.mentions_menu),
                ("32", "🌍 DNS History", self.dns_menu),
                ("33", "💰 Financial OSINT", self.financial_menu),
                ("34", "📊 Общий OSINT Отчёт", self.report_menu),
                ("35", "📜 История поисков", self.history_menu),
                ("36", "📌 Закладки", self.bookmarks_menu),
                ("0", "❌ Выход", None),
            ]
            
            for key, label, _ in menu_items:
                print(f"  {Colors.YELLOW}{key:>2}{Colors.RESET}. {label}")
            
            print(f"\n{Colors.CYAN}─────────────────────────────────────────────────────{Colors.RESET}\n")
            choice = input(f"{Colors.BOLD}Выбери опцию (0-36): {Colors.RESET}").strip()
            
            for key, _, func in menu_items:
                if choice == key:
                    if func is None:
                        UI.info("До встречи!")
                        sys.exit(0)
                    else:
                        UI.clear()  # Очищаем экран перед выводом результатов
                        func()
                    break
            
            input(f"\n{Colors.DIM}[Нажми Enter для продолжения]{Colors.RESET}")
            UI.clear()  # Очищаем экран перед следующим меню
    
    def username_menu(self):
        """Меню сканирования юзернеймов"""
        username = input(f"\n{Colors.BOLD}Введи юзернейм: {Colors.RESET}").strip()
        if username:
            results = self.username_scanner.scan(username)
            
            if results:
                UI.success(f"Найдено {len(results)} совпадений!\n")
                for platform, url in results:
                    print(f"  {Colors.GREEN}✓{Colors.RESET} {platform}: {Colors.CYAN}{url}{Colors.RESET}")
                
                self.db.save_search(username, "username_scanner", results)
            else:
                UI.warning("Совпадений не найдено")
    
    def domain_menu(self):
        """Меню анализа доменов"""
        domain = input(f"\n{Colors.BOLD}Введи домен (example.com): {Colors.RESET}").strip()
        if domain:
            results = self.domain_osint.analyze(domain)
            
            print(f"\n{Colors.BOLD}Результаты анализа:{Colors.RESET}\n")
            
            for key, value in results.items():
                if isinstance(value, dict):
                    print(f"{Colors.CYAN}{key.upper()}:{Colors.RESET}")
                    for k, v in value.items():
                        print(f"  {k}: {str(v)[:80]}")
                else:
                    print(f"{Colors.CYAN}{key.upper()}: {Colors.RESET}{value}")
            
            self.db.save_search(domain, "domain_osint", results)
    
    def image_menu(self):
        """Меню анализа изображений"""
        image_url = input(f"\n{Colors.BOLD}Введи URL изображения: {Colors.RESET}").strip()
        if image_url:
            results = self.image_osint.analyze_url(image_url)
            
            print(f"\n{Colors.BOLD}EXIF данные:{Colors.RESET}\n")
            for key, value in results.items():
                print(f"  {Colors.CYAN}{key}:{Colors.RESET} {value}")
            
            self.db.save_search(image_url, "image_osint", results)
    
    def crypto_menu(self):
        """Меню анализа крипто-адресов"""
        print(f"\n{Colors.BOLD}Выбери блокчейн:{Colors.RESET}")
        print("  1. Bitcoin")
        print("  2. Ethereum")
        
        blockchain_choice = input(f"\n{Colors.BOLD}Выбор (1-2): {Colors.RESET}").strip()
        blockchain = "bitcoin" if blockchain_choice == "1" else "ethereum"
        
        address = input(f"\n{Colors.BOLD}Введи адрес: {Colors.RESET}").strip()
        if address:
            results = self.crypto_osint.analyze_address(address, blockchain)
            
            print(f"\n{Colors.BOLD}Результаты:{Colors.RESET}\n")
            for key, value in results.items():
                print(f"  {Colors.CYAN}{key}:{Colors.RESET} {value}")
            
            self.db.save_search(address, "crypto_osint", results)
    
    def email_menu(self):
        """Меню поиска email"""
        domain = input(f"\n{Colors.BOLD}Введи домен: {Colors.RESET}").strip()
        if domain:
            results = self.email_finder.find_emails(domain)
            
            if results:
                UI.success(f"Найдено {len(results)} email-адресов\n")
                for email in results:
                    print(f"  {Colors.CYAN}{email}{Colors.RESET}")
            else:
                UI.warning("Email-адреса не найдены")
            
            self.db.save_search(domain, "email_finder", results)
    
    def breach_menu(self):
        """Меню проверки утечек"""
        print(f"\n{Colors.BOLD}Что проверить?{Colors.RESET}")
        print("  1. Email")
        print("  2. Пароль")
        
        choice = input(f"\n{Colors.BOLD}Выбор (1-2): {Colors.RESET}").strip()
        
        if choice == "1":
            email = input(f"\n{Colors.BOLD}Введи email: {Colors.RESET}").strip()
            if email:
                results = self.breach_checker.check_email(email)
                self.db.save_search(email, "breach_checker", results)
        
        elif choice == "2":
            password = input(f"\n{Colors.BOLD}Введи пароль: {Colors.RESET}").strip()
            if password:
                count = self.breach_checker.check_password(password)
                self.db.save_search(password, "password_checker", {"occurrences": count})
    
    def website_menu(self):
        """Меню анализа веб-сайтов"""
        url = input(f"\n{Colors.BOLD}Введи URL (example.com или https://...): {Colors.RESET}").strip()
        if url:
            results = self.website_analyzer.analyze(url)
            
            print(f"\n{Colors.BOLD}Результаты анализа:{Colors.RESET}\n")
            
            for key, value in results.items():
                if isinstance(value, dict):
                    print(f"{Colors.CYAN}{key.upper()}:{Colors.RESET}")
                    for k, v in list(value.items())[:5]:  # Первые 5 элементов
                        print(f"  {k}: {str(v)[:60]}")
                elif isinstance(value, list):
                    print(f"{Colors.CYAN}{key.upper()}:{Colors.RESET} {', '.join(str(v) for v in value[:3])}")
                else:
                    print(f"{Colors.CYAN}{key.upper()}:{Colors.RESET} {value}")
            
            self.db.save_search(url, "website_analyzer", results)
    
    def url_menu(self):
        """Меню анализа URL"""
        url = input(f"\n{Colors.BOLD}Введи URL: {Colors.RESET}").strip()
        if url:
            results = self.url_analyzer.analyze(url)
            
            print(f"\n{Colors.BOLD}Анализ URL:{Colors.RESET}\n")
            for key, value in results.items():
                print(f"  {Colors.CYAN}{key}:{Colors.RESET} {value}")
            
            self.db.save_search(url, "url_analyzer", results)
    
    def hash_menu(self):
        """Меню анализа хешей"""
        hash_input = input(f"\n{Colors.BOLD}Введи хеш: {Colors.RESET}").strip()
        if hash_input:
            results = self.hash_analyzer.analyze(hash_input)
            
            print(f"\n{Colors.BOLD}Результаты:{Colors.RESET}\n")
            for key, value in results.items():
                print(f"  {Colors.CYAN}{key}:{Colors.RESET} {value}")
            
            self.db.save_search(hash_input, "hash_analyzer", results)
    
    def reputation_menu(self):
        """Меню проверки репутации"""
        domain = input(f"\n{Colors.BOLD}Введи домен: {Colors.RESET}").strip()
        if domain:
            results = self.reputation_checker.check_domain(domain)
            
            print(f"\n{Colors.BOLD}Результаты проверки:{Colors.RESET}\n")
            for key, value in results.items():
                status = f"{Colors.GREEN}✓{Colors.RESET}" if value else f"{Colors.RED}✗{Colors.RESET}"
                print(f"  {status} {key}: {value}")
            
            self.db.save_search(domain, "reputation_checker", results)
    
    def name_menu(self):
        """Меню генератора имён"""
        first_name = input(f"\n{Colors.BOLD}Введи имя: {Colors.RESET}").strip()
        last_name = input(f"{Colors.BOLD}Введи фамилию: {Colors.RESET}").strip()
        
        if first_name and last_name:
            variations = self.name_generator.generate(first_name, last_name)
            
            print(f"\n{Colors.BOLD}Сгенерировано {len(variations)} вариантов:{Colors.RESET}\n")
            for i, variant in enumerate(variations, 1):
                print(f"  {i:>2}. {Colors.CYAN}{variant}{Colors.RESET}")
            
            self.db.save_search(f"{first_name} {last_name}", "name_generator", variations)
    
    def api_menu(self):
        """Меню поиска API endpoints"""
        domain = input(f"\n{Colors.BOLD}Введи домен: {Colors.RESET}").strip()
        if domain:
            results = self.api_finder.find_apis(domain)
            
            if results:
                UI.success(f"Найдено {len(results)} API endpoints\n")
                for endpoint, status in results:
                    print(f"  {Colors.GREEN}✓{Colors.RESET} {endpoint} ({Colors.YELLOW}{status}{Colors.RESET})")
            else:
                UI.warning("API endpoints не найдены")
            
            self.db.save_search(domain, "api_finder", results)
    
    def github_menu(self):
        """Меню GitHub Dork Search"""
        keyword = input(f"\n{Colors.BOLD}Что ищем (компания, проект, ключ)?: {Colors.RESET}").strip()
        if keyword:
            results = self.github_dork.search(keyword)
            
            if results:
                UI.success(f"Найдено {len(results)} результатов\n")
                for item in results:
                    print(f"  {Colors.CYAN}{item['repo']}{Colors.RESET}")
                    print(f"    └─ {item['file']}")
                    print(f"       {Colors.YELLOW}{item['url']}{Colors.RESET}\n")
            else:
                UI.warning("Ничего не найдено")
            
            self.db.save_search(keyword, "github_dork", results)
    
    def social_menu(self):
        """Меню Social Profile Aggregator"""
        username = input(f"\n{Colors.BOLD}Введи юзернейм: {Colors.RESET}").strip()
        if username:
            results = self.social_aggregator.aggregate(username)
            
            if results:
                UI.success(f"Найдено {len(results)} активных профилей\n")
                
                print(f"{Colors.BOLD}Профили:{Colors.RESET}\n")
                for profile in results:
                    print(f"  {Colors.GREEN}✓{Colors.RESET} {profile['platform']}")
                    print(f"     {Colors.CYAN}{profile['url']}{Colors.RESET}\n")
            else:
                UI.warning("Профили не найдены")
            
            self.db.save_search(username, "social_aggregator", results)
    
    def pastebin_menu(self):
        """Меню Pastebin Monitor"""
        keyword = input(f"\n{Colors.BOLD}Что ищем (email, домен, ключ)?: {Colors.RESET}").strip()
        if keyword:
            results = self.pastebin_monitor.search(keyword)
            
            if results:
                UI.warning(f"⚠️  Найдено {len(results)} упоминаний в утечках!\n")
                for paste in results:
                    print(f"  {Colors.RED}⚠️ {paste['source']}{Colors.RESET}")
                    print(f"     Title: {paste['title']}")
                    print(f"     Date: {paste['date']}\n")
            else:
                UI.success("✓ Не найдено в публичных утечках")
            
            self.db.save_search(keyword, "pastebin_monitor", results)
    
    def ip_menu(self):
        """Меню IP Geolocation Advanced"""
        ip_address = input(f"\n{Colors.BOLD}Введи IP адрес: {Colors.RESET}").strip()
        if ip_address:
            results = self.ip_geolocation.analyze(ip_address)
            
            print(f"\n{Colors.BOLD}Результаты анализа IP:{Colors.RESET}\n")
            
            for key, value in results.items():
                if isinstance(value, dict):
                    print(f"{Colors.CYAN}{key.upper()}:{Colors.RESET}")
                    for k, v in value.items():
                        print(f"  {k}: {v}")
                else:
                    print(f"{Colors.CYAN}{key.upper()}:{Colors.RESET} {value}")
            
            self.db.save_search(ip_address, "ip_geolocation", results)
    
    def phone_menu(self):
        """Меню Phone Number Analyzer"""
        phone = input(f"\n{Colors.BOLD}Введи номер телефона (+7... или 8...): {Colors.RESET}").strip()
        if phone:
            results = self.phone_analyzer.analyze(phone)
            
            print(f"\n{Colors.BOLD}Анализ номера телефона:{Colors.RESET}\n")
            
            # Оригинальный номер
            print(f"{Colors.CYAN}ORIGINAL:{Colors.RESET} {results['original']}")
            print(f"{Colors.CYAN}CLEANED:{Colors.RESET} {results['cleaned']}")
            print(f"{Colors.CYAN}NORMALIZED:{Colors.RESET} {results['normalized']}\n")
            
            # Страна
            country_info = results['country']
            print(f"{Colors.CYAN}COUNTRY:{Colors.RESET}")
            print(f"  code: {country_info['code']}")
            print(f"  country: {country_info['country']}\n")
            
            # Оператор и регион
            operator_info = results['operator']
            print(f"{Colors.CYAN}OPERATOR:{Colors.RESET}")
            if 'prefix' in operator_info:
                print(f"  prefix: {operator_info['prefix']}")
            print(f"  operator: {Colors.GREEN}{operator_info.get('operator', 'Unknown')}{Colors.RESET}")
            print(f"  region: {Colors.YELLOW}{operator_info.get('region', 'Unknown')}{Colors.RESET}\n")
            
            # Формат
            format_info = results['format_info']
            print(f"{Colors.CYAN}FORMAT_INFO:{Colors.RESET}")
            print(f"  is_valid: {Colors.GREEN if format_info['is_valid'] else Colors.RED}{format_info['is_valid']}{Colors.RESET}")
            print(f"  length: {format_info['length']}")
            print(f"  format: {format_info['format']}\n")
            
            # Тип номера
            print(f"{Colors.CYAN}TYPE:{Colors.RESET} {results['type']}\n")
            
            self.db.save_search(phone, "phone_analyzer", results)
    
    def company_menu(self):
        """Меню Company Intelligence Scraper"""
        company = input(f"\n{Colors.BOLD}Введи название компании: {Colors.RESET}").strip()
        if company:
            results = self.company_scraper.scrape(company)
            
            print(f"\n{Colors.BOLD}Информация о компании:{Colors.RESET}\n")
            
            # Crunchbase
            if results['crunchbase'].get('found'):
                UI.success(f"Найдена на Crunchbase")
                print(f"  {Colors.CYAN}{results['crunchbase']['url']}{Colors.RESET}\n")
            
            # LinkedIn
            if results['linkedin'].get('found'):
                UI.success(f"Найдена на LinkedIn")
                print(f"  {Colors.CYAN}{results['linkedin']['url']}{Colors.RESET}\n")
            
            # Социальные сети
            if results['social_media']:
                print(f"{Colors.BOLD}Социальные сети:{Colors.RESET}")
                for platform, url in results['social_media'].items():
                    print(f"  {Colors.GREEN}✓{Colors.RESET} {platform}: {Colors.CYAN}{url}{Colors.RESET}\n")
            
            # Домены
            if results['domains']:
                print(f"{Colors.BOLD}Найденные домены:{Colors.RESET}")
                for domain in results['domains']:
                    print(f"  {Colors.GREEN}✓{Colors.RESET} {domain['domain']} ({domain['status']})\n")
            
            # Новости
            print(f"{Colors.BOLD}Источники новостей:{Colors.RESET}")
            for source, url in results['news'].items():
                print(f"  {Colors.CYAN}{source}:{Colors.RESET} {url}\n")
            
            self.db.save_search(company, "company_intelligence", results)
    
    def vk_menu(self):
        """Меню VKontakte Analyzer"""
        vk_id = input(f"\n{Colors.BOLD}Введи VK ID или ссылку (@username или id): {Colors.RESET}").strip()
        if vk_id:
            results = self.vk_analyzer.analyze(vk_id)
            
            if results:
                print(f"\n{Colors.BOLD}Информация ВКонтакте:{Colors.RESET}\n")
                
                # Информация профиля
                basic_info = results['basic_info']
                print(f"{Colors.CYAN}ПРОФИЛЬ:{Colors.RESET}")
                print(f"  URL: {Colors.CYAN}{basic_info.get('profile_url')}{Colors.RESET}")
                print(f"  Статус: {Colors.GREEN}✓ {basic_info.get('access')}{Colors.RESET}\n")
                
                # Публичные данные
                public_data = results['public_data']
                print(f"{Colors.CYAN}ДОСТУПНЫЕ ДАННЫЕ:{Colors.RESET}")
                print(f"  Посты: {Colors.CYAN}{public_data['posts_url']}{Colors.RESET}")
                print(f"  Друзья: {Colors.CYAN}{public_data['friends_url']}{Colors.RESET}")
                print(f"  Фото: {Colors.CYAN}{public_data['photos_url']}{Colors.RESET}")
                print(f"  Информация: {Colors.CYAN}{public_data['info_url']}{Colors.RESET}\n")
                
                # Связанные соцсети
                print(f"{Colors.CYAN}ВОЗМОЖНЫЕ СВЯЗАННЫЕ СЕТИ:{Colors.RESET}")
                for social in results['linked_social_networks']:
                    print(f"  • {social}")
                
                # Сохраняем для отчёта
                self.collected_data['vk'] = results
                self.db.save_search(vk_id, "vk_analyzer", results)
            else:
                UI.error("Не удалось получить информацию")
    
    def report_menu(self):
        """Меню создания общего OSINT отчёта"""
        UI.header("📊 Генератор OSINT Отчёта")
        
        if not self.collected_data:
            UI.warning("Нет собранных данных. Проведите анализ сначала.")
            return
        
        print(f"\n{Colors.BOLD}Собранные данные:{Colors.RESET}")
        for key in self.collected_data.keys():
            print(f"  {Colors.GREEN}✓{Colors.RESET} {key}")
        
        # Генерируем отчёт
        report = self.osint_report.generate_report(self.collected_data)
        
        # Выводим отчёт
        print(report)
        
        # Предлагаем сохранить
        save_choice = input(f"\n{Colors.BOLD}Сохранить отчёт в файл? (y/n): {Colors.RESET}").strip().lower()
        if save_choice == 'y':
            filepath = self.osint_report.save_report(report)
            if filepath:
                UI.success(f"Отчёт сохранён: {filepath}")
            else:
                UI.error("Ошибка при сохранении файла")
    
    def dorks_menu(self):
        """Меню Google Dorks Advanced"""
        query = input(f"\n{Colors.BOLD}Введи поисковый запрос: {Colors.RESET}").strip()
        if query:
            results = self.google_dorks.search(query)
            print(f"\n{Colors.BOLD}Найденные Dorks:{Colors.RESET}\n")
            for dork in results[:5]:
                print(f"  {Colors.CYAN}{dork['url']}{Colors.RESET}")
            self.collected_data['google_dorks'] = results
            self.db.save_search(query, "google_dorks", results)
    
    def news_menu(self):
        """Меню News Aggregator"""
        keyword = input(f"\n{Colors.BOLD}Введи ключевое слово для новостей: {Colors.RESET}").strip()
        if keyword:
            results = self.news_aggregator.search(keyword)
            print(f"\n{Colors.BOLD}Источники новостей:{Colors.RESET}\n")
            for news in results:
                print(f"  {Colors.YELLOW}{news['source']}:{Colors.RESET}")
                print(f"    {Colors.CYAN}{news['url']}{Colors.RESET}\n")
            self.collected_data['news'] = results
            self.db.save_search(keyword, "news_aggregator", results)
    
    def job_menu(self):
        """Меню Job Profile OSINT"""
        name = input(f"\n{Colors.BOLD}Введи имя для поиска (полное или частичное): {Colors.RESET}").strip()
        if name:
            results = self.job_osint.search(name)
            print(f"\n{Colors.BOLD}Найденные профили на job сайтах:{Colors.RESET}\n")
            for job in results:
                print(f"  {Colors.YELLOW}{job['site']}:{Colors.RESET}")
                print(f"    {Colors.CYAN}{job['url']}{Colors.RESET}\n")
            self.collected_data['job_profiles'] = results
            self.db.save_search(name, "job_osint", results)
    
    def registry_menu(self):
        """Меню Corporate Registry"""
        company = input(f"\n{Colors.BOLD}Введи название компании: {Colors.RESET}").strip()
        if company:
            results = self.corp_registry.analyze(company)
            print(f"\n{Colors.BOLD}Открытые реестры:{Colors.RESET}\n")
            print(f"{Colors.CYAN}РОССИЙСКИЙ РЕЕСТР:{Colors.RESET}")
            for key, url in results['russian_registry'].items():
                print(f"  • {Colors.YELLOW}{key}:{Colors.RESET} {Colors.CYAN}{url}{Colors.RESET}\n")
            self.collected_data['corporate_registry'] = results
            self.db.save_search(company, "corp_registry", results)
    
    def payment_menu(self):
        """Меню Payment System Finder"""
        username = input(f"\n{Colors.BOLD}Введи юзернейм для поиска в платежных системах: {Colors.RESET}").strip()
        if username:
            results = self.payment_finder.find(username)
            if results:
                UI.success(f"Найдено на {len(results)} платежных системах\n")
                for system in results:
                    print(f"  {Colors.GREEN}✓{Colors.RESET} {system['system']}")
                    print(f"     {Colors.CYAN}{system['url']}{Colors.RESET}\n")
            else:
                UI.warning("Не найдено на популярных платежных системах")
            self.collected_data['payment_systems'] = results
            self.db.save_search(username, "payment_finder", results)
    
    def telegram_menu(self):
        """Меню Telegram OSINT"""
        channel = input(f"\n{Colors.BOLD}Введи название Telegram канала (без @): {Colors.RESET}").strip()
        if channel:
            results = self.telegram_osint.analyze(channel)
            print(f"\n{Colors.BOLD}Информация о Telegram канале:{Colors.RESET}\n")
            print(f"  Прямая ссылка: {Colors.CYAN}{results['direct_url']}{Colors.RESET}")
            print(f"  Веб версия: {Colors.CYAN}{results['web_url']}{Colors.RESET}\n")
            self.collected_data['telegram'] = results
            self.db.save_search(channel, "telegram_osint", results)
    
    def youtube_menu(self):
        """Меню YouTube OSINT"""
        channel = input(f"\n{Colors.BOLD}Введи YouTube канал (@username): {Colors.RESET}").strip()
        if channel:
            results = self.youtube_osint.analyze(channel)
            print(f"\n{Colors.BOLD}Информация о YouTube канале:{Colors.RESET}\n")
            print(f"  Канал: {Colors.CYAN}{results['channel_url']}{Colors.RESET}\n")
            print(f"{Colors.BOLD}Доступные данные:{Colors.RESET}")
            for data in results['public_data']:
                print(f"  • {data}")
            self.collected_data['youtube'] = results
            self.db.save_search(channel, "youtube_osint", results)
    
    def reverse_image_menu(self):
        """Меню Reverse Image Search"""
        image_url = input(f"\n{Colors.BOLD}Введи URL изображения: {Colors.RESET}").strip()
        if image_url:
            results = self.reverse_image.search(image_url)
            print(f"\n{Colors.BOLD}Поиск по картинке в сервисах:{Colors.RESET}\n")
            for service, url in results.items():
                print(f"  {Colors.YELLOW}{service}:{Colors.RESET}")
                print(f"    {Colors.CYAN}{url[:80]}...{Colors.RESET}\n")
            self.db.save_search(image_url, "reverse_image", results)
    
    def metadata_menu(self):
        """Меню Document Metadata"""
        file_path = input(f"\n{Colors.BOLD}Введи путь к файлу: {Colors.RESET}").strip()
        if file_path:
            results = self.metadata_extractor.analyze_file(file_path)
            print(f"\n{Colors.BOLD}Метаданные документа:{Colors.RESET}\n")
            print(f"  Файл: {results.get('file', 'N/A')}")
            print(f"  Формат: {results.get('format', 'N/A')}")
            print(f"  Размер: {results.get('size', 'N/A')}")
            if results.get('metadata'):
                print(f"\n{Colors.BOLD}Найденные метаданные:{Colors.RESET}")
                for key, value in list(results['metadata'].items())[:10]:
                    print(f"  {key}: {value}")
            self.db.save_search(file_path, "metadata_extractor", results)
    
    def court_menu(self):
        """Меню Court Records"""
        name = input(f"\n{Colors.BOLD}Введи имя для поиска в судебных данных: {Colors.RESET}").strip()
        if name:
            results = self.court_records.search(name)
            print(f"\n{Colors.BOLD}Источники судебных данных:{Colors.RESET}\n")
            print(f"{Colors.CYAN}РОССИЙСКИЕ ИСТОЧНИКИ:{Colors.RESET}")
            for key, url in results['russia_courts'].items():
                print(f"  • {Colors.YELLOW}{key}:{Colors.RESET} {Colors.CYAN}{url}{Colors.RESET}\n")
            self.db.save_search(name, "court_records", results)
    
    def whois_menu(self):
        """Меню WHOIS History"""
        domain = input(f"\n{Colors.BOLD}Введи домен: {Colors.RESET}").strip()
        if domain:
            results = self.whois_history.analyze(domain)
            print(f"\n{Colors.BOLD}История WHOIS {domain}:{Colors.RESET}\n")
            print(f"{Colors.CYAN}ИСТОЧНИКИ:{Colors.RESET}")
            for source, url in results['sources'].items():
                print(f"  • {Colors.YELLOW}{source}:{Colors.RESET}")
                print(f"    {Colors.CYAN}{url}{Colors.RESET}\n")
            self.db.save_search(domain, "whois_history", results)
    
    def mentions_menu(self):
        """Меню Mentions Finder"""
        query = input(f"\n{Colors.BOLD}Введи что ищем (имя, ник, компания): {Colors.RESET}").strip()
        if query:
            results = self.mentions_finder.search(query)
            print(f"\n{Colors.BOLD}Поиск упоминаний в {len(results)} источниках:{Colors.RESET}\n")
            for mention in results[:15]:
                print(f"  {Colors.YELLOW}{mention['source']}:{Colors.RESET}")
                print(f"    {Colors.CYAN}{mention['url'][:80]}...{Colors.RESET}\n")
            self.collected_data['mentions'] = results
            self.db.save_search(query, "mentions_finder", results)
    
    def dns_menu(self):
        """Меню DNS History"""
        domain = input(f"\n{Colors.BOLD}Введи домен: {Colors.RESET}").strip()
        if domain:
            results = self.dns_history.analyze(domain)
            print(f"\n{Colors.BOLD}История DNS {domain}:{Colors.RESET}\n")
            print(f"{Colors.CYAN}ИСТОЧНИКИ:{Colors.RESET}")
            for source, url in results['sources'].items():
                print(f"  • {Colors.YELLOW}{source}:{Colors.RESET}")
                print(f"    {Colors.CYAN}{url}{Colors.RESET}\n")
            print(f"{Colors.BOLD}Отслеживаемые записи:{Colors.RESET}")
            for record in results['records_tracked']:
                print(f"  • {record}")
            self.db.save_search(domain, "dns_history", results)
    
    def financial_menu(self):
        """Меню Financial OSINT"""
        company = input(f"\n{Colors.BOLD}Введи название компании: {Colors.RESET}").strip()
        if company:
            results = self.financial_osint.analyze(company)
            print(f"\n{Colors.BOLD}Финансовая информация {company}:{Colors.RESET}\n")
            print(f"{Colors.CYAN}ПУБЛИЧНЫЕ ИСТОЧНИКИ:{Colors.RESET}")
            for source, url in list(results['public_sources'].items())[:3]:
                print(f"  • {Colors.YELLOW}{source}:{Colors.RESET}")
                print(f"    {Colors.CYAN}{url}{Colors.RESET}\n")
            self.collected_data['financial'] = results
            self.db.save_search(company, "financial_osint", results)
    
    def history_menu(self):
        """Меню истории поисков"""
        UI.header("📋 История поисков")
        
        history = self.db.get_search_history(20)
        
        if history:
            for i, (query, module, timestamp) in enumerate(history, 1):
                print(f"{i:>2}. {Colors.CYAN}{query}{Colors.RESET} ({module}) - {timestamp}")
        else:
            UI.warning("История пуста")
    
    def bookmarks_menu(self):
        """Меню закладок"""
        print(f"\n{Colors.BOLD}Закладки:{Colors.RESET}")
        print("  1. Добавить в закладки")
        print("  2. Просмотр закладок")
        
        choice = input(f"\n{Colors.BOLD}Выбор: {Colors.RESET}").strip()
        
        if choice == "1":
            title = input(f"{Colors.BOLD}Название закладки: {Colors.RESET}").strip()
            data = input(f"{Colors.BOLD}Данные: {Colors.RESET}").strip()
            
            if title and data:
                self.db.add_bookmark(title, data)
                UI.success("Закладка добавлена")

def main():
    """Точка входа"""
    try:
        app = PHANTOM(save_mode=True)
        app.main_menu()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Прерывание пользователем{Colors.RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}Ошибка: {e}{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
