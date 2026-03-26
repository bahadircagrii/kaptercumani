import sqlite3
import logging
import time
from pathlib import Path
import requests

logger  = logging.getLogger(__name__)
KAP_URL = "https://www.kap.org.tr/tr/api/disclosures"
DB_PATH = Path(__file__).parent / "seen.db"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.kap.org.tr/",
    "Accept":  "application/json, text/plain, */*",
    "Origin":  "https://www.kap.org.tr",
}


def _get_conn():
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
    from datetime import datetime
    conn.execute("INSERT OR IGNORE INTO seen_disclosures (id,fetched_at) VALUES (?,?)",
                 (disc_id, datetime.utcnow().isoformat()))
    conn.commit()

def _is_seen(conn, disc_id):
    return bool(conn.execute("SELECT 1 FROM seen_disclosures WHERE id=?", (disc_id,)).fetchone())


def _get_with_retry(url, retries=3, timeout=30):
    """Timeout olursa 3 kez dener."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.exceptions.Timeout:
            wait = (attempt + 1) * 10
            logger.warning("KAP timeout (deneme %d/%d). %d sn bekleniyor...", attempt+1, retries, wait)
            if attempt < retries - 1:
                time.sleep(wait)
        except Exception as exc:
            logger.error("KAP hatasi: %s", exc)
            return None
    logger.error("KAP %d denemede de yanit vermedi.", retries)
    return None


def fetch_new_disclosures():
    conn    = _get_conn()
    max_idx = _get_max_index(conn)
    url     = KAP_URL if max_idx == 0 else f"{KAP_URL}?afterDisclosureIndex={max_idx}"

    resp = _get_with_retry(url)
    if resp is None:
        return []

    try:
        items = resp.json()
    except Exception:
        logger.error("JSON parse hatasi")
        return []

    if not isinstance(items, list) or not items:
        logger.info("Yeni bildirim yok.")
        return []

    if max_idx == 0:
        top_idx = items[0].get("basic", {}).get("disclosureIndex", 0)
        _set_max_index(conn, top_idx)
        logger.info("Ilk calisma: index kaydedildi (%d). Sonraki taramadan itibaren bildirimler islenir.", top_idx)
        return []

    new_disclosures = []
    new_max = max_idx
    for item in items:
        basic   = item.get("basic", {})
        disc_id = str(basic.get("disclosureIndex", ""))
        if not disc_id or _is_seen(conn, disc_id):
            continue
        stock_codes = basic.get("stockCodes") or []
        ticker = (stock_codes[0].get("code","") if stock_codes else "") or basic.get("companyCode","")
        new_disclosures.append({
            "id":           disc_id,
            "ticker":       ticker.upper(),
            "title":        basic.get("title") or basic.get("disclosureSubject") or "",
            "body_url":     f"https://www.kap.org.tr/tr/Bildirim/{disc_id}",
            "published_at": basic.get("publishDate",""),
            "raw":          basic,
        })
        _mark_seen(conn, disc_id)
        new_max = max(new_max, int(disc_id))

    if new_max > max_idx:
        _set_max_index(conn, new_max)
    logger.info("%d yeni bildirim bulundu.", len(new_disclosures))
    return new_disclosures


def fetch_disclosure_text(disc_id):
    resp = _get_with_retry(f"https://www.kap.org.tr/tr/api/disclosure/{disc_id}", retries=2, timeout=20)
    if resp is None:
        return ""
    try:
        data = resp.json()
        return data.get("content") or data.get("text") or data.get("body") or ""
    except Exception:
        return ""
