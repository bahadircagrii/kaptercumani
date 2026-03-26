"""
KAP Scraper
-----------
Doğru endpoint: https://www.kap.org.tr/tr/api/disclosures
Yanıt yapısı:   her öğe { basic: { disclosureIndex, title, stockCodes, companyName, ... } }
Yeni bildirimler için: ?afterDisclosureIndex=<son_index>
"""

import sqlite3
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

KAP_URL = "https://www.kap.org.tr/tr/api/disclosures"
DB_PATH = Path(__file__).parent / "seen.db"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.kap.org.tr/",
    "Accept":  "application/json, text/plain, */*",
    "Origin":  "https://www.kap.org.tr",
}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_disclosures (
            id         TEXT PRIMARY KEY,
            fetched_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS state (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _get_max_index(conn):
    row = conn.execute(
        "SELECT value FROM state WHERE key = 'max_disclosure_index'"
    ).fetchone()
    return int(row[0]) if row else 0


def _set_max_index(conn, idx):
    conn.execute(
        "INSERT OR REPLACE INTO state (key, value) VALUES ('max_disclosure_index', ?)",
        (str(idx),),
    )
    conn.commit()


def _mark_seen(conn, disc_id):
    from datetime import datetime
    conn.execute(
        "INSERT OR IGNORE INTO seen_disclosures (id, fetched_at) VALUES (?, ?)",
        (disc_id, datetime.utcnow().isoformat()),
    )
    conn.commit()


def _is_seen(conn, disc_id):
    return bool(
        conn.execute(
            "SELECT 1 FROM seen_disclosures WHERE id = ?", (disc_id,)
        ).fetchone()
    )


def fetch_new_disclosures():
    conn    = _get_conn()
    max_idx = _get_max_index(conn)

    url = KAP_URL
    if max_idx > 0:
        url = f"{KAP_URL}?afterDisclosureIndex={max_idx}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        items = resp.json()
    except Exception as exc:
        logger.error("KAP API hatasi: %s", exc)
        return []

    if not isinstance(items, list) or not items:
        logger.info("Yeni bildirim yok.")
        return []

    # İlk çalışmada sadece index kaydet
    if max_idx == 0:
        top_idx = items[0].get("basic", {}).get("disclosureIndex", 0)
        _set_max_index(conn, top_idx)
        logger.info(
            "Ilk calisma: %d bildirim bulundu, index kaydedildi (%d). "
            "Bir sonraki taramadan itibaren yeni bildirimler islenir.",
            len(items), top_idx,
        )
        return []

    new_disclosures = []
    new_max = max_idx

    for item in items:
        basic   = item.get("basic", {})
        disc_id = str(basic.get("disclosureIndex", ""))
        if not disc_id or _is_seen(conn, disc_id):
            continue

        stock_codes = basic.get("stockCodes") or []
        ticker = (
            stock_codes[0].get("code", "") if stock_codes else ""
        ) or basic.get("companyCode", "")
        ticker = ticker.upper()

        title   = basic.get("title") or basic.get("disclosureSubject") or ""
        pub_raw = basic.get("publishDate") or ""

        new_disclosures.append({
            "id":           disc_id,
            "ticker":       ticker,
            "title":        title,
            "body_url":     f"https://www.kap.org.tr/tr/Bildirim/{disc_id}",
            "published_at": pub_raw,
            "raw":          basic,
        })
        _mark_seen(conn, disc_id)
        new_max = max(new_max, int(disc_id))

    if new_max > max_idx:
        _set_max_index(conn, new_max)

    logger.info("%d yeni bildirim bulundu", len(new_disclosures))
    return new_disclosures


def fetch_disclosure_text(disc_id):
    try:
        url  = f"https://www.kap.org.tr/tr/api/disclosure/{disc_id}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("content") or data.get("text") or data.get("body") or ""
    except Exception:
        return ""
