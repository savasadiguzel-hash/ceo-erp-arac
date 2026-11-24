"""Barkod okutma sorguları — CEO ERP'den YALNIZCA OKUR.

Depo bazlı bakiye kuralı (ERP-OKUMA.md "Bakiye Formülü" ile aynı):
  - Faturaya dönüşmüş irsaliyeler (sh.FaturaId dolu) sayılmaz; kısmi fatura
    FaturaDetayId üzerinden düşülür.
  - 23 = depo transferi: DepoKartId'den çıkar, KarsiDepoKartId'ye girer.
  - Satırdaki depo (shd.DepoKartId) başlıktaki depoya göre önceliklidir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from db.baglanti import cursor_ctx

GIRIS = (1, 4, 5, 8, 15, 16, 20, 22, 26, 29)
CIKIS = (2, 3, 6, 7, 17, 18, 19, 21, 24, 28)
TRANSFER = 23

ISLEM_ADI = {
    1: 'Alış faturası', 2: 'Satış faturası', 3: 'Alış iadesi', 4: 'Satış iadesi',
    5: 'Alış irsaliyesi', 6: 'Satış irsaliyesi', 16: 'Üretimden giriş', 17: 'Üretime çıkış',
    18: 'Fire çıkışı', 19: 'Sarf / garanti çıkışı', 20: 'Sayım fazlası girişi',
    21: 'Sayım eksiği çıkışı', 22: 'Devir / sayım girişi', 23: 'Depo transferi',
}


def islem_adi(kod: int) -> str:
    return ISLEM_ADI.get(int(kod), f'İşlem {kod}')


@dataclass
class KartBilgi:
    id: int
    kodu: str
    adi: str
    birim: str
    aktif: bool
    depo_bakiye: dict = field(default_factory=dict)      # {depo_id: miktar}
    recete_kullanim: list = field(default_factory=list)  # [{mamul_kodu, mamul_adi, hat, miktar, birim}]
    dolayli_mamuller: list = field(default_factory=list) # [{kodu, adi, seviye}]  (seviye ≥ 2)
    son_hareketler: list = field(default_factory=list)   # [{tarih, islem, belge, depo, karsi_depo, miktar, notlar}]

    @property
    def toplam_bakiye(self) -> float:
        return round(sum(self.depo_bakiye.values()), 6)


# ───────────────────────── sözlükler ─────────────────────────
_depo_cache: dict | None = None
_birim_cache: dict | None = None


def depolar(conn, yenile: bool = False) -> dict[int, str]:
    """{StokDepoKarti.Id: 'DepoNo - Adı'} (aktif depolar)."""
    global _depo_cache
    if _depo_cache is None or yenile:
        with cursor_ctx(conn) as cur:
            cur.execute("SELECT Id, DepoNo, Adi FROM StokDepoKarti WHERE Aktif = 1 ORDER BY DepoNo")
            _depo_cache = {int(r[0]): f"{(r[1] or '').strip()} - {(r[2] or '').strip()}" for r in cur.fetchall()}
    return _depo_cache


def birim_adlari(conn) -> dict[str, str]:
    """{birim GUID (küçük harf, süslü parantezsiz): açıklama}."""
    global _birim_cache
    if _birim_cache is None:
        from db.sorgular import birimleri_getir
        _birim_cache = {str(g).casefold().strip('{}'): a for a, g in birimleri_getir(conn).items()}
    return _birim_cache


def _birim(conn, guid) -> str:
    return birim_adlari(conn).get(str(guid or '').casefold().strip('{}'), '') if guid else ''


# ───────────────────────── bakiye ─────────────────────────
def depo_bakiyeleri(conn, kart_idler: list[int] | None = None, depo_id: int | None = None,
                    tarih: date | None = None) -> dict[tuple[int, int], float]:
    """{(kart_id, depo_id): bakiye}. kart_idler None ise tüm stok kartları.

    depo_id verilirse yalnız o deponun bakiyeleri döner.
    """
    t = (tarih or date.today()).strftime('%Y-%m-%d')
    gir = ','.join(map(str, GIRIS))
    cik = ','.join(map(str, CIKIS))
    filtre, param = '', []
    if kart_idler is not None:
        if not kart_idler:
            return {}
    sonuc: dict[tuple[int, int], float] = {}
    parcalar = [None] if kart_idler is None else [kart_idler[i:i + 500] for i in range(0, len(kart_idler), 500)]
    for parca in parcalar:
        filtre, param = '', []
        if parca is not None:
            filtre = f" AND shd.IslemKartId IN ({','.join('?' * len(parca))})"
            param = list(parca)
        sql = f"""
            SELECT x.KartId, x.Depo, SUM(x.M) FROM (
                SELECT shd.IslemKartId AS KartId,
                       COALESCE(shd.DepoKartId, sh.DepoKartId) AS Depo,
                       CASE WHEN sh.IslemKodu IN ({gir}) THEN 1 ELSE -1 END
                         * (shd.Miktar - ISNULL(f.Miktar, 0)) AS M
                FROM StokHareketDetay shd
                JOIN StokHareket sh ON sh.Id = shd.HareketId
                LEFT JOIN StokHareketDetay f ON f.Id = shd.FaturaDetayId
                WHERE shd.Turu = 1 AND shd.Aktif = 1 AND sh.Aktif = 1 AND sh.FaturaId IS NULL
                  AND sh.IslemKodu IN ({gir},{cik},{TRANSFER})
                  AND CAST(sh.BelgeTarihi AS DATE) <= '{t}' {filtre}
                UNION ALL
                SELECT shd.IslemKartId, COALESCE(shd.KarsiDepoKartId, sh.KarsiDepoKartId), shd.Miktar
                FROM StokHareketDetay shd
                JOIN StokHareket sh ON sh.Id = shd.HareketId
                WHERE shd.Turu = 1 AND shd.Aktif = 1 AND sh.Aktif = 1 AND sh.IslemKodu = {TRANSFER}
                  AND COALESCE(shd.KarsiDepoKartId, sh.KarsiDepoKartId) IS NOT NULL
                  AND CAST(sh.BelgeTarihi AS DATE) <= '{t}' {filtre}
            ) x
            {'WHERE x.Depo = ?' if depo_id is not None else ''}
            GROUP BY x.KartId, x.Depo
        """
        p = param + param + ([depo_id] if depo_id is not None else [])
        with cursor_ctx(conn) as cur:
            cur.execute(sql, *p)
            for kid, d, m in cur.fetchall():
                if d is None:
                    continue
                v = round(float(m or 0), 6)
                if abs(v) > 1e-9:
                    sonuc[(int(kid), int(d))] = v
    return sonuc


# ───────────────────────── kart sorgusu ─────────────────────────
def kart_bilgi(conn, kart_id: int, hareket_sayisi: int = 10, dolayli: bool = True) -> KartBilgi | None:
    """Okutulan kartın tüm özeti: bakiye (depo bazlı), reçete kullanımı, son hareketler."""
    with cursor_ctx(conn) as cur:
        cur.execute("SELECT Id, Kodu, Adi, StokBirim, Aktif FROM StokKarti WHERE Id = ?", kart_id)
        r = cur.fetchone()
    if not r:
        return None
    k = KartBilgi(int(r[0]), (r[1] or '').strip(), (r[2] or '').strip(), _birim(conn, r[3]), bool(r[4]))

    k.depo_bakiye = {d: m for (_, d), m in depo_bakiyeleri(conn, [k.id]).items()}
    k.recete_kullanim = recete_kullanim(conn, k.id)

    if dolayli and k.recete_kullanim:
        from db.sorgular import bilesen_mamul_bul
        try:
            s = bilesen_mamul_bul(conn, [k.kodu]).get(k.kodu.upper(), {})
            k.dolayli_mamuller = [m for m in s.get('mamullar', []) if m['seviye'] >= 2]
        except Exception:
            k.dolayli_mamuller = []

    k.son_hareketler = son_hareketler(conn, k.id, hareket_sayisi)
    return k


def recete_kullanim(conn, kart_id: int) -> list[dict]:
    """Kartın doğrudan girdi olduğu aktif reçeteler + hat + adet."""
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT ur.Kodu, ISNULL(sk_u.Adi, ur.Tanim), ISNULL(hk.Kodu, ''), SUM(g.Miktar), g.BirimId
            FROM UretimReceteHatPlaniGirdi g
            JOIN UretimReceteHatPlani hp ON hp.Id = g.UretimReceteHatPlaniId
            JOIN UretimRecete ur        ON ur.Id = hp.UretimReceteId
            LEFT JOIN StokKarti sk_u    ON sk_u.Kodu = ur.Kodu AND sk_u.Aktif = 1
            LEFT JOIN StokKarti hk      ON hk.Id = hp.KartId
            WHERE g.Tipi = 1 AND g.KartId = ?
              AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
            GROUP BY ur.Kodu, ISNULL(sk_u.Adi, ur.Tanim), ISNULL(hk.Kodu, ''), g.BirimId
            ORDER BY ur.Kodu
        """, kart_id)
        rr = cur.fetchall()
    return [{
        'mamul_kodu': (a or '').strip(),
        'mamul_adi': (b or '').strip(),
        'hat': (h or '').strip() if (h or '').strip() != (a or '').strip() else '',
        'miktar': float(m or 0),
        'birim': _birim(conn, br),
    } for a, b, h, m, br in rr]


def son_hareketler(conn, kart_id: int, adet: int = 10) -> list[dict]:
    with cursor_ctx(conn) as cur:
        cur.execute(f"""
            SELECT TOP {int(adet)} sh.BelgeTarihi, sh.IslemKodu,
                   LTRIM(RTRIM(ISNULL(sh.BelgeSeriNo, '') + ' ' + ISNULL(CAST(sh.BelgeSiraNo AS nvarchar(30)), ''))),
                   COALESCE(shd.DepoKartId, sh.DepoKartId), COALESCE(shd.KarsiDepoKartId, sh.KarsiDepoKartId),
                   shd.Miktar, CAST(sh.Notlar AS nvarchar(120)), sh.FaturaId
            FROM StokHareketDetay shd
            JOIN StokHareket sh ON sh.Id = shd.HareketId
            WHERE shd.IslemKartId = ? AND shd.Turu = 1 AND shd.Aktif = 1 AND sh.Aktif = 1
            ORDER BY sh.BelgeTarihi DESC, sh.Id DESC
        """, kart_id)
        rr = cur.fetchall()
    return [{
        'tarih': t, 'islem_kodu': int(ik), 'islem': islem_adi(ik), 'belge': b or '',
        'depo': d, 'karsi_depo': kd, 'miktar': float(m or 0), 'notlar': (n or '').strip(),
        'faturalasmis': fid is not None,
    } for t, ik, b, d, kd, m, n, fid in rr]


def kart_ozetleri(conn, kart_idler: list[int]) -> dict[int, dict]:
    """{Id: {kodu, adi, birim, aktif}} — sayım listesi / Excel için toplu okuma."""
    sonuc: dict[int, dict] = {}
    for i in range(0, len(kart_idler), 500):
        parca = kart_idler[i:i + 500]
        with cursor_ctx(conn) as cur:
            cur.execute(f"SELECT Id, Kodu, Adi, StokBirim, Aktif FROM StokKarti WHERE Id IN ({','.join('?' * len(parca))})", *parca)
            for r in cur.fetchall():
                sonuc[int(r[0])] = {'kodu': (r[1] or '').strip(), 'adi': (r[2] or '').strip(),
                                    'birim': _birim(conn, r[3]), 'aktif': bool(r[4])}
    return sonuc
