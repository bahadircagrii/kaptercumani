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
# KAP BİLDİRİM KATEGORİLERİ
# Her kategori: keywords (başlıkta aranır) + default_label
# ---------------------------------------------------------------------------
CATEGORIES = {

    # ── 1. TEMETTÜ ──────────────────────────────────────────────────────────
    "temettü": {
        "keywords": [
            "temettü", "kar payı", "kâr payı", "dividend",
            "nakit temettü", "temettü dağıtım",
        ],
        "default_label": "Hafif olumlu",
    },

    # ── 2. PAY GERİ ALIMI ───────────────────────────────────────────────────
    "geri_alim": {
        "keywords": [
            "geri alım", "geri alim", "pay geri", "hisse geri",
            "geri satın alma",
        ],
        "default_label": "Olumlu sinyal",
    },

    # ── 3. SERMAYE ARTIRIMI ─────────────────────────────────────────────────
    "sermaye_artirimi": {
        "keywords": [
            "sermaye artırımı", "sermaye artirimi",
            "bedelsiz", "bedelli", "rüçhan", "ruchan",
            "hisse bölünme", "pay bölünme", "split",
        ],
        "default_label": "Nötr",
    },

    # ── 4. ÖNEMLİ SÖZLEŞME / İHALE ─────────────────────────────────────────
    "sozlesme": {
        "keywords": [
            "sözleşme", "sozlesme", "ihale", "iş ilişkisi",
            "is iliskisi", "anlaşma", "anlasma",
            "sipariş", "siparis", "satış sözleşme",
            "tedarik sözleşme", "hizmet sözleşme",
            "ön anlaşma", "mutabakat", "protokol",
        ],
        "default_label": "Hafif olumlu",
    },

    # ── 5. FİNANSAL SONUÇ ──────────────────────────────────────────────────
    "finansal_sonuc": {
        "keywords": [
            "finansal sonuç", "finansal sonuc",
            "bilanço", "bilanco", "gelir tablosu",
            "ara dönem", "ara donem",
            "yıllık rapor", "yillik rapor",
            "konsolide finansal", "solo finansal",
            "faaliyet raporu",
        ],
        "default_label": "Nötr",
    },

    # ── 6. BÜYÜK YATIRIM / KAPASİTE ─────────────────────────────────────────
    "yatirim": {
        "keywords": [
            "yatırım", "yatirim", "kapasite artış", "kapasite artis",
            "tesis", "fabrika", "üretim hattı", "uretim hatti",
            "açılış", "acilis", "yeni tesis", "genişleme",
        ],
        "default_label": "Hafif olumlu",
    },

    # ── 7. TAHVİL / BORÇ ÖDEMELERİ ─────────────────────────────────────────
    # Ödeme haberleri nötr; gecikme/temerrüt kritik
    "tahvil_borc": {
        "keywords": [
            "tahvil", "bono", "eurobond", "sukuk",
            "anapara ödemesi", "anapara odemesi",
            "faiz ödemesi", "faiz odemesi",
            "kupon ödemesi", "kupon odemesi",
            "borç ödemesi", "borc odemesi",
            "kredi geri ödeme", "itfa",
            "temerrüt", "temerrut", "ödeme güçlüğü",
            "ödeme gecikme","borçlanma aracı", "borclanma araci",
"spk başvurusu", "ihraç başvurusu",
        ],
        "default_label": "Nötr",
    },

    # ── 8. YÖNETİM DEĞİŞİKLİĞİ ──────────────────────────────────────────────
    # Ani CEO/CFO ayrılışları piyasada genellikle olumsuz okunur
    "yonetim_degisikligi": {
        "keywords": [
            "genel müdür", "genel mudur",
            "ceo", "cfo", "coo",
            "yönetim kurulu üye", "yonetim kurulu uye",
            "yönetim kurulu değişiklik", "yonetim degisiklik",
            "icra başkanı", "icra baskani",
            "görevden", "gorevden", "istifa",
            "atama", "görevlendirme",
        ],
        "default_label": "Nötr",
    },

    # ── 9. HUKUKİ / İDARİ İŞLEM ─────────────────────────────────────────────
    # SPK/BDDK/Rekabet Kurumu kararları, davalar fiyatı doğrudan etkiler
    "hukuki": {
        "keywords": [
            "spk", "bddk", "rekabet kurumu",
            "dava", "hukuki", "yaptırım", "yaptirim",
            "ceza", "soruşturma", "sorusturma",
            "kovuşturma", "kovusturma",
            "idari para cezası", "idari para cezasi",
            "mahkeme", "kayyum", "tedbir kararı",
            "haciz", "konkordato", "iflas", "icra",
        ],
        "default_label": "Hafif olumsuz",
    },

    # ── 10. İÇERİDEN KİŞİ PAY ALIM SATIMI ──────────────────────────────────
    # Yönetici/ortak alımları olumlu; satışlar izlenmeli
    "insider": {
        "keywords": [
            "içeriden", "iceride",
            "yönetici işlem", "yonetici islem",
            "pay alım bildirimi", "pay satım bildirimi",
            "önemli pay", "onemli pay",
            "büyük ortak", "buyuk ortak",
            "pay edinim", "pay elden çıkarma",
            "hisse alım bildirimi", "hisse satım bildirimi",
        ],
        "default_label": "Nötr",
    },

    # ── 11. BİRLEŞME / DEVRALMA / SATMA (M&A) ───────────────────────────────
    # Piyasada en sert fiyat hareketini yaratan kategori
    "birlesme_devralma": {
        "keywords": [
            "birleşme", "birlesme", "devralma",
            "satın alma", "satin alma",
            "hisse devri", "ortaklık devri",
            "iştirak", "istirak",
            "bağlı ortaklık satış", "bagli ortaklik satis",
            "tam bölünme", "kısmi bölünme", "kismi bolunme",
            "pay devri",
        ],
        "default_label": "Kritik",
    },

    # ── 12. KREDİ DERECELENDİRME ─────────────────────────────────────────────
    # Moody's / Fitch / S&P kararları kurumsal yatırımcıları etkiler
    "kredi_derecelendirme": {
        "keywords": [
            "kredi notu", "kredi derecelendirme",
            "rating", "moody", "fitch", "s&p",
            "not artırım", "not indirimi",
            "görünüm değişikliği",
        ],
        "default_label": "Kritik",
    },

    # ── 13. ÜRETİM / OPERASYONEL RİSK ───────────────────────────────────────
    # Kaza, grev, doğal afet → iş sürekliliği riski
    "operasyonel_risk": {
        "keywords": [
            "grev", "lokavt",
            "iş kazası", "is kazasi",
            "yangın", "yangin",
            "patlama", "sel", "deprem",
            "üretim durdu", "uretim durdu",
            "operasyonel aksaklık", "operasyonel aksama",
            "mücbir sebep",
        ],
        "default_label": "Hafif olumsuz",
    },

    # ── 14. LİSANS / RUHSAT / İZİN ──────────────────────────────────────────
    # Enerji, telekom, finans şirketleri için kritik
    "lisans_ruhsat": {
        "keywords": [
            "lisans", "ruhsat", "izin",
            "lisans genişleme", "lisans iptali",
            "ruhsat iptali", "faaliyet izni",
            "işletme lisansı", "üretim lisansı",
        ],
        "default_label": "Nötr",
    },

}
