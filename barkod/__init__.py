"""Barkod modülü — okutma, sorgu, sayım (GUI'den bağımsız iş mantığı).

Barkod içeriği CEO'nun benzersiz kart anahtarıdır: S + StokKarti.Id (6 hane).
Etikette ise okunur bilgi (kod, ad, birim) yer alır.
"""

SURUM = '1.0'
FIRMA = 'Gempa Elektro Mekanik Müh. Ltd. Şti.'
GELISTIRICI = 'Savaş ADIGÜZEL'


def logo_yolu():
    """Firma logosu (assets/logo.jpeg); derlenmiş exe'de paketin içinden okunur."""
    import sys
    from pathlib import Path
    taban = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    p = taban / 'assets' / 'logo.jpeg'
    return p if p.exists() else None
