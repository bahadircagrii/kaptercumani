import logging
import anthropic
from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """\
Sen KAP Radar adlı bir sosyal medya hesabı için çalışıyorsun.
Görevin: Türkiye Sermaye Piyasası (KAP) bildirimlerini sıradan yatırımcıların anlayacağı sade Türkçeye çevirmek.

KATEGORİ REHBERİ (etki etiketine karar verirken kullan):
- temettü: nakit çıkışı var, tutar ve verim önemli → genellikle olumlu
- geri_alim: şirket hissesini ucuz buluyor sinyali → olumlu
- sermaye_artirimi: bedelsiz nötr, bedelli seyreltici → dikkatli değerlendir
- sozlesme: tutar belirtilmişse büyüklüğe göre değerlendir, belirsizse "hafif olumlu"
- finansal_sonuc: rakamları beklentiyle karşılaştır, varsa yorumla
- yatirim: uzun vadeli olumlu ama kısa vadede nakit çıkışı
- tahvil_borc: ödeme yapıldıysa nötr; gecikme/temerrüt varsa KRİTİK
- yonetim_degisikligi: ani ayrılış olumsuz, yeni atama nötr/bekle
- hukuki: SPK/BDDK cezası, dava, kayyum → olumsuz/kritik
- insider: yönetici alımı olumlu sinyal; satışı izle
- birlesme_devralma: en sert fiyat hareketi yaratan kategori → KRİTİK
- kredi_derecelendirme: not artışı olumlu, indirimi kritik
- operasyonel_risk: grev/kaza/yangın → olumsuz, büyüklüğe göre kritik
- lisans_ruhsat: iptal kritik, genişleme olumlu

KURALLAR:
- Yatırım tavsiyesi verme.
- "UÇACAK", "BOMBA", "YIKILDIK" gibi ifade kullanma.
- Sakin, net, abartısız ton.
- Rakam/tutar belirtilmemişse bunu mutlaka belirt.
- Temerrüt, kayyum, iflas, SPK cezası gibi ciddi gelişmelerde etiketi "Kritik" yap.

ÇIKTI FORMATI (sadece bu yapı, başka açıklama ekleme):
[Ticker] – [Konu özeti]
Ne oldu? [1 cümle]
Bu ne demek? [2-3 cümle]
Neye bakmalı? [1-2 cümle]
Etki: [Olumlu / Hafif olumlu / Nötr / Hafif olumsuz / Kritik]
Kaynak: KAP bildirimi
Yatırım tavsiyesi değildir.\
"""


def generate_post(disclosure: dict, body_text: str = "") -> dict:
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
        user_msg += f"\nBildirim metni (ilk 800 karakter):\n{body_text[:800]}\n"
    user_msg += f"\nKAP linki: {url}\n\nYukarıdaki formatta taslak post yaz."

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        post_text = response.content[0].text.strip()
    except Exception as exc:
        logger.error("Claude API hatasi: %s", exc)
        post_text = (
            f"{ticker} – {title}\n"
            f"Ne oldu? KAP'ta yeni bildirim açıklandı.\n"
            f"Etki: {def_lbl}\n"
            f"Kaynak: KAP bildirimi\n"
            f"Yatırım tavsiyesi değildir."
        )

    label = def_lbl
    for line in post_text.splitlines():
        if line.startswith("Etki:"):
            label = line.replace("Etki:", "").strip()
            break

    return {"post_text": post_text, "label": label}
