"""
Özetleyici (Claude API)
-----------------------
Bildirimi alır, insan diliyle yazılmış taslak post üretir.
"""

import logging
import anthropic
from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """\
Sen KAP Radar adlı bir sosyal medya hesabı için çalışıyorsun.
Görevin: Türkiye Sermaye Piyasası (KAP) bildirimlerini sıradan yatırımcıların anlayacağı sade Türkçeye çevirmek.

KURAL:
- Yatırım tavsiyesi verme.
- Clickbait yapma. "UÇACAK", "BOMBA", "YIKILDIK" gibi ifadeleri kesinlikle kullanma.
- Abartmadan, sakin ve net bir ton kullan.
- Bildirimde tutar/rakam belirtilmemişse "tutar açıklanmadı" veya "oran henüz bilinmiyor" gibi bir not düş.
- Etki etiketi için sadece şu 5 seçenekten birini kullan:
  "Olumlu" | "Hafif olumlu" | "Nötr" | "Hafif olumsuz" | "Kritik"

ÇIKTI FORMATI (tam olarak bu yapıyı kullan, başka açıklama ekleme):
[Ticker] – [Bildirim konusu özeti]
Ne oldu? [1 cümle]
Bu ne demek? [2-3 cümle insan dili açıklama]
Neye bakmalı? [1-2 cümle yatırımcı sorusu]
Etki: [etiket]
Kaynak: KAP bildirimi
Yatırım tavsiyesi değildir.\
"""


def generate_post(disclosure: dict, body_text: str = "") -> dict:
    """
    Bildirim için taslak post üretir.
    Dönen dict: {'post_text': str, 'label': str}
    """
    ticker   = disclosure.get("ticker", "?")
    title    = disclosure.get("title", "")
    category = disclosure.get("category", "")
    def_lbl  = disclosure.get("default_label", "Nötr")
    url      = disclosure.get("body_url", "")

    user_msg = (
        f"Şirket: {ticker}\n"
        f"KAP Başlığı: {title}\n"
        f"Kategori: {category}\n"
        f"Varsayılan etki: {def_lbl}\n"
    )
    if body_text:
        # Çok uzunsa kırp
        user_msg += f"\nBildirim metni (ilk 800 karakter):\n{body_text[:800]}\n"
    user_msg += f"\nKAP linki: {url}\n\nYukarıdaki formatta taslak post yaz."

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        post_text = response.content[0].text.strip()
    except Exception as exc:
        logger.error("Claude API hatası: %s", exc)
        # Fallback: basit şablon
        post_text = (
            f"{ticker} – {title}\n"
            f"Ne oldu? KAP'ta yeni bildirim açıklandı.\n"
            f"Etki: {def_lbl}\n"
            f"Kaynak: KAP bildirimi\n"
            f"Yatırım tavsiyesi değildir."
        )

    # Etki etiketini metinden çıkar
    label = def_lbl
    for line in post_text.splitlines():
        if line.startswith("Etki:"):
            label = line.replace("Etki:", "").strip()
            break

    return {"post_text": post_text, "label": label}
