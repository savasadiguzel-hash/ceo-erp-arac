"""Barkod stok fişleri — CEO ERP'ye YAZAR (Giriş 20 / Çıkış 21 / Transfer 23).

Kalıp: CEO'nun kendi yazdığı 20/21/23 fişleri ve `tools/sene_sonu_uretim/hat_kapat.py`
(CEO ile 134 satırın 130'unda birebir maliyet). Kurallar:
  - Başlık + detaylar TEK transaction; detaylar TEK TEK insert edilir
    (StokHareketDetay tetikleyicisi tek satır okuyup StokKumulatif'i günceller).
  - BirimKatsayisi = KalanMiktar = Miktar, MaliyetTarihi = BelgeTarihi, MaliyetTutari = Tutar.
  - Çıkış/transferde depo bakiyesi hem belge tarihinde hem bugün yetmeli → eksiye düşürmez.
  - Maliyet: çıkış/transfer = kaynak depoda depo bazlı FIFO; giriş = son giriş fiyatı (düzenlenebilir).
  - Yazım sonrası: StokKumulatif tutarlılığı + yeni eksi kontrolü; sorun varsa ROLLBACK.
  - `fis_yaz(..., commit=False)` = deneme: her şeyi yazar, kontrol eder, geri alır.
Notlara asla "Claude" yazılmaz; açıklamayı kullanıcı girer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from barkod.sorgu import CIKIS, GIRIS, TRANSFER

ISLEMLER = {
    20: {'ad': 'Giriş (Sayım fazlası)', 'seri': 'SYM', 'yon': +1},
    21: {'ad': 'Çıkış (Sayım eksiği)', 'seri': 'SYMCKS', 'yon': -1},
    23: {'ad': 'Depo transferi', 'seri': '', 'yon': 0},
}


@dataclass
class FisSatir:
    kart_id: int
    kodu: str
    adi: str
    birim: str
    birim_guid: str
    miktar: float
    birim_fiyat: float | None = None   # None → otomatik hesaplanır
    fiyat_elle: bool = False
    kaynak_bakiye: float | None = None # çıkış/transfer: kaynak depoda min(belge tarihi, bugün)
    hata: str = ''                     # engelleyici
    uyari: str = ''                    # engellemez

    @property
    def tutar(self) -> float:
        return round((self.birim_fiyat or 0) * self.miktar, 6)


@dataclass
class FisTaslak:
    islem: int
    depo_id: int
    karsi_depo_id: int | None
    tarih: date
    notlar: str
    kullanici_guid: str
    satirlar: list = field(default_factory=list)

    @property
    def engel(self) -> list[str]:
        e = [f'{s.kodu}: {s.hata}' for s in self.satirlar if s.hata]
        if not self.satirlar:
            e.append('Liste boş')
        if self.islem == TRANSFER and (not self.karsi_depo_id or self.karsi_depo_id == self.depo_id):
            e.append('Transferde hedef depo, kaynak depodan farklı olmalı')
        if not self.kullanici_guid:
            e.append('Kullanıcı seçilmedi')
        return e

    @property
    def toplam(self) -> float:
        return round(sum(s.tutar for s in self.satirlar), 2)


# ───────────────────────── yardımcılar ─────────────────────────
def _hareketler(cur, kid: int, t: datetime):
    cur.execute(f"""
        SELECT sh.Id, sh.BelgeTarihi, sh.IslemKodu, d.Miktar - ISNULL(f.Miktar, 0), d.BirimFiyat,
               COALESCE(d.DepoKartId, sh.DepoKartId), COALESCE(d.KarsiDepoKartId, sh.KarsiDepoKartId)
        FROM StokHareketDetay d
        JOIN StokHareket sh ON sh.Id = d.HareketId
        LEFT JOIN StokHareketDetay f ON f.Id = d.FaturaDetayId
        WHERE d.IslemKartId = ? AND d.Turu = 1 AND d.Aktif = 1 AND sh.Aktif = 1 AND sh.FaturaId IS NULL
          AND sh.BelgeTarihi <= ? AND sh.IslemKodu IN {GIRIS + CIKIS + (TRANSFER,)}""", kid, t)
    return cur.fetchall()


def depo_bakiye(cur, kid: int, depo: int, t: datetime) -> float:
    b = 0.0
    for _, _, ik, m, _, d, kd in _hareketler(cur, kid, t):
        m = float(m or 0)
        if ik == TRANSFER:
            if d == depo: b -= m
            if kd == depo: b += m
        elif d == depo:
            b += m if ik in GIRIS else -m
    return round(b, 6)


def fifo(cur, kid: int, miktar: float, depo: int, t: datetime) -> float:
    """Depo bazlı FIFO birim maliyet (hat_kapat.py ile aynı). Yetmezse son giriş fiyatı."""
    gir, cik = [], 0.0
    for i, bt, ik, m, f, d, kd in _hareketler(cur, kid, t):
        m = float(m or 0); f = float(f or 0)
        if ik == TRANSFER:
            if kd == depo: gir.append((bt, i, m, f))
            if d == depo: cik += m
        elif ik in GIRIS and d == depo:
            gir.append((bt, i, m, f))
        elif ik in CIKIS and d == depo:
            cik += m
    gir.sort()
    kal, top, al = cik, 0.0, 0.0
    for bt, i, m, f in gir:
        if kal >= m - 1e-9:
            kal -= m; continue
        u = min(m - kal, miktar - al); top += u * f; al += u; kal = 0
        if al >= miktar - 1e-9:
            break
    if al < miktar - 1e-9:
        top += (miktar - al) * (gir[-1][3] if gir else 0.0)
    return round(top / miktar, 6) if miktar else 0.0


def son_giris_fiyati(cur, kid: int) -> float:
    """Giriş fişi için öneri: fiyatı > 0 olan son giriş hareketinin birim fiyatı (TL)."""
    cur.execute(f"""
        SELECT TOP 1 d.BirimFiyat FROM StokHareketDetay d JOIN StokHareket sh ON sh.Id = d.HareketId
        WHERE d.IslemKartId = ? AND d.Turu = 1 AND d.Aktif = 1 AND sh.Aktif = 1 AND d.BirimFiyat > 0
          AND sh.IslemKodu IN {GIRIS + (TRANSFER,)}
        ORDER BY sh.BelgeTarihi DESC, sh.Id DESC""", kid)
    r = cur.fetchone()
    return round(float(r[0]), 6) if r else 0.0


def _belge_tarihi(islem: int, t: date) -> datetime:
    # CEO: 20/21 gece yarısı; 23 oluşturma anı (saatli). Geçmiş tarihli transfer → gün sonu değil, 12:00.
    if islem == TRANSFER:
        return datetime.now() if t == date.today() else datetime(t.year, t.month, t.day, 12, 0)
    return datetime(t.year, t.month, t.day)


# ───────────────────────── taslak ─────────────────────────
def taslak_hazirla(conn, islem: int, depo_id: int, karsi_depo_id: int | None, tarih: date,
                   kalemler: list[tuple[int, float, float | None]], notlar: str, kullanici_guid: str) -> FisTaslak:
    """kalemler: [(kart_id, miktar, elle_birim_fiyat|None)] → fiyatlı, kontrollü taslak (yazmaz)."""
    from barkod.sorgu import birim_adlari
    assert islem in ISLEMLER, islem
    tz = FisTaslak(islem, depo_id, karsi_depo_id, tarih, notlar, kullanici_guid)
    bt = _belge_tarihi(islem, tarih).replace(hour=23, minute=59, second=59)
    bugun = datetime.now().replace(hour=23, minute=59, second=59)
    badi = birim_adlari(conn)
    cur = conn.cursor()
    try:
        for kid, miktar, elle in kalemler:
            cur.execute("SELECT Kodu, Adi, CAST(StokBirim AS nvarchar(40)), Aktif FROM StokKarti WHERE Id = ?", kid)
            r = cur.fetchone()
            if not r:
                tz.satirlar.append(FisSatir(kid, f'Id {kid}', '', '', '', miktar, hata='Kart yok')); continue
            s = FisSatir(kid, (r[0] or '').strip(), (r[1] or '').strip(),
                         badi.get(str(r[2] or '').casefold().strip('{}'), ''), r[2], float(miktar))
            if not r[3]:
                s.hata = 'Pasif kart'
            elif not s.birim_guid:
                s.hata = 'Kartın birimi yok'
            elif s.miktar <= 0:
                s.hata = 'Miktar sıfır'
            if ISLEMLER[islem]['yon'] <= 0:          # çıkış / transfer: kaynakta yeterli mi
                b = min(depo_bakiye(cur, kid, depo_id, bt), depo_bakiye(cur, kid, depo_id, bugun))
                s.kaynak_bakiye = b
                if not s.hata and b < s.miktar - 1e-6:
                    s.hata = f'Depoda yetersiz (bakiye {b:g})'
                if not s.hata:
                    s.birim_fiyat = fifo(cur, kid, s.miktar, depo_id, bt)
            else:
                s.birim_fiyat = son_giris_fiyati(cur, kid)
            if elle is not None:
                s.birim_fiyat, s.fiyat_elle = round(float(elle), 6), True
            if not s.hata and not s.birim_fiyat:
                s.uyari = 'Fiyat 0 — maliyet sıfır yazılacak'
            tz.satirlar.append(s)
    finally:
        cur.close()
    return tz


# ───────────────────────── yazım ─────────────────────────
def _bosalt(cur) -> None:
    """Eski {SQL Server} sürücüsü MARS desteklemez: bekleyen sonuç kümelerini (tetikleyici satır sayıları) tüket."""
    try:
        while cur.nextset():
            pass
    except Exception:
        pass


def _sira_no(cur, islem: int, seri: str) -> int:
    cur.execute("""SELECT TOP 1 BelgeSiraNo FROM StokHareket WITH (UPDLOCK, HOLDLOCK)
                   WHERE IslemKodu = ? AND ISNULL(BelgeSeriNo, '') = ? ORDER BY Id DESC""", islem, seri)
    r = cur.fetchone()
    _bosalt(cur)
    return int(r[0] or 0) + 1 if r else 1


def fis_yaz(conn, tz: FisTaslak, commit: bool = False) -> dict:
    """Taslağı yazar. commit=False → yazar, kontrol eder, ROLLBACK (deneme)."""
    if tz.engel:
        raise ValueError('Fiş yazılamaz: ' + '; '.join(tz.engel))
    from db.sorgular import stok_guncel_bakiyeleri

    bilgi = ISLEMLER[tz.islem]
    bt = _belge_tarihi(tz.islem, tz.tarih)
    karsi = tz.karsi_depo_id if tz.islem == TRANSFER else None
    u = tz.kullanici_guid
    eski_ac = conn.autocommit
    conn.autocommit = False
    cur = conn.cursor()
    try:
        kodlar = sorted({s.kodu for s in tz.satirlar})
        once = stok_guncel_bakiyeleri(conn, kodlar, '2099-12-31')
        yer = ','.join('?' * len(kodlar))
        kum_sql = f"""SELECT sk.Kodu, k.GirenMiktar - k.CikanMiktar FROM StokKumulatif k
                        JOIN StokKarti sk ON sk.Id = k.StokKartId WHERE sk.Kodu IN ({yer})"""
        cur.execute(kum_sql, *kodlar)
        kum_once = {r[0]: float(r[1] or 0) for r in cur.fetchall()}
        sira = _sira_no(cur, tz.islem, bilgi['seri'])
        now = datetime.now()
        cur.execute("""SET NOCOUNT ON; INSERT INTO StokHareket (Aktif, IhracKayitliMi, IslemKodu, BelgeTarihi, BelgeSeriNo, BelgeSiraNo,
            DepoKartId, KarsiDepoKartId, ToplamTutar, SatirlarinIskontoToplamTutari, KdvMatrahiToplamTutari, KdvToplamTutari,
            KdvTevfikatTutari, OtvTutari, OzelIletisimVerigisiToplamTutari, NetTutar, IrsaliyedenMi, KonsinyedenMi, Acik,
            CreatedBy, CreationTime, ModifiedBy, ModificationTime, Notlar, EntegreDurumu, MusteriBolgeId, HareketBolgeId,
            ITS, PTS, EPDKdanmi, HatirlatmayaGelmesin, OdemePlaniIslendi, Odendi, InternetSatisi, KdvDahil)
          VALUES (1,0,?,?,?,?,?,?,?,0,0,0,0,0,0,?,0,0,0,?,?,?,?,?,0,2,2,0,0,0,0,0,0,0,0); SELECT CAST(SCOPE_IDENTITY() AS bigint)""",
            tz.islem, bt, bilgi['seri'] or None, sira, tz.depo_id, karsi, tz.toplam, tz.toplam,
            u, now, u, now, (tz.notlar or '').strip()[:250] or None)
        while cur.description is None:
            if not cur.nextset():
                raise RuntimeError('Fiş Id okunamadı')
        hid = int(cur.fetchone()[0])
        _bosalt(cur)

        for s in tz.satirlar:
            now = datetime.now()
            cur.execute("""INSERT INTO StokHareketDetay (Aktif, Yazdirma, Turu, HareketId, IslemKartId, KdvOrani, StokBirimId,
                Miktar, BirimFiyat, Tutar, OzelIslemVergisiOrani, DepoKartId, KarsiDepoKartId, BirimKatsayisi, MaliyetTarihi,
                MaliyetTutari, IslemKodu, IrsaliyedenMi, KalanMiktar, KonsinyedenMi, CreatedBy, CreationTime, ModifiedBy, ModificationTime)
              VALUES (1,0,1,?,?,0,?,?,?,?,0,?,?,?,?,?,?,0,?,0,?,?,?,?)""",
                hid, s.kart_id, s.birim_guid, s.miktar, s.birim_fiyat or 0, s.tutar, tz.depo_id, karsi,
                s.miktar, bt, s.tutar, tz.islem, s.miktar, u, now, u, now)
            _bosalt(cur)

        # ── kontroller (aynı transaction içinde) ──
        sorunlar = []
        sonra = stok_guncel_bakiyeleri(conn, kodlar, '2099-12-31')
        beklenen_fark = {}
        for s in tz.satirlar:
            beklenen_fark[s.kodu] = beklenen_fark.get(s.kodu, 0) + bilgi['yon'] * s.miktar
        for k in kodlar:
            if abs((sonra[k] - once[k]) - beklenen_fark.get(k, 0)) > 1e-6:
                sorunlar.append(f'{k}: bakiye değişimi beklenmedik ({once[k]:g} → {sonra[k]:g})')
        cur.execute(kum_sql, *kodlar)
        kum = {r[0]: float(r[1] or 0) for r in cur.fetchall()}
        # bazı kartlarda önbellek zaten farklı → yalnız fişin yarattığı değişimi karşılaştır (DECIMAL(18,2) yuvarlama payı)
        for k in kodlar:
            if k in kum_once and abs((kum[k] - kum_once[k]) - beklenen_fark.get(k, 0)) > 0.011:
                sorunlar.append(f'{k}: StokKumulatif değişimi {kum[k] - kum_once[k]:g}, beklenen {beklenen_fark.get(k, 0):g}')
        if bilgi['yon'] <= 0:
            for s in tz.satirlar:
                b = depo_bakiye(cur, s.kart_id, tz.depo_id, datetime.now().replace(hour=23, minute=59))
                if b < -1e-6:
                    sorunlar.append(f'{s.kodu}: kaynak depo eksiye düştü ({b:g})')

        sonuc = {'hareket_id': hid, 'belge': f"{bilgi['seri']} {sira}".strip(), 'islem': bilgi['ad'],
                 'satir': len(tz.satirlar), 'toplam': tz.toplam, 'sorunlar': sorunlar, 'commit': False}
        if commit and not sorunlar:
            conn.commit(); sonuc['commit'] = True
        else:
            conn.rollback()
        return sonuc
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.autocommit = eski_ac
