import requests
import sqlite3
import os
import time
import random

DB_PATH = os.path.join("Data", "MangaZekdb.db")
BASE_URL = "https://api.mangadex.org"

def sleep():
    time.sleep(random.uniform(1.5, 3.0))

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS manga (
            id TEXT PRIMARY KEY,
            title TEXT,
            cover_url TEXT,
            authors TEXT,
            genres TEXT,
            status TEXT,
            created_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS chapter (
            id TEXT PRIMARY KEY,
            manga_id TEXT,
            title TEXT,
            images TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_manga_list(limit=100, offset=0):
    params = {
        "limit": limit,
        "offset": offset,
        "availableTranslatedLanguage[]": "en",
        "order[createdAt]": "desc",
        "includes[]": ["author", "artist", "cover_art"]
    }
    r = requests.get(f"{BASE_URL}/manga", params=params)
    r.raise_for_status()
    sleep()
    return r.json().get("data", [])

def get_chapters(manga_id, limit=10):
    params = {
        "limit": limit,
        "translatedLanguage[]": "en",
        "order[chapter]": "asc"
    }
    r = requests.get(f"{BASE_URL}/manga/{manga_id}/feed", params=params)
    r.raise_for_status()
    sleep()
    return r.json().get("data", [])

def get_chapter_images(chap_id):
    r = requests.get(f"{BASE_URL}/at-home/server/{chap_id}")
    r.raise_for_status()
    sleep()
    d = r.json()
    base_url = d["baseUrl"]
    hash_val = d["chapter"]["hash"]
    files = d["chapter"]["data"]
    return [f"{base_url}/data/{hash_val}/{f}" for f in files]

def parse_metadata(manga):
    id = manga["id"]
    attr = manga["attributes"]
    title = attr["title"].get("en", "No title")
    status = attr.get("status", "unknown")
    created_at = attr.get("createdAt", "")

    authors = []
    cover_file = ""
    genres = []

    for rel in manga.get("relationships", []):
        if rel["type"] in ["author", "artist"]:
            authors.append(rel["attributes"]["name"])
        elif rel["type"] == "cover_art":
            cover_file = rel["attributes"]["fileName"]

    for tag in attr.get("tags", []):
        name = tag["attributes"]["name"].get("en")
        if name:
            genres.append(name)

    cover_url = f"https://uploads.mangadex.org/covers/{id}/{cover_file}.256.jpg" if cover_file else "https://via.placeholder.com/200"

    return {
        "id": id,
        "title": title,
        "cover_url": cover_url,
        "authors": ", ".join(set(authors)),
        "genres": ", ".join(genres),
        "status": status,
        "created_at": created_at
    }

def save(manga, chapters):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO manga VALUES (?, ?, ?, ?, ?, ?, ?)", (
        manga["id"],
        manga["title"],
        manga["cover_url"],
        manga["authors"],
        manga["genres"],
        manga["status"],
        manga["created_at"]
    ))
    for chap in chapters:
        chap_id = chap["id"]
        images = get_chapter_images(chap_id)
        c.execute("INSERT OR IGNORE INTO chapter VALUES (?, ?, ?, ?)", (
            chap_id,
            manga["id"],
            chap["attributes"].get("title", ""),
            "\n".join(images)
        ))
    conn.commit()
    conn.close()

def main():
    print("🚀 MangaDex crawling started...")
    init_db()
    total_manga = 100  # Tổng số truyện muốn crawl
    batch_size = 10    # Số truyện crawl mỗi lần

    for offset in range(0, total_manga, batch_size):
        print(f"\n📦 Crawling offset {offset}")
        try:
            manga_list = get_manga_list(limit=batch_size, offset=offset)
        except Exception as e:
            print(f"❌ Manga list error: {e}")
            continue

        for manga in manga_list:
            try:
                info = parse_metadata(manga)
                print(f"🔹 {info['title']}")
                chapters = get_chapters(info["id"], limit=10)  # Lấy tối đa 10 chapter
                if not chapters:
                    print("⛔ No chapters.")
                    continue
                save(info, chapters)
                print(f"✅ Saved {len(chapters)} chapters with images.")
            except Exception as e:
                print(f"⚠️ Error: {e}")
            sleep()

if __name__ == "__main__":
    main()