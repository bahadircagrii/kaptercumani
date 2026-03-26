import asyncio
import logging
import sys

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
        raw = fetch_new_disclosures()
        filtered = filter_disclosures(raw)
        if not filtered:
            logger.info("Yeni ilgili bildirim yok.")
            return
        logger.info("%d ilgili bildirim, ozetleniyor...", len(filtered))
        for disc in filtered:
            try:
                body = fetch_disclosure_text(disc["id"])
                item = generate_post(disc, body_text=body)
                item["disclosure"] = disc
                await send_approval_request(app, item)
                await asyncio.sleep(2)
            except Exception as e:
                logger.error("Bildirim isleme hatasi (%s): %s", disc.get("id"), e)
    except Exception as exc:
        logger.error("poll_kap hatasi: %s", exc)


async def main() -> None:
    app = build_app()
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("KAP Radar aktif. Tarama suresi: %d dk.", POLL_INTERVAL_MINUTES)

    while True:
        try:
            await poll_kap(app)
        except Exception as e:
            logger.error("Ana dongu hatasi: %s", e)
        await asyncio.sleep(POLL_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    asyncio.run(main())
