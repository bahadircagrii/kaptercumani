"""
KAP Radar — Ana Orkestratör
----------------------------
Her POLL_INTERVAL_MINUTES dakikada bir:
  1. KAP'tan yeni bildirimleri çeker
  2. Kategoriye göre filtreler
  3. Claude ile taslak post üretir
  4. Admin'e onay mesajı gönderir

Çalıştır:  python main.py
"""

import asyncio
import logging
import signal
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import POLL_INTERVAL_MINUTES
from kap_scraper import fetch_new_disclosures, fetch_disclosure_text
from filter_engine import filter_disclosures
from summarizer import generate_post
from approval_bot import build_app, send_approval_request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("kap_radar.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


async def poll_kap(app) -> None:
    """Periyodik KAP tarama işi."""
    logger.info("KAP taranıyor...")
    raw      = fetch_new_disclosures()
    filtered = filter_disclosures(raw)

    if not filtered:
        logger.info("Yeni ilgili bildirim yok.")
        return

    logger.info("%d ilgili bildirim bulundu, özetleniyor...", len(filtered))
    for disc in filtered:
        body = fetch_disclosure_text(disc["id"])
        item = generate_post(disc, body_text=body)
        item["disclosure"] = disc
        await send_approval_request(app, item)
        await asyncio.sleep(1)  # API hız limiti


async def main() -> None:
    app = build_app()

    # Scheduler'ı kur
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_kap,
        trigger=IntervalTrigger(minutes=POLL_INTERVAL_MINUTES),
        kwargs={"app": app},
        id="kap_poll",
        name=f"KAP Tarama (her {POLL_INTERVAL_MINUTES} dk)",
        misfire_grace_time=60,
    )

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown(scheduler, app)))

    logger.info("KAP Radar başlatılıyor...")
    await app.initialize()
    await app.start()

    # İlk çalışma hemen
    await poll_kap(app)

    scheduler.start()
    logger.info(
        "Scheduler aktif. Sonraki tarama %d dakika sonra.",
        POLL_INTERVAL_MINUTES,
    )

    await app.updater.start_polling(drop_pending_updates=True)

    # Sonsuza kadar çalış
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass


async def _shutdown(scheduler, app) -> None:
    logger.info("Kapatılıyor...")
    scheduler.shutdown(wait=False)
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    asyncio.get_event_loop().stop()


if __name__ == "__main__":
    asyncio.run(main())
