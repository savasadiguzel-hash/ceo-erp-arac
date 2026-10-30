"""
Tüm veri erişimi bu modülden yapılır. SQL Server ile çalışır.
Kural: her sorgu cursor_ctx(conn) ile açılır; finally bloğu cursor'ı kesinlikle kapatır.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from db.baglanti import cursor_ctx


def _kod23_paired_ids_str(conn) -> str:
    """
    IslemKodu=23 kayıtları arasında, aynı IslemKartId + BelgeSiraNo için
    IslemKodu=5 (Alış İrsaliyesi) eşi olan StokHareket.Id listesini döner.
    Bu kayıtlar depoya irsaliye kökenli girişi temsil eder ve GirenMiktar olarak sayılır.
    Eşi olmayan IslemKodu=23 (saf depo transferi) sayılmaz — karşı IslemKodu=18 ile netleşir.
    Sonuç: SQL IN operatörüne hazır string (örn. '743389,741897').
    Eş yok ise '-1' döner (boş IN listesi yerine geçer).
    """
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT DISTINCT sh23.Id
            FROM StokHareket sh23
            JOIN StokHareketDetay shd23 ON shd23.HareketId = sh23.Id
            WHERE sh23.IslemKodu = 23 AND sh23.Aktif = 1
              AND EXISTS (
                  SELECT 1 FROM StokHareket sh5
                  JOIN StokHareketDetay shd5 ON shd5.HareketId = sh5.Id
                  WHERE sh5.IslemKodu = 5 AND sh5.Aktif = 1
                    AND sh5.BelgeSiraNo  = sh23.BelgeSiraNo
                    AND shd5.IslemKartId = shd23.IslemKartId
              )
        """)
        ids = [str(int(r[0])) for r in cur.fetchall()]
    return ','.join(ids) if ids else '-1'


# ── Araç 1: Mamül Ağacı Bağlantı ──────────────────────────────────────────────

def tarama_istatistikleri(conn) -> list[tuple[str, int]]:
    """İlerleme animasyonu için (mesaj, toplam) çiftleri döner."""
    adimlar = []
    with cursor_ctx(conn) as cur:
        cur.execute("SELECT COUNT(*) FROM StokKarti WHERE Aktif=1")
        n = cur.fetchone()[0] or 0
        adimlar.append(("Stok kartları taranıyor…", n))
    with cursor_ctx(conn) as cur:
        cur.execute("SELECT COUNT(*) FROM UretimReceteHatPlani")
        n = cur.fetchone()[0] or 0
        adimlar.append(("Reçeteler inceleniyor…", max(n, 1)))
    with cursor_ctx(conn) as cur:
        cur.execute("SELECT COUNT(*) FROM StokMasrafKarti WHERE Aktif=1")
        n = cur.fetchone()[0] or 0
        adimlar.append(("Masraf kartları taranıyor…", max(n, 1)))
    return adimlar


def mamul_agaci_listesi(conn) -> list[tuple[str, str]]:
    """
    [(kod, ad), ...] döner. Aktif reçetesi olan (bizim ürettiğimiz) mamülleri listeler.

    DÜZELTME (2026-09-14): Eskiden `UretimReceteHatPlani.KartId = sk.Id` eşleşmesine
    bakıyordu. Bu YANLIŞ — HatPlani.KartId, ürünün kendisini değil, o reçetenin
    alt-montaj/bileşen GRUBUNU temsil eder (bkz. UretimRecete→UretimReceteHatPlani→
    UretimReceteHatPlaniGirdi hiyerarşisi, ERP-OKUMA.md). Tek-hatlı "basit" reçetelerde
    HatPlani.KartId tesadüfen ürünün kendi kartına eşitti (self-reference) ama çok-hatlı
    montaj reçetelerinde (ör. GMP-101-230022 — 5 ayrı hat grubu, hiçbiri kendi kartına
    referans vermiyor) bu eşleşme hiç oluşmuyor ve ürün tamamen kayboluyordu.

    Doğrusu, `uretim_emir_bom_patlat()`'ın da kullandığı desen: bir StokKarti'nin
    "mamul" sayılması için `UretimRecete.Kodu = StokKarti.Kodu` eşleşen aktif bir
    reçete başlığının var olması yeterli ve gerekli — hat planının kaç gruba
    bölündüğü önemli değil.
    """
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT DISTINCT sk.Kodu, sk.Adi
            FROM StokKarti sk
            INNER JOIN UretimRecete ur ON ur.Kodu = sk.Kodu
            WHERE sk.Aktif = 1
              AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
            ORDER BY sk.Kodu
        """)
        return [(r[0], r[1]) for r in cur.fetchall()]


def mamul_hat_planlari(conn, mamul_kodu: str) -> list[dict]:
    """Aktif mamül reçetesindeki seçilebilir hat planlarını döner."""
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT hp.Id, ISNULL(sk.Kodu, ''), ISNULL(sk.Adi, ''), hp.Tipi
            FROM UretimRecete ur
            JOIN UretimReceteHatPlani hp ON hp.UretimReceteId = ur.Id
            LEFT JOIN StokKarti sk ON sk.Id = hp.KartId
            WHERE ur.Kodu = ?
              AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
            ORDER BY ur.Id, hp.Id
        """, mamul_kodu)
        return [
            {"id": int(r[0]), "kod": str(r[1]), "ad": str(r[2]), "tip": int(r[3])}
            for r in cur.fetchall()
        ]


def recetesiz_stok_hareketleri(conn, bas_tarih: str, bit_tarih: str) -> list[dict]:
    """
    Kesişim kümesindeki stokların alış faturası/irsaliyesi satırlarını döner.
    bas_tarih / bit_tarih: 'DD.MM.YYYY' formatı.
    Her eleman: stok_kodu, stok_adi, hareket_id, islem_turu, belge_no,
                tarih (DD.MM.YYYY), tarih_iso (YYYY-MM-DD),
                miktar, birim_fiyat, tutar, tedarikci

    Faturalaşan irsaliye — mükerrer sayım düzeltmesi: bkz. satis_faturalari()
    ve proje_satinalma_hareketleri() docstring'leri. Sadece IslemKodu=1
    (Alış Faturası) VE FaturaId'si BOŞ olan IslemKodu=5 (henüz faturalaşmamış
    irsaliye) satırları toplanır — aksi hâlde aynı alım iki kez sayılır.
    """
    bas_parts = bas_tarih.split('.')
    bit_parts = bit_tarih.split('.')
    bas_sql = f"{bas_parts[2]}-{bas_parts[1]}-{bas_parts[0]}"
    bit_sql = f"{bit_parts[2]}-{bit_parts[1]}-{bit_parts[0]}"

    with cursor_ctx(conn) as cur:
        cur.execute(f"""
            SELECT
                sk.Kodu,
                sk.Adi,
                ISNULL(sk.Adi2, ''),
                sh.Id,
                CASE sh.IslemKodu WHEN 1 THEN 'Alış Faturası' ELSE 'Alış İrsaliyesi' END,
                ISNULL(sh.BelgeSeriNo, '') + ISNULL(CAST(sh.BelgeSiraNo AS VARCHAR(20)), '') ,
                CONVERT(VARCHAR(10), sh.BelgeTarihi, 104),
                CONVERT(VARCHAR(10), sh.BelgeTarihi, 120),
                ISNULL(shd.Miktar, 0),
                ISNULL(shd.BirimFiyat, 0),
                ISNULL(shd.Tutar, 0),
                ISNULL(cmk.Unvani, '')
            FROM StokKarti sk
            JOIN StokHareketDetay shd ON shd.IslemKartId = sk.Id
            JOIN StokHareket sh ON sh.Id = shd.HareketId
            LEFT JOIN CariMusteriKarti cmk ON sh.MusteriKartId = cmk.Id
            WHERE sk.Id NOT IN (
                SELECT DISTINCT KartId FROM UretimReceteHatPlani WHERE KartId IS NOT NULL
            )
              AND sk.Id NOT IN (
                SELECT DISTINCT KartId FROM UretimReceteHatPlaniGirdi WHERE KartId IS NOT NULL
              )
              AND sk.Id NOT IN (
                SELECT DISTINCT KartId FROM UrunAgaciDetay WHERE KartId IS NOT NULL
              )
              AND sk.Aktif = 1
              AND (sh.IslemKodu = 1 OR (sh.IslemKodu = 5 AND sh.FaturaId IS NULL))
              AND shd.Turu = 1
              AND shd.BirimFiyat > 0
              AND shd.Miktar > 0
              AND CAST(sh.BelgeTarihi AS DATE) >= CAST('{bas_sql}' AS DATE)
              AND CAST(sh.BelgeTarihi AS DATE) <= CAST('{bit_sql}' AS DATE)
            ORDER BY sk.Kodu, sh.BelgeTarihi ASC, sh.Id ASC
        """)
        return [
            {
                'stok_kodu':   row[0],
                'kart_tipi':   'stok',
                'stok_adi':    row[1],
                'stok_adi2':   row[2],
                'hareket_id':  int(row[3]),
                'islem_turu':  row[4],
                'belge_no':    row[5],
                'tarih':       row[6],
                'tarih_iso':   row[7],
                'miktar':      float(row[8]),
                'birim_fiyat': float(row[9]),
                'tutar':       float(row[10]),
                'tedarikci':   row[11],
            }
            for row in cur.fetchall()
        ]


def recetesiz_masraf_hareketleri(conn, bas_tarih: str, bit_tarih: str) -> list[dict]:
    """Alış belgesi olan ve hiçbir reçetede girdi olmayan masraf kartları."""
    bas_g, bas_a, bas_y = bas_tarih.split('.')
    bit_g, bit_a, bit_y = bit_tarih.split('.')
    bas_sql = f"{bas_y}-{bas_a}-{bas_g}"
    bit_sql = f"{bit_y}-{bit_a}-{bit_g}"
    with cursor_ctx(conn) as cur:
        cur.execute(f"""
            SELECT smk.Kodu, smk.Adi, sh.Id,
                   CASE sh.IslemKodu WHEN 1 THEN 'Alış Faturası'
                        ELSE 'Alış İrsaliyesi' END,
                   ISNULL(sh.BelgeSeriNo, '') + ISNULL(CAST(sh.BelgeSiraNo AS VARCHAR(20)), ''),
                   CONVERT(VARCHAR(10), sh.BelgeTarihi, 104),
                   CONVERT(VARCHAR(10), sh.BelgeTarihi, 120),
                   ISNULL(shd.Miktar, 0), ISNULL(shd.BirimFiyat, 0),
                   ISNULL(shd.Tutar, 0), ISNULL(cmk.Unvani, '')
            FROM StokMasrafKarti smk
            JOIN StokHareketDetay shd ON shd.IslemKartId = smk.Id
            JOIN StokHareket sh ON sh.Id = shd.HareketId
            LEFT JOIN CariMusteriKarti cmk ON cmk.Id = sh.MusteriKartId
            WHERE smk.Aktif = 1
              AND NOT EXISTS (
                  SELECT 1 FROM UretimReceteHatPlaniGirdi gi
                  WHERE gi.KartId = smk.Id AND gi.Tipi = 2
              )
              AND (sh.IslemKodu = 1 OR (sh.IslemKodu = 5 AND sh.FaturaId IS NULL))
              AND shd.Turu = 3
              AND shd.BirimFiyat > 0 AND shd.Miktar > 0
              AND CAST(sh.BelgeTarihi AS DATE) >= CAST('{bas_sql}' AS DATE)
              AND CAST(sh.BelgeTarihi AS DATE) <= CAST('{bit_sql}' AS DATE)
            ORDER BY smk.Kodu, sh.BelgeTarihi, sh.Id
        """)
        return [
            {
                'kart_tipi': 'masraf', 'stok_kodu': row[0], 'stok_adi': row[1],
                'stok_adi2': '', 'hareket_id': int(row[2]),
                'islem_turu': row[3], 'belge_no': row[4],
                'tarih': row[5], 'tarih_iso': row[6],
                'miktar': float(row[7]), 'birim_fiyat': float(row[8]),
                'tutar': float(row[9]), 'tedarikci': row[10],
            }
            for row in cur.fetchall()
        ]


def recetesiz_faturali_ozet(hareketler: list[dict], yontem: str) -> list[dict]:
    """
    Ham hareket listesini kart türü ve koduna göre özetler.
    yontem: 'FIFO' → ilk alış fiyatı, 'LIFO' → son alış fiyatı,
            'WA'   → ağırlıklı ortalama (toplam tutar / toplam miktar)
    """
    from collections import defaultdict
    gruplar: dict[tuple[str, str], list] = defaultdict(list)
    for h in hareketler:
        gruplar[(h.get('kart_tipi', 'stok'), h['stok_kodu'])].append(h)

    ozet = []
    for kart_tipi, stok_kodu in sorted(gruplar):
        grup = gruplar[(kart_tipi, stok_kodu)]
        sirali = sorted(grup, key=lambda x: (x['tarih_iso'], x['hareket_id']))

        if yontem == 'FIFO':
            ref = sirali[0]
            birim_fiyat = ref['birim_fiyat']
        elif yontem == 'LIFO':
            ref = sirali[-1]
            birim_fiyat = ref['birim_fiyat']
        else:  # WA
            ref = sirali[-1]
            total_tutar  = sum(h['tutar']  for h in grup)
            total_miktar = sum(h['miktar'] for h in grup)
            birim_fiyat  = total_tutar / total_miktar if total_miktar > 0 else 0.0

        ozet.append({
            'stok_kodu':   stok_kodu,
            'kart_tipi':   kart_tipi,
            'stok_adi':    grup[0]['stok_adi'],
            'stok_adi2':   grup[0].get('stok_adi2', ''),
            'fatura_sayisi': len(set(h['hareket_id'] for h in grup)),
            'birim_fiyat': round(birim_fiyat, 4),
            'ilk_fatura':  sirali[0]['tarih'],
            'son_fatura':  sirali[-1]['tarih'],
            'tedarikci':   ref['tedarikci'],
        })
    return ozet


def stok_birimleri_getir(conn, stok_kodlari: list) -> dict:
    """
    Stok kodları için birim adlarını döner: {stok_kodu: birim_adi}.

    CEO ERP'de birim ana tablosu şirket veritabanında değil, ortak
    ``CeoCommon`` veritabanında tutulur. Şirket veritabanında tablo yoksa
    eskiden her bilinmeyen GUID'i ADET gösteriyorduk; bu, KG/METRE gibi
    birimlerin raporda yanlış görünmesine yol açıyordu. Çözülemeyen birimi
    artık ADET diye etiketlemeyip ``Bilinmiyor`` döndürüyoruz.
    """
    if not stok_kodlari:
        return {}
    # StokKarti.StokBirim sütunu (uniqueidentifier) GUID olarak alınır
    guid_map: dict[str, str] = {}
    _YIGIN = 500
    for i in range(0, len(stok_kodlari), _YIGIN):
        parca = stok_kodlari[i: i + _YIGIN]
        yer = ','.join(['?'] * len(parca))
        with cursor_ctx(conn) as cur:
            cur.execute(
                f"SELECT Kodu, ISNULL(CONVERT(NVARCHAR(50), StokBirim), '') "
                f"FROM StokKarti WHERE Kodu IN ({yer})",
                *parca
            )
            for row in cur.fetchall():
                guid_map[row[0]] = str(row[1])
    # GUID → birim adı çözümlemesi. Birim ana tablosu CeoCommon'dadır.
    birimler = birimleri_getir(conn)          # {Adi: guid_str}
    guid_to_adi = {
        str(v).casefold().strip('{}'): k
        for k, v in birimler.items()
    }
    return {
        kod: (guid_to_adi.get(guid.casefold().strip('{}'), 'Bilinmiyor')
              if guid else 'Bilinmiyor')
        for kod, guid in guid_map.items()
    }


def masraf_birimleri_getir(conn, masraf_kodlari: list) -> dict:
    """Masraf kartlarının birimlerini CeoCommon sözlüğünden çözer."""
    if not masraf_kodlari:
        return {}
    guid_map = {}
    for i in range(0, len(masraf_kodlari), 500):
        parca = masraf_kodlari[i:i + 500]
        yer = ','.join('?' for _ in parca)
        with cursor_ctx(conn) as cur:
            cur.execute(
                f"SELECT Kodu, ISNULL(CONVERT(NVARCHAR(50), StokBirimId), '') "
                f"FROM StokMasrafKarti WHERE Aktif = 1 AND Kodu IN ({yer})",
                *parca,
            )
            for kod, guid in cur.fetchall():
                guid_map[kod] = str(guid)
    guid_to_adi = {
        str(guid).casefold().strip('{}'): adi
        for adi, guid in birimleri_getir(conn).items()
    }
    return {
        kod: (guid_to_adi.get(guid.casefold().strip('{}'), 'Bilinmiyor')
              if guid else 'Bilinmiyor')
        for kod, guid in guid_map.items()
    }


def stok_guncel_bakiyeleri(conn, stok_kodlari: list, tarih: str | None = None) -> dict:
    """
    Verilen stok kodları için belirtilen tarih itibarıyla güncel stok bakiyesi.
    `tarih` verilmezse bugün kullanılır (format: 'YYYY-MM-DD').
    Döner: {stok_kodu: bakiye_float}
    """
    from datetime import date
    if not stok_kodlari:
        return {}
    bugun = tarih or date.today().strftime('%Y-%m-%d')
    sonuc = {k: 0.0 for k in stok_kodlari}
    _YIGIN = 500
    for i in range(0, len(stok_kodlari), _YIGIN):
        parca = stok_kodlari[i: i + _YIGIN]
        yer = ','.join(['?'] * len(parca))
        with cursor_ctx(conn) as cur:
            cur.execute(f"""
                SELECT sk.Kodu,
                       SUM(CASE
                           WHEN sh.IslemKodu IN (1,4,5,8,15,16,20,22,26,29)
                               THEN (shd.Miktar - ISNULL(shd_f.Miktar, 0))
                           WHEN sh.IslemKodu IN (2,3,6,7,17,18,19,21,24,28)
                               THEN -(shd.Miktar - ISNULL(shd_f.Miktar, 0))
                           ELSE 0
                       END)
                FROM StokHareketDetay shd
                JOIN StokHareket sh    ON sh.Id  = shd.HareketId
                LEFT JOIN StokHareketDetay shd_f ON shd_f.Id = shd.FaturaDetayId
                JOIN StokKarti sk      ON sk.Id  = shd.IslemKartId
                WHERE sk.Kodu IN ({yer})
                  AND shd.Turu = 1 AND shd.Aktif = 1
                  AND sh.Aktif = 1
                  AND sh.FaturaId IS NULL
                  AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27,23)
                  AND CAST(sh.BelgeTarihi AS DATE) <= CAST('{bugun}' AS DATE)
                GROUP BY sk.Kodu
            """, *parca)
            for row in cur.fetchall():
                if row[0] in sonuc:
                    sonuc[row[0]] = float(row[1]) if row[1] is not None else 0.0
    return sonuc


def karti_receteye_bagla(
    conn, kart_kodu: str, kart_tipi: str, mamul_kodu: str,
    hat_plani_id: int, miktar: float,
) -> int:
    """Tek kart bağlama çağrıları için toplu işlemin bir kartlık sürümü."""
    return kartlari_receteye_toplu_bagla(
        conn, [{"kart_kodu": kart_kodu, "kart_tipi": kart_tipi, "miktar": miktar}],
        mamul_kodu, hat_plani_id,
    )[0]


def kartlari_receteye_toplu_bagla(
    conn, kartlar: list[dict], mamul_kodu: str, hat_plani_id: int,
    ilerleme=None,
) -> list[int]:
    """Seçilen kartları mevcut reçete grubuna tek transaction içinde ekler."""
    kart_tablolari = {
        'stok': ('StokKarti', 'StokBirim', 1),
        'masraf': ('StokMasrafKarti', 'StokBirimId', 2),
    }
    if not kartlar:
        raise ValueError("Bağlanacak kart seçilmedi.")
    if hat_plani_id is None:
        raise ValueError("Reçete grubu seçilmedi.")

    hazir = []
    gorulen = set()
    for kart in kartlar:
        kod = str(kart.get('kart_kodu') or '').strip()
        tip = kart.get('kart_tipi')
        if not kod or tip not in kart_tablolari:
            raise ValueError(f"Geçersiz kart kodu veya türü: {kod}")
        anahtar = (tip, kod.casefold())
        if anahtar in gorulen:
            raise ValueError(f"Seçimde yinelenen kart var: {kod}")
        gorulen.add(anahtar)
        try:
            miktar = Decimal(str(kart.get('miktar')))
        except Exception as exc:
            raise ValueError(f"Geçerli bir reçete miktarı girin: {kod}") from exc
        if not miktar.is_finite() or miktar <= 0:
            raise ValueError(f"Reçete miktarı sıfırdan büyük olmalı: {kod}")
        hazir.append((kod, tip, miktar))

    girdi_ids = []
    try:
        with cursor_ctx(conn) as cur:
            # Mevcut grubun seçili aktif reçeteye ait olduğunu doğrula ve aynı
            # reçeteye eşzamanlı toplu bağlamaları transaction boyunca sırala.
            cur.execute("""
                SELECT TOP 1 hp.DepoId
                FROM UretimRecete ur WITH (UPDLOCK, HOLDLOCK)
                JOIN UretimReceteHatPlani hp ON hp.UretimReceteId = ur.Id
                WHERE ur.Kodu = ?
                  AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
                  AND hp.Id = ?
            """, mamul_kodu, hat_plani_id)
            hat = cur.fetchone()
            if not hat:
                raise ValueError(f"Seçilen hat planı aktif mamüle ait değil: {mamul_kodu}")
            depo_id = hat[0]
            if depo_id is None:
                raise ValueError("Seçilen hat planında depo tanımlı değil.")

            for sira, (kart_kodu, kart_tipi, miktar_deger) in enumerate(hazir, 1):
                tablo, birim_alani, girdi_tipi = kart_tablolari[kart_tipi]
                cur.execute(
                    f"SELECT TOP 1 Id, {birim_alani} FROM {tablo} "
                    "WHERE Kodu = ? AND Aktif = 1 ORDER BY Id", kart_kodu
                )
                kart = cur.fetchone()
                if not kart:
                    raise ValueError(f"Aktif {kart_tipi} kartı bulunamadı: {kart_kodu}")
                kart_id, birim_id = kart
                if birim_id is None:
                    raise ValueError(f"Kartta birim tanımlı değil: {kart_kodu}")

                cur.execute("""
                    SELECT TOP 1 gi.Id
                    FROM UretimRecete ur
                    JOIN UretimReceteHatPlani hp ON hp.UretimReceteId = ur.Id
                    JOIN UretimReceteHatPlaniGirdi gi
                      ON gi.UretimReceteHatPlaniId = hp.Id
                    WHERE ur.Kodu = ?
                      AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
                      AND gi.Tipi = ? AND gi.KartId = ?
                """, mamul_kodu, girdi_tipi, kart_id)
                if cur.fetchone():
                    raise ValueError(f"Kart bu mamülün reçetesinde zaten var: {kart_kodu}")

                cur.execute("""
                    INSERT INTO UretimReceteHatPlaniGirdi
                        (UretimReceteHatPlaniId, Tipi, KartId, Miktar,
                         SabitMiktar, GarantiKapsaminda, BirimId, DepoId)
                    OUTPUT INSERTED.Id
                    VALUES (?, ?, ?, ?, 0, 0, ?, ?)
                """, hat_plani_id, girdi_tipi, kart_id, miktar_deger, birim_id, depo_id)
                girdi_ids.append(int(cur.fetchone()[0]))
                if ilerleme is not None:
                    ilerleme(sira, len(hazir))
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    logging.info(
        "%s kart mamül %s reçete grubu %s içine bağlandı.",
        len(girdi_ids), mamul_kodu, hat_plani_id,
    )
    return girdi_ids


# ── Araç 2: Maliyet Hesaplama ─────────────────────────────────────────────────

def bom_listesi(conn) -> dict:
    """dict döner: {mamul_kodu: {ad, birim, bilesenleri: [...]}}

    Gerçek bileşenler UretimReceteHatPlaniGirdi tablosunda saklanır.
    UretimReceteHatPlani üst satırdır; Girdi alt tablosu hammadde/parça girdilerini içerir.
    """
    birim_adlari = {
        str(guid).casefold().strip('{}'): adi
        for adi, guid in birimleri_getir(conn).items()
    }

    def _birim_adi(guid) -> str:
        temiz = str(guid or '').casefold().strip('{}')
        return birim_adlari.get(temiz, 'Bilinmiyor') if temiz else 'Bilinmiyor'

    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT DISTINCT
                ur.Kodu  AS MamulKodu,
                ur.Tanim AS MamulAdi,
                sk.Kodu  AS BilesenKodu,
                sk.Adi   AS BilesenAdi,
                urhpg.Miktar,
                ISNULL(urhpg.BirimId, sk.StokBirim) AS BilesenBirimId,
                mamul_sk.StokBirim AS MamulBirimId
            FROM UretimRecete ur
            INNER JOIN UretimReceteHatPlani urhp
                    ON urhp.UretimReceteId = ur.Id
            INNER JOIN UretimReceteHatPlaniGirdi urhpg
                    ON urhpg.UretimReceteHatPlaniId = urhp.Id
            INNER JOIN StokKarti sk
                    ON sk.Id = urhpg.KartId
            LEFT JOIN StokKarti mamul_sk
                    ON mamul_sk.Kodu = ur.Kodu
            WHERE urhpg.KartId IS NOT NULL
              AND sk.Aktif = 1
            ORDER BY ur.Kodu, sk.Kodu
        """)

        # Sonuçları organize et; gerçek reçetesi olan mamülleri işaretle
        bom = {}
        gercek_receteli = set()   # UretimReceteHatPlaniGirdi'den gelen mamüller
        for (mamul_kodu, mamul_adi, bilesen_kodu, bilesen_adi, miktar,
             bilesen_birim_guid, mamul_birim_guid) in cur.fetchall():
            if mamul_kodu not in bom:
                bom[mamul_kodu] = {
                    "ad": mamul_adi,
                    "birim": _birim_adi(mamul_birim_guid),
                    "bilesenleri": [],
                }
            if not any(b["kod"] == bilesen_kodu for b in bom[mamul_kodu]["bilesenleri"]):
                bom[mamul_kodu]["bilesenleri"].append({
                    "kod":    bilesen_kodu,
                    "ad":     bilesen_adi,
                    "miktar": float(miktar) if miktar is not None else 1.0,
                    "birim":  _birim_adi(bilesen_birim_guid),
                    "tip":    "stok",
                })
            gercek_receteli.add(mamul_kodu)

    # ── Masraf bileşenleri (Tipi=2 → StokMasrafKarti) ───────────────────────
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT DISTINCT
                ur.Kodu  AS MamulKodu,
                ur.Tanim AS MamulAdi,
                smk.Kodu AS BilesenKodu,
                smk.Adi  AS BilesenAdi,
                urhpg.Miktar,
                ISNULL(urhpg.BirimId, smk.StokBirimId) AS BilesenBirimId,
                mamul_sk.StokBirim AS MamulBirimId
            FROM UretimRecete ur
            INNER JOIN UretimReceteHatPlani urhp
                    ON urhp.UretimReceteId = ur.Id
            INNER JOIN UretimReceteHatPlaniGirdi urhpg
                    ON urhpg.UretimReceteHatPlaniId = urhp.Id
            INNER JOIN StokMasrafKarti smk
                    ON smk.Id = urhpg.KartId
            LEFT JOIN StokKarti mamul_sk
                    ON mamul_sk.Kodu = ur.Kodu
            WHERE urhpg.KartId IS NOT NULL
              AND urhpg.Tipi = 2
              AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
            ORDER BY ur.Kodu, smk.Kodu
        """)
        for (mamul_kodu, mamul_adi, bilesen_kodu, bilesen_adi, miktar,
             bilesen_birim_guid, mamul_birim_guid) in cur.fetchall():
            if mamul_kodu not in bom:
                bom[mamul_kodu] = {
                    "ad": mamul_adi,
                    "birim": _birim_adi(mamul_birim_guid),
                    "bilesenleri": [],
                }
            if not any(b["kod"] == bilesen_kodu for b in bom[mamul_kodu]["bilesenleri"]):
                bom[mamul_kodu]["bilesenleri"].append({
                    "kod":    bilesen_kodu,
                    "ad":     bilesen_adi,
                    "miktar": float(miktar) if miktar is not None else 1.0,
                    "birim":  _birim_adi(bilesen_birim_guid),
                    "tip":    "masraf",
                })

    # ── Operasyon alt kodları (KOD:XX) ──────────────────────────────────────
    # CEO ERP'de imalat operasyonları KOD:20 (FREZE), KOD:60 (KAPLAMA),
    # KOD:100 (LAZER) gibi ayrı StokKarti kayıtlarıyla tutulur.
    # Gerçek reçetesi olmayan her stok için KOD:XX alt operasyonlarını
    # sanal BOM girişi olarak ekle.
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT sk_parent.Kodu, sk_parent.Adi,
                   sk_child.Kodu,  sk_child.Adi
            FROM StokKarti sk_parent
            JOIN StokKarti sk_child
                ON sk_child.Kodu LIKE sk_parent.Kodu + ':%'
               AND sk_child.Kodu NOT LIKE sk_parent.Kodu + ':%:%'
            WHERE sk_parent.Aktif = 1
              AND sk_child.Aktif  = 1
              AND sk_parent.Kodu NOT LIKE '%:%'
            ORDER BY sk_parent.Kodu, sk_child.Kodu
        """)
        for p_kod, p_adi, c_kod, c_adi in cur.fetchall():
            # Gerçek reçetesi olan mamüllere dokunma
            if p_kod in gercek_receteli:
                continue
            if p_kod not in bom:
                bom[p_kod] = {"ad": p_adi, "birim": "Bilinmiyor", "bilesenleri": []}
            if not any(b["kod"] == c_kod for b in bom[p_kod]["bilesenleri"]):
                bom[p_kod]["bilesenleri"].append({
                    "kod":    c_kod,
                    "ad":     c_adi,
                    "miktar": 1.0,
                    "birim":  "Bilinmiyor",
                    "tip":    "stok",
                })

    return bom


def ihtiyac_bom_patlat(conn, ihtiyaclar: dict, bom: dict | None = None) -> list[dict]:
    """
    Verilen {stok_kodu: uretim_ihtiyaci} sözlüğünü (örn. satılıp üretilmemiş
    ürünlerin eksik miktarları) kaynak alarak, bom_listesi() reçetesini en alt
    kademeye kadar (max 8 seviye) recursive patlatır; her bileşen kod için
    toplam ihtiyaç, güncel bakiye ve eksik miktarı döner.

    `ihtiyaclar`'daki miktarlar zaten "net üretim ihtiyacı" (bakiye mahsup
    edilmiş) kabul edilir — seed seviyesinde tekrar bakiye düşülmez; yalnızca
    alt bileşenlere inerken (bir alt montajın kendi bakiyesi varsa) mahsup
    uygulanır. `uretim_emir_bom_patlat()`'taki `_patlat()` ile aynı net/mahsuplu
    mantık — bir alt montajın stoğu yetiyorsa onun kendi bileşenlerine inilmez.

    Masraf/operasyon bileşenleri (StokMasrafKarti, `:XX` kodlar dahil) de
    listeye dahil edilir; bunların stok bakiyesi kavramı olmadığından
    bakiye/eksik alanları None döner ve filtrelenmeden (miktarları > 0 olan
    tüm satırlar) gösterilir.

    `bom`: dışarıdan geçilirse DB'ye tekrar gidilmez (bom_listesi() pahalı —
    `logic/maliyet.py::mamul_maliyet_hesapla()` ile aynı performans deseni).
    None ise lazy-load yapılır.

    Döner: [{kodu, adi, tip ('stok'|'masraf'), toplam_ihtiyac, bakiye, eksik,
             kaynaklar (bu bileşene ihtiyaç duyan seed ürün kodları)}, ...]
    — stok tipinde yalnızca eksik > 0 olanlar, masraf tipinde tüm satırlar;
    stok satırları eksik miktara göre azalan sıralı, masraf satırları sonda.
    """
    from collections import defaultdict

    if bom is None:
        bom = bom_listesi(conn)

    # ── 1. BFS: recursive taranacak tüm stok bileşenlerini bul (bakiye için) ──
    stok_kodlari: set[str] = set()
    kuyruk = [k for k in ihtiyaclar if k in bom]
    gorulen: set[str] = set(kuyruk)
    while kuyruk:
        kod = kuyruk.pop()
        for bil in bom.get(kod, {}).get('bilesenleri', []):
            if bil['tip'] != 'stok' or bil['kod'] in gorulen:
                continue
            gorulen.add(bil['kod'])
            stok_kodlari.add(bil['kod'])
            if bil['kod'] in bom:
                kuyruk.append(bil['kod'])

    # ── 2. Bakiyeler (toplu) ────────────────────────────────────────────────
    bakiyeler = stok_guncel_bakiyeleri(conn, list(stok_kodlari)) if stok_kodlari else {}

    # ── 3. Recursive patlatma ───────────────────────────────────────────────
    toplam_talep: dict[str, float] = defaultdict(float)
    kaynaklar: dict[str, set] = defaultdict(set)
    ad_map: dict[str, str] = {}
    tip_map: dict[str, str] = {}

    def _explode(kod: str, uretim_gerekli: float, seed: str, depth: int) -> None:
        if depth > 8:
            return
        for bil in bom.get(kod, {}).get('bilesenleri', []):
            bkod = bil['kod']
            bil_ihtiyac = bil['miktar'] * uretim_gerekli
            toplam_talep[bkod] += bil_ihtiyac
            kaynaklar[bkod].add(seed)
            ad_map[bkod] = bil['ad']
            tip_map[bkod] = bil['tip']
            if bil['tip'] != 'stok' or bkod not in bom:
                continue
            bakiye = bakiyeler.get(bkod, 0.0)
            alt_uretim_gerekli = max(0.0, bil_ihtiyac - bakiye)
            if alt_uretim_gerekli > 0:
                _explode(bkod, alt_uretim_gerekli, seed, depth + 1)

    for seed_kod, eksik in ihtiyaclar.items():
        if eksik and eksik > 0:
            _explode(seed_kod, eksik, seed_kod, 0)

    # ── 4. Sonuç listesi ─────────────────────────────────────────────────────
    # NOT: Operasyon kodları (`:XX` sonekli) çoğunlukla StokMasrafKarti'de
    # tutulur (Tipi=2 → tip_map='masraf'), ama bazı reçetelerde aynı operasyon
    # StokKarti tarafına da girilmiş olabilir (Tipi=1 → tip_map='stok') —
    # bkz. "Masraf / Operasyon Kartları" bölümü, ERP-OKUMA.md. Böyle bir kod
    # gerçek fiziksel stok değildir; bakiye/eksik hesabı anlamsız olur ve
    # eksik-filtresine tabi tutulmamalı — `:` sonekine göre yakalanır.
    sonuc: list[dict] = []
    for kod, ihtiyac in toplam_talep.items():
        tip = tip_map.get(kod, 'stok')
        if tip == 'masraf' or kod.count(':') == 1:
            sonuc.append({
                'kodu': kod, 'adi': ad_map.get(kod, ''), 'tip': 'masraf',
                'toplam_ihtiyac': round(ihtiyac, 2),
                'bakiye': None, 'eksik': None,
                'kaynaklar': sorted(kaynaklar[kod]),
            })
        else:
            bakiye  = bakiyeler.get(kod, 0.0)
            eksik_m = bakiye - ihtiyac
            if eksik_m >= 0:
                continue
            sonuc.append({
                'kodu': kod, 'adi': ad_map.get(kod, ''), 'tip': 'stok',
                'toplam_ihtiyac': round(ihtiyac, 2),
                'bakiye': round(bakiye, 2), 'eksik': round(-eksik_m, 2),
                'kaynaklar': sorted(kaynaklar[kod]),
            })

    sonuc.sort(key=lambda r: (r['tip'] == 'masraf', -(r['eksik'] or 0)))
    return sonuc


def acik_uretim_emri_ihtiyaclari(conn, stok_kodlari: list) -> dict:
    """
    Açık üretim emirlerindeki malzeme taleplerini stok kodu bazında toplar.

    CEO ERP'de DurumId=3, "Devam Ediyor" durumudur. TalepMiktar, üretim
    emrinin ilgili malzemeden fiilen talep ettiği miktardır; reçetedeki
    birimlik Miktar alanından farklıdır. HatTipi=1 ve 2, Üretim Eksik Stok
    raporundaki ana hat ve aksesuar grubu kapsamıyla aynıdır.

    Döner: {stok_kodu: açık_üretim_emri_talep_toplamı}. Masraf/operasyon
    kartları StokKarti üzerinden takip edilmediği için bu sorguya alınmaz.
    """
    if not stok_kodlari:
        return {}

    sonuc = {k: 0.0 for k in stok_kodlari}
    _YIGIN = 500
    for i in range(0, len(stok_kodlari), _YIGIN):
        parca = stok_kodlari[i: i + _YIGIN]
        yer = ",".join("?" * len(parca))
        with cursor_ctx(conn) as cur:
            cur.execute(f"""
                SELECT sk.Kodu, SUM(ISNULL(uehpg.TalepMiktar, 0))
                FROM UretimEmri ue
                JOIN UretimEmriHatPlani uehp
                    ON uehp.UretimEmriId = ue.Id
                JOIN UretimEmriHatPlaniGirdi uehpg
                    ON uehpg.UretimEmriHatPlaniId = uehp.Id
                JOIN StokKarti sk ON sk.Id = uehpg.KartId
                WHERE ue.DurumId = 3
                  AND uehp.HatTipi IN (1, 2)
                  AND uehpg.KartId IS NOT NULL
                  AND uehpg.TalepMiktar > 0
                  AND sk.Kodu IN ({yer})
                GROUP BY sk.Kodu
            """, *parca)
            for kod, toplam in cur.fetchall():
                if kod in sonuc:
                    sonuc[kod] = float(toplam or 0.0)
    return sonuc


def son_alis_fiyati_toplu(conn, stok_kodlari: list, masraf_kodlari: list) -> dict:
    """
    Verilen stok VE masraf kodları için, TARİH SINIRI OLMADAN geriye giderek
    en son (en güncel tarihli) alım fiyatını bulur — `stok_fiyat_gecmisi()` /
    `masraf_fiyat_gecmisi()`'nin aksine bir başlangıç tarihi almaz, kaydın
    bulunduğu en eski tarihe kadar arar.

    Faturalaşan irsaliye mükerrer sayım düzeltmesiyle aynı desen: yalnızca
    IslemKodu=1 (Alış Faturası) VE FaturaId'si BOŞ olan IslemKodu=5 (henüz
    faturalaşmamış irsaliye) satırları dikkate alınır (bkz. satis_faturalari()
    docstring'i). Masraf tarafında `Turu` filtrelenmez (masraf faturaları
    çoğunlukla Turu=3 kullanır — bkz. masraf_fiyat_gecmisi()).

    Döner: {kod: {'fiyat': float, 'tarih': 'DD.MM.YYYY'}} — hiç alım
    bulunamayan kodlar sözlükte YER ALMAZ (çağıran taraf `.get(kod)` ile
    None kontrolü yapıp hücreyi boş bırakmalı; "hiç alım yok" iddiası
    yalnızca bu sorgunun gerçekten sıfır satır döndürdüğü kodlar içindir).
    """
    sonuc: dict[str, dict] = {}
    _YIGIN = 500

    if stok_kodlari:
        for i in range(0, len(stok_kodlari), _YIGIN):
            parca = stok_kodlari[i: i + _YIGIN]
            yer = ",".join("?" * len(parca))
            with cursor_ctx(conn) as cur:
                cur.execute(f"""
                    ;WITH Siralama AS (
                        SELECT
                            sk.Kodu,
                            shd.BirimFiyat,
                            sh.BelgeTarihi,
                            ROW_NUMBER() OVER (
                                PARTITION BY sk.Kodu
                                ORDER BY sh.BelgeTarihi DESC, sh.Id DESC
                            ) AS rn
                        FROM StokHareketDetay shd
                        JOIN StokHareket sh ON sh.Id = shd.HareketId
                        JOIN StokKarti sk   ON sk.Id = shd.IslemKartId
                        WHERE sk.Kodu IN ({yer})
                          AND (sh.IslemKodu = 1 OR (sh.IslemKodu = 5 AND sh.FaturaId IS NULL))
                          AND shd.Turu = 1
                          AND shd.BirimFiyat > 0
                          AND shd.Miktar > 0
                    )
                    SELECT Kodu, BirimFiyat, CONVERT(VARCHAR(10), BelgeTarihi, 104)
                    FROM Siralama WHERE rn = 1
                """, *parca)
                for kod, fiyat, tarih in cur.fetchall():
                    sonuc[kod] = {'fiyat': float(fiyat), 'tarih': tarih}

    if masraf_kodlari:
        for i in range(0, len(masraf_kodlari), _YIGIN):
            parca = masraf_kodlari[i: i + _YIGIN]
            yer = ",".join("?" * len(parca))
            with cursor_ctx(conn) as cur:
                cur.execute(f"""
                    ;WITH Siralama AS (
                        SELECT
                            smk.Kodu,
                            shd.BirimFiyat,
                            sh.BelgeTarihi,
                            ROW_NUMBER() OVER (
                                PARTITION BY smk.Kodu
                                ORDER BY sh.BelgeTarihi DESC, sh.Id DESC
                            ) AS rn
                        FROM StokHareketDetay shd
                        JOIN StokHareket sh      ON sh.Id = shd.HareketId
                        JOIN StokMasrafKarti smk ON smk.Id = shd.IslemKartId
                        WHERE smk.Kodu IN ({yer})
                          AND (sh.IslemKodu = 1 OR (sh.IslemKodu = 5 AND sh.FaturaId IS NULL))
                          AND shd.BirimFiyat > 0
                          AND shd.Miktar > 0
                    )
                    SELECT Kodu, BirimFiyat, CONVERT(VARCHAR(10), BelgeTarihi, 104)
                    FROM Siralama WHERE rn = 1
                """, *parca)
                for kod, fiyat, tarih in cur.fetchall():
                    sonuc[kod] = {'fiyat': float(fiyat), 'tarih': tarih}

    return sonuc


def bom_operasyon_kodlarini_tamamla(conn, bom: dict) -> list[str]:
    """
    Excel'den okunan taslak BOM'daki bileşenler için, CEO ERP'de aynı kodun
    StokKarti veya StokMasrafKarti tarafında ':XX' soneki ile kayıtlı bir
    operasyon/masraf kodu varsa (ör. GMP-200-240822 için dışarıda yaptırılan
    GMP-200-240822:30 FREZE/TORNA/KAPLAMA gibi), Excel'de açıkça yazılmamış
    olsa bile otomatik bulunup masraf bileşeni olarak eklenir. Miktar olarak
    ana parçanın miktarı kullanılır.

    bom sözlüğü yerinde (in place) güncellenir. Döner: eklenen kodlar için
    bilgi mesajları listesi.
    """
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT Kodu, Adi, 'stok' FROM StokKarti
            WHERE Kodu LIKE '%:%' AND Kodu NOT LIKE '%:%:%' AND Aktif = 1
            UNION ALL
            SELECT Kodu, Adi, 'masraf' FROM StokMasrafKarti
            WHERE Kodu LIKE '%:%' AND Kodu NOT LIKE '%:%:%' AND Aktif = 1
        """)
        cocuklar: dict[str, list[tuple[str, str, str]]] = {}
        for kodu, adi, kaynak in cur.fetchall():
            taban = kodu.rsplit(":", 1)[0]
            cocuklar.setdefault(taban, []).append((kodu, adi, kaynak))

    mesajlar: list[str] = []
    for veri in bom.values():
        orijinal = veri["bilesenleri"]
        mevcut_kodlar = {x["kod"] for x in orijinal}
        yeni_liste: list[dict] = []
        for b in orijinal:
            yeni_liste.append(b)
            taban_kod = b["kod"]
            if ":" in taban_kod or b.get("tip") == "masraf":
                continue   # zaten bir operasyon kodu ya da masraf olarak işaretli
            for child_kod, child_adi, _kaynak in cocuklar.get(taban_kod, []):
                if child_kod in mevcut_kodlar:
                    continue   # zaten Excel'de açıkça yazılmış
                # Ana parçanın hemen altına eklenir — rapor sırasında yan yana görünsün
                yeni_liste.append({
                    "kod": child_kod, "ad": child_adi, "miktar": b["miktar"],
                    "birim": b["birim"], "tip": "masraf", "oto": True,
                })
                mevcut_kodlar.add(child_kod)
                mesajlar.append(
                    f"{child_kod} ({child_adi}) — {taban_kod} için otomatik "
                    f"bulunan operasyon kodu eklendi (miktar: {b['miktar']})"
                )
        veri["bilesenleri"] = yeni_liste
    return mesajlar


def stok_fiyat_gecmisi(conn, stok_kodu: str, bas: str, bit: str) -> list[dict]:
    """
    Verilen tarih aralığında stok için fatura fiyat geçmişi.
    Her eleman: tarih (YYYY-MM-DD), birim_fiyat, miktar, birim

    Faturalaşan irsaliye — mükerrer sayım düzeltmesi: bkz. satis_faturalari()
    ve proje_satinalma_hareketleri() docstring'leri. Sadece IslemKodu=1
    (Alış Faturası) VE FaturaId'si BOŞ olan IslemKodu=5 (henüz faturalaşmamış
    irsaliye) satırları toplanır — aksi hâlde aynı alım iki kez sayılır ve
    FIFO/LIFO/WA fiyat hesabına mükerrer satır girer.
    """
    with cursor_ctx(conn) as cur:
        cur.execute(f"""
            SELECT
                CONVERT(VARCHAR(10), sh.BelgeTarihi, 120) as Tarih,
                shd.BirimFiyat as BirimFiyat,
                shd.Miktar as Miktar
            FROM StokHareketDetay shd
            JOIN StokHareket sh ON sh.Id = shd.HareketId
            JOIN StokKarti sk ON sk.Id = shd.IslemKartId
            WHERE sk.Kodu = ?
              AND (sh.IslemKodu = 1 OR (sh.IslemKodu = 5 AND sh.FaturaId IS NULL))
              AND shd.Turu = 1
              AND CAST(sh.BelgeTarihi AS DATE) >= CAST('{bas}' AS DATE)
              AND CAST(sh.BelgeTarihi AS DATE) <= CAST('{bit}' AS DATE)
              AND shd.BirimFiyat > 0
              AND shd.Miktar > 0
            ORDER BY sh.BelgeTarihi ASC
        """, stok_kodu)

        return [
            {
                "tarih": tarih,
                "birim_fiyat": float(birim_fiyat) if birim_fiyat else 0.0,
                "miktar": float(miktar) if miktar else 0.0,
                "birim": "ADET",
            }
            for tarih, birim_fiyat, miktar in cur.fetchall()
        ]


def masraf_fiyat_gecmisi(conn, masraf_kodu: str, bas: str, bit: str) -> list[dict]:
    """
    Verilen tarih aralığında masraf kartı için fatura fiyat geçmişi.
    StokHareketDetay.IslemKartId → StokMasrafKarti.Id üzerinden çekilir.
    Her eleman: tarih (YYYY-MM-DD), birim_fiyat, miktar, birim

    NOT: Masraf hareketleri stok hareketlerinden farklı `Turu` değeri
    kullanır (çoğunlukla Turu=3). Bu yüzden stok sorgusundaki `Turu=1`
    filtresi burada UYGULANMAZ — aksi halde tüm masraf faturaları elenir.

    Faturalaşan irsaliye — mükerrer sayım düzeltmesi: bkz. satis_faturalari()
    ve proje_satinalma_hareketleri() docstring'leri. Sadece IslemKodu=1
    (Alış Faturası) VE FaturaId'si BOŞ olan IslemKodu=5 (henüz faturalaşmamış
    irsaliye) satırları toplanır.
    """
    with cursor_ctx(conn) as cur:
        cur.execute(f"""
            SELECT
                CONVERT(VARCHAR(10), sh.BelgeTarihi, 120) AS Tarih,
                shd.BirimFiyat AS BirimFiyat,
                shd.Miktar AS Miktar
            FROM StokHareketDetay shd
            JOIN StokHareket sh ON sh.Id = shd.HareketId
            JOIN StokMasrafKarti smk ON smk.Id = shd.IslemKartId
            WHERE smk.Kodu = ?
              AND (sh.IslemKodu = 1 OR (sh.IslemKodu = 5 AND sh.FaturaId IS NULL))
              AND CAST(sh.BelgeTarihi AS DATE) >= CAST('{bas}' AS DATE)
              AND CAST(sh.BelgeTarihi AS DATE) <= CAST('{bit}' AS DATE)
              AND shd.BirimFiyat > 0
              AND shd.Miktar > 0
            ORDER BY sh.BelgeTarihi ASC
        """, masraf_kodu)

        return [
            {
                "tarih":      tarih,
                "birim_fiyat": float(birim_fiyat) if birim_fiyat else 0.0,
                "miktar":     float(miktar) if miktar else 0.0,
                "birim":      "ADET",
            }
            for tarih, birim_fiyat, miktar in cur.fetchall()
        ]


def uretim_emri_masraf_maliyet_onizle(conn, emir_kodu: str) -> dict:
    """Üretim emrindeki masraf satırları için maliyet ön izlemesi döndürür.

    CEO ERP, ``Tipi=2`` masraf satırlarının maliyetinde üretim emri satırındaki
    ``Tutar`` alanını kullanır; masraf kartı alış fiyatını bu alana otomatik
    taşımaz. Bu yardımcı üretim emri tarihine kadar olan son geçerli alış
    fiyatını bulur ve yalnızca mevcut tutarı sıfır olan satırlar için öneri
    hesaplar.
    """
    emir_kodu = (emir_kodu or "").strip()
    if not emir_kodu:
        raise ValueError("Üretim emri kodu boş olamaz.")

    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT Id, Kodu, Aciklama, UretimEmriTarihi, DurumId
            FROM UretimEmri
            WHERE Kodu = ?
        """, emir_kodu)
        emir = cur.fetchone()
        if not emir:
            raise ValueError(f"Üretim emri bulunamadı: {emir_kodu}")

        emir_id, kodu, aciklama, emir_tarihi, durum_id = emir
        cur.execute("""
            SELECT
                ueg.Id,
                ueg.KartId,
                smk.Kodu,
                smk.Adi,
                ueg.Miktar,
                ueg.TalepMiktar,
                ISNULL(ueg.Tutar, 0),
                kaynak.HareketId,
                kaynak.DetayId,
                kaynak.BelgeTarihi,
                kaynak.BirimFiyat
            FROM UretimEmriHatPlaniGirdi ueg
            INNER JOIN UretimEmriHatPlani uep
                ON uep.Id = ueg.UretimEmriHatPlaniId
            INNER JOIN UretimEmri ue
                ON ue.Id = uep.UretimEmriId
            INNER JOIN StokMasrafKarti smk
                ON smk.Id = ueg.KartId
            OUTER APPLY (
                SELECT TOP 1
                    sh.Id AS HareketId,
                    shd.Id AS DetayId,
                    sh.BelgeTarihi,
                    shd.BirimFiyat
                FROM StokHareket sh
                INNER JOIN StokHareketDetay shd
                    ON shd.HareketId = sh.Id
                WHERE shd.Turu = 3
                  AND (shd.IslemKartId = ueg.KartId
                       OR shd.StokMasrafKartId = ueg.KartId)
                  AND sh.Aktif = 1
                  AND shd.Aktif = 1
                  AND (sh.IslemKodu = 1
                       OR (sh.IslemKodu = 5 AND sh.FaturaId IS NULL))
                  AND shd.BirimFiyat > 0
                  AND shd.Miktar > 0
                  AND CAST(sh.BelgeTarihi AS DATE)
                      <= CAST(ue.UretimEmriTarihi AS DATE)
                ORDER BY sh.BelgeTarihi DESC, sh.Id DESC, shd.Id DESC
            ) kaynak
            WHERE ue.Id = ?
              AND ueg.Tipi = 2
            ORDER BY ueg.Id
        """, emir_id)

        satirlar = []
        for row in cur.fetchall():
            (girdi_id, kart_id, masraf_kodu, masraf_adi, miktar,
             talep_miktari, eski_tutar, hareket_id, detay_id,
             belge_tarihi, birim_fiyat) = row
            eski = Decimal(str(eski_tutar or 0))
            yeni = None
            if birim_fiyat is not None and talep_miktari is not None:
                yeni = (
                    Decimal(str(talep_miktari)) * Decimal(str(birim_fiyat))
                ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

            if eski != 0:
                durum = "zaten_dolu"
            elif yeni is None:
                durum = "fiyat_yok"
            else:
                durum = "uygulanabilir"

            satirlar.append({
                "girdi_id": int(girdi_id),
                "masraf_kart_id": int(kart_id),
                "kod": str(masraf_kodu),
                "ad": str(masraf_adi or "").strip(),
                "miktar": float(miktar or 0),
                "talep_miktari": float(talep_miktari or 0),
                "eski_tutar": float(eski),
                "kaynak_hareket_id": int(hareket_id) if hareket_id is not None else None,
                "kaynak_detay_id": int(detay_id) if detay_id is not None else None,
                "kaynak_tarihi": (
                    belge_tarihi.strftime("%d.%m.%Y")
                    if belge_tarihi is not None else None
                ),
                "birim_fiyat": float(birim_fiyat) if birim_fiyat is not None else None,
                "yeni_tutar": float(yeni) if yeni is not None else None,
                "durum": durum,
            })

    return {
        "emir": {
            "id": int(emir_id),
            "kodu": str(kodu),
            "aciklama": str(aciklama or "").strip(),
            "tarih": emir_tarihi.strftime("%d.%m.%Y") if emir_tarihi else "",
            "durum_id": int(durum_id) if durum_id is not None else None,
        },
        "satirlar": satirlar,
    }


def uretim_emri_masraf_maliyet_uygula(conn, emir_kodu: str) -> dict:
    """Uygun masraf tutarlarını üretim emrine transaction ile yazar.

    Yalnızca ``Tutar=0`` olan ve üretim emri tarihinden önce alış fiyatı
    bulunan ``Tipi=2`` satırlar güncellenir. Fatura, irsaliye ve stok
    hareketleri değiştirilmez.
    """
    onizleme = uretim_emri_masraf_maliyet_onizle(conn, emir_kodu)
    adaylar = [
        satir for satir in onizleme["satirlar"]
        if satir["durum"] == "uygulanabilir"
    ]
    guncellenen = []
    if not adaylar:
        return {"onizleme": onizleme, "guncellenen": [], "atlanan": []}

    try:
        with cursor_ctx(conn) as cur:
            for satir in adaylar:
                cur.execute("""
                    UPDATE UretimEmriHatPlaniGirdi
                    SET Tutar = ?
                    WHERE Id = ?
                      AND Tipi = 2
                      AND ISNULL(Tutar, 0) = 0
                """, satir["yeni_tutar"], satir["girdi_id"])
                if cur.rowcount == 1:
                    guncellenen.append(satir)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    atlanan = [satir for satir in adaylar if satir not in guncellenen]
    return {
        "onizleme": onizleme,
        "guncellenen": guncellenen,
        "atlanan": atlanan,
    }


def proje_kodlari_listele(conn) -> list[str]:
    """
    CEO ERP'deki Proje.ProjeKodu değerlerini (trimlenmiş, tekil, sıralı) döner.

    Kullanım amacı: proje kodu serbest metin olarak elle girildiğinde ufak bir
    yazım farkı (ör. "ADLAS MKE" yerine gerçek kod "ADLAS-MKE") satır bazlı
    ProjeId eşleşmesini sessizce sıfır satırla sonuçlandırır — kullanıcı hiç
    fark etmeden "%100 fark" gibi yanıltıcı bir sonuç görebilir. Bu liste
    UI'da otomatik tamamlama için kullanılır.
    """
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT DISTINCT LTRIM(RTRIM(ProjeKodu))
            FROM Proje
            WHERE ProjeKodu IS NOT NULL AND LTRIM(RTRIM(ProjeKodu)) <> ''
            ORDER BY LTRIM(RTRIM(ProjeKodu))
        """)
        return [row[0] for row in cur.fetchall()]


def proje_satinalma_hareketleri(conn, proje_kodu: str, bas: str, bit: str) -> list[dict]:
    """
    Bir projeye (CEO ERP'deki Proje.ProjeKodu) fiilen kesilmiş alış
    faturası/irsaliyesi satırlarını ve alış iadelerini döner — hem stok hem
    masraf/operasyon kartı tarafı.

    Proje kodu StokHareketDetay.ProjeId üzerinden SATIR bazında tutulur
    (belge/fatura başlığında değil) — bu yüzden aynı faturanın bazı satırları
    bu projeye ait, bazıları başka bir projeye ait olabilir; her satır kendi
    ProjeId'siyle filtrelenir.

    Faturalaşan irsaliye tekrarına karşı koruma
    --------------------------------------------
    Bir irsaliye (IslemKodu=5) sonradan faturalandırıldığında CEO ERP
    StokHareket.FaturaId alanını doldurur; hem irsaliye hem onun faturası
    ayrı satır olarak durur ve tutarı iki kez saymamak için sadece
    IslemKodu=1 (Alış Faturası) VE FaturaId'si BOŞ olan IslemKodu=5
    (henüz faturalaşmamış irsaliye) satırları toplanır. Bu davranış CEO
    ERP'nin kendi "Stok Hareketleri Raporu"ndaki (Detay İşlem Türü filtresi)
    Stok/Masraf toplamlarıyla ADLAS-MKE projesi üzerinde satır satır
    doğrulanmıştır (bkz. ERP-OKUMA.md).

    Alış iadesi (IslemKodu=3)
    -------------------------
    CEO ERP'de alış iadesi miktar ve tutarı pozitif saklar. Bu fonksiyon bu
    hareketleri de alır, ancak sonuçta miktar ve tutarı ``-ABS(...)`` olarak
    döndürür. Böylece proje fiili maliyeti ve satınalma toplamı iadeleri
    otomatik olarak düşer. İade satırları rapor detayında "Alış İadesi" olarak
    görünür.

    NOT: Aynı düzeltme artık satis_faturalari() (satış aynası), stok_fiyat_gecmisi(),
    masraf_fiyat_gecmisi(), recetesiz_stok_hareketleri() ve stok_fiyatlari_toplu()
    fonksiyonlarına da uygulanmıştır (2026-09-14) — hepsi eski `IslemKodu IN (1, 5)`
    / `IN (2, 6)` deseninden `FaturaId IS NULL` kontrollü hâle geçirildi.

    Sabit Kıymet alımları (StokHareketDetay.SabitKiymetId) bu fonksiyona
    DAHİL DEĞİLDİR — BOM'a girmeyen demirbaş/ekipman alımları olduğundan
    kasıtlı olarak dışarıda bırakıldı.

    Her eleman: bil_kod, bil_ad, tip ('stok'|'masraf'), hareket_id,
                islem_turu, belge_no, tarih (DD.MM.YYYY), tarih_iso,
                miktar, birim_fiyat, tutar, tedarikci
    """
    with cursor_ctx(conn) as cur:
        cur.execute(f"""
            SELECT
                sk.Kodu, sk.Adi, 'stok',
                sh.Id,
                CASE sh.IslemKodu
                    WHEN 1 THEN 'Alış Faturası'
                    WHEN 3 THEN 'Alış İadesi'
                    ELSE 'Alış İrsaliyesi'
                END,
                ISNULL(sh.BelgeSeriNo, '') + ISNULL(CAST(sh.BelgeSiraNo AS VARCHAR(20)), ''),
                CONVERT(VARCHAR(10), sh.BelgeTarihi, 104),
                CONVERT(VARCHAR(10), sh.BelgeTarihi, 120),
                CASE WHEN sh.IslemKodu = 3
                     THEN -ABS(ISNULL(shd.Miktar, 0))
                     ELSE ISNULL(shd.Miktar, 0) END,
                ISNULL(shd.BirimFiyat, 0),
                CASE WHEN sh.IslemKodu = 3
                     THEN -ABS(ISNULL(shd.Tutar, 0))
                     ELSE ISNULL(shd.Tutar, 0) END,
                ISNULL(cmk.Unvani, '')
            FROM StokHareketDetay shd
            JOIN StokHareket sh ON sh.Id = shd.HareketId
            JOIN StokKarti sk   ON sk.Id = shd.IslemKartId
            JOIN Proje p        ON p.Id = shd.ProjeId
            LEFT JOIN CariMusteriKarti cmk ON sh.MusteriKartId = cmk.Id
            WHERE p.ProjeKodu = ?
              AND (sh.IslemKodu = 1
                   OR sh.IslemKodu = 3
                   OR (sh.IslemKodu = 5 AND sh.FaturaId IS NULL))
              AND shd.Turu = 1
              AND CAST(sh.BelgeTarihi AS DATE) >= CAST('{bas}' AS DATE)
              AND CAST(sh.BelgeTarihi AS DATE) <= CAST('{bit}' AS DATE)

            UNION ALL

            SELECT
                smk.Kodu, smk.Adi, 'masraf',
                sh.Id,
                CASE sh.IslemKodu
                    WHEN 1 THEN 'Alış Faturası'
                    WHEN 3 THEN 'Alış İadesi'
                    ELSE 'Alış İrsaliyesi'
                END,
                ISNULL(sh.BelgeSeriNo, '') + ISNULL(CAST(sh.BelgeSiraNo AS VARCHAR(20)), ''),
                CONVERT(VARCHAR(10), sh.BelgeTarihi, 104),
                CONVERT(VARCHAR(10), sh.BelgeTarihi, 120),
                CASE WHEN sh.IslemKodu = 3
                     THEN -ABS(ISNULL(shd.Miktar, 0))
                     ELSE ISNULL(shd.Miktar, 0) END,
                ISNULL(shd.BirimFiyat, 0),
                CASE WHEN sh.IslemKodu = 3
                     THEN -ABS(ISNULL(shd.Tutar, 0))
                     ELSE ISNULL(shd.Tutar, 0) END,
                ISNULL(cmk.Unvani, '')
            FROM StokHareketDetay shd
            JOIN StokHareket sh      ON sh.Id = shd.HareketId
            JOIN StokMasrafKarti smk ON smk.Id = shd.IslemKartId
            JOIN Proje p             ON p.Id = shd.ProjeId
            LEFT JOIN CariMusteriKarti cmk ON sh.MusteriKartId = cmk.Id
            WHERE p.ProjeKodu = ?
              AND (sh.IslemKodu = 1
                   OR sh.IslemKodu = 3
                   OR (sh.IslemKodu = 5 AND sh.FaturaId IS NULL))
              AND CAST(sh.BelgeTarihi AS DATE) >= CAST('{bas}' AS DATE)
              AND CAST(sh.BelgeTarihi AS DATE) <= CAST('{bit}' AS DATE)

            ORDER BY 7 ASC
        """, proje_kodu, proje_kodu)

        return [
            {
                "bil_kod":     row[0],
                "bil_ad":      row[1],
                "tip":         row[2],
                "hareket_id":  int(row[3]),
                "islem_turu":  row[4],
                "belge_no":    row[5],
                "tarih":       row[6],
                "tarih_iso":   row[7],
                "miktar":      float(row[8]),
                "birim_fiyat": float(row[9]),
                "tutar":       float(row[10]),
                "tedarikci":   row[11],
            }
            for row in cur.fetchall()
        ]


def stok_fiyatlari_toplu(
    conn, stok_kodlari: list, bas: str, bit: str
) -> dict:
    """
    Birden fazla stok kodu için fiyat geçmişini TEK sorguda çeker.
    Döner: {stok_kodu: [{"tarih", "birim_fiyat", "miktar", "birim"}, ...]}
    IslemKodu 1=Alış Faturası, 5=Alış İrsaliyesi.

    Faturalaşan irsaliye — mükerrer sayım düzeltmesi: bkz. satis_faturalari()
    ve proje_satinalma_hareketleri() docstring'leri. Sadece IslemKodu=1
    (Alış Faturası) VE FaturaId'si BOŞ olan IslemKodu=5 (henüz faturalaşmamış
    irsaliye) satırları toplanır — Maliyet sekmesinin asıl FIFO/LIFO/WA fiyat
    kaynağı olduğundan bu düzeltme burada özellikle önemli.
    """
    if not stok_kodlari:
        return {}

    sonuc = {k: [] for k in stok_kodlari}
    # SQL Server IN() parametresi için 2000'lik parçalara böl
    _YIGIN = 2000
    for i in range(0, len(stok_kodlari), _YIGIN):
        parcalar = stok_kodlari[i: i + _YIGIN]
        yer = ",".join("?" * len(parcalar))
        with cursor_ctx(conn) as cur:
            cur.execute(f"""
                SELECT
                    sk.Kodu,
                    CONVERT(VARCHAR(10), sh.BelgeTarihi, 120),
                    shd.BirimFiyat,
                    shd.Miktar
                FROM StokHareketDetay shd
                JOIN StokHareket sh ON sh.Id = shd.HareketId
                JOIN StokKarti sk   ON sk.Id = shd.IslemKartId
                WHERE sk.Kodu IN ({yer})
                  AND (sh.IslemKodu = 1 OR (sh.IslemKodu = 5 AND sh.FaturaId IS NULL))
                  AND shd.Turu = 1
                  AND CAST(sh.BelgeTarihi AS DATE) >= CAST('{bas}' AS DATE)
                  AND CAST(sh.BelgeTarihi AS DATE) <= CAST('{bit}' AS DATE)
                  AND shd.BirimFiyat > 0
                  AND shd.Miktar > 0
                ORDER BY sk.Kodu, sh.BelgeTarihi ASC
            """, *parcalar)
            for kod, tarih, birim_fiyat, miktar in cur.fetchall():
                if kod in sonuc:
                    sonuc[kod].append({
                        "tarih": tarih,
                        "birim_fiyat": float(birim_fiyat) if birim_fiyat else 0.0,
                        "miktar": float(miktar) if miktar else 0.0,
                        "birim": "ADET",
                    })
    return sonuc


# ── Araç 6: Üretim Eksik Stok Raporu ─────────────────────────────────────────

def uretim_emirleri_listesi(conn) -> list[dict]:
    """'Devam Ediyor' tüm üretim emirlerini en yeni tarih önce döner."""
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT
                ue.Id,
                ue.Kodu,
                ISNULL(ue.Aciklama, '')                         AS Aciklama,
                CONVERT(VARCHAR(10), ue.UretimEmriTarihi, 104)  AS EmirTarihi
            FROM UretimEmri ue
            WHERE ue.DurumId = 3
            ORDER BY ue.UretimEmriTarihi DESC, ue.Kodu
        """)
        return [
            {
                'id':       int(row[0]),
                'kodu':     row[1],
                'aciklama': row[2],
                'tarih':    row[3],
            }
            for row in cur.fetchall()
        ]


def uretim_emir_eksik_stok(conn, emir_id: int) -> list[dict]:
    """
    Belirli bir üretim emrinin HatTipi=1 hat planındaki malzemeleri için
    ÜRETİM EMRİ TARİHİNDEKİ bakiyeyi hesaplayıp yetersiz olanları döner.

    Bakiye formülü (CEO ERP StokHareketIsGiris + FaturaDetayId çift-sayım önleme):
      GirenMiktar : IslemKodu IN (1,4,5,8,15,16,20,22,26,29)
        1=Alış Faturası, 4=Satış İade, 5=Alış İrsaliyesi (FaturaDetayId ile net=0 faturalıysa)
        16=Üretimden Giriş, 20=Sayım Fazlası, 22=Devir Girişi
      CikanMiktar : IslemKodu IN (2,3,6,7,17,18,19,21,23,24,28)
        2=Satış Faturası, 6=Satış İrsaliyesi (FaturaDetayId ile net=0 faturalıysa)
        17=Üretime Çıkış, 18=Depolar Arası Çıkış, 19=Sayım Eksiği, 21=Fire
        23=Depolar Arası Giriş (CEO'da çıkış sayılır — toplam bakiyede düşer)
      Tarih filtresi: BelgeTarihi <= UretimEmriTarihi
      Hat filtresi  : HatTipi IN (1, 2) (ana hat + aksesuar grubu)

    Her eleman: malzeme_kodu, malzeme_adi, ihtiyac, bakiye_emir_tarihi, eksik
    """
    with cursor_ctx(conn) as cur:
        cur.execute(f"""
            WITH EmirBilgi AS (
                SELECT CAST(UretimEmriTarihi AS DATE) AS EmirTarihi
                FROM UretimEmri WHERE Id = ?
            ),
            ToplamTalep AS (
                -- Sadece HatTipi=1 (ana hat); aynı malzeme birden fazla satırda olabilir
                SELECT uehpg.KartId, SUM(uehpg.TalepMiktar) AS ToplamTalep
                FROM UretimEmriHatPlani      uehp
                JOIN UretimEmriHatPlaniGirdi uehpg ON uehpg.UretimEmriHatPlaniId = uehp.Id
                WHERE uehp.UretimEmriId = ?
                  AND uehp.HatTipi IN (1, 2)
                  AND uehpg.KartId IS NOT NULL
                  AND uehpg.TalepMiktar > 0
                GROUP BY uehpg.KartId
            ),
            BakiyeEmirTarih AS (
                SELECT
                    shd.IslemKartId,
                    SUM(CASE
                        WHEN sh.IslemKodu IN (1,4,5,8,15,16,20,22,26,29)
                            THEN (shd.Miktar - ISNULL(shd_f.Miktar, 0))
                        WHEN sh.IslemKodu IN (2,3,6,7,17,18,19,21,24,28)
                            THEN -(shd.Miktar - ISNULL(shd_f.Miktar, 0))
                        ELSE 0
                    END) AS Bakiye
                FROM StokHareketDetay shd
                JOIN StokHareket sh ON sh.Id = shd.HareketId
                LEFT JOIN StokHareketDetay shd_f ON shd_f.Id = shd.FaturaDetayId
                WHERE shd.IslemKartId IN (SELECT KartId FROM ToplamTalep)
                  AND shd.Turu = 1 AND shd.Aktif = 1
                  AND sh.Aktif = 1
                  AND sh.FaturaId IS NULL
                  AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27,23)
                  AND CAST(sh.BelgeTarihi AS DATE) <= (SELECT EmirTarihi FROM EmirBilgi)
                GROUP BY shd.IslemKartId
            )
            SELECT
                sk.Kodu                                           AS MalzemeKodu,
                sk.Adi                                            AS MalzemeAdi,
                tt.ToplamTalep                                    AS Ihtiyac,
                ISNULL(b.Bakiye, 0)                               AS BakiyeEmirTarihi,
                ISNULL(b.Bakiye, 0) - tt.ToplamTalep              AS Eksik
            FROM ToplamTalep tt
            JOIN StokKarti sk              ON sk.Id             = tt.KartId
            LEFT JOIN BakiyeEmirTarih b   ON b.IslemKartId     = tt.KartId
            WHERE ISNULL(b.Bakiye, 0) < tt.ToplamTalep
            ORDER BY sk.Kodu
        """, emir_id, emir_id)
        return [
            {
                'malzeme_kodu':        row[0],
                'malzeme_adi':         row[1],
                'ihtiyac':             float(row[2]),
                'bakiye_emir_tarihi':  float(row[3]),
                'eksik':               float(row[4]),
            }
            for row in cur.fetchall()
        ]


def uretim_emir_bom_patlat(conn, emir_id: int) -> list[dict]:
    """
    HatTipi=1 hat planındaki malzemelerin BOM-patlatmalı eksik stok analizi.

    Alt montaj tespit edilirse standart UretimRecete üzerinden recursive patlatılır;
    her seviyede emri tarihindeki bakiye mahsup edilerek üretilmesi gereken miktar
    bulunur.  Ortak bileşenler için (hem ana hatta hem alt montajda olanlar) toplam
    talep ve toplam eksik gösterilir.

    Dönüş: yalnızca eksik kalemler (eksik < 0), kök seviyede hat planı sırası.
    Her dict:
        kart_id, kodu, adi,
        ihtiyac  – toplam (ağırlıklı) talep,
        bakiye   – emri tarihi bakiyesi,
        eksik    – bakiye - ihtiyac,
        is_alt_montaj,
        bilesenler – [aynı yapı; ihtiyac bu ebeveynden gelen katkıdır]
    """
    # ── 1. Emir tarihi ──────────────────────────────────────────────────────
    with cursor_ctx(conn) as cur:
        cur.execute(
            "SELECT CAST(UretimEmriTarihi AS DATE) FROM UretimEmri WHERE Id=?",
            emir_id
        )
        row = cur.fetchone()
        if not row:
            return []
        emir_tarihi = str(row[0])   # 'YYYY-MM-DD'

    # ── 2. HatTipi=1 hat planı ─────────────────────────────────────────────
    hat_talep: dict[int, dict] = {}
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT uehpg.KartId, sk.Kodu, sk.Adi, SUM(uehpg.TalepMiktar),
                   MIN(uehpg.StokDepoId) AS StokDepoId
            FROM UretimEmriHatPlani      uehp
            JOIN UretimEmriHatPlaniGirdi uehpg ON uehpg.UretimEmriHatPlaniId = uehp.Id
            JOIN StokKarti               sk     ON sk.Id = uehpg.KartId
            WHERE uehp.UretimEmriId   = ?
              AND uehp.HatTipi IN (1, 2)
              AND uehpg.KartId        IS NOT NULL
              AND uehpg.TalepMiktar   > 0
            GROUP BY uehpg.KartId, sk.Kodu, sk.Adi
            ORDER BY sk.Kodu
        """, emir_id)
        for row in cur.fetchall():
            hat_talep[int(row[0])] = {
                'kodu':     row[1],
                'adi':      str(row[2] or '').strip(),
                'talep':    float(row[3]),
                'depo_id':  int(row[4]) if row[4] is not None else None,
            }

    if not hat_talep:
        return []

    # ── 3. Tüm aktif standart reçeteler (tek sorguda) ──────────────────────
    # receteler: {urun_kart_id: [{kart_id, kodu, adi, miktar}]}
    receteler: dict[int, list[dict]] = {}
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT
                sk_u.Id              AS UrunKartId,
                urhpg.KartId         AS BilesenKartId,
                sk_b.Kodu            AS BilesenKodu,
                sk_b.Adi             AS BilesenAdi,
                SUM(urhpg.Miktar)    AS ToplamMiktar
            FROM UretimRecete ur
            JOIN StokKarti sk_u
                ON sk_u.Kodu = ur.Kodu
            JOIN UretimReceteHatPlani urhp
                ON urhp.UretimReceteId = ur.Id
            JOIN UretimReceteHatPlaniGirdi urhpg
                ON urhpg.UretimReceteHatPlaniId = urhp.Id
            JOIN StokKarti sk_b
                ON sk_b.Id = urhpg.KartId
            WHERE (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
              AND urhpg.KartId IS NOT NULL
              AND urhpg.Miktar > 0
            GROUP BY sk_u.Id, urhpg.KartId, sk_b.Kodu, sk_b.Adi
        """)
        for row in cur.fetchall():
            uid = int(row[0])
            if uid not in receteler:
                receteler[uid] = []
            receteler[uid].append({
                'kart_id': int(row[1]),
                'kodu':    row[2],
                'adi':     str(row[3] or '').strip(),
                'miktar':  float(row[4]),
            })

    # ── 4. BFS: tüm ilgili kart ID'lerini bul ──────────────────────────────
    all_ids: set[int] = set(hat_talep.keys())
    queue   = list(hat_talep.keys())
    seen:   set[int] = set(hat_talep.keys())
    while queue:
        kid = queue.pop()
        if kid in receteler:
            for bil in receteler[kid]:
                if bil['kart_id'] not in seen:
                    seen.add(bil['kart_id'])
                    all_ids.add(bil['kart_id'])
                    queue.append(bil['kart_id'])

    # ── 5. Bakiyeler (toplu, 500'lük yığınlar) ─────────────────────────────
    bakiyeler: dict[int, float] = {}
    ids_list = list(all_ids)
    _YIGIN = 500
    for i in range(0, len(ids_list), _YIGIN):
        parca = ids_list[i: i + _YIGIN]
        yer   = ','.join(['?'] * len(parca))
        with cursor_ctx(conn) as cur:
            cur.execute(f"""
                SELECT shd.IslemKartId,
                       SUM(CASE
                           WHEN sh.IslemKodu IN (1,4,5,8,15,16,20,22,26,29)
                               THEN (shd.Miktar - ISNULL(shd_f.Miktar, 0))
                           WHEN sh.IslemKodu IN (2,3,6,7,17,18,19,21,24,28)
                               THEN -(shd.Miktar - ISNULL(shd_f.Miktar, 0))
                           ELSE 0
                       END) AS Bakiye
                FROM StokHareketDetay shd
                JOIN StokHareket sh ON sh.Id = shd.HareketId
                LEFT JOIN StokHareketDetay shd_f ON shd_f.Id = shd.FaturaDetayId
                WHERE shd.IslemKartId IN ({yer})
                  AND shd.Turu = 1 AND shd.Aktif = 1
                  AND sh.Aktif = 1
                  AND sh.FaturaId IS NULL
                  AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27,23)
                  AND CAST(sh.BelgeTarihi AS DATE) <= CAST(? AS DATE)
                GROUP BY shd.IslemKartId
            """, *tuple(parca), emir_tarihi)
            for row in cur.fetchall():
                bakiyeler[int(row[0])] = float(row[1])

    # ── 5b. Hat planı malzemeleri için depo bazlı bakiye ───────────────────
    # CEO ERP, StokDepoId'ye göre depo bakiyesine bakar; depo bakiyesi
    # negatifse toplam bakiyeden öncelikli kullanılır.
    from collections import defaultdict
    hat_bakiyeler_depo: dict[int, float] = {}
    depo_to_kids: dict = defaultdict(list)
    for kid, bilgi in hat_talep.items():
        d = bilgi.get('depo_id')
        if d:
            depo_to_kids[d].append(kid)
    for depo_id, kids in depo_to_kids.items():
        for i in range(0, len(kids), _YIGIN):
            parca = kids[i: i + _YIGIN]
            yer   = ','.join(['?'] * len(parca))
            with cursor_ctx(conn) as cur:
                cur.execute(f"""
                    SELECT shd.IslemKartId,
                           SUM(CASE
                               WHEN sh.IslemKodu IN (1,4,5,8,15,16,20,22,26,29)
                                   THEN (shd.Miktar - ISNULL(shd_f.Miktar, 0))
                               WHEN sh.IslemKodu IN (2,3,6,7,17,18,19,21,24,28)
                                   THEN -(shd.Miktar - ISNULL(shd_f.Miktar, 0))
                               ELSE 0
                           END)
                    FROM StokHareketDetay shd
                    JOIN StokHareket sh ON sh.Id = shd.HareketId
                    LEFT JOIN StokHareketDetay shd_f ON shd_f.Id = shd.FaturaDetayId
                    WHERE shd.IslemKartId IN ({yer})
                      AND shd.Turu = 1 AND shd.Aktif = 1
                      AND sh.Aktif = 1
                      AND sh.FaturaId IS NULL
                      AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27,23)
                      AND sh.DepoKartId = ?
                      AND CAST(sh.BelgeTarihi AS DATE) <= CAST(? AS DATE)
                    GROUP BY shd.IslemKartId
                """, *tuple(parca), depo_id, emir_tarihi)
                for row in cur.fetchall():
                    hat_bakiyeler_depo[int(row[0])] = float(row[1])

    # ── 6. Talep birikimi + ağaç inşası ────────────────────────────────────
    toplam_talep: dict[int, float] = {
        kid: bilgi['talep'] for kid, bilgi in hat_talep.items()
    }

    def _patlat(kart_id: int, ihtiyac: float, depth: int = 0) -> list[dict]:
        """
        Alt montajı reçetesine göre açar; toplam_talep'e katkı ekler.
        Döner: çocuk düğüm listesi (bu ebeveynden gelen bireysel katkıyla).
        """
        if depth >= 8 or kart_id not in receteler:
            return []
        bakiye         = bakiyeler.get(kart_id, 0.0)
        uretim_gerekli = max(0.0, ihtiyac - bakiye)
        if uretim_gerekli <= 0:
            return []
        children = []
        for bil in receteler[kart_id]:
            bid         = bil['kart_id']
            bil_ihtiyac = bil['miktar'] * uretim_gerekli
            toplam_talep[bid] = toplam_talep.get(bid, 0.0) + bil_ihtiyac
            sub_ch = _patlat(bid, bil_ihtiyac, depth + 1)
            bbakiye = bakiyeler.get(bid, 0.0)
            children.append({
                'kart_id':      bid,
                'kodu':         bil['kodu'],
                'adi':          bil['adi'],
                'ihtiyac':      bil_ihtiyac,
                'bakiye':       bbakiye,
                'eksik':        bbakiye - bil_ihtiyac,
                'is_alt_montaj': bid in receteler,
                'bilesenler':   sub_ch,
            })
        return children

    # Hat planındaki alt montajları patlatıyoruz
    hat_bilesenler: dict[int, list[dict]] = {}
    for kid, bilgi in hat_talep.items():
        if kid in receteler:
            hat_bilesenler[kid] = _patlat(kid, bilgi['talep'])

    # ── 7. Kök düğümleri oluştur — yalnızca eksik olanlar ──────────────────
    # Depo bakiyesi negatifse CEO ERP bunu yetersiz kabul eder; toplam
    # bakiyeden önce depo bakiyesi kontrol edilir.
    sonuc: list[dict] = []
    for kid, bilgi in hat_talep.items():
        agr_talep    = toplam_talep.get(kid, bilgi['talep'])
        bakiye_total = bakiyeler.get(kid, 0.0)
        if kid in hat_bakiyeler_depo:
            bakiye_depo = hat_bakiyeler_depo[kid]
            efektif_bakiye = bakiye_depo if bakiye_depo < 0 else bakiye_total
        else:
            efektif_bakiye = bakiye_total
        eksik = efektif_bakiye - agr_talep
        if eksik >= 0:
            continue
        sonuc.append({
            'kart_id':      kid,
            'kodu':         bilgi['kodu'],
            'adi':          bilgi['adi'],
            'ihtiyac':      agr_talep,
            'bakiye':       efektif_bakiye,
            'eksik':        eksik,
            'is_alt_montaj': kid in receteler,
            'bilesenler':   hat_bilesenler.get(kid, []),
        })

    sonuc.sort(key=lambda x: x['kodu'])
    return sonuc


def tum_emirler_eksik_stok(conn) -> list[dict]:
    """Tüm açık emirler için BOM patlatmalı eksik stok listesi.

    Her emir kendi tarihi esas alınarak hesaplanır.
    Döner: [{'id', 'kodu', 'aciklama', 'tarih', 'eksikler': [...]}, ...]
    Sadece en az bir eksik malzeme olan emirler dahildir.
    """
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT ue.Id, ue.Kodu, ISNULL(ue.Aciklama, ''),
                   CONVERT(VARCHAR(10), ue.UretimEmriTarihi, 104)
            FROM UretimEmri ue
            WHERE ue.DurumId = 3
            ORDER BY ue.UretimEmriTarihi DESC, ue.Kodu
        """)
        emirler = [
            {'id': int(r[0]), 'kodu': r[1], 'aciklama': str(r[2] or '').strip(), 'tarih': r[3]}
            for r in cur.fetchall()
        ]

    sonuc = []
    for e in emirler:
        eksikler = uretim_emir_bom_patlat(conn, e['id'])
        if eksikler:
            sonuc.append({**e, 'eksikler': eksikler})
    return sonuc


# ── Araç 4b: Muhasebe Eksik Raporu (ATP destekli, kronolojik) ─────────────────

def muhasebe_eksik_raporu_olustur(conn) -> list[dict]:
    """
    Tüm "Devam Ediyor" emirlerin kronolojik sırayla ATP destekli muhasebe eksik raporu.

    Algoritma:
      1. Emirler UretimEmriTarihi ASC sıralanır.
      2. Her emir için Hat Planı (HatTipi=1) alınır; yarı mamüller dahil recursive
         BOM patlatması yapılır (brüt talep, bakiyeden bağımsız).
      3. Bakiye: emir tarihinde toplam + depo bazlı hibrit (hat planı itemleri için).
      4. ATP rezervasyon: daha eski emirlerin kümülatif talebi net bakiyeden düşülür.

    Döner: sadece net_eksik > 0 olan satırlar; her dict:
        emir_tarihi, emir_kodu, emir_aciklama,
        stok_kodu, stok_adi,
        ihtiyac           – brüt talep (bu emir)
        erp_bakiye        – emir tarihindeki hibrit bakiye
        onceki_rezervasyon – eski emirlerin kümülatif talebi
        net_eksik         – pozitif sayı; stoka girilmesi gereken miktar
    """
    from collections import defaultdict

    _GIR = (1, 4, 5, 8, 15, 16, 20, 22, 26, 29)
    _CIK = (2, 3, 6, 7, 17, 18, 19, 21, 24, 28)   # k23 hariç — CEO fnStokBakiyeGetir
    _YIG = 500
    gir_s = ','.join(str(x) for x in _GIR)
    cik_s = ','.join(str(x) for x in _CIK)

    # ── 1. Emirler ASC ────────────────────────────────────────────────────────
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT ue.Id,
                   ue.Kodu,
                   ISNULL(ue.Aciklama, ''),
                   CAST(ue.UretimEmriTarihi AS DATE),
                   CONVERT(VARCHAR(10), ue.UretimEmriTarihi, 104)
            FROM UretimEmri ue
            WHERE ue.DurumId = 3
            ORDER BY ue.UretimEmriTarihi ASC, ue.Kodu
        """)
        emirler = [
            {
                'id':        int(r[0]),
                'kodu':      r[1],
                'aciklama':  str(r[2] or '').strip(),
                'tarih':     str(r[3]),    # YYYY-MM-DD  — SQL filtresi
                'tarih_fmt': str(r[4]),    # DD.MM.YYYY  — Excel
            }
            for r in cur.fetchall()
        ]
    if not emirler:
        return []

    emir_ids = [e['id'] for e in emirler]

    # ── 2. Hat planları (tüm emirler, tek toplu sorgu) ─────────────────────────
    hat_all: dict[int, dict[int, dict]] = defaultdict(dict)
    for i in range(0, len(emir_ids), _YIG):
        batch = emir_ids[i: i + _YIG]
        yer   = ','.join(['?'] * len(batch))
        with cursor_ctx(conn) as cur:
            cur.execute(f"""
                SELECT uehp.UretimEmriId,
                       uehpg.KartId,
                       sk.Kodu,
                       sk.Adi,
                       SUM(uehpg.TalepMiktar),
                       MIN(uehpg.StokDepoId)
                FROM UretimEmriHatPlani      uehp
                JOIN UretimEmriHatPlaniGirdi uehpg
                    ON uehpg.UretimEmriHatPlaniId = uehp.Id
                JOIN StokKarti sk ON sk.Id = uehpg.KartId
                WHERE uehp.UretimEmriId IN ({yer})
                  AND uehp.HatTipi IN (1, 2)
                  AND uehpg.KartId       IS NOT NULL
                  AND uehpg.TalepMiktar  > 0
                GROUP BY uehp.UretimEmriId, uehpg.KartId, sk.Kodu, sk.Adi
            """, *tuple(batch))
            for row in cur.fetchall():
                eid = int(row[0])
                kid = int(row[1])
                hat_all[eid][kid] = {
                    'kodu':    row[2],
                    'adi':     str(row[3] or '').strip(),
                    'talep':   float(row[4]),
                    'depo_id': int(row[5]) if row[5] is not None else None,
                }

    # ── 3. Tüm aktif reçeteler ────────────────────────────────────────────────
    receteler: dict[int, list[dict]] = {}
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT sk_u.Id,
                   urhpg.KartId,
                   sk_b.Kodu,
                   sk_b.Adi,
                   SUM(urhpg.Miktar)
            FROM UretimRecete ur
            JOIN StokKarti sk_u
                ON sk_u.Kodu = ur.Kodu
            JOIN UretimReceteHatPlani urhp
                ON urhp.UretimReceteId = ur.Id
            JOIN UretimReceteHatPlaniGirdi urhpg
                ON urhpg.UretimReceteHatPlaniId = urhp.Id
            JOIN StokKarti sk_b
                ON sk_b.Id = urhpg.KartId
            WHERE (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
              AND urhpg.KartId IS NOT NULL
              AND urhpg.Miktar > 0
            GROUP BY sk_u.Id, urhpg.KartId, sk_b.Kodu, sk_b.Adi
        """)
        for row in cur.fetchall():
            uid = int(row[0])
            receteler.setdefault(uid, []).append({
                'kart_id': int(row[1]),
                'kodu':    row[2],
                'adi':     str(row[3] or '').strip(),
                'miktar':  float(row[4]),
            })

    # ── 4. Her emir için düz BOM (yarı mamüller dahil, brüt talep) ────────────
    def _flat_bom(hat_talep: dict) -> dict[int, dict]:
        """
        Hat planı itemleri + tüm recursive bileşenler tek listede.
        Yarı mamüllerin kendi stok kodları da yer alır (hat planında olsun ya da olmasın).
        Aynı kart_id birden fazla yoldan geliyorsa ihtiyac toplanır.
        depo_id sadece hat planında doğrudan yer alan itemlar için tutulur
        (depo bazlı hibrit bakiye hesabında kullanılır).
        """
        sonuc: dict[int, dict] = {}

        def _ekle(kid: int, kodu: str, adi: str,
                  ihtiyac: float, depo_id, depth: int) -> None:
            if kid in sonuc:
                sonuc[kid]['ihtiyac'] += ihtiyac
            else:
                sonuc[kid] = {
                    'kodu':    kodu,
                    'adi':     adi,
                    'ihtiyac': ihtiyac,
                    'depo_id': depo_id,
                }
            if depth < 8 and kid in receteler:
                for bil in receteler[kid]:
                    _ekle(bil['kart_id'], bil['kodu'], bil['adi'],
                          bil['miktar'] * ihtiyac, None, depth + 1)

        for kid, info in hat_talep.items():
            _ekle(kid, info['kodu'], info['adi'],
                  info['talep'], info.get('depo_id'), 0)
        return sonuc

    flat_boms: dict[int, dict] = {
        e['id']: _flat_bom(hat_all.get(e['id'], {}))
        for e in emirler
    }

    # ── 5. Tarih bazında gerekli kart_id'leri topla ───────────────────────────
    tarih_to_kids:     dict[str, set[int]]       = defaultdict(set)
    tarih_to_depo_map: dict[str, dict[int, int]] = defaultdict(dict)

    for e in emirler:
        t = e['tarih']
        for kid, info in flat_boms[e['id']].items():
            tarih_to_kids[t].add(kid)
            if info.get('depo_id'):
                tarih_to_depo_map[t].setdefault(kid, info['depo_id'])

    # ── 6. Toplu bakiye sorguları (tarih başına) ──────────────────────────────
    # Toplam bakiye + depo bazlı bakiye (hat planı itemleri için).
    # Depo bakiyesi < 0 ise efektif bakiye olarak depo kullanılır;
    # böylece "başka depoda stok var ama hedef depo boş" durumu yakalanır.
    bak:      dict[tuple, float] = {}   # (kid, tarih)          -> toplam bakiye
    bak_depo: dict[tuple, float] = {}   # (kid, tarih, depo_id) -> depo bakiyesi

    for tarih, kids in tarih_to_kids.items():
        kids_list = list(kids)

        # — Toplam bakiye —
        for i in range(0, len(kids_list), _YIG):
            parca = kids_list[i: i + _YIG]
            yer   = ','.join(['?'] * len(parca))
            with cursor_ctx(conn) as cur:
                cur.execute(f"""
                    SELECT shd.IslemKartId,
                           SUM(CASE
                               WHEN sh.IslemKodu IN ({gir_s})
                                   THEN (shd.Miktar - ISNULL(shd_f.Miktar, 0))
                               WHEN sh.IslemKodu IN ({cik_s})
                                   THEN -(shd.Miktar - ISNULL(shd_f.Miktar, 0))
                               ELSE 0
                           END)
                    FROM StokHareketDetay shd
                    JOIN StokHareket sh ON sh.Id = shd.HareketId
                    LEFT JOIN StokHareketDetay shd_f ON shd_f.Id = shd.FaturaDetayId
                    WHERE shd.IslemKartId IN ({yer})
                      AND shd.Turu = 1 AND shd.Aktif = 1
                      AND sh.Aktif = 1
                      AND sh.FaturaId IS NULL
                      AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27,23)
                      AND CAST(sh.BelgeTarihi AS DATE) <= CAST(? AS DATE)
                    GROUP BY shd.IslemKartId
                """, *tuple(parca), tarih)
                for row in cur.fetchall():
                    bak[(int(row[0]), tarih)] = float(row[1])

        # — Depo bazlı bakiye —
        depo_to_kids_map: dict[int, list] = defaultdict(list)
        for kid, did in tarih_to_depo_map.get(tarih, {}).items():
            depo_to_kids_map[did].append(kid)

        for did, dkids in depo_to_kids_map.items():
            for i in range(0, len(dkids), _YIG):
                parca = dkids[i: i + _YIG]
                yer   = ','.join(['?'] * len(parca))
                with cursor_ctx(conn) as cur:
                    cur.execute(f"""
                        SELECT shd.IslemKartId,
                               SUM(CASE
                                   WHEN sh.IslemKodu IN ({gir_s})
                                       THEN (shd.Miktar - ISNULL(shd_f.Miktar, 0))
                                   WHEN sh.IslemKodu IN ({cik_s})
                                       THEN -(shd.Miktar - ISNULL(shd_f.Miktar, 0))
                                   ELSE 0
                               END)
                        FROM StokHareketDetay shd
                        JOIN StokHareket sh ON sh.Id = shd.HareketId
                        LEFT JOIN StokHareketDetay shd_f ON shd_f.Id = shd.FaturaDetayId
                        WHERE shd.IslemKartId IN ({yer})
                          AND shd.Turu = 1 AND shd.Aktif = 1
                          AND sh.Aktif = 1
                          AND sh.FaturaId IS NULL
                          AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27,23)
                          AND sh.DepoKartId = ?
                          AND CAST(sh.BelgeTarihi AS DATE) <= CAST(? AS DATE)
                        GROUP BY shd.IslemKartId
                    """, *tuple(parca), did, tarih)
                    for row in cur.fetchall():
                        bak_depo[(int(row[0]), tarih, did)] = float(row[1])

    # ── 7. Kronolojik ATP analizi ─────────────────────────────────────────────
    rezervasyon: dict[int, float] = {}
    satirlar: list[dict] = []

    for e in emirler:
        tarih = e['tarih']
        flat  = flat_boms[e['id']]

        for kid, info in sorted(flat.items(), key=lambda x: x[1]['kodu']):
            bak_total = bak.get((kid, tarih), 0.0)
            did = info.get('depo_id')
            if did:
                bak_d   = bak_depo.get((kid, tarih, did))
                efektif = bak_d if (bak_d is not None and bak_d < 0) else bak_total
            else:
                efektif = bak_total
            onceki_rez = rezervasyon.get(kid, 0.0)
            ihtiyac    = info['ihtiyac']
            bos        = efektif - ihtiyac - onceki_rez
            net_eksik  = round(-bos, 4) if bos < -0.0001 else 0.0

            if net_eksik > 0:
                satirlar.append({
                    'emir_tarihi':        e['tarih_fmt'],
                    'emir_kodu':          e['kodu'],
                    'emir_aciklama':      e['aciklama'],
                    'stok_kodu':          info['kodu'],
                    'stok_adi':           info['adi'],
                    'ihtiyac':            round(ihtiyac, 4),
                    'erp_bakiye':         round(efektif, 4),
                    'onceki_rezervasyon': round(onceki_rez, 4),
                    'net_eksik':          net_eksik,
                })

            # Rezervasyonu her durumda güncelle (eksik olsun ya da olmasın)
            rezervasyon[kid] = onceki_rez + ihtiyac

    return satirlar

# ── Araç 5: Satış Faturaları ──────────────────────────────────────────────────

def satis_faturalari(conn, bas_tarih: str, bit_tarih: str) -> list[dict]:
    """
    Belirtilen tarih aralığındaki satış fatura ve irsaliye satırlarını döner.
    bas_tarih / bit_tarih: 'DD.MM.YYYY' formatı.
    IslemKodu 2 = Satış Faturası, 6 = Satış İrsaliyesi.

    Faturalaşan irsaliye — mükerrer sayım düzeltmesi
    -------------------------------------------------
    Bir satış irsaliyesi (IslemKodu=6) sonradan faturaya dönüştüğünde CEO ERP
    StokHareket.FaturaId alanını doldurur; hem irsaliye hem onun faturası ayrı
    satır olarak durur. Sadece IslemKodu=2 (Satış Faturası) VE FaturaId'si BOŞ
    olan IslemKodu=6 (henüz faturalaşmamış irsaliye) satırları toplanır —
    aksi hâlde aynı satış iki kez sayılır. Bakiye formülündeki
    `sh.FaturaId IS NULL` kuralıyla aynı mantık (bkz. ERP-OKUMA.md); bu,
    proje_satinalma_hareketleri()'ndeki alış tarafı düzeltmesinin satış
    aynasıdır.
    """
    bas_parts = bas_tarih.split('.')
    bit_parts = bit_tarih.split('.')
    bas_sql = f"{bas_parts[2]}-{bas_parts[1]}-{bas_parts[0]}"
    bit_sql = f"{bit_parts[2]}-{bit_parts[1]}-{bit_parts[0]}"

    with cursor_ctx(conn) as cur:
        cur.execute(f"""
            SELECT
                ISNULL(cmk.Unvani, ''),
                sk.Kodu,
                sk.Adi,
                CASE sh.IslemKodu WHEN 2 THEN 'Satış Faturası' ELSE 'Satış İrsaliyesi' END,
                ISNULL(sh.BelgeSeriNo, '') + ISNULL(CAST(sh.BelgeSiraNo AS VARCHAR(20)), ''),
                CONVERT(VARCHAR(10), sh.BelgeTarihi, 104),
                CONVERT(VARCHAR(10), sh.BelgeTarihi, 120),
                ISNULL(shd.Miktar, 0),
                ISNULL(shd.BirimFiyat, 0),
                ISNULL(shd.Tutar, 0)
            FROM StokHareket sh
            JOIN StokHareketDetay shd ON shd.HareketId = sh.Id
            JOIN StokKarti sk ON sk.Id = shd.IslemKartId
            LEFT JOIN CariMusteriKarti cmk ON sh.MusteriKartId = cmk.Id
            WHERE (sh.IslemKodu = 2 OR (sh.IslemKodu = 6 AND sh.FaturaId IS NULL))
              AND shd.Turu = 1
              AND shd.Miktar > 0
              AND CAST(sh.BelgeTarihi AS DATE) >= CAST('{bas_sql}' AS DATE)
              AND CAST(sh.BelgeTarihi AS DATE) <= CAST('{bit_sql}' AS DATE)
            ORDER BY sh.BelgeTarihi ASC, cmk.Unvani ASC, sk.Kodu ASC
        """)
        return [
            {
                'musteri':     row[0],
                'stok_kodu':   row[1],
                'stok_adi':    row[2],
                'islem_turu':  row[3],
                'belge_no':    row[4],
                'tarih':       row[5],
                'tarih_iso':   row[6],
                'miktar':      float(row[7]),
                'birim_fiyat': float(row[8]),
                'tutar':       float(row[9]),
            }
            for row in cur.fetchall()
        ]


# ── Araç 8: Reçete Sorgula — Bileşen → Mamül Ağacı ───────────────────────────

def bilesen_mamul_bul(conn, kodlar: list[str]) -> dict[str, dict]:
    """
    Verilen stok kodlarının hangi mamül ağaçlarında bileşen olarak kullanıldığını bulur.
    BFS ile tüm seviyeleri (recursive) tarar: direkt ve dolaylı (alt montaj üzerinden).

    Returns:
        {giris_kodu: {
            "mamullar": [{"kodu", "adi", "seviye"}, ...],  # seviye 1=direkt
            "bulundu":    bool,
            "kod_gecerli": bool,
        }}
    """
    from collections import defaultdict

    # 1. Tüm aktif BOM kenarları: mamül ID → bileşen ID
    #    Tipi=1 (StokKarti) ve Tipi=2 (StokMasrafKarti) birlikte alınır.
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT DISTINCT
                sk_u.Id         AS MamulId,
                sk_u.Kodu       AS MamulKodu,
                sk_u.Adi        AS MamulAdi,
                urhpg.KartId    AS BilesenId
            FROM UretimRecete ur
            JOIN StokKarti sk_u
                ON sk_u.Kodu = ur.Kodu
            JOIN UretimReceteHatPlani urhp
                ON urhp.UretimReceteId = ur.Id
            JOIN UretimReceteHatPlaniGirdi urhpg
                ON urhpg.UretimReceteHatPlaniId = urhp.Id
            WHERE (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
              AND urhpg.KartId IS NOT NULL
        """)
        kenarlar = cur.fetchall()

    mamul_bilgi: dict[int, dict] = {}
    ust_harita: dict[int, set] = defaultdict(set)  # bilesen_id → {mamul_id, ...}

    for mamul_id, mamul_kodu, mamul_adi, bilesen_id in kenarlar:
        mid, bid = int(mamul_id), int(bilesen_id)
        mamul_bilgi[mid] = {"kodu": mamul_kodu, "adi": str(mamul_adi or "").strip()}
        ust_harita[bid].add(mid)

    # 2. Girdi kodları → Id eşlemesi: StokKarti (Tipi=1) + StokMasrafKarti (Tipi=2)
    with cursor_ctx(conn) as cur:
        cur.execute("SELECT Id, Kodu FROM StokKarti WHERE Aktif = 1")
        kodu_to_id: dict[str, int] = {r[1]: int(r[0]) for r in cur.fetchall()}
    with cursor_ctx(conn) as cur:
        cur.execute("SELECT Id, Kodu FROM StokMasrafKarti")
        masraf_kodu_to_id: dict[str, int] = {r[1]: int(r[0]) for r in cur.fetchall()}

    sonuclar: dict[str, dict] = {}

    for giris_kodu in kodlar:
        gk = giris_kodu.strip().upper()
        if not gk:
            continue

        if gk not in kodu_to_id and gk not in masraf_kodu_to_id:
            sonuclar[gk] = {"mamullar": [], "bulundu": False, "kod_gecerli": False}
            continue

        giris_id = kodu_to_id.get(gk) or masraf_kodu_to_id.get(gk)

        # BFS yukarı: kısa yol garantili, döngü korumalı
        min_seviye: dict[int, int] = {}
        visited: set = {giris_id}
        queue = [(giris_id, 0)]

        while queue:
            sonraki = []
            for current_id, sev in queue:
                for parent_id in ust_harita.get(current_id, set()):
                    if parent_id not in visited:
                        visited.add(parent_id)
                        min_seviye[parent_id] = sev + 1
                        sonraki.append((parent_id, sev + 1))
            queue = sonraki

        mamullar = sorted(
            [
                {
                    "kodu":   mamul_bilgi[mid]["kodu"],
                    "adi":    mamul_bilgi[mid]["adi"],
                    "seviye": sev,
                }
                for mid, sev in min_seviye.items()
                if mid in mamul_bilgi
            ],
            key=lambda x: (x["seviye"], x["kodu"]),
        )

        sonuclar[gk] = {
            "mamullar": mamullar,
            "bulundu":  bool(mamullar),
            "kod_gecerli": True,
        }

    return sonuclar


# ── Araç 9: Stok Hazırlık — Birimler / Reçete Kontrol ────────────────────────

def recete_yukle(conn, mamul_kod: str, max_derinlik: int = 8) -> dict | None:
    """
    mamul_kod için CEO ERP'den reçete ağacını recursive yükler.
    Döner nested dict veya None (reçete yok).

    Dict yapısı (her node):
      {kod, stok_id, adi, adi2, birim_guid, tip, girdi_id, org_miktar, miktar, children}
    birim_guid: StokKarti.StokBirim kolonundan alınan GUID str (JOIN yok).
                Thread tarafında isim çözümü yapılır.
    girdi_id: bu öğenin parent reçetesindeki UretimReceteHatPlaniGirdi.Id
              Root öğe için None.
    """
    # Tüm aktif reçete kodları — tek sorguda al
    with cursor_ctx(conn) as cur:
        cur.execute(
            "SELECT Kodu FROM UretimRecete "
            "WHERE KullanimDisi IS NULL OR KullanimDisi = 0"
        )
        recipe_codes: set[str] = {str(r[0]) for r in cur.fetchall()}

    if mamul_kod not in recipe_codes:
        return None

    # Adi2 kolonu var mı? (tek seferlik; hata olursa rollback + devam)
    _adi2_var = False
    try:
        with cursor_ctx(conn) as cur:
            cur.execute("SELECT TOP 0 Adi2 FROM StokKarti")
        _adi2_var = True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    def _fmt(f: float) -> str:
        return str(int(f)) if f == int(f) else str(round(f, 4))

    def _stok_bilgi(kod: str):
        """StokKarti bilgisi. StokBirim tablosuna JOIN YAPMA — GUID doğrudan al."""
        if _adi2_var:
            q = ("SELECT Id, ISNULL(Adi,''), ISNULL(Adi2,''), "
                 "ISNULL(CONVERT(NVARCHAR(50),StokBirim),'') "
                 "FROM StokKarti WHERE Kodu = ? AND Aktif = 1")
        else:
            q = ("SELECT Id, ISNULL(Adi,''), '', "
                 "ISNULL(CONVERT(NVARCHAR(50),StokBirim),'') "
                 "FROM StokKarti WHERE Kodu = ? AND Aktif = 1")
        with cursor_ctx(conn) as cur:
            cur.execute(q, kod)
            return cur.fetchone()

    def _bilesenleri(kod: str) -> list:
        """
        Reçete bileşenleri. Tipi=1 → StokKarti, Tipi=2 → StokMasrafKarti.
        Her satır: (c_kod, c_id, c_adi, c_adi2, c_birim_guid, c_girdi_id, c_miktar, c_tipi)
        StokBirim JOIN yok — GUID direkt alınır.
        """
        # Tipi=1: normal stok bileşenleri
        if _adi2_var:
            q1 = """
                SELECT sk.Kodu, sk.Id, ISNULL(sk.Adi,''), ISNULL(sk.Adi2,''),
                       ISNULL(CONVERT(NVARCHAR(50), sk.StokBirim),''),
                       urhpg.Id, urhpg.Miktar, 1
                FROM UretimRecete ur
                INNER JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
                INNER JOIN UretimReceteHatPlaniGirdi urhpg
                    ON urhpg.UretimReceteHatPlaniId = urhp.Id
                INNER JOIN StokKarti sk ON sk.Id = urhpg.KartId
                WHERE ur.Kodu = ?
                  AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
                  AND urhpg.Tipi = 1
                  AND sk.Aktif = 1
            """
        else:
            q1 = """
                SELECT sk.Kodu, sk.Id, ISNULL(sk.Adi,''), '',
                       ISNULL(CONVERT(NVARCHAR(50), sk.StokBirim),''),
                       urhpg.Id, urhpg.Miktar, 1
                FROM UretimRecete ur
                INNER JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
                INNER JOIN UretimReceteHatPlaniGirdi urhpg
                    ON urhpg.UretimReceteHatPlaniId = urhp.Id
                INNER JOIN StokKarti sk ON sk.Id = urhpg.KartId
                WHERE ur.Kodu = ?
                  AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
                  AND urhpg.Tipi = 1
                  AND sk.Aktif = 1
            """
        # Tipi=2: masraf bileşenleri (StokMasrafKarti — Adi2 yok, birim StokBirimId)
        q2 = """
            SELECT smk.Kodu, smk.Id, ISNULL(smk.Adi,''), '',
                   ISNULL(CONVERT(NVARCHAR(50), smk.StokBirimId),''),
                   urhpg.Id, urhpg.Miktar, 2
            FROM UretimRecete ur
            INNER JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
            INNER JOIN UretimReceteHatPlaniGirdi urhpg
                ON urhpg.UretimReceteHatPlaniId = urhp.Id
            INNER JOIN StokMasrafKarti smk ON smk.Id = urhpg.KartId
            WHERE ur.Kodu = ?
              AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi = 0)
              AND urhpg.Tipi = 2
        """
        with cursor_ctx(conn) as cur:
            cur.execute(q1, kod)
            rows = cur.fetchall()
        with cursor_ctx(conn) as cur:
            cur.execute(q2, kod)
            rows = rows + cur.fetchall()
        return rows

    ziyaret_edildi: set[str] = set()

    def _yukle(kod: str, girdi_id, org_miktar: float, depth: int) -> dict | None:
        if depth > max_derinlik or kod in ziyaret_edildi:
            return None
        ziyaret_edildi.add(kod)
        try:
            sb = _stok_bilgi(kod)
            if not sb:
                return None
            stok_id = int(sb[0])
            adi, adi2, birim_guid = str(sb[1]), str(sb[2]), str(sb[3] or "")

            children = []
            if kod in recipe_codes:
                for row in _bilesenleri(kod):
                    c_kod, c_id, c_adi, c_adi2, c_birim_guid, c_girdi_id, c_miktar, c_tipi = row
                    if c_tipi == 2:
                        # Masraf bileşeni — StokMasrafKarti, her zaman yaprak düğüm
                        children.append({
                            "kod":        str(c_kod),
                            "stok_id":    int(c_id),
                            "adi":        str(c_adi),
                            "adi2":       "",
                            "birim_guid": str(c_birim_guid or ""),
                            "birim_adi":  "ADET",
                            "tip":        "Masraf",
                            "girdi_id":   int(c_girdi_id),
                            "org_miktar": float(c_miktar or 1.0),
                            "miktar":     _fmt(float(c_miktar or 1.0)),
                            "children":   [],
                        })
                    else:
                        child = _yukle(str(c_kod), int(c_girdi_id), float(c_miktar or 1.0), depth + 1)
                        if child:
                            children.append(child)

            if depth == 0:
                tip = "Mamül"
            elif children:
                tip = "Reçete"
            else:
                tip = "Hammadde"

            return {
                "kod":        kod,
                "stok_id":    stok_id,
                "adi":        adi,
                "adi2":       adi2,
                "birim_guid": birim_guid,   # thread GUID → adi çözümü yapar
                "birim_adi":  "ADET",       # thread tarafında güncellenir
                "tip":        tip,
                "girdi_id":   girdi_id,
                "org_miktar": org_miktar,
                "miktar":     _fmt(org_miktar),
                "children":   children,
            }
        finally:
            ziyaret_edildi.discard(kod)

    return _yukle(mamul_kod, None, 1.0, 0)


def birimleri_getir(conn) -> dict:
    """CeoCommon.StokBirim → ``{açıklama: GUID}``.

    CEO ERP'de birim sözlüğü şirket DB'sinde değil ortak DB'de tutulur.
    Eski kurulumlarda ortak tablo erişilemiyorsa aktarım akışını tamamen
    durdurmamak için yalnızca kesin bildiğimiz ADET GUID'i fallback olarak
    bırakılır; rapor tarafındaki bilinmeyen GUID'ler ``Bilinmiyor`` gösterilir.
    """
    try:
        with cursor_ctx(conn) as cur:
            cur.execute("""
                SELECT StokBirimAciklama, StokBirimID
                FROM [CeoCommon].dbo.StokBirim
                WHERE Aktif = 1
                ORDER BY StokBirimAciklama
            """)
            return {str(r[0]): str(r[1]) for r in cur.fetchall()}
    except Exception:
        return {"ADET": "4acc21e3-3140-4863-922d-a0b3d35de8c1"}


def stok_hazirlik_kod_bilgileri(conn, kodlar: list[str]) -> dict[str, dict]:
    """Stok Hazırlık Excel satırlarını ERP kart bilgileriyle eşleştirir.

    Sonuç, girişteki kodların boşlukları kırpılmış hâliyle anahtarlanır. Her
    kayıtta ``stok`` ve/veya ``masraf`` anahtarı bulunabilir; ayrıca kodun aktif
    bir reçete başlığı olup olmadığı ``receteli`` alanında verilir. Sorgular
    toplu ve parametreli çalışır; Excel'den gelen değerleri değiştirmez.

    Aynı kodun iki kart tablosunda da bulunması özellikle korunur. UI, Excel'deki
    tip ipucunu kullanarak doğru kartı seçer ve bu durumu kullanıcıya bildirir.
    """
    temiz = []
    gorulen = set()
    for kod in kodlar or []:
        k = str(kod or "").strip()
        anahtar = k.casefold()
        if k and anahtar not in gorulen:
            gorulen.add(anahtar)
            temiz.append(k)
    if not temiz:
        return {}

    sonuc: dict[str, dict] = {}
    # SQL Server'ın parametre sınırına yaklaşmamak ve uzun IN listelerinde de
    # aynı davranışı korumak için kodları küçük gruplar hâlinde sorgula.
    for bas in range(0, len(temiz), 500):
        grup = temiz[bas:bas + 500]
        yerler = ",".join("?" for _ in grup)

        def _ekle(kod, kaynak, kayit):
            key = str(kod or "").strip().casefold()
            giris = next((x for x in grup if x.casefold() == key), None)
            if giris is None:
                return
            hedef = sonuc.setdefault(giris, {"receteli": False})
            # Aynı kaynak tablosunda kopya kod varsa ilk kaydı kullan; aktif
            # kayıtlar SQL sıralamasıyla önce gelir.
            hedef.setdefault(kaynak, kayit)

        with cursor_ctx(conn) as cur:
            try:
                cur.execute(f"""
                    SELECT Kodu, Id, ISNULL(Adi, ''), ISNULL(Adi2, ''),
                           ISNULL(CONVERT(NVARCHAR(50), StokBirim), ''),
                           ISNULL(Aktif, 0)
                    FROM StokKarti
                    WHERE Kodu IN ({yerler})
                    ORDER BY Kodu, Aktif DESC, Id
                """, grup)
            except Exception:
                # Bazı eski CEO kurulumlarında Adi2 kolonu bulunmayabilir.
                try:
                    conn.rollback()
                except Exception:
                    pass
                cur.execute(f"""
                    SELECT Kodu, Id, ISNULL(Adi, ''), '',
                           ISNULL(CONVERT(NVARCHAR(50), StokBirim), ''),
                           ISNULL(Aktif, 0)
                    FROM StokKarti
                    WHERE Kodu IN ({yerler})
                    ORDER BY Kodu, Aktif DESC, Id
                """, grup)
            for r in cur.fetchall():
                _ekle(r[0], "stok", {
                    "id": int(r[1]), "kod": str(r[0]).strip(),
                    "adi": str(r[2] or ""), "adi2": str(r[3] or ""),
                    "birim_guid": str(r[4] or ""), "aktif": bool(r[5]),
                })

        with cursor_ctx(conn) as cur:
            cur.execute(f"""
                SELECT Kodu, Id, ISNULL(Adi, ''),
                       ISNULL(CONVERT(NVARCHAR(50), StokBirimId), ''),
                       ISNULL(Aktif, 0)
                FROM StokMasrafKarti
                WHERE Kodu IN ({yerler})
                ORDER BY Kodu, Aktif DESC, Id
            """, grup)
            for r in cur.fetchall():
                _ekle(r[0], "masraf", {
                    "id": int(r[1]), "kod": str(r[0]).strip(),
                    "adi": str(r[2] or ""), "adi2": "",
                    "birim_guid": str(r[3] or ""), "aktif": bool(r[4]),
                })

        with cursor_ctx(conn) as cur:
            cur.execute(f"""
                SELECT DISTINCT Kodu
                FROM UretimRecete
                WHERE Kodu IN ({yerler})
                  AND (KullanimDisi IS NULL OR KullanimDisi = 0)
            """, grup)
            for r in cur.fetchall():
                key = str(r[0] or "").strip().casefold()
                giris = next((x for x in grup if x.casefold() == key), None)
                if giris is not None:
                    sonuc.setdefault(giris, {"receteli": False})["receteli"] = True

    return sonuc


def recete_var_mi(conn, parent_kod: str) -> tuple:
    """
    parent_kod için UretimRecete ve ilk HatPlani Id'lerini döner.
    Döner: (recete_id, hat_plani_id) — biri veya ikisi None olabilir.
    """
    try:
        with cursor_ctx(conn) as cur:
            cur.execute(
                "SELECT TOP 1 Id FROM UretimRecete "
                "WHERE Kodu = ? AND (KullanimDisi IS NULL OR KullanimDisi = 0)",
                parent_kod,
            )
            row = cur.fetchone()
        if not row:
            return None, None
        recete_id = row[0]
        with cursor_ctx(conn) as cur:
            cur.execute(
                "SELECT TOP 1 Id FROM UretimReceteHatPlani WHERE UretimReceteId = ?",
                recete_id,
            )
            h = cur.fetchone()
        return recete_id, (h[0] if h else None)
    except Exception:
        return None, None


# ── İş Emri Formu ─────────────────────────────────────────────────────────────

def tum_is_emirleri_listesi(conn):
    """Tüm durumlardaki üretim emirlerini döndürür (iş emri formu için)."""
    sql = """
        SELECT
            ue.Id,
            ue.Kodu,
            ISNULL(ue.Aciklama, '') AS Aciklama,
            CONVERT(VARCHAR(10), ue.UretimEmriTarihi, 104) AS EmirTarihi,
            ue.DurumId
        FROM UretimEmri ue
        ORDER BY ue.UretimEmriTarihi DESC, ue.Kodu
    """
    try:
        with cursor_ctx(conn) as cur:
            cur.execute(sql)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        return []


def is_emri_malzeme_listesi(conn, emir_id):
    """Hat Planı üst tablosundan tüm satırları döndürür (HatTipi fark etmez) — PDF iş emri formu için."""
    sql = """
        SELECT
            sk.Kodu           AS Kodu,
            sk.Adi            AS Adi,
            uehp.TalepMiktari AS Miktar
        FROM UretimEmriHatPlani uehp
        JOIN StokKarti sk ON sk.Id = uehp.KartId
        WHERE uehp.UretimEmriId = ?
        ORDER BY uehp.sira
    """
    try:
        with cursor_ctx(conn) as cur:
            cur.execute(sql, emir_id)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        return []
