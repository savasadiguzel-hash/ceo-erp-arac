"""
Tüm veri erişimi bu modülden yapılır. SQL Server ile çalışır.
Kural: her sorgu cursor_ctx(conn) ile açılır; finally bloğu cursor'ı kesinlikle kapatır.
"""
import logging
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
    StokBirim tablosu yoksa 'ADET' fallback kullanılır.
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
    # GUID → birim adı çözümlemesi (StokBirim tablosu yoksa fallback ADET)
    birimler = birimleri_getir(conn)          # {Adi: guid_str}
    guid_to_adi = {v: k for k, v in birimler.items()}
    return {
        kod: (guid_to_adi.get(guid, 'ADET') if guid else 'ADET')
        for kod, guid in guid_map.items()
    }


def stok_guncel_bakiyeleri(conn, stok_kodlari: list) -> dict:
    """
    Verilen stok kodları için bugünkü tarih itibarıyla güncel stok bakiyesi.
    Döner: {stok_kodu: bakiye_float}
    """
    from datetime import date
    if not stok_kodlari:
        return {}
    bugun = date.today().strftime('%Y-%m-%d')
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
    """StokBirim → {Adi: Id_str}; hata olursa ADET fallback."""
    try:
        with cursor_ctx(conn) as cur:
            cur.execute("SELECT Id, Adi FROM StokBirim WHERE Aktif = 1 ORDER BY Adi")
            return {r[1]: str(r[0]) for r in cur.fetchall()}
    except Exception:
        return {"ADET": "4acc21e3-3140-4863-922d-a0b3d35de8c1"}


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
