"""
Tüm veri erişimi bu modülden yapılır. SQL Server ile çalışır.
Kural: her sorgu cursor_ctx(conn) ile açılır; finally bloğu cursor'ı kesinlikle kapatır.
"""
import logging
from db.baglanti import cursor_ctx


# ── Araç 1: Mamül Ağacı Bağlantı ──────────────────────────────────────────────

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


def recetesiz_faturali_stoklar(conn, fatura_turleri: list[str],
                               bas_tarih: str, bit_tarih: str) -> list[dict]:
    """
    Kesişim kümesi: reçete/mamül ağacında olmayan VE belirtilen tarih aralığında
    faturası olan stoklar. bas_tarih / bit_tarih: 'DD.MM.YYYY' formatı.
    Her eleman: stok_kodu, stok_adi, fatura_sayisi, toplam_tutar,
                ilk_fatura, son_fatura, tedarikci, fatura_turleri
    """
    with cursor_ctx(conn) as cur:
        # İki filtreli kesişim:
        # 1) Reçete bileşeninde olmayan stoklar
        # 2) Ürün ağacında olmayan stoklar
        # 3) Bu stoklar arasında belirtilen tarih aralığında fatura görmüş olanlar

        # Tarihi DD.MM.YYYY -> YYYY-MM-DD formatına çevir
        bas_parts = bas_tarih.split('.')
        bit_parts = bit_tarih.split('.')
        bas_sql = f"{bas_parts[2]}-{bas_parts[1]}-{bas_parts[0]}"
        bit_sql = f"{bit_parts[2]}-{bit_parts[1]}-{bit_parts[0]}"

        # SQL'de BETWEEN kullanalım, CAST ile dönüştürelim
        cur.execute(f"""
            SELECT
                sk.Kodu as stok_kodu,
                sk.Adi as stok_adi,
                COUNT(DISTINCT sh.Id) as fatura_sayisi,
                SUM(ISNULL(shd.Tutar, 0)) as toplam_tutar,
                CONVERT(VARCHAR(10), MIN(sh.BelgeTarihi), 104) as ilk_fatura,
                CONVERT(VARCHAR(10), MAX(sh.BelgeTarihi), 104) as son_fatura,
                ISNULL(cmk.Unvani, '') as tedarikci,
                'Alış, Masraf, Hizmet, İthalat' as fatura_turleri
            FROM StokKarti sk
            JOIN StokHareketDetay shd ON shd.IslemKartId IS NULL OR shd.IslemKartId NOT IN (
                SELECT DISTINCT Id FROM UretimRecete
            )
            JOIN StokHareket sh ON sh.Id = shd.HareketId
            LEFT JOIN CariMusteriKarti cmk ON sh.MusteriKartId = cmk.Id
            WHERE sk.Id NOT IN (
                -- Reçete bileşenleri hariç tut
                SELECT DISTINCT KartId FROM UretimReceteHatPlani WHERE KartId IS NOT NULL
            )
              AND sk.Id NOT IN (
                -- Ürün ağacı bileşenleri hariç tut (varsa)
                SELECT DISTINCT KartId FROM UrunAgaciDetay WHERE KartId IS NOT NULL
              )
              AND sk.Aktif = 1
              AND CAST(sh.BelgeTarihi AS DATE) >= CAST('{bas_sql}' AS DATE)
              AND CAST(sh.BelgeTarihi AS DATE) <= CAST('{bit_sql}' AS DATE)
            GROUP BY sk.Id, sk.Kodu, sk.Adi, cmk.Unvani
            ORDER BY sk.Kodu
        """)

        results = []
        for row in cur.fetchall():
            results.append({
                'stok_kodu': row[0],
                'stok_adi': row[1],
                'fatura_sayisi': int(row[2]),
                'toplam_tutar': f"{row[3]:,.2f} ₺".replace(',', '.'),
                'ilk_fatura': row[4],
                'son_fatura': row[5],
                'tedarikci': row[6],
                'fatura_turleri': row[7],
            })
        return results


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
    Tarihi DD.MM.YYYY formatında geçirse de, dönen veriler YYYY-MM-DD'dir.
    """
    with cursor_ctx(conn) as cur:
        # Tarihi DD.MM.YYYY -> YYYY-MM-DD formatına çevir
        bas_parts = bas.split('.')
        bit_parts = bit.split('.')
        bas_sql = f"{bas_parts[2]}-{bas_parts[1]}-{bas_parts[0]}"
        bit_sql = f"{bit_parts[2]}-{bit_parts[1]}-{bit_parts[0]}"

        # Tüm mamül reçetelerinin bileşen stok kodlarını ara
        cur.execute("""
            SELECT DISTINCT KartId
            FROM UretimReceteHatPlani
            WHERE Tipi = 1
        """)
        bilesen_ids = [r[0] for r in cur.fetchall()]

        # Yalnızca stok bileşeni olmayan (reçete ağacında yer almayan) hareketleri al
        # Veya tüm hareketleri almaya çalış
        cur.execute(f"""
            SELECT
                CONVERT(VARCHAR(10), sh.BelgeTarihi, 120) as Tarih,
                shd.BirimFiyat as BirimFiyat,
                shd.Miktar as Miktar,
                'ADET' as BirimAciklama
            FROM StokHareketDetay shd
            JOIN StokHareket sh ON sh.Id = shd.HareketId
            JOIN StokKarti sk ON sk.Id = shd.IslemKartId
            WHERE sk.Kodu = ?
              AND CAST(sh.BelgeTarihi AS DATE) >= CAST('{bas_sql}' AS DATE)
              AND CAST(sh.BelgeTarihi AS DATE) <= CAST('{bit_sql}' AS DATE)
              AND shd.BirimFiyat > 0
              AND shd.Miktar > 0
            ORDER BY sh.BelgeTarihi ASC
        """, stok_kodu)

        results = []
        for tarih, birim_fiyat, miktar, birim_aciklama in cur.fetchall():
            results.append({
                "tarih": tarih,
                "birim_fiyat": float(birim_fiyat) if birim_fiyat else 0.0,
                "miktar": float(miktar) if miktar else 0.0,
                "birim": birim_aciklama
            })

        return results


