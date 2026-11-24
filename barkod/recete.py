"""Barkodla mamül reçetesine (`UretimReceteHatPlaniGirdi`) parça ekleme / miktar artırma.

Kurallar (`ERP-OKUMA.md` & `db/sorgular.py::kartlari_receteye_toplu_bagla`):
  - Yalnız aktif reçetenin (`UretimRecete.KullanimDisi = 0/NULL`) seçili mevcut hat planına
    (`UretimReceteHatPlani`) `Tipi=1` (StokKarti) bileşeni ekler veya mevcut tekil satırın miktarını artırır.
  - Zorunlu NOT NULL alanlar: `UretimReceteHatPlaniId`, `Tipi=1`, `KartId`, `Miktar`,
    `BirimId` (kartın kendi `StokBirim` GUID'si — NULL bırakılmaz),
    `DepoId` (hat planının `DepoId` değeri, boşsa 2=Merkez — NULL bırakılmaz),
    `SabitMiktar=0`, `GarantiKapsaminda=0`, `Yazdirma=0`.
  - Reçete başlığında `ModifiedBy = kullanici_guid` ve `ModificationTime = now` güncellenir
    (CEO ERP iyimser eşzamanlılık kontrolü için zorunlu).
  - `recete_yaz(..., commit=False)` deneme modudur: tek transaction içinde yazar, doğrular ve ROLLBACK yapar.
  - `recete_yaz(..., commit=True)` işlem öncesi değerleri JSON yedeğine (`recete_barkod_yedek_*.json`)
    ve `barkod_fis_gunlugu.jsonl`'a kaydedip COMMIT eder.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from db.baglanti import cursor_ctx


@dataclass
class ReceteSatir:
    kart_id: int
    kodu: str
    adi: str
    birim: str
    birim_guid: str
    eklenecek_miktar: float
    mevcut_girdi_id: int | None = None
    mevcut_miktar: float = 0.0
    hata: str = ''
    uyari: str = ''

    @property
    def yeni_miktar(self) -> float:
        return round(self.mevcut_miktar + self.eklenecek_miktar, 6)

    @property
    def islem_turu(self) -> str:
        return 'guncelle' if self.mevcut_girdi_id is not None else 'ekle'


@dataclass
class ReceteTaslak:
    recete_id: int | None
    mamul_kodu: str
    mamul_adi: str
    hat_plani_id: int | None
    hat_kodu: str
    hat_adi: str
    depo_id: int
    kullanici_guid: str
    satirlar: list[ReceteSatir] = field(default_factory=list)
    genel_hata: str = ''

    @property
    def engel(self) -> list[str]:
        e = []
        if self.genel_hata:
            e.append(self.genel_hata)
        if not self.mamul_kodu or not self.recete_id:
            e.append('Aktif mamül reçetesi seçilmedi')
        if not self.hat_plani_id:
            e.append('Reçete hat planı (grup) seçilmedi')
        if not self.kullanici_guid:
            e.append('Sağ üstten Kullanıcı seçilmedi')
        if not self.satirlar:
            e.append('Liste boş')
        e.extend(f'{s.kodu}: {s.hata}' for s in self.satirlar if s.hata)
        return e


def _bosalt(cur) -> None:
    try:
        while cur.nextset():
            pass
    except Exception:
        pass


# ───────────────────────── okuma sorguları ─────────────────────────
def aktif_mamuller(conn) -> list[dict]:
    """Aktif reçetesi olan mamüller: [{'recete_id', 'kodu', 'adi', 'hat_sayisi'}, ...]."""
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT ur.Id, ur.Kodu, ISNULL(sk.Adi, ur.Tanim), COUNT(hp.Id)
            FROM UretimRecete ur
            LEFT JOIN StokKarti sk ON sk.Kodu = ur.Kodu AND sk.Aktif = 1
            LEFT JOIN UretimReceteHatPlani hp ON hp.UretimReceteId = ur.Id
            WHERE (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
            GROUP BY ur.Id, ur.Kodu, ISNULL(sk.Adi, ur.Tanim)
            HAVING COUNT(hp.Id) > 0
            ORDER BY ur.Kodu
        """)
        return [{
            'recete_id': int(r[0]),
            'kodu': (r[1] or '').strip(),
            'adi': (r[2] or '').strip(),
            'hat_sayisi': int(r[3] or 0),
        } for r in cur.fetchall()]


def hat_planlari_getir(conn, mamul_kodu: str) -> list[dict]:
    """Seçili mamülün hat planları: [{'id', 'recete_id', 'kod', 'ad', 'tip', 'depo_id', 'girdi_sayisi'}]."""
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT hp.Id, ur.Id, ISNULL(sk.Kodu, ''), ISNULL(sk.Adi, ''),
                   ISNULL(hp.Tipi, 1), ISNULL(hp.DepoId, 2),
                   (SELECT COUNT(*) FROM UretimReceteHatPlaniGirdi g WHERE g.UretimReceteHatPlaniId = hp.Id)
            FROM UretimRecete ur
            JOIN UretimReceteHatPlani hp ON hp.UretimReceteId = ur.Id
            LEFT JOIN StokKarti sk ON sk.Id = hp.KartId
            WHERE ur.Kodu = ?
              AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
            ORDER BY ur.Id, hp.Id
        """, mamul_kodu)
        return [{
            'id': int(r[0]),
            'recete_id': int(r[1]),
            'kod': (r[2] or '').strip(),
            'ad': (r[3] or '').strip(),
            'tip': int(r[4]),
            'depo_id': int(r[5] or 2),
            'girdi_sayisi': int(r[6] or 0),
        } for r in cur.fetchall()]


def hat_girdileri_getir(conn, hat_plani_id: int) -> list[dict]:
    """Seçili hat planındaki mevcut girdiler (Stok Tipi=1 ve Masraf Tipi=2)."""
    from barkod.sorgu import birim_adlari
    badi = birim_adlari(conn)
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT g.Id, g.Tipi, g.KartId,
                   CASE WHEN g.Tipi = 2 THEN ISNULL(smk.Kodu, '') ELSE ISNULL(sk.Kodu, '') END AS Kodu,
                   CASE WHEN g.Tipi = 2 THEN ISNULL(smk.Adi, '')  ELSE ISNULL(sk.Adi, '')  END AS Adi,
                   ISNULL(g.Miktar, 0),
                   CAST(COALESCE(g.BirimId, sk.StokBirim, smk.StokBirimId) AS nvarchar(40))
            FROM UretimReceteHatPlaniGirdi g
            LEFT JOIN StokKarti sk        ON g.Tipi = 1 AND sk.Id  = g.KartId
            LEFT JOIN StokMasrafKarti smk ON g.Tipi = 2 AND smk.Id = g.KartId
            WHERE g.UretimReceteHatPlaniId = ?
            ORDER BY g.Tipi, Kodu, g.Id
        """, hat_plani_id)
        rows = cur.fetchall()
    return [{
        'girdi_id': int(r[0]),
        'tipi': int(r[1] or 1),
        'tur': 'Masraf' if int(r[1] or 1) == 2 else 'Stok',
        'kart_id': int(r[2]) if r[2] is not None else 0,
        'kodu': (r[3] or '').strip(),
        'adi': (r[4] or '').strip(),
        'miktar': float(r[5] or 0),
        'birim': badi.get(str(r[6] or '').casefold().strip('{}'), ''),
    } for r in rows]


# ───────────────────────── taslak hazırlama ─────────────────────────
def recete_taslak_hazirla(
    conn,
    mamul_kodu: str,
    hat_plani_id: int | None,
    kalemler: list[tuple[int, float]],
    kullanici_guid: str,
) -> ReceteTaslak:
    """[(kart_id, eklenecek_miktar), ...] → kontrol edilmiş ReceteTaslak (veritabanına yazmaz)."""
    from barkod.sorgu import birim_adlari
    badi = birim_adlari(conn)

    recete_id = None
    mamul_adi = ''
    hat_kodu = ''
    hat_adi = ''
    depo_id = 2
    genel_hata = ''

    with cursor_ctx(conn) as cur:
        if mamul_kodu and hat_plani_id:
            cur.execute("""
                SELECT TOP 1 ur.Id, ISNULL(sk_m.Adi, ur.Tanim),
                       ISNULL(sk_h.Kodu, ''), ISNULL(sk_h.Adi, ''), ISNULL(hp.DepoId, 2)
                FROM UretimRecete ur
                JOIN UretimReceteHatPlani hp ON hp.UretimReceteId = ur.Id
                LEFT JOIN StokKarti sk_m ON sk_m.Kodu = ur.Kodu AND sk_m.Aktif = 1
                LEFT JOIN StokKarti sk_h ON sk_h.Id = hp.KartId
                WHERE ur.Kodu = ?
                  AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
                  AND hp.Id = ?
            """, mamul_kodu, hat_plani_id)
            r = cur.fetchone()
            if r:
                recete_id = int(r[0])
                mamul_adi = (r[1] or '').strip()
                hat_kodu = (r[2] or '').strip()
                hat_adi = (r[3] or '').strip()
                depo_id = int(r[4] or 2)
            else:
                genel_hata = f'Seçilen hat planı ({hat_plani_id}) aktif {mamul_kodu} reçetesine ait değil'

        tz = ReceteTaslak(
            recete_id=recete_id,
            mamul_kodu=mamul_kodu or '',
            mamul_adi=mamul_adi,
            hat_plani_id=hat_plani_id,
            hat_kodu=hat_kodu,
            hat_adi=hat_adi,
            depo_id=depo_id,
            kullanici_guid=kullanici_guid or '',
            genel_hata=genel_hata,
        )

        for kid, miktar in kalemler:
            cur.execute(
                "SELECT Kodu, Adi, CAST(StokBirim AS nvarchar(40)), Aktif FROM StokKarti WHERE Id = ?",
                kid,
            )
            kr = cur.fetchone()
            if not kr:
                tz.satirlar.append(ReceteSatir(kid, f'Id {kid}', '', '', '', float(miktar), hata='Kart bulunamadı'))
                continue
            kodu = (kr[0] or '').strip()
            adi = (kr[1] or '').strip()
            b_guid = (kr[2] or '').strip()
            birim = badi.get(b_guid.casefold().strip('{}'), '')
            aktif = bool(kr[3])

            s = ReceteSatir(kid, kodu, adi, birim, b_guid, round(float(miktar), 6))
            if not aktif:
                s.hata = 'Pasif kart'
            elif not b_guid:
                s.hata = 'Kartta birim tanımlı değil'
            elif s.eklenecek_miktar <= 0:
                s.hata = 'Miktar sıfırdan büyük olmalı'
            elif mamul_kodu and kodu.upper() == mamul_kodu.upper():
                s.hata = 'Mamül kendi reçetesine bileşen olarak eklenemez'
            elif hat_kodu and kodu.upper() == hat_kodu.upper():
                s.hata = 'Hat grubu kartı kendi altına bileşen olarak eklenemez'

            if recete_id and hat_plani_id:
                # 1) Seçili hat planında zaten var mı?
                cur.execute("""
                    SELECT Id, ISNULL(Miktar, 0)
                    FROM UretimReceteHatPlaniGirdi
                    WHERE UretimReceteHatPlaniId = ? AND Tipi = 1 AND KartId = ?
                    ORDER BY Id
                """, hat_plani_id, kid)
                mevcutlar = cur.fetchall()
                if len(mevcutlar) == 1:
                    s.mevcut_girdi_id = int(mevcutlar[0][0])
                    s.mevcut_miktar = round(float(mevcutlar[0][1] or 0), 6)
                    if not s.hata:
                        s.uyari = f'Mevcut miktar artırılacak ({s.mevcut_miktar:g} → {s.yeni_miktar:g})'
                elif len(mevcutlar) > 1:
                    s.mevcut_girdi_id = int(mevcutlar[0][0])
                    s.mevcut_miktar = round(sum(float(m[1] or 0) for m in mevcutlar), 6)
                    if not s.hata:
                        s.hata = f'Bu hatta {len(mevcutlar)} mükerrer girdi satırı var; önce reçete temizlenmeli'

                # 2) Aynı reçetenin başka bir hat planında var mı?
                cur.execute("""
                    SELECT ISNULL(sk.Kodu, CAST(hp.Id AS nvarchar(20))), ISNULL(g.Miktar, 0)
                    FROM UretimReceteHatPlaniGirdi g
                    JOIN UretimReceteHatPlani hp ON hp.Id = g.UretimReceteHatPlaniId
                    LEFT JOIN StokKarti sk ON sk.Id = hp.KartId
                    WHERE hp.UretimReceteId = ? AND hp.Id <> ? AND g.Tipi = 1 AND g.KartId = ?
                """, recete_id, hat_plani_id, kid)
                diger = cur.fetchall()
                if diger and not s.hata:
                    ozet = ', '.join(f"{(r[0] or '').strip()}: {float(r[1] or 0):g}" for r in diger)
                    ek = f'Diğer hatta da var ({ozet})'
                    s.uyari = f'{s.uyari} · {ek}' if s.uyari else ek

            tz.satirlar.append(s)
    return tz


# ───────────────────────── yazım (dry-run & commit) ─────────────────────────
def _yedek_yaz(veri: dict) -> Path:
    from config import CONFIG_PATH
    dizin = Path(CONFIG_PATH).parent
    yol = dizin / f"recete_barkod_yedek_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(yol, 'w', encoding='utf-8') as f:
        json.dump(veri, f, ensure_ascii=False, indent=2, default=str)
    return yol


def recete_yaz(conn, tz: ReceteTaslak, commit: bool = False) -> dict:
    """Reçete taslağını tek transaction içinde uygular.

    commit=False → tüm INSERT/UPDATE ve doğrulama sorgularını çalıştırıp ROLLBACK yapar (deneme).
    commit=True  → JSON yedeği yazar ve doğrulama temizse COMMIT eder.
    """
    if tz.engel:
        raise ValueError('Reçeteye yazılamaz: ' + '; '.join(tz.engel))

    eski_ac = conn.autocommit
    conn.autocommit = False
    cur = conn.cursor()
    try:
        # 1. Reçete ve hat planını kilitleyip doğrula
        cur.execute("""
            SELECT ur.Id, ISNULL(hp.DepoId, 2), CAST(ur.ModifiedBy AS nvarchar(40)), ur.ModificationTime
            FROM UretimRecete ur WITH (UPDLOCK, HOLDLOCK)
            JOIN UretimReceteHatPlani hp ON hp.UretimReceteId = ur.Id
            WHERE ur.Id = ? AND hp.Id = ?
              AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
        """, tz.recete_id, tz.hat_plani_id)
        hdr = cur.fetchone()
        if not hdr:
            raise ValueError(f'Aktif reçete / hat planı bulunamadı ({tz.mamul_kodu} / {tz.hat_plani_id})')
        depo_id = int(hdr[1] or 2)
        onceki_mod_by = hdr[2]
        onceki_mod_time = hdr[3]

        eklenenler = []
        guncellenenler = []
        sorunlar = []

        for s in tz.satirlar:
            # Transaction içinde mevcut durumu tekrar oku
            cur.execute("""
                SELECT Id, ISNULL(Miktar, 0)
                FROM UretimReceteHatPlaniGirdi
                WHERE UretimReceteHatPlaniId = ? AND Tipi = 1 AND KartId = ?
                ORDER BY Id
            """, tz.hat_plani_id, s.kart_id)
            mevcutlar = cur.fetchall()
            if len(mevcutlar) > 1:
                sorunlar.append(f'{s.kodu}: hatta {len(mevcutlar)} mükerrer satır bulundu')
                continue

            if len(mevcutlar) == 1:
                gid = int(mevcutlar[0][0])
                eski_m = float(mevcutlar[0][1] or 0)
                hedef_m = Decimal(str(round(eski_m + s.eklenecek_miktar, 6)))
                cur.execute("""
                    UPDATE UretimReceteHatPlaniGirdi
                    SET Miktar = ?,
                        BirimId = COALESCE(BirimId, ?),
                        DepoId  = COALESCE(DepoId, ?)
                    WHERE Id = ?
                """, hedef_m, s.birim_guid, depo_id, gid)
                _bosalt(cur)
                guncellenenler.append({
                    'girdi_id': gid, 'kart_id': s.kart_id, 'kodu': s.kodu,
                    'eski_miktar': eski_m, 'eklenen_miktar': s.eklenecek_miktar,
                    'yeni_miktar': float(hedef_m),
                })
            else:
                hedef_m = Decimal(str(round(s.eklenecek_miktar, 6)))
                cur.execute("""
                    SET NOCOUNT ON;
                    INSERT INTO UretimReceteHatPlaniGirdi
                        (UretimReceteHatPlaniId, Tipi, KartId, Miktar,
                         SabitMiktar, GarantiKapsaminda, BirimId, DepoId, Yazdirma)
                    VALUES (?, 1, ?, ?, 0, 0, ?, ?, 0);
                    SELECT CAST(SCOPE_IDENTITY() AS bigint);
                """, tz.hat_plani_id, s.kart_id, hedef_m, s.birim_guid, depo_id)
                while cur.description is None:
                    if not cur.nextset():
                        raise RuntimeError(f'{s.kodu}: yeni girdi Id okunamadı')
                yeni_id = int(cur.fetchone()[0])
                _bosalt(cur)
                eklenenler.append({
                    'girdi_id': yeni_id, 'kart_id': s.kart_id, 'kodu': s.kodu,
                    'miktar': float(hedef_m), 'birim_guid': s.birim_guid, 'depo_id': depo_id,
                })

            # Satır doğrulaması (NULL alan veya miktar uyumsuzluğu var mı?)
            cur.execute("""
                SELECT Miktar, BirimId, DepoId
                FROM UretimReceteHatPlaniGirdi
                WHERE UretimReceteHatPlaniId = ? AND Tipi = 1 AND KartId = ?
            """, tz.hat_plani_id, s.kart_id)
            kontrol = cur.fetchall()
            if len(kontrol) != 1:
                sorunlar.append(f'{s.kodu}: yazım sonrası satır sayısı {len(kontrol)}')
            else:
                km, kb, kd = kontrol[0]
                if abs(float(km or 0) - float(hedef_m)) > 1e-5:
                    sorunlar.append(f'{s.kodu}: miktar doğrulanamadı ({km} != {hedef_m})')
                if kb is None or kd is None:
                    sorunlar.append(f'{s.kodu}: BirimId veya DepoId NULL kaldı')

        now = datetime.now()
        cur.execute("""
            UPDATE UretimRecete
            SET ModifiedBy = ?, ModificationTime = ?
            WHERE Id = ?
        """, tz.kullanici_guid, now, tz.recete_id)
        _bosalt(cur)

        sonuc = {
            'recete_id': tz.recete_id,
            'mamul_kodu': tz.mamul_kodu,
            'hat_plani_id': tz.hat_plani_id,
            'hat_kodu': tz.hat_kodu,
            'eklenen': eklenenler,
            'guncellenen': guncellenenler,
            'sorunlar': sorunlar,
            'yedek_dosya': '',
            'commit': False,
        }

        if commit and not sorunlar:
            yedek_yol = _yedek_yaz({
                'zaman': now.strftime('%Y-%m-%d %H:%M:%S'),
                'islem': 'barkod_recete_ekle',
                'kullanici_guid': tz.kullanici_guid,
                'recete_id': tz.recete_id,
                'mamul_kodu': tz.mamul_kodu,
                'hat_plani_id': tz.hat_plani_id,
                'hat_kodu': tz.hat_kodu,
                'onceki_modified_by': onceki_mod_by,
                'onceki_modification_time': str(onceki_mod_time or ''),
                'eklenen_satirlar': eklenenler,
                'guncellenen_satirlar': guncellenenler,
            })
            conn.commit()
            sonuc['commit'] = True
            sonuc['yedek_dosya'] = str(yedek_yol)
        else:
            conn.rollback()
        return sonuc
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.autocommit = eski_ac
