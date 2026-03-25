import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_CHAT_ID  = int(os.getenv("TELEGRAM_ADMIN_CHAT_ID", "0"))
TELEGRAM_CHANNEL_ID     = os.getenv("TELEGRAM_CHANNEL_ID", "")
ANTHROPIC_API_KEY       = os.getenv("ANTHROPIC_API_KEY", "")
X_API_KEY               = os.getenv("X_API_KEY", "")
X_API_SECRET            = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN          = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET   = os.getenv("X_ACCESS_TOKEN_SECRET", "")
POLL_INTERVAL_MINUTES   = int(os.getenv("POLL_INTERVAL_MINUTES", "15"))
ENABLE_X_POSTING        = os.getenv("ENABLE_X_POSTING", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Kategori tanımları: KAP bildirim başlığında bu kelimeler geçerse işle.
# Her kategorinin anahtar kelimeleri ve varsayılan etki etiketi var.
# ---------------------------------------------------------------------------
CATEGORIES = {
    "temettü": {
        "keywords": ["temettü", "kar payı", "kâr payı", "dividend"],
        "default_label": "Hafif olumlu",
    },
    "geri_alim": {
        "keywords": ["geri alım", "geri alim", "pay geri", "hisse geri"],
        "default_label": "Olumlu sinyal",
    },
    "sermaye_artirimi": {
        "keywords": [
            "sermaye artırımı", "sermaye artirimi",
            "bedelsiz", "bedelli", "rüçhan", "ruchan",
        ],
        "default_label": "Nötr",
    },
    "sozlesme": {
        "keywords": [
            "sözleşme", "sozlesme", "ihale", "iş ilişkisi",
            "is iliskisi", "anlaşma", "anlasma", "sipariş", "siparis",
        ],
        "default_label": "Hafif olumlu",
    },
    "finansal_sonuc": {
        "keywords": [
            "finansal sonuç", "finansal sonuc",
            "bilanço", "bilanco", "gelir tablosu",
            "ara dönem", "ara donem", "yıllık rapor", "yillik rapor",
        ],
        "default_label": "Nötr",
    },
    "yatirim": {
        "keywords": [
            "yatırım", "yatirim", "kapasite artış", "kapasite artis",
            "tesis", "fabrika", "üretim hattı", "uretim hatti",
        ],
        "default_label": "Hafif olumlu",
    },
}
