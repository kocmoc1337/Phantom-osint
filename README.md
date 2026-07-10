# 🎭 PHANTOM v5.0 — Open Source Intelligence Tool

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/Platform-Pydroid%20%7C%20Linux%20%7C%20Windows-green.svg" alt="Platform">
  <img src="https://img.shields.io/badge/Author-@jecrs-purple.svg" alt="Author">
</p>

**PHANTOM** — это модульный консольный инструмент для комплексного сбора информации из открытых источников (OSINT) и анализа данных. Разработан специально для работы в мобильной среде **Pydroid**, а также полностью совместим с десктопными терминалами.

---

## 📸 Интерфейс программы

<p align="center">
  <img src="menu.jpg" width="600" alt="PHANTOM v5.0 Main Menu">
</p>

---

## ✨ Возможности инструмента (36 встроенных модулей)

Программа включает в себя мощный арсенал для поиска, разбитый по ключевым категориям:

* **🕵️‍♂️ Поиск людей и профилей:** Сканер юзернеймов по 180+ сайтам, Email Finder, Поиск в базах утечек (Data Breach), Социальный агрегатор, VKontakte Analyzer, Job Profile OSINT (анализ резюме и вакансий), Mentions Finder.
* **🌐 Сетевой и веб-анализ:** Domain OSINT, Углубленный анализ веб-сайтов и URL, API Endpoint Finder, Advanced Google/GitHub Dorks, WHOIS & DNS History, Поиск скрытых систем и реестров.
* **📱 Мобильный, Гео и Медиа-анализ:** Анализатор номеров телефонов, продвинутая IP-геолокация, Telegram & YouTube OSINT, извлечение метаданных из документов, обратный поиск по изображениям (Reverse Image Search).
* **🔒 Безопасность и Крипта:** Анализ криптокошельков (Crypto Analysis), расшифровка и анализ хэшей (Hash Analyzer), проверка репутации IP/доменов (Reputation Checker).
* **📊 Системные модули:** Локальное кэширование и история поисков, система закладок для важных находок, генерация полного Общего OSINT-Отчёта.

---

## 🚀 Инструкция по установке и запуску

### Установка на Android (в Pydroid 3)
1. Откройте вкладку **Pip** в меню Pydroid 3.
2. Перейдите в раздел **Quick install** и установите библиотеки `requests` и `pillow`.
3. Запустите скрипт `phantom.py` кнопкой **Play**.

### Установка на ПК (Linux / Windows / macOS)
1. Склонируйте данный репозиторий:
   ```bash
   git clone [https://github.com/kocmoc1337/Phantom-osint.git](https://github.com/kocmoc1337/Phantom-osint.git)
   cd Phantom-osint
2. Установите зависимости:
pip install -r requirements.txt
3. Запустите проэкт:
   python phantom.py
