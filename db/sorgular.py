"""
Tüm veri erişimi bu modülden yapılır.
USE_DEMO=True  → demo_data sabitlerini döner
USE_DEMO=False → gerçek SQL sorgularını çalıştırır (TODO: tablo adları netleşince doldurulacak)

Kural: her sorgu cursor_ctx(conn) ile açılır; finally bloğu cursor'ı kesinlikle kapatır.
"""
from config import USE_DEMO
from db.baglanti import cursor_ctx
from db.demo_data import (
    DEMO_MAMUL_AGACLARI, DEMO_STOKLAR,
    DEMO_TARAMA_ADIMLARI, DEMO_BOM, DEMO_FIYATLAR,
)


# ── Araç 1: Mamül Ağacı Bağlantı ──────────────────────────────────────────────

def mamul_agaci_listesi(conn) -> list[tuple[str, str]]:
    """[(kod, ad), ...] döner."""
    if USE_DEMO:
        return DEMO_MAMUL_AGACLARI
    with cursor_ctx(conn) as cur:
        # TODO: CEO ERP tablo adı netleşince doldurun
        # cur.execute("SELECT StokKodu, StokAdi FROM tbl_Mamul ORDER BY StokKodu")
        # return [(r[0], r[1]) for r in cur.fetchall()]
        raise NotImplementedError("Gerçek sorgu henüz yazılmadı.")


def recetesiz_faturali_stoklar(conn, fatura_turleri: list[str],
                               bas_tarih: str, bit_tarih: str) -> list[dict]:
    """
    Kesişim kümesi: reçete/mamül ağacında olmayan VE belirtilen tarih aralığında
    faturası olan stoklar. bas_tarih / bit_tarih: 'DD.MM.YYYY' formatı.
    Her eleman: stok_kodu, stok_adi, fatura_sayisi, toplam_tutar,
                ilk_fatura, son_fatura, tedarikci, fatura_turleri
    """
    if USE_DEMO:
        return DEMO_STOKLAR
    with cursor_ctx(conn) as cur:
        # TODO: iki adımlı sorgu
        # 1) Reçetede/mamül ağacında olmayan stok kodları
        # 2) Bu kodlardan bas_tarih–bit_tarih aralığında seçili türde fatura olanlar
        # tur_filtre = ", ".join(f"'{t}'" for t in fatura_turleri)
        # cur.execute(f"""
        #     SELECT s.StokKodu, s.StokAdi, ...
        #     FROM   tbl_Stok s
        #     JOIN   tbl_Fatura f ON f.StokKodu = s.StokKodu
        #     WHERE  s.StokKodu NOT IN (SELECT StokKodu FROM tbl_Recete)
        #       AND  f.FaturaTuru IN ({tur_filtre})
        #       AND  f.Tarih BETWEEN ? AND ?
        # """, bas_tarih, bit_tarih)
        # return [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
        raise NotImplementedError("Gerçek sorgu henüz yazılmadı.")


def stoku_mamule_bagla(conn, stok_kodu: str, mamul_kodu: str) -> None:
    """Stoku mamül ağacına bağlar (DB güncelleme)."""
    if USE_DEMO:
        return
    with cursor_ctx(conn) as cur:
        # TODO: tablo adı ve kolon yapısı netleşince doldurun
        # cur.execute(
        #     "INSERT INTO tbl_MamulAgaci (StokKodu, MamulKodu) VALUES (?, ?)",
        #     stok_kodu, mamul_kodu,
        # )
        # conn.commit()
        raise NotImplementedError("Gerçek sorgu henüz yazılmadı.")


# ── Araç 2: Maliyet Hesaplama ─────────────────────────────────────────────────

def bom_listesi(conn) -> dict:
    """DEMO_BOM formatında dict döner: {mamul_kodu: {ad, birim, bilesenleri: [...]}}"""
    if USE_DEMO:
        return DEMO_BOM
    with cursor_ctx(conn) as cur:
        # TODO: reçete + mamül ağacı tabloları
        # cur.execute("SELECT MamulKodu, MamulAdi, BilesenkKodu, ... FROM tbl_Recete ...")
        # bom = {}
        # for r in cur.fetchall():
        #     ...
        # return bom
        raise NotImplementedError("Gerçek sorgu henüz yazılmadı.")


def stok_fiyat_gecmisi(conn, stok_kodu: str, bas: str, bit: str) -> list[dict]:
    """
    Verilen tarih aralığında stok için fatura fiyat geçmişi.
    Her eleman: tarih (YYYY-MM-DD), birim_fiyat, miktar
    """
    if USE_DEMO:
        return DEMO_FIYATLAR.get(stok_kodu, [])
    with cursor_ctx(conn) as cur:
        # TODO: fatura satırları tablosu
        # cur.execute("""
        #     SELECT FORMAT(f.Tarih, 'yyyy-MM-dd'), fs.BirimFiyat, fs.Miktar
        #     FROM   tbl_FaturaSatir fs
        #     JOIN   tbl_Fatura f ON f.FaturaNo = fs.FaturaNo
        #     WHERE  fs.StokKodu = ? AND f.Tarih BETWEEN ? AND ?
        #     ORDER  BY f.Tarih
        # """, stok_kodu, bas, bit)
        # return [{"tarih": r[0], "birim_fiyat": r[1], "miktar": r[2]} for r in cur.fetchall()]
        raise NotImplementedError("Gerçek sorgu henüz yazılmadı.")


def tarama_istatistikleri(conn) -> list[tuple[str, int]]:
    """Tarama animasyonu için (adım_mesajı, kayıt_sayısı) listesi."""
    if USE_DEMO:
        return DEMO_TARAMA_ADIMLARI
    with cursor_ctx(conn) as cur:
        # TODO: COUNT sorguları ile gerçek kayıt sayıları
        # cur.execute("SELECT COUNT(*) FROM tbl_Stok")
        # toplam_stok = cur.fetchone()[0]
        # ...
        raise NotImplementedError("Gerçek sorgu henüz yazılmadı.")
