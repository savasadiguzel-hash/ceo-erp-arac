"""
Tüm veri erişimi bu modülden yapılır.
USE_DEMO=True  → demo_data sabitlerini döner
USE_DEMO=False → gerçek SQL sorgularını çalıştırır (TODO: tablo adları netleşince doldurulacak)
"""
from config import USE_DEMO
from db.demo_data import (
    DEMO_MAMUL_AGACLARI, DEMO_STOKLAR,
    DEMO_TARAMA_ADIMLARI, DEMO_BOM, DEMO_FIYATLAR,
)


# ── Araç 1: Mamül Ağacı Bağlantı ──────────────────────────────────────────────

def mamul_agaci_listesi(conn) -> list[tuple[str, str]]:
    """[(kod, ad), ...] döner."""
    if USE_DEMO:
        return DEMO_MAMUL_AGACLARI
    # TODO: CEO ERP tablo adı netleşince doldurulacak
    # cur = conn.cursor()
    # cur.execute("SELECT StokKodu, StokAdi FROM tbl_Mamul WHERE ... ORDER BY StokKodu")
    # return [(r.StokKodu, r.StokAdi) for r in cur.fetchall()]
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
    # TODO: iki adımlı sorgu
    # 1) Reçetede/mamül ağacında olmayan stok kodları
    # 2) Bu kodlardan bas_tarih–bit_tarih aralığında fatura olanlar
    raise NotImplementedError("Gerçek sorgu henüz yazılmadı.")


def stoku_mamule_bagla(conn, stok_kodu: str, mamul_kodu: str) -> None:
    """Stoku mamül ağacına bağlar (DB güncelleme)."""
    if USE_DEMO:
        return  # demo modda yazma yapılmaz
    # TODO: INSERT INTO tbl_MamulAgaci ...
    raise NotImplementedError("Gerçek sorgu henüz yazılmadı.")


# ── Araç 2: Maliyet Hesaplama ─────────────────────────────────────────────────

def bom_listesi(conn) -> dict:
    """DEMO_BOM formatında dict döner: {mamul_kodu: {ad, birim, bilesenleri: [...]}}"""
    if USE_DEMO:
        return DEMO_BOM
    # TODO: reçete + mamül ağacı tabloları
    raise NotImplementedError("Gerçek sorgu henüz yazılmadı.")


def stok_fiyat_gecmisi(conn, stok_kodu: str, bas: str, bit: str) -> list[dict]:
    """
    Verilen tarih aralığında stok için fatura fiyat geçmişi.
    Her eleman: tarih (YYYY-MM-DD), birim_fiyat, miktar
    """
    if USE_DEMO:
        return DEMO_FIYATLAR.get(stok_kodu, [])
    # TODO: fatura satırları tablosu
    raise NotImplementedError("Gerçek sorgu henüz yazılmadı.")


def tarama_istatistikleri(conn) -> list[tuple[str, int]]:
    """Tarama animasyonu için (adım_mesajı, kayıt_sayısı) listesi."""
    if USE_DEMO:
        return DEMO_TARAMA_ADIMLARI
    raise NotImplementedError("Gerçek sorgu henüz yazılmadı.")
