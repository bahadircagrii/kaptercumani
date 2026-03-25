"""
Filtre Motoru
-------------
Bildirimleri CATEGORIES sözlüğündeki anahtar kelimelere göre sınıflandırır.
Eşleşme yoksa None döner → o bildirim işlenmiyor.
"""

from config import CATEGORIES


def categorize(disclosure: dict) -> dict | None:
    """
    Bildirime uygun kategoriyi bul.
    Bulunursa disclosure'a 'category' ve 'default_label' ekleyerek döndür.
    Bulunmazsa None.
    """
    title_lower = (disclosure.get("title") or "").lower()

    for cat_key, cat_cfg in CATEGORIES.items():
        for kw in cat_cfg["keywords"]:
            if kw.lower() in title_lower:
                return {
                    **disclosure,
                    "category":      cat_key,
                    "default_label": cat_cfg["default_label"],
                }
    return None


def filter_disclosures(disclosures: list[dict]) -> list[dict]:
    """Listeyi filtreler; sadece kategorilendirilebilenleri döndürür."""
    result = []
    for d in disclosures:
        categorized = categorize(d)
        if categorized:
            result.append(categorized)
    return result
