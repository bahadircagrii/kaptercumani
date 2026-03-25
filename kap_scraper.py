"""
KAP Scraper
-----------
KAP'ın genel erişime açık JSON uç noktalarından bildirimleri çeker.
Hiç kayıt kaçırılmaması için SQLite'ta görülen bildirimler saklanır.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

KAP_DISCLOSURE_URL = "https://www.kap.org.tr/tr/api/memberNotificationQuery"
DB_PATH = Path(__file__).parent / "seen.db"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.kap.org.tr/",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.kap.org.tr",
}


# ---------------------------------------------------------------------------
# Veritabanı
# ---------------------------------------------------------------------------

def _init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_disclosures (
            id          TEXT PRIMARY KEY,
            fetched_at  TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _is_seen(conn: sqlite3.Connection, disc_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM seen_disclosures WHERE id = ?", (disc_id,)
    ).fetchone()
    return row is not None


def _mark_seen(conn: sqlite3.Connection, disc_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seen_disclosures (id, fetched_at) VALUES (?, ?)",
        (disc_id, datetime.utcnow().isoformat()),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Ana çekici
# ---------------------------------------------------------------------------

def fetch_new_disclosures() -> list[dict]:
    """
    KAP'tan son bildirimleri çeker, daha önce görülmüş olanları filtreler.
    Her bildirim dict şu anahtarları taşır:
        id, ticker, title, body_url, published_at, raw
    """
    conn = _init_db()

    # KAP API'si POST + JSON body bekliyor
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    payload = {
        "fromDate": yesterday,
        "toDate":   today,
        "term":     "",
    }

    try:
        resp = requests.post(
            KAP_DISCLOSURE_URL,
            json=payload,
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("KAP API hatası: %s", exc)
        return []

    # API bazen liste, bazen {"data": [...]} döndürebilir
    items = data if isinstance(data, list) else data.get("data", [])

    new_disclosures = []
    for item in items:
        disc_id = str(item.get("id") or item.get("disclosureIndex", ""))
        if not disc_id:
            continue
        if _is_seen(conn, disc_id):
            continue

        # Alan adları KAP'ın döndürdüğü JSON'a göre ayarla
        ticker  = (item.get("memberCode") or item.get("ticker") or "").upper()
        title   = item.get("title") or item.get("header") or ""
        pub_raw = item.get("publishDate") or item.get("publishedAt") or ""

        new_disclosures.append(
            {
                "id":           disc_id,
                "ticker":       ticker,
                "title":        title,
                "body_url":     f"https://www.kap.org.tr/tr/Bildirim/{disc_id}",
                "published_at": pub_raw,
                "raw":          item,
            }
        )
        _mark_seen(conn, disc_id)

    logger.info("%d yeni bildirim bulundu", len(new_disclosures))
    return new_disclosures


def fetch_disclosure_text(disc_id: str) -> str:
    """Bildirim detay sayfasından metni çekmeye çalışır."""
    try:
        url  = f"https://www.kap.org.tr/tr/api/memberNotification/{disc_id}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Metin content / text / body alanından gelebilir
        return (
            data.get("content")
            or data.get("text")
            or data.get("body")
            or ""
        )
    except Exception:
        return ""
