import sqlite3
import logging
from pathlib import Path
from contextlib import closing
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

KAP_URL = "https://www.kap.org.tr/tr/api/disclosures"
DISCLOSURE_DETAIL_URL = "https://www.kap.org.tr/tr/api/disclosure/{disc_id}"
DB_PATH = Path(__file__).parent / "seen.db"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.kap.org.tr/",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.kap.org.tr",
}

CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30


def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = _build_session()


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


def _get_max_index(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT value FROM state WHERE key = 'max_disclosure_index'"
    ).fetchone()
    return int(row[0]) if row and row[0].isdigit() else 0


def _set_max_index(conn: sqlite3.Connection, idx: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO state (key, value) VALUES ('max_disclosure_index', ?)",
        (str(idx),),
    )
    conn.commit()


def _mark_seen(conn: sqlite3.Connection, disc_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seen_disclosures (id, fetched_at) VALUES (?, ?)",
        (disc_id, datetime.utcnow().isoformat()),
    )
    conn.commit()


def _is_seen(conn: sqlite3.Connection, disc_id: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM seen_disclosures WHERE id = ?", (disc_id,)
        ).fetchone()
    )


def _request_json(url: str):
    try:
        resp = SESSION.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ReadTimeout:
        logger.error("KAP API read timeout: %s", url)
    except requests.exceptions.ConnectTimeout:
        logger.error("KAP API connect timeout: %s", url)
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        text = exc.response.text[:500] if exc.response is not None else ""
        logger.error("KAP API HTTP hatasi (%s): %s | body=%s", status, url, text)
    except requests.exceptions.RequestException as exc:
        logger.error("KAP API baglanti hatasi: %s | url=%s", exc, url)
    except ValueError as exc:
        logger.error("KAP API JSON parse hatasi: %s | url=%s", exc, url)

    return None


def fetch_new_disclosures():
    with closing(_get_conn()) as conn:
        max_idx = _get_max_index(conn)

        url = KAP_URL if max_idx <= 0 else f"{KAP_URL}?afterDisclosureIndex={max_idx}"
        items = _request_json(url)

        if items is None:
            return []

        if not isinstance(items, list) or not items:
            logger.info("Yeni bildirim yok.")
            return []

        # İlk çalışmada sadece son index'i kaydet
        if max_idx == 0:
            top_idx = 0
            for item in items:
                basic = item.get("basic", {})
                idx = basic.get("disclosureIndex", 0)
                if isinstance(idx, int):
                    top_idx = max(top_idx, idx)
                else:
                    try:
                        top_idx = max(top_idx, int(idx))
                    except (TypeError, ValueError):
                        pass

            if top_idx > 0:
                _set_max_index(conn, top_idx)

            logger.info(
                "Ilk calisma: %d bildirim bulundu, index kaydedildi (%d). "
                "Bir sonraki taramada sadece yeni bildirimler islenecek.",
                len(items), top_idx,
            )
            return []

        new_disclosures = []
        new_max = max_idx

        for item in items:
            basic = item.get("basic", {})
            disclosure_index = basic.get("disclosureIndex")

            try:
                disclosure_index = int(disclosure_index)
            except (TypeError, ValueError):
                continue

            disc_id = str(disclosure_index)

            if _is_seen(conn, disc_id):
                continue

            stock_codes = basic.get("stockCodes") or []
            ticker = (
                stock_codes[0].get("code", "") if stock_codes else ""
            ) or basic.get("companyCode", "")
            ticker = ticker.upper().strip()

            title = (basic.get("title") or basic.get("disclosureSubject") or "").strip()
            pub_raw = basic.get("publishDate") or ""

            new_disclosures.append(
                {
                    "id": disc_id,
                    "ticker": ticker,
                    "title": title,
                    "body_url": f"https://www.kap.org.tr/tr/Bildirim/{disc_id}",
                    "published_at": pub_raw,
                    "raw": basic,
                }
            )

            _mark_seen(conn, disc_id)
            new_max = max(new_max, disclosure_index)

        if new_max > max_idx:
            _set_max_index(conn, new_max)

        logger.info("%d yeni bildirim bulundu", len(new_disclosures))
        return new_disclosures


def fetch_disclosure_text(disc_id: str) -> str:
    url = DISCLOSURE_DETAIL_URL.format(disc_id=disc_id)
    data = _request_json(url)

    if not isinstance(data, dict):
        return ""

    return (
        data.get("content")
        or data.get("text")
        or data.get("body")
        or ""
    )
