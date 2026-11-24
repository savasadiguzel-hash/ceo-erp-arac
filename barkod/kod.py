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


def coz(conn, deger: str) -> tuple[int | None, str]:
    """Barkod (S######) ya da elle yazılmış stok kodu → (StokKarti.Id, durum).

    durum: 'ok' | 'yok' | 'mukerrer'.
    Barkod biçimi önce denenir (Id'ye birebir, pasif kart da olabilir).
    Elle kodda: önce tek AKTİF kart; aktif yoksa tek PASİF kart. Birden çok
    aday varsa 'mukerrer' (barkod okutulmalı). Böylece barkod ve elle kod aynı
    kartı çözer (pasif dâhil).
    """
    from db.baglanti import cursor_ctx

    kid = barkod_coz(deger)
    with cursor_ctx(conn) as cur:
        if kid is not None:
            cur.execute("SELECT Id FROM StokKarti WHERE Id = ?", kid)
            r = cur.fetchone()
            return (int(r[0]), 'ok') if r else (None, 'yok')
        kod = (deger or '').strip()
        if not kod:
            return (None, 'yok')
        cur.execute("SELECT Id, Aktif FROM StokKarti WHERE UPPER(LTRIM(RTRIM(Kodu))) = UPPER(?)", kod)
        rr = cur.fetchall()
        aktif = [r for r in rr if r[1]]
        if len(aktif) == 1:
            return (int(aktif[0][0]), 'ok')
        if len(aktif) > 1:
            return (None, 'mukerrer')
        if len(rr) == 1:          # aktif yok, tek pasif kart
            return (int(rr[0][0]), 'ok')
        return (None, 'mukerrer' if len(rr) > 1 else 'yok')


def coz_mesaj(durum: str, deger: str) -> str:
    return {
        'yok': f'Tanınmayan barkod / kod: {deger}',
        'mukerrer': f'Bu kod birden çok kartta var; barkodu okutun: {deger}',
    }.get(durum, '')


def okutma_coz(conn, deger: str) -> int | None:
    """Geriye dönük sade sarmalayıcı: yalnız Id döndürür (çözülemezse None)."""
    return coz(conn, deger)[0]
