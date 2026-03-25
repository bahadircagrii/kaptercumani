"""
Yayıncı
-------
Onaylanan postu Telegram kanalına (ve isteğe bağlı X'e) gönderir.
"""

import logging
import tweepy
from config import (
    TELEGRAM_CHANNEL_ID,
    X_API_KEY, X_API_SECRET,
    X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET,
    ENABLE_X_POSTING,
)

logger = logging.getLogger(__name__)


async def publish_to_telegram(app, post_text: str) -> bool:
    """python-telegram-bot Application nesnesiyle kanal postu atar."""
    try:
        await app.bot.send_message(
            chat_id=TELEGRAM_CHANNEL_ID,
            text=post_text,
            parse_mode=None,   # sade metin
            disable_web_page_preview=True,
        )
        logger.info("Telegram kanalına gönderildi.")
        return True
    except Exception as exc:
        logger.error("Telegram yayın hatası: %s", exc)
        return False


def publish_to_x(post_text: str) -> bool:
    """Twitter/X API v2 ile tweet atar (isteğe bağlı)."""
    if not ENABLE_X_POSTING:
        return False
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET]):
        logger.warning("X API anahtarları eksik, atlanıyor.")
        return False
    try:
        client = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_TOKEN_SECRET,
        )
        # X 280 karakter sınırı; uzunsa kırp
        tweet = post_text[:277] + "..." if len(post_text) > 280 else post_text
        client.create_tweet(text=tweet)
        logger.info("X'e gönderildi.")
        return True
    except Exception as exc:
        logger.error("X yayın hatası: %s", exc)
        return False
