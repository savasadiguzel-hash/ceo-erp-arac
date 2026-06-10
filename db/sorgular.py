"""
Tüm veri erişimi bu modülden yapılır. SQL Server ile çalışır.
Kural: her sorgu cursor_ctx(conn) ile açılır; finally bloğu cursor'ı kesinlikle kapatır.
"""
import logging
from db.baglanti import cursor_ctx


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
    return adimlar


def mamul_agaci_listesi(conn) -> list[tuple[str, str]]:
    """[(kod, ad), ...] döner. Aktif reçete/mamülleri listeler."""
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT DISTINCT sk.Kodu, sk.Adi
            FROM StokKarti sk
            INNER JOIN UretimReceteHatPlani urhp ON urhp.KartId = sk.Id
            WHERE sk.Aktif = 1
            ORDER BY sk.Kodu
        """)
        return [(r[0], r[1]) for r in cur.fetchall()]


def recetesiz_stok_hareketleri(conn, bas_tarih: str, bit_tarih: str) -> list[dict]:
    """
    Kesişim kümesindeki stokların alış faturası/irsaliyesi satırlarını döner.
    bas_tarih / bit_tarih: 'DD.MM.YYYY' formatı.
    Her eleman: stok_kodu, stok_adi, hareket_id, islem_turu, belge_no,
                tarih (DD.MM.YYYY), tarih_iso (YYYY-MM-DD),
                miktar, birim_fiyat, tutar, tedarikci
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
              AND sh.IslemKodu IN (1, 5)
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
                'stok_adi':    row[1],
                'hareket_id':  int(row[2]),
                'islem_turu':  row[3],
                'belge_no':    row[4],
                'tarih':       row[5],
                'tarih_iso':   row[6],
                'miktar':      float(row[7]),
                'birim_fiyat': float(row[8]),
                'tutar':       float(row[9]),
                'tedarikci':   row[10],
            }
            for row in cur.fetchall()
        ]


def recetesiz_faturali_ozet(hareketler: list[dict], yontem: str) -> list[dict]:
    """
    Ham hareket listesini stok bazında özetler.
    yontem: 'FIFO' → ilk alış fiyatı, 'LIFO' → son alış fiyatı,
            'WA'   → ağırlıklı ortalama (toplam tutar / toplam miktar)
    """
    from collections import defaultdict
    gruplar: dict[str, list] = defaultdict(list)
    for h in hareketler:
        gruplar[h['stok_kodu']].append(h)

    ozet = []
    for stok_kodu in sorted(gruplar):
        grup = gruplar[stok_kodu]
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
            'stok_adi':    grup[0]['stok_adi'],
            'fatura_sayisi': len(set(h['hareket_id'] for h in grup)),
            'birim_fiyat': round(birim_fiyat, 4),
            'ilk_fatura':  sirali[0]['tarih'],
            'son_fatura':  sirali[-1]['tarih'],
            'tedarikci':   ref['tedarikci'],
        })
    return ozet


def stoku_mamule_bagla(conn, stok_kodu: str, mamul_kodu: str) -> None:
    """Stoku reçete bileşenlerine ekler (DB güncelleme)."""
    with cursor_ctx(conn) as cur:
        # Stok ve mamülün ID'sini bul
        cur.execute("SELECT Id FROM StokKarti WHERE Kodu = ?", stok_kodu)
        stok_id_result = cur.fetchone()
        if not stok_id_result:
            raise ValueError(f"Stok bulunamadı: {stok_kodu}")
        stok_id = stok_id_result[0]

        cur.execute("SELECT Id FROM StokKarti WHERE Kodu = ?", mamul_kodu)
        mamul_id_result = cur.fetchone()
        if not mamul_id_result:
            raise ValueError(f"Mamül bulunamadı: {mamul_kodu}")
        mamul_id = mamul_id_result[0]

        # Mamüle karşılık gelen reçeteyi bul (StokKarti.Id -> UretimReceteHatPlani.KartId)
        cur.execute(
            "SELECT DISTINCT ur.Id FROM UretimRecete ur "
            "JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id "
            "WHERE urhp.KartId = ?",
            mamul_id
        )
        recete_result = cur.fetchone()
        if not recete_result:
            raise ValueError(f"Mamüle karşılık reçete bulunamadı: {mamul_kodu}")
        recete_id = recete_result[0]

        # Stoku reçete bileşenlerine ekle (UretimReceteHatPlani tablosuna)
        # Tabloda KartId (bileşen stok), Miktar ve BirimId gerekli
        cur.execute("""
            INSERT INTO UretimReceteHatPlani
            (UretimReceteId, Tipi, KartId, Miktar, BirimId, DepoId, Aciklama)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            recete_id,  # UretimReceteId
            1,          # Tipi = 1 (Stok bileşeni)
            stok_id,    # KartId = Stok ID'si
            1.0,        # Miktar = 1 (varsayılan)
            None,       # BirimId (NULL - sistem birimi kullanacak)
            None,       # DepoId (NULL - herhangi depo)
            f"Sistem tarafından {stok_kodu} eklendi"  # Aciklama
        )
        conn.commit()
        logging.info(f"Stok {stok_kodu} mamül {mamul_kodu} ({recete_id}) bileşenlerine eklendi.")


# ── Araç 2: Maliyet Hesaplama ─────────────────────────────────────────────────

def bom_listesi(conn) -> dict:
    """dict döner: {mamul_kodu: {ad, birim, bilesenleri: [...]}}

    Gerçek bileşenler UretimReceteHatPlaniGirdi tablosunda saklanır.
    UretimReceteHatPlani üst satırdır; Girdi alt tablosu hammadde/parça girdilerini içerir.
    """
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT DISTINCT
                ur.Kodu  AS MamulKodu,
                ur.Tanim AS MamulAdi,
                sk.Kodu  AS BilesenKodu,
                sk.Adi   AS BilesenAdi,
                urhpg.Miktar
            FROM UretimRecete ur
            INNER JOIN UretimReceteHatPlani urhp
                    ON urhp.UretimReceteId = ur.Id
            INNER JOIN UretimReceteHatPlaniGirdi urhpg
                    ON urhpg.UretimReceteHatPlaniId = urhp.Id
            INNER JOIN StokKarti sk
                    ON sk.Id = urhpg.KartId
            WHERE urhpg.KartId IS NOT NULL
              AND sk.Aktif = 1
            ORDER BY ur.Kodu, sk.Kodu
        """)

        # Sonuçları organize et; gerçek reçetesi olan mamülleri işaretle
        bom = {}
        gercek_receteli = set()   # UretimReceteHatPlaniGirdi'den gelen mamüller
        for mamul_kodu, mamul_adi, bilesen_kodu, bilesen_adi, miktar in cur.fetchall():
            if mamul_kodu not in bom:
                bom[mamul_kodu] = {"ad": mamul_adi, "birim": "ADET", "bilesenleri": []}
            if not any(b["kod"] == bilesen_kodu for b in bom[mamul_kodu]["bilesenleri"]):
                bom[mamul_kodu]["bilesenleri"].append({
                    "kod":    bilesen_kodu,
                    "ad":     bilesen_adi,
                    "miktar": float(miktar) if miktar is not None else 1.0,
                    "birim":  "ADET",
                })
            gercek_receteli.add(mamul_kodu)

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
                bom[p_kod] = {"ad": p_adi, "birim": "ADET", "bilesenleri": []}
            if not any(b["kod"] == c_kod for b in bom[p_kod]["bilesenleri"]):
                bom[p_kod]["bilesenleri"].append({
                    "kod":    c_kod,
                    "ad":     c_adi,
                    "miktar": 1.0,
                    "birim":  "ADET",
                })

    return bom


def stok_fiyat_gecmisi(conn, stok_kodu: str, bas: str, bit: str) -> list[dict]:
    """
    Verilen tarih aralığında stok için fatura fiyat geçmişi.
    Her eleman: tarih (YYYY-MM-DD), birim_fiyat, miktar, birim
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
              AND sh.IslemKodu IN (1, 5)
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


def stok_fiyatlari_toplu(
    conn, stok_kodlari: list, bas: str, bit: str
) -> dict:
    """
    Birden fazla stok kodu için fiyat geçmişini TEK sorguda çeker.
    Döner: {stok_kodu: [{"tarih", "birim_fiyat", "miktar", "birim"}, ...]}
    IslemKodu 1=Alış Faturası, 5=Alış İrsaliyesi.
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
                  AND sh.IslemKodu IN (1, 5)
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
    Belirli bir üretim emrinin hat planındaki malzemeleri için
    ÜRETİM EMRİ TARİHİNDEKİ bakiyeyi hesaplayıp yetersiz olanları döner.

    Bakiye formülü (CEO ERP ile eşleşen):
      GirenMiktar : IslemKodu IN (1, 20) AND Aktif=1
      CikanMiktar : IslemKodu IN (2, 6, 17, 18, 19, 21) AND Aktif=1
      Tarih filtresi: BelgeTarihi <= UretimEmriTarihi

    Her eleman: malzeme_kodu, malzeme_adi, ihtiyac, bakiye_emir_tarihi, eksik
    """
    with cursor_ctx(conn) as cur:
        cur.execute("""
            WITH EmirBilgi AS (
                SELECT CAST(UretimEmriTarihi AS DATE) AS EmirTarihi
                FROM UretimEmri WHERE Id = ?
            ),
            ToplamTalep AS (
                -- Aynı malzeme birden fazla hat planı satırında olabilir; toplam alınır
                SELECT uehpg.KartId, SUM(uehpg.TalepMiktar) AS ToplamTalep
                FROM UretimEmriHatPlani      uehp
                JOIN UretimEmriHatPlaniGirdi uehpg ON uehpg.UretimEmriHatPlaniId = uehp.Id
                WHERE uehp.UretimEmriId = ?
                  AND uehpg.KartId IS NOT NULL
                  AND uehpg.TalepMiktar > 0
                GROUP BY uehpg.KartId
            ),
            BakiyeEmirTarih AS (
                SELECT
                    shd.IslemKartId,
                    SUM(CASE
                        WHEN sh.IslemKodu IN (1, 20)             THEN  shd.Miktar
                        WHEN sh.IslemKodu IN (2, 6, 17, 18, 19, 21) THEN -shd.Miktar
                        ELSE 0
                    END) AS Bakiye
                FROM StokHareketDetay shd
                JOIN StokHareket sh ON sh.Id = shd.HareketId
                WHERE shd.IslemKartId IN (SELECT KartId FROM ToplamTalep)
                  AND sh.Aktif = 1
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


# ── Araç 5: Satış Faturaları ──────────────────────────────────────────────────

def satis_faturalari(conn, bas_tarih: str, bit_tarih: str) -> list[dict]:
    """
    Belirtilen tarih aralığındaki satış fatura ve irsaliye satırlarını döner.
    bas_tarih / bit_tarih: 'DD.MM.YYYY' formatı.
    IslemKodu 2 = Satış Faturası, 6 = Satış İrsaliyesi.
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
            WHERE sh.IslemKodu IN (2, 6)
              AND shd.Turu = 1
              AND shd.BirimFiyat > 0
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
