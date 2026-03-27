import os
import sqlite3
import logging
import time
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup

logger  = logging.getLogger(__name__)
DB_PATH = Path(os.getenv("DB_PATH", str(Path(__file__).parent / "seen.db")))

# KAP'ın herkese açık bildirim listesi (HTML sayfa)
KAP_LIST_URL = "https://www.kap.org.tr/tr/bildirim-sorgu"
# Yeni bildirimler JSON endpoint (daha basit, deneyelim)
KAP_API_URL  = "https://www.kap.org.tr/tr/api/disclosures"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.kap.org.tr/tr/",
}
API_HEADERS = {**HEADERS, "Accept": "application/json, text/plain, */*", "Origin": "https://www.kap.org.tr"}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS seen_disclosures (id TEXT PRIMARY KEY, fetched_at TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit()
    return conn

def _get_max_index(conn):
    row = conn.execute("SELECT value FROM state WHERE key='max_disclosure_index'").fetchone()
    return int(row[0]) if row else 0

def _set_max_index(conn, idx):
    conn.execute("INSERT OR REPLACE INTO state (key,value) VALUES ('max_disclosure_index',?)", (str(idx),))
    conn.commit()

def _mark_seen(conn, disc_id):
    conn.execute("INSERT OR IGNORE INTO seen_disclosures (id,fetched_at) VALUES (?,?)",
                 (disc_id, datetime.utcnow().isoformat()))
    conn.commit()

def _is_seen(conn, disc_id):
    return bool(conn.execute("SELECT 1 FROM seen_disclosures WHERE id=?", (disc_id,)).fetchone())


def _try_api(max_idx):
    """Önce JSON API'yi dene."""
    url = KAP_API_URL if max_idx == 0 else f"{KAP_API_URL}?afterDisclosureIndex={max_idx}"
    try:
        # Önce ana sayfayı ziyaret et (cookie al)
        SESSION.get("https://www.kap.org.tr/tr", timeout=20)
        time.sleep(1)
        resp = SESSION.get(url, headers=API_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            logger.info("API basarili, %d bildirim.", len(data))
            return data
    except Exception as e:
        logger.warning("API denemesi basarisiz: %s", e)
    return None


def _try_html():
    """API çalışmazsa HTML sayfasını parse et."""
    try:
        SESSION.get("https://www.kap.org.tr/tr", timeout=20)
        time.sleep(1)
        resp = SESSION.get(KAP_LIST_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        # KAP bildirim tablosunu bul
        rows = soup.select("table tbody tr") or soup.select(".notification-row") or soup.select("[class*='disclosure']")
        for row in rows[:50]:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            # Link varsa disclosure ID'yi çıkar
            link = row.find("a", href=True)
            if not link:
                continue
            href = link.get("href","")
            disc_id = ""
            if "/Bildirim/" in href:
                disc_id = href.split("/Bildirim/")[-1].strip("/")
            if not disc_id:
                continue

            title  = cols[2].get_text(strip=True) if len(cols) > 2 else link.get_text(strip=True)
            ticker = cols[1].get_text(strip=True) if len(cols) > 1 else ""

            results.append({"basic": {
                "disclosureIndex": int(disc_id) if disc_id.isdigit() else 0,
                "title": title,
                "stockCodes": [{"code": ticker}] if ticker else [],
                "publishDate": "",
            }})

        logger.info("HTML parse: %d bildirim bulundu.", len(results))
        return results if results else None
    except Exception as e:
        logger.error("HTML parse hatasi: %s", e)
        return None


def fetch_new_disclosures():
    conn    = _get_conn()
    max_idx = _get_max_index(conn)

    # Önce API dene, olmadı HTML'e geç
    items = _try_api(max_idx)
    if items is None:
        items = _try_html()
    if not items:
        logger.info("Hicbir kaynaktan veri alinamadi.")
        return []

    if max_idx == 0:
        top_idx = items[0].get("basic", {}).get("disclosureIndex", 0)
        if top_idx:
            _set_max_index(conn, top_idx)
            logger.info("Ilk calisma: index kaydedildi (%d). Sonraki taramadan bildirimler islenir.", top_idx)
        return []

    new_disclosures = []
    new_max = max_idx
    for item in items:
        basic   = item.get("basic", {})
        disc_id = str(basic.get("disclosureIndex", ""))
        if not disc_id or disc_id == "0" or _is_seen(conn, disc_id):
            continue
        stock_codes = basic.get("stockCodes") or []
        ticker = (stock_codes[0].get("code","") if stock_codes else "") or basic.get("companyCode","")
        new_disclosures.append({
            "id":           disc_id,
            "ticker":       ticker.upper(),
            "title":        basic.get("title") or "",
            "body_url":     f"https://www.kap.org.tr/tr/Bildirim/{disc_id}",
            "published_at": basic.get("publishDate",""),
            "raw":          basic,
        })
        _mark_seen(conn, disc_id)
        try:
            new_max = max(new_max, int(disc_id))
        except ValueError:
            pass

    if new_max > max_idx:
        _set_max_index(conn, new_max)
    logger.info("%d yeni ilgili aday bildirim.", len(new_disclosures))
    return new_disclosures


def fetch_disclosure_text(disc_id):
    try:
        resp = SESSION.get(
            f"https://www.kap.org.tr/tr/api/disclosure/{disc_id}",
            headers=API_HEADERS, timeout=20
        )
        data = resp.json()
        return data.get("content") or data.get("text") or data.get("body") or ""
    except Exception:
        return ""
