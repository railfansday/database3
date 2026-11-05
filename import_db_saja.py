import sqlite3
import feedparser
import requests
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ==========================================================================
# KONFIGURASI
# ==========================================================================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = str(BASE_DIR / "database_hasil5" / "database.sqlite")
RSS_FILE = str(BASE_DIR / "rss_list.txt")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ==========================================================================
# FUNGSI DATABASE
# ==========================================================================
def inisialisasi_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artikel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE, judul TEXT, konten TEXT, gambar TEXT,
            tanggal_publish TEXT, tanggal_update TEXT
        )
    """)
    conn.commit()
    conn.close()

# ==========================================================================
# FUNGSI SCRAPING (TANPA BATAS WAKTU)
# ==========================================================================
def proses_feed(feed_url):
    feed_url = feed_url.strip()
    if not feed_url or feed_url.startswith("#"): return 0, 0

    baru = 0
    duplikat = 0

    try:
        # Timeout 10 detik
        resp = requests.get(feed_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200: return 0, 0
        
        feed = feedparser.parse(resp.content)
        conn = sqlite3.connect(DB_PATH, timeout=15)
        cursor = conn.cursor()

        # Ambil semua artikel dari feed (Google News biasanya berisi 100 artikel)
        for entry in feed.entries:
            link = entry.get('link', '')
            judul = entry.get('title', 'Tanpa Judul')
            if not link: continue

            cursor.execute("SELECT id FROM artikel WHERE link = ?", (link,))
            if cursor.fetchone():
                duplikat += 1
                continue

            # Karena Google News tidak menyediakan konten penuh, kita simpan ringkasannya saja
            summary = entry.get('summary', 'Baca selengkapnya di sumber asli.')
            
            # Gambar dari RSS (jika ada)
            gambar = ""
            if 'media_content' in entry and entry.media_content:
                gambar = entry.media_content[0].get('url', '')
            
            img_tag = f'<div style="text-align:center; margin-bottom:20px;"><img src="{gambar}" alt="{judul}" style="max-width:100%; height:auto;"></div>' if gambar else ""
            
            konten_lengkap = f"""
            {img_tag}
            <div style="font-size: 16px; line-height: 1.8;">
                {summary}
                <p style="margin-top: 25px;">
                    <a href="{link}" target="_blank" rel="nofollow">Baca artikel asli &rarr;</a>
                </p>
            </div>
            """

            tanggal = datetime.now().isoformat()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                tanggal = datetime(*entry.published_parsed[:6]).isoformat()

            try:
                cursor.execute(
                    "INSERT INTO artikel (link, judul, konten, gambar, tanggal_publish, tanggal_update) VALUES (?, ?, ?, ?, ?, ?)",
                    (link, judul, konten_lengkap, gambar, tanggal, datetime.now().isoformat())
                )
                conn.commit()
                baru += 1
            except Exception:
                pass
                
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
        
    return baru, duplikat

# ==========================================================================
# MAIN
# ==========================================================================
if __name__ == "__main__":
    print("=" * 50)
    print("MULAI IMPORT DATABASE (GOOGLE NEWS)")
    print("=" * 50)
    
    if not os.path.exists(RSS_FILE):
        print(f"[ERROR] File {RSS_FILE} tidak ditemukan!")
        exit(1)
        
    inisialisasi_database()
    
    with open(RSS_FILE, "r", encoding="utf-8") as f:
        rss_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
    print(f"[*] Memproses {len(rss_urls)} sumber RSS...")
    
    total_baru, total_duplikat = 0, 0
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(proses_feed, url): url for url in rss_urls}
        for future in as_completed(futures):
            b, d = future.result()
            total_baru += b
            total_duplikat += d

    print("\n" + "="*45)
    print(f"[SELESAI]")
    print(f" - Artikel Baru disimpan : {total_baru}")
    print(f" - Dilewati (Duplikat)   : {total_duplikat}")
    print("="*45)
