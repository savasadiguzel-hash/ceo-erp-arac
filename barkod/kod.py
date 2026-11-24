"""Barkod değeri üretme/çözme.

Barkod içeriği yalnız ASCII (S + rakam) → okuyucunun klavye düzeninden
(Türkçe Q / US) etkilenmez. İleride: R = raf, E = iş emri önekleri.
"""
from __future__ import annotations

ONEK_STOK = 'S'


def barkod_degeri(kart_id: int) -> str:
    """StokKarti.Id → barkod içeriği, örn. 468311 → 'S468311'."""
    return f'{ONEK_STOK}{int(kart_id):06d}'


def barkod_coz(deger: str) -> int | None:
    """Okutulan değeri StokKarti.Id'ye çevirir; tanınmazsa None.

    Türkçe Q klavyede bazı okuyucular 'S' yerine 'ş'/'s' gönderebilir;
    küçük harf ve baştaki/sondaki boşluklar tolere edilir.
    """
    d = (deger or '').strip().upper()
    if len(d) >= 2 and d[0] in (ONEK_STOK, 'Ş') and d[1:].isdigit():
        return int(d[1:])
    return None


def okutma_coz(conn, deger: str) -> int | None:
    """Barkod (S######) ya da elle yazılmış stok kodu → aktif StokKarti.Id.

    Önce barkod biçimi denenir; olmazsa birebir stok kodu (büyük/küçük harf
    duyarsız, kenar boşlukları kırpılmış) aranır. Birden çok aktif kart
    aynı koda sahipse (bilinen mükerrerler) None döner — barkod kullanılmalı.
    """
    from db.baglanti import cursor_ctx

    kid = barkod_coz(deger)
    with cursor_ctx(conn) as cur:
        if kid is not None:
            cur.execute("SELECT Id FROM StokKarti WHERE Id = ?", kid)
            r = cur.fetchone()
            return int(r[0]) if r else None
        kod = (deger or '').strip()
        if not kod:
            return None
        cur.execute("SELECT Id FROM StokKarti WHERE Aktif = 1 AND UPPER(LTRIM(RTRIM(Kodu))) = UPPER(?)", kod)
        rr = cur.fetchall()
        return int(rr[0][0]) if len(rr) == 1 else None
