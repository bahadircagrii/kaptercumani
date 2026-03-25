# KAP Radar 📡

KAP bildirimlerini otomatik olarak izler, Claude ile insan diline çevirir
ve sana Telegram üzerinden onay için gönderir.

---

## Mimari

```
KAP API (15 dk)
    │
    ▼
kap_scraper.py   → yeni bildirimleri çeker, görülenleri SQLite'ta saklar
    │
    ▼
filter_engine.py → kategori eşleşmesi (temettü, geri alım, sözleşme…)
    │
    ▼
summarizer.py    → Claude API ile insan dili taslak üretir
    │
    ▼
approval_bot.py  → sana Telegram'dan: [✅ Onayla] [✏️ Düzenle] [⏭ Geç]
    │
    ▼
publisher.py     → Telegram kanalı + X (isteğe bağlı)
```

---

## Kurulum (5 adım)

### 1. Python ortamı

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Telegram botu oluştur

1. Telegram'da **@BotFather**'a mesaj at
2. `/newbot` → isim: `KAP Radar` → kullanıcı adı: `kapradar_bot`
3. Token'ı kopyala → `.env` dosyasına `TELEGRAM_BOT_TOKEN` olarak yapıştır

**Admin chat ID'ni öğren:**
```bash
# Bota herhangi bir mesaj at, sonra:
curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
# "chat":{"id":XXXXXXXX} değerini kopyala
```
Bu değeri `TELEGRAM_ADMIN_CHAT_ID` olarak kaydet.

**Yayın kanalı:**
- Telegram'da bir kanal oluştur (ör: `@kapradar`)
- Botu kanala admin olarak ekle
- `TELEGRAM_CHANNEL_ID` = `@kapradar` (veya `-100xxxxxxxxx` formatında)

### 3. Anthropic API

https://console.anthropic.com adresinden API anahtarı al.
`.env` dosyasına `ANTHROPIC_API_KEY` olarak ekle.

### 4. .env dosyasını oluştur

```bash
cp .env.example .env
# .env dosyasını düzenle
```

### 5. Çalıştır

```bash
python main.py
```

İlk çalıştırmada KAP hemen taranır. Yeni bildirim varsa sana Telegram'dan mesaj gelir.

---

## Telegram Komutları

| Komut | Açıklama |
|-------|----------|
| `/start` | Botu başlat |
| `/pending` | Kuyrukta kaç bildirim var |
| `/status` | Genel durum |

---

## Onay Akışı

Bot sana şunu gönderir:

```
🆕 THYAO — yeni bildirim

THYAO – Temettü dağıtım kararı
Ne oldu? ...
Bu ne demek? ...
Etki: Hafif olumlu
Kaynak: KAP bildirimi
Yatırım tavsiyesi değildir.

[✅ Onayla]  [✏️ Düzenle]  [⏭ Geç]
```

- **Onayla** → Telegram kanalına ve X'e (açıksa) gönderir
- **Düzenle** → Yeni metni yazmanı bekler, sonra tekrar onay sorar
- **Geç** → Bildirim atlanır

---

## Yeni Kategori Eklemek

`config.py` dosyasındaki `CATEGORIES` sözlüğüne ekle:

```python
"bölünme": {
    "keywords": ["hisse bölünme", "pay bölünme", "split"],
    "default_label": "Nötr",
},
```

---

## X (Twitter) Entegrasyonu

1. https://developer.twitter.com adresinde uygulama oluştur
2. Read + Write izni ver
3. Anahtarları `.env` dosyasına ekle
4. `.env` dosyasında `ENABLE_X_POSTING=true` yap

---

## Arka Planda Çalıştır (Linux/Mac)

```bash
# systemd servisi veya basit screen:
screen -S kapradar
python main.py
# Ctrl+A, D ile ayır
```

Ya da **screen** yerine `nohup`:
```bash
nohup python main.py > kap_radar.log 2>&1 &
```

---

## Log Dosyası

```bash
tail -f kap_radar.log
```

---

## Notlar

- KAP'ın genel erişime açık API'si kullanılıyor.
- `seen.db` (SQLite) aynı bildirimi iki kez göndermez.
- İlk 30 gün tam otomatik paylaşmayı açma; onay akışını kullan.
