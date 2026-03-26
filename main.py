"""
KAP Radar — Ana Orkestrator
"""

import asyncio
import logging
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
    format="%(asctime)s [%(levelname)s] %(name)s -- %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("kap_radar.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


async def poll_kap(app) -> None:
    logger.info("KAP taraniyor...")
    try:
        raw      = fetch_new_disclosures()
        filtered = filter_disclosures(raw)

        if not filtered:
            logger.info("Yeni ilgili bildirim yok.")
            return

        logger.info("%d ilgili bildirim bulundu, ozetleniyor...", len(filtered))
        for disc in filtered:
            body = fetch_disclosure_text(disc["id"])
            item = generate_post(disc, body_text=body)
            item["disclosure"] = disc
            await send_approval_request(app, item)
            await asyncio.sleep(1)
    except Exception as exc:
        logger.error("poll_kap hatasi: %s", exc)


async def main() -> None:
    app = build_app()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_kap,
        trigger=IntervalTrigger(minutes=POLL_INTERVAL_MINUTES),
        kwargs={"app": app},
        id="kap_poll",
        misfire_grace_time=60,
    )

    logger.info("KAP Radar baslatiliyor...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    # İlk tarama hemen
    await poll_kap(app)

    scheduler.start()
    logger.info("Scheduler aktif. Sonraki tarama %d dakika sonra.", POLL_INTERVAL_MINUTES)

    # Sonsuza kadar çalış
    stop_event = asyncio.Event()
    await stop_event.wait()


if __name__ == "__main__":
    asyncio.run(main())
