"""Excel raporu üretme iş mantığı. UI'dan bağımsızdır."""
from datetime import datetime
from math import isfinite
from pathlib import Path
import openpyxl
from openpyxl.styles import PatternFill, Font as XFont, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from logic.maliyet import (
    mamul_maliyet_hesapla, proje_fiili_maliyet, proje_fark_raporu,
)
from db.sorgular import (
    bom_listesi, stok_fiyatlari_toplu, stok_guncel_bakiyeleri,
    bom_operasyon_kodlarini_tamamla, proje_satinalma_hareketleri,
)

# ── Stil sabitleri ────────────────────────────────────────────────────────────

_KENAR = Border(
    left=Side(style="thin", color="DDDDDD"), right=Side(style="thin", color="DDDDDD"),
    top=Side(style="thin", color="DDDDDD"),  bottom=Side(style="thin", color="DDDDDD"),
)
_ORTA = Alignment(horizontal="center", vertical="center", wrap_text=True)
_SOL  = Alignment(horizontal="left",   vertical="center", wrap_text=True)
_SAG  = Alignment(horizontal="right",  vertical="center")

_FILL = {
    "bilgi":    PatternFill("solid", fgColor="E8EAF6"),
    "baslik":   PatternFill("solid", fgColor="1A237E"),
    "mamul":    PatternFill("solid", fgColor="3F51B5"),
    "bileseni": PatternFill("solid", fgColor="F5F5F5"),
    "iscilik":  PatternFill("solid", fgColor="FFF3E0"),
    "toplam":   PatternFill("solid", fgColor="E8F5E9"),
    "baglandi": PatternFill("solid", fgColor="E8F5E9"),
    "atlandi":  PatternFill("solid", fgColor="FFF8E1"),
    "fark_yok": PatternFill("solid", fgColor="FFCDD2"),   # sadece bir tarafta var
    "fark_var": PatternFill("solid", fgColor="FFF3E0"),   # miktar farkı
    "fark_ok":  PatternFill("solid", fgColor="E8F5E9"),   # eşleşiyor
}
_FONT = {
    "baslik":   XFont(bold=True, color="FFFFFF", name="Segoe UI", size=11),
    "mamul":    XFont(bold=True, color="FFFFFF", name="Segoe UI", size=11),
    "bileseni": XFont(name="Segoe UI", size=10),
    "iscilik":  XFont(italic=True, name="Segoe UI", size=10, color="E65100"),
    "toplam":   XFont(bold=True, name="Segoe UI", size=11, color="1B5E20"),
    "bilgi":    XFont(name="Segoe UI", size=10, color="555555"),
    "veri":     XFont(name="Segoe UI", size=10),
    "fark_yok": XFont(name="Segoe UI", size=10, color="B71C1C"),
    "fark_var": XFont(name="Segoe UI", size=10, color="E65100"),
    "fark_ok":  XFont(name="Segoe UI", size=10, color="1B5E20"),
}

# ── Sayı format sabitleri ─────────────────────────────────────────────────────
# Excel'in "Metin olarak saklanan sayı" uyarısını önlemek için tüm sayısal
# hücreler cast edilip bu formatlarla yazılır.

_FMT_PARA   = '#,##0.00 "₺"'   # para birimi (2 ondalık)
_FMT_BIRIM  = '#,##0.0000 "₺"' # birim maliyet (4 ondalık)
_FMT_MIKTAR = '#,##0.##'        # BOM miktarı (isteğe bağlı ondalık)
_FMT_ADET   = '#,##0'           # tam sayı (fatura sayısı vb.)

# ── Sütun tanımları ───────────────────────────────────────────────────────────

_MALIYET_SUTUNLAR = [
    ("Tip", 10), ("Mamül Kodu", 14), ("Mamül Adı", 28),
    ("Bileşen Kodu", 14), ("Bileşen Adı", 30), ("BOM Miktarı", 13),
    ("Birim", 10), ("Birim Maliyet ₺", 18), ("Satır Maliyeti ₺", 18),
    ("Hammadde Toplamı ₺", 20), ("İşçilik ₺", 16), ("Genel Toplam ₺", 20),
    ("Stok Miktarı", 14),
]

# (alan_adı, sayısal?, number_format)
_BAGLAMA_ALAN = [
    ("kart_tipi",     False, None),
    ("stok_kodu",     False, None),
    ("stok_adi",      False, None),
    ("birim",         False, None),
    ("guncel_miktar",  True, _FMT_MIKTAR),
    ("fatura_sayisi",  True, _FMT_ADET),
    ("birim_fiyat",    True, _FMT_BIRIM),
    ("ilk_fatura",    False, None),
    ("son_fatura",    False, None),
    ("tedarikci",     False, None),
    ("mamul_kodu",    False, None),
    ("mamul_adi",     False, None),
    ("islem",         False, None),
    ("hat_kodu",      False, None),
    ("hat_plani_id",   True, _FMT_ADET),
    ("recete_miktari", True, _FMT_MIKTAR),
]

_BAGLAMA_GENISLIK = [12, 14, 32, 10, 16, 14, 20, 14, 14, 30, 14, 30, 13, 18, 15, 18]

# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def _hucre(ws, row, col, val, fill_key, font_key, alignment=_ORTA, fmt=None):
    """Hücreyi yazar; val=None ise boş bırakır (metin-sayı uyarısı olmaz)."""
    h = ws.cell(row=row, column=col, value=val)
    h.fill      = _FILL[fill_key]
    h.font      = _FONT[font_key]
    h.alignment = alignment
    h.border    = _KENAR
    if fmt:
        h.number_format = fmt
    return h


def _para(v) -> float | None:
    """
    Herhangi bir para birimi değerini float'a dönüştürür.
    Türkçe formatlı string ("37.500,00 ₺") ve sayısal tip desteklenir.
    Dönüştürülemeyen değer için None döner (boş hücre).
    """
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        # "37.500,00 ₺" → "37500.00"
        temiz = v.replace("₺", "").replace("\xa0", "").strip()
        temiz = temiz.replace(".", "").replace(",", ".")
        try:
            return float(temiz)
        except ValueError:
            return None
    return None


def _adet(v) -> int | None:
    """Tam sayıya dönüştürür; dönüştürülemeyen için None."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _miktar(v) -> float | None:
    """BOM miktarı — int veya float, None'a düşmez."""
    if isinstance(v, bool) or v is None:
        return None
    return float(v)


# ── Maliyet Raporu ────────────────────────────────────────────────────────────

def _mamul_blogu_yaz(ws, satir: int, mamul_kodu: str, mamul: dict,
                      bilesenleri: list[dict], hammadde_top: float,
                      iscilik: float, bakiyeler: dict) -> int:
    """Tek mamül için başlık + bileşen + işçilik + toplam satırlarını yazar.
    Bir sonraki boş satır numarasını döner."""
    genel_top = hammadde_top + iscilik

    ws.row_dimensions[satir].height = 22
    _m = "mamul"
    for col, (val, aln, fmt) in enumerate([
        ("MAMÜL",       _ORTA, None),
        (mamul_kodu,    _ORTA, None),
        (mamul["ad"],   _SOL,  None),
        (None, _ORTA, None), (None, _ORTA, None), (None, _ORTA, None),
        (None, _ORTA, None), (None, _ORTA, None), (None, _ORTA, None),
        (round(hammadde_top, 2), _SAG, _FMT_PARA),
        (round(iscilik,      2), _SAG, _FMT_PARA),
        (round(genel_top,    2), _SAG, _FMT_PARA),
        (_miktar(bakiyeler.get(mamul_kodu, 0.0)), _SAG, _FMT_MIKTAR),
    ], 1):
        _hucre(ws, satir, col, val, _m, _m, aln, fmt)
    satir += 1

    for b in bilesenleri:
        ws.row_dimensions[satir].height = 18
        bom_miktar = _miktar(b["bom_miktar"])
        birim_mal  = round(float(b["birim_mal"]),  4)
        satir_top  = round(float(b["satir_top"]),  2)
        _b = "bileseni"
        for col, (val, aln, fmt) in enumerate([
            (b["tip"],   _ORTA, None),
            (mamul_kodu, _ORTA, None),
            (mamul["ad"],_SOL,  None),
            (b["bil_kod"],_ORTA, None),
            (b["bil_ad"], _SOL,  None),
            (bom_miktar,  _SAG,  _FMT_MIKTAR),
            (b["birim"],  _ORTA, None),
            (birim_mal,   _SAG,  _FMT_BIRIM),
            (satir_top,   _SAG,  _FMT_PARA),
            (None, _ORTA, None), (None, _ORTA, None), (None, _ORTA, None),
            (_miktar(bakiyeler.get(b["bil_kod"], 0.0)) if not b["tip"].startswith("MASRAF") else None,
             _SAG, _FMT_MIKTAR),
        ], 1):
            _hucre(ws, satir, col, val, _b, _b, aln, fmt)
        satir += 1

    if iscilik > 0:
        ws.row_dimensions[satir].height = 18
        _i = "iscilik"
        for col, (val, aln, fmt) in enumerate([
            ("İŞÇİLİK",              _ORTA, None),
            (mamul_kodu,             _ORTA, None),
            (mamul["ad"],            _SOL,  None),
            ("—",                    _ORTA, None),
            ("Manuel İşçilik Tutarı",_SOL,  None),
            (None, _ORTA, None), (None, _ORTA, None), (None, _ORTA, None),
            (round(iscilik, 2),      _SAG,  _FMT_PARA),
            (None, _ORTA, None), (None, _ORTA, None), (None, _ORTA, None),
            (None, _ORTA, None),
        ], 1):
            _hucre(ws, satir, col, val, _i, _i, aln, fmt)
        satir += 1

    ws.row_dimensions[satir].height = 20
    _t = "toplam"
    for col, (val, aln, fmt) in enumerate([
        ("TOPLAM",      _ORTA, None),
        (mamul_kodu,    _ORTA, None),
        (mamul["ad"],   _SOL,  None),
        (None, _ORTA, None), (None, _ORTA, None), (None, _ORTA, None),
        (None, _ORTA, None), (None, _ORTA, None), (None, _ORTA, None),
        (round(hammadde_top, 2), _SAG, _FMT_PARA),
        (round(iscilik,      2), _SAG, _FMT_PARA),
        (round(genel_top,    2), _SAG, _FMT_PARA),
        (None, _ORTA, None),
    ], 1):
        _hucre(ws, satir, col, val, _t, _t, aln, fmt)
    satir += 1

    ws.row_dimensions[satir].height = 6
    satir += 1
    return satir


def maliyet_excel_kaydet(
    dosya: str, conn,
    secili: list[tuple[str, float]],   # [(mamul_kodu, iscilik_float), ...]
    metod: str, bas: str, bit: str, bas_g: str, bit_g: str,
    ilerleme_cb=None,   # callable(str) | None — her mamül başında çağrılır
) -> None:
    metod_ad = {"WA": "Ağırlıklı Ortalama", "FIFO": "FIFO", "LIFO": "LIFO"}[metod]
    bom = bom_listesi(conn)

    # Tüm BOM'daki yaprak bileşen kodlarını topla ve fiyat geçmişini TEK sorguda çek.
    # Bu cache'i mamul_maliyet_hesapla ile paylaşarak her bileşen için ayrı DB
    # sorgusu gönderilmesini engeller (N+1 → 1 sorgu).
    cache: dict = {}
    yaprak_kodlari = list({
        b["kod"]
        for mamul_veri in bom.values()
        for b in mamul_veri["bilesenleri"]
        if b["kod"] not in bom and b.get("tip") != "masraf"
    })
    if yaprak_kodlari:
        toplu = stok_fiyatlari_toplu(conn, yaprak_kodlari, bas, bit)
        for stok_kodu, fiyat_listesi in toplu.items():
            key = ("birim", stok_kodu, metod, bas, bit)
            if not fiyat_listesi:
                cache[key] = 0.0
            elif metod == "WA":
                top_t = sum(f["birim_fiyat"] * f["miktar"] for f in fiyat_listesi)
                top_m = sum(f["miktar"] for f in fiyat_listesi)
                cache[key] = top_t / top_m if top_m else 0.0
            elif metod == "FIFO":
                cache[key] = min(fiyat_listesi, key=lambda x: x["tarih"])["birim_fiyat"]
            elif metod == "LIFO":
                cache[key] = max(fiyat_listesi, key=lambda x: x["tarih"])["birim_fiyat"]
            else:
                cache[key] = 0.0

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Maliyet Raporu"

    # Bilgi satırı
    n_sutun = len(_MALIYET_SUTUNLAR)
    ws.merge_cells(f"A1:{get_column_letter(n_sutun)}1")
    h = ws.cell(row=1, column=1,
                value=f"CEO ERP — Maliyet Raporu  |  Yöntem: {metod_ad}  |  "
                      f"Dönem: {bas_g} – {bit_g}  |  "
                      f"Oluşturma: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    h.fill = _FILL["bilgi"]; h.font = _FONT["bilgi"]
    h.alignment = _SOL; h.border = _KENAR
    ws.row_dimensions[1].height = 24

    # Başlık satırı
    ws.row_dimensions[2].height = 28
    for col, (ad, gen) in enumerate(_MALIYET_SUTUNLAR, 1):
        _hucre(ws, 2, col, ad, "baslik", "baslik")
        ws.column_dimensions[get_column_letter(col)].width = gen

    # Stok miktarı sütunu için bakiyeleri tek sorguda topla (bitiş tarihi itibarıyla).
    # cache paylaşıldığından mamul_maliyet_hesapla aşağıda tekrar çağrıldığında
    # DB'ye gitmez (cache hit).
    kodlar: set[str] = set()
    for mamul_kodu, _ in secili:
        if mamul_kodu not in bom:
            continue
        kodlar.add(mamul_kodu)
        bilesenleri, _ = mamul_maliyet_hesapla(
            conn, mamul_kodu, metod, bas, bit, _cache=cache, bom=bom
        )
        for b in bilesenleri:
            if not b["tip"].startswith("MASRAF"):
                kodlar.add(b["bil_kod"])
    bakiyeler = stok_guncel_bakiyeleri(conn, list(kodlar), bit)

    satir = 3

    for mamul_kodu, iscilik_ham in secili:
        mamul = bom.get(mamul_kodu)
        if not mamul:
            continue
        if ilerleme_cb:
            ilerleme_cb(f"{mamul_kodu} — {mamul['ad']} hesaplanıyor...")

        bilesenleri, hammadde_top = mamul_maliyet_hesapla(
            conn, mamul_kodu, metod, bas, bit, _cache=cache, bom=bom
        )
        satir = _mamul_blogu_yaz(ws, satir, mamul_kodu, mamul, bilesenleri,
                                  hammadde_top, float(iscilik_ham), bakiyeler)

    ws.auto_filter.ref = f"A2:{get_column_letter(n_sutun)}2"
    ws.freeze_panes = "A3"
    wb.save(dosya)


# ── Excel Taslak Mamül Ağacından Maliyet Raporu ───────────────────────────────

def maliyet_excel_kaydet_excel_bom(
    dosya_cikti: str, conn, excel_bom_dosyasi: str,
    metod: str, bas: str, bit: str, bas_g: str, bit_g: str,
    iscilik: float = 0.0, ilerleme_cb=None,
) -> list[str]:
    """
    CEO ERP'ye henüz işlenmemiş, Excel'de hazırlanmış taslak bir mamül ağacını
    aynı 13 sütunlu maliyet raporu formatıyla hesaplar. BOM kaynağı
    db.sorgular.bom_listesi() yerine mamul_agaci_excel_oku'dan gelir; geri
    kalan hesap/rapor mantığı maliyet_excel_kaydet ile aynıdır.

    Döner: uyarılar listesi (miktarı tahmin edilen satırlar, mükerrer kodlar vb.)
    """
    from logic.mamul_agaci_excel_oku import excel_dosyasindan_bom_oku

    metod_ad = {"WA": "Ağırlıklı Ortalama", "FIFO": "FIFO", "LIFO": "LIFO"}[metod]
    bom, kok_kodlari, uyarilar = excel_dosyasindan_bom_oku(excel_bom_dosyasi)
    uyarilar.extend(bom_operasyon_kodlarini_tamamla(conn, bom))

    cache: dict = {}
    yaprak_kodlari = list({
        b["kod"]
        for mamul_veri in bom.values()
        for b in mamul_veri["bilesenleri"]
        if b["kod"] not in bom and b.get("tip") != "masraf"
    })
    if yaprak_kodlari:
        toplu = stok_fiyatlari_toplu(conn, yaprak_kodlari, bas, bit)
        for stok_kodu, fiyat_listesi in toplu.items():
            key = ("birim", stok_kodu, metod, bas, bit)
            if not fiyat_listesi:
                cache[key] = 0.0
            elif metod == "WA":
                top_t = sum(f["birim_fiyat"] * f["miktar"] for f in fiyat_listesi)
                top_m = sum(f["miktar"] for f in fiyat_listesi)
                cache[key] = top_t / top_m if top_m else 0.0
            elif metod == "FIFO":
                cache[key] = min(fiyat_listesi, key=lambda x: x["tarih"])["birim_fiyat"]
            elif metod == "LIFO":
                cache[key] = max(fiyat_listesi, key=lambda x: x["tarih"])["birim_fiyat"]
            else:
                cache[key] = 0.0

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Maliyet Raporu"

    n_sutun = len(_MALIYET_SUTUNLAR)
    ws.merge_cells(f"A1:{get_column_letter(n_sutun)}1")
    bilgi = (f"CEO ERP — Excel Taslak Maliyet Raporu  |  Kaynak: {Path(excel_bom_dosyasi).name}  |  "
             f"Yöntem: {metod_ad}  |  Dönem: {bas_g} – {bit_g}  |  "
             f"Oluşturma: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    if uyarilar:
        bilgi += f"  |  ⚠ {len(uyarilar)} uyarı (rapor sonunda)"
    h = ws.cell(row=1, column=1, value=bilgi)
    h.fill = _FILL["bilgi"]; h.font = _FONT["bilgi"]
    h.alignment = _SOL; h.border = _KENAR
    ws.row_dimensions[1].height = 24

    ws.row_dimensions[2].height = 28
    for col, (ad, gen) in enumerate(_MALIYET_SUTUNLAR, 1):
        _hucre(ws, 2, col, ad, "baslik", "baslik")
        ws.column_dimensions[get_column_letter(col)].width = gen

    kodlar: set[str] = set()
    for mamul_kodu in kok_kodlari:
        if mamul_kodu not in bom:
            continue
        kodlar.add(mamul_kodu)
        bilesenleri, _ = mamul_maliyet_hesapla(
            conn, mamul_kodu, metod, bas, bit, _cache=cache, bom=bom
        )
        for b in bilesenleri:
            if not b["tip"].startswith("MASRAF"):
                kodlar.add(b["bil_kod"])
    bakiyeler = stok_guncel_bakiyeleri(conn, list(kodlar), bit)

    satir = 3
    for mamul_kodu in kok_kodlari:
        mamul = bom.get(mamul_kodu)
        if not mamul:
            continue
        if ilerleme_cb:
            ilerleme_cb(f"{mamul_kodu} — {mamul['ad']} hesaplanıyor...")
        bilesenleri, hammadde_top = mamul_maliyet_hesapla(
            conn, mamul_kodu, metod, bas, bit, _cache=cache, bom=bom
        )
        satir = _mamul_blogu_yaz(ws, satir, mamul_kodu, mamul, bilesenleri,
                                  hammadde_top, float(iscilik), bakiyeler)

    if uyarilar:
        satir += 1
        ws.cell(row=satir, column=1, value="Uyarılar:").font = _FONT["iscilik"]
        satir += 1
        for u in uyarilar:
            ws.merge_cells(start_row=satir, start_column=1, end_row=satir, end_column=n_sutun)
            ws.cell(row=satir, column=1, value=f"• {u}").font = _FONT["bilgi"]
            satir += 1

    ws.auto_filter.ref = f"A2:{get_column_letter(n_sutun)}2"
    ws.freeze_panes = "A3"
    wb.save(dosya_cikti)
    return uyarilar


# ── Proje Fiili Satınalma & Fark Raporu ───────────────────────────────────────

_PROJE_FARK_SUTUNLAR = [
    ("Tip", 12), ("Kod", 16), ("Ad", 32),
    ("BOM Miktarı", 14), ("BOM Tutarı ₺", 16),
    ("Satınalma Miktarı", 16), ("Satınalma Tutarı ₺", 18),
    ("Fark Miktarı", 14), ("Fark Tutarı ₺", 16), ("Durum", 20),
]

_PROJE_SATINALMA_SUTUNLAR = [
    ("Tip", 10), ("Kod", 16), ("Ad", 32), ("Belge Türü", 16),
    ("Belge No", 14), ("Tarih", 12), ("Miktar", 12),
    ("Birim Fiyat ₺", 16), ("Tutar ₺", 16), ("Tedarikçi", 32),
]

_DURUM_STIL = {
    "Sadece Satınalmada": "fark_yok",
    "Sadece BOM'da":      "fark_yok",
    "Miktar Farkı":       "fark_var",
    "Eşleşiyor":          "fark_ok",
}


def proje_fark_excel_kaydet(
    dosya: str, conn,
    secili_mamul_kodlari: list[str],
    proje_kodu: str,
    metod: str, bas: str, bit: str, bas_g: str, bit_g: str,
    ilerleme_cb=None,   # callable(str) | None
) -> tuple[float, float]:
    """
    Seçilen, CEO ERP'ye zaten işlenmiş mamül(ler)in BOM'dan hesaplanan
    TEORİK maliyetini, verilen proje koduna fiilen kesilmiş alış faturası/
    irsaliyesi satırlarıyla (FİİLİ) karşılaştırır ve kalem bazında farkı
    raporlar. Alış iadeleri fiili toplamdan düşülmüş olarak hesaplanır.
    Taslak/Excel kaynaklı BOM için proje_fark_excel_bom_kaydet()
    kullanılır — workbook yazımı _proje_fark_workbook_yaz() ile ortaktır.

    Not: Her mamül 1 birim üretim varsayılır — uygulamanın geri kalanındaki
    BOM hesaplama mantığıyla (maliyet_excel_kaydet) tutarlıdır. Birden fazla
    üretim adedi söz konusuysa teorik tarafı buna göre yorumlayın.

    Excel çıktısı 3 sayfa:
      - Özet             : proje kodu, dönem, teorik/fiili toplam ve fark
      - Fark Detayı       : proje_fark_raporu() sonucu, kod bazında
      - Satınalma Detayı  : proje_satinalma_hareketleri() ham satırları

    Döner: (teorik_toplam, fiili_toplam)
    """
    metod_ad = {"WA": "Ağırlıklı Ortalama", "FIFO": "FIFO", "LIFO": "LIFO"}[metod]
    bom = bom_listesi(conn)

    cache: dict = {}
    bom_satirlari_toplam: list[dict] = []
    teorik_toplam = 0.0
    mamul_adlari: list[str] = []
    for mamul_kodu in secili_mamul_kodlari:
        mamul = bom.get(mamul_kodu)
        if not mamul:
            continue
        if ilerleme_cb:
            ilerleme_cb(f"{mamul_kodu} — {mamul['ad']} teorik maliyeti hesaplanıyor...")
        bilesenleri, top = mamul_maliyet_hesapla(
            conn, mamul_kodu, metod, bas, bit, _cache=cache, bom=bom
        )
        bom_satirlari_toplam.extend(bilesenleri)
        teorik_toplam += top
        mamul_adlari.append(f"{mamul_kodu} — {mamul['ad']}")

    return _proje_fark_workbook_yaz(
        dosya, conn, bom_satirlari_toplam, teorik_toplam, mamul_adlari,
        proje_kodu, metod_ad, bas, bit, bas_g, bit_g, ilerleme_cb=ilerleme_cb,
    )


def proje_fark_excel_bom_kaydet(
    dosya: str, conn,
    excel_bom_dosyasi: str,
    proje_kodu: str,
    metod: str, bas: str, bit: str, bas_g: str, bit_g: str,
    ilerleme_cb=None,   # callable(str) | None
) -> tuple[float, float, list[str]]:
    """
    CEO ERP'ye henüz işlenmemiş (reçetesi yüklenmemiş), Excel'de hazırlanmış
    taslak bir mamül ağacının TEORİK maliyetini, verilen proje koduna fiilen
    kesilmiş alış faturası/irsaliyesi satırlarıyla (FİİLİ) karşılaştırır.
    BOM kaynağı maliyet_excel_kaydet_excel_bom ile aynıdır
    (excel_dosyasindan_bom_oku + bom_operasyon_kodlarini_tamamla).

    İşçilik SORULMAZ — bu rapor sadece malzeme/masraf karşılaştırmasıdır,
    satınalma tarafının işçilik kalemi yoktur.

    Döner: (teorik_toplam, fiili_toplam, uyarilar)
    """
    from logic.mamul_agaci_excel_oku import excel_dosyasindan_bom_oku

    metod_ad = {"WA": "Ağırlıklı Ortalama", "FIFO": "FIFO", "LIFO": "LIFO"}[metod]
    bom, kok_kodlari, uyarilar = excel_dosyasindan_bom_oku(excel_bom_dosyasi)
    uyarilar.extend(bom_operasyon_kodlarini_tamamla(conn, bom))

    cache: dict = {}
    bom_satirlari_toplam: list[dict] = []
    teorik_toplam = 0.0
    mamul_adlari: list[str] = []
    for mamul_kodu in kok_kodlari:
        mamul = bom.get(mamul_kodu)
        if not mamul:
            continue
        if ilerleme_cb:
            ilerleme_cb(f"{mamul_kodu} — {mamul['ad']} teorik maliyeti hesaplanıyor...")
        bilesenleri, top = mamul_maliyet_hesapla(
            conn, mamul_kodu, metod, bas, bit, _cache=cache, bom=bom
        )
        bom_satirlari_toplam.extend(bilesenleri)
        teorik_toplam += top
        mamul_adlari.append(f"{mamul_kodu} — {mamul['ad']}")

    teorik_toplam_sonuc, fiili_toplam = _proje_fark_workbook_yaz(
        dosya, conn, bom_satirlari_toplam, teorik_toplam, mamul_adlari,
        proje_kodu, metod_ad, bas, bit, bas_g, bit_g,
        uyarilar=uyarilar, ilerleme_cb=ilerleme_cb,
    )
    return teorik_toplam_sonuc, fiili_toplam, uyarilar


def _proje_fark_workbook_yaz(
    dosya: str, conn,
    bom_satirlari_toplam: list[dict], teorik_toplam: float, mamul_adlari: list[str],
    proje_kodu: str, metod_ad: str, bas: str, bit: str, bas_g: str, bit_g: str,
    uyarilar: list[str] | None = None,
    ilerleme_cb=None,
) -> tuple[float, float]:
    """
    proje_fark_excel_kaydet() ve proje_fark_excel_bom_kaydet() tarafından
    paylaşılan ortak adım: fiili satınalmayı çeker, farkı hesaplar, 3 (veya
    uyarı varsa 4) sayfalık Excel workbook'unu yazar. Döner: (teorik_toplam, fiili_toplam)
    """
    if ilerleme_cb:
        ilerleme_cb(f"Proje '{proje_kodu}' satınalma hareketleri çekiliyor...")
    sat_satirlari, fiili_toplam = proje_fiili_maliyet(conn, proje_kodu, bas, bit)
    ham_hareketler = proje_satinalma_hareketleri(conn, proje_kodu, bas, bit)

    fark = proje_fark_raporu(bom_satirlari_toplam, sat_satirlari)
    fark_toplam = fiili_toplam - teorik_toplam
    fark_yuzde = (fark_toplam / teorik_toplam * 100) if teorik_toplam else None

    wb = openpyxl.Workbook()

    # ── Özet sayfası ──────────────────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Özet"
    ws1.column_dimensions["A"].width = 28
    ws1.column_dimensions["B"].width = 40
    satirlar_ozet = [
        ("Proje Kodu", proje_kodu),
        ("Dönem", f"{bas_g} – {bit_g}"),
        ("Maliyet Yöntemi", metod_ad),
        ("Seçilen Mamüller", ", ".join(mamul_adlari) if mamul_adlari else "—"),
        ("", ""),
        ("Teorik Maliyet (BOM) ₺", round(teorik_toplam, 2)),
        ("Fiili Satınalma ₺", round(fiili_toplam, 2)),
        ("Fark ₺", round(fark_toplam, 2)),
        ("Fark %", round(fark_yuzde, 1) if fark_yuzde is not None else "—"),
        ("", ""),
        ("Oluşturma", datetime.now().strftime("%d.%m.%Y %H:%M")),
    ]
    if uyarilar:
        satirlar_ozet.append(("Uyarı Sayısı (bkz. Uyarılar sayfası)", len(uyarilar)))
    for i, (etiket_, deger) in enumerate(satirlar_ozet, 1):
        e = ws1.cell(row=i, column=1, value=etiket_)
        e.font = _FONT["iscilik"] if etiket_ else _FONT["veri"]
        d = ws1.cell(row=i, column=2, value=deger)
        if isinstance(deger, (int, float)):
            d.number_format = _FMT_PARA if "₺" in etiket_ else _FMT_MIKTAR
            d.font = _FONT["toplam"]

    # ── Fark Detayı sayfası ──────────────────────────────────────────────────
    ws2 = wb.create_sheet("Fark Detayı")
    n2 = len(_PROJE_FARK_SUTUNLAR)
    ws2.row_dimensions[1].height = 26
    for col, (ad, gen) in enumerate(_PROJE_FARK_SUTUNLAR, 1):
        _hucre(ws2, 1, col, ad, "baslik", "baslik")
        ws2.column_dimensions[get_column_letter(col)].width = gen
    satir = 2
    for f in fark:
        stil = _DURUM_STIL.get(f["durum"], "veri")
        fill_key = stil if stil in _FILL else "bileseni"
        font_key = stil if stil in _FONT else "veri"
        for col, (val, aln, fmt) in enumerate([
            (f["tip"],              _ORTA, None),
            (f["bil_kod"],          _ORTA, None),
            (f["bil_ad"],           _SOL,  None),
            (_miktar(f["bom_miktar"]),        _SAG, _FMT_MIKTAR),
            (round(f["bom_tutar"], 2),        _SAG, _FMT_PARA),
            (_miktar(f["satinalma_miktar"]),  _SAG, _FMT_MIKTAR),
            (round(f["satinalma_tutar"], 2),  _SAG, _FMT_PARA),
            (_miktar(f["fark_miktar"]),       _SAG, _FMT_MIKTAR),
            (round(f["fark_tutar"], 2),       _SAG, _FMT_PARA),
            (f["durum"],            _ORTA, None),
        ], 1):
            _hucre(ws2, satir, col, val, fill_key, font_key, aln, fmt)
        satir += 1
    ws2.auto_filter.ref = f"A1:{get_column_letter(n2)}{satir - 1}"
    ws2.freeze_panes = "A2"

    # ── Satınalma Detayı sayfası ─────────────────────────────────────────────
    ws3 = wb.create_sheet("Satınalma Detayı")
    n3 = len(_PROJE_SATINALMA_SUTUNLAR)
    ws3.row_dimensions[1].height = 26
    for col, (ad, gen) in enumerate(_PROJE_SATINALMA_SUTUNLAR, 1):
        _hucre(ws3, 1, col, ad, "baslik", "baslik")
        ws3.column_dimensions[get_column_letter(col)].width = gen
    satir = 2
    for h in ham_hareketler:
        for col, (val, aln, fmt) in enumerate([
            (h["tip"],              _ORTA, None),
            (h["bil_kod"],          _ORTA, None),
            (h["bil_ad"],           _SOL,  None),
            (h["islem_turu"],       _ORTA, None),
            (h["belge_no"],         _ORTA, None),
            (h["tarih"],            _ORTA, None),
            (_miktar(h["miktar"]),  _SAG,  _FMT_MIKTAR),
            (round(h["birim_fiyat"], 4), _SAG, _FMT_BIRIM),
            (round(h["tutar"], 2),  _SAG,  _FMT_PARA),
            (h["tedarikci"],        _SOL,  None),
        ], 1):
            _hucre(ws3, satir, col, val, "bileseni", "veri", aln, fmt)
        satir += 1
    ws3.auto_filter.ref = f"A1:{get_column_letter(n3)}{satir - 1}"
    ws3.freeze_panes = "A2"

    # ── Uyarılar sayfası (yalnızca taslak Excel BOM kaynağında olabilir) ────
    if uyarilar:
        ws4 = wb.create_sheet("Uyarılar")
        ws4.column_dimensions["A"].width = 100
        ws4.cell(row=1, column=1, value=f"{len(uyarilar)} uyarı").font = _FONT["iscilik"]
        for i, u in enumerate(uyarilar, 2):
            ws4.cell(row=i, column=1, value=f"• {u}").font = _FONT["bilgi"]

    wb.save(dosya)
    return teorik_toplam, fiili_toplam


# ── Kesişim Kümesi Raporu ─────────────────────────────────────────────────────

_KESISIM_SUTUNLAR = [
    ("Kart Türü", 12), ("Kart Kodu", 16), ("Kart Adı", 36), ("Kart Adı-2", 36),
    ("Birim", 10), ("Güncel Miktar", 16),
    ("Fatura Sayısı", 14), ("Birim Fiyat ₺", 20),
    ("İlk Fatura", 14), ("Son Fatura", 14), ("Tedarikçi", 34),
]

_KESISIM_ALAN = [
    ("kart_tipi",     False, None),
    ("stok_kodu",     False, None),
    ("stok_adi",      False, None),
    ("stok_adi2",     False, None),
    ("birim",         False, None),
    ("guncel_miktar",  True, _FMT_MIKTAR),
    ("fatura_sayisi",  True, _FMT_ADET),
    ("birim_fiyat",    True, _FMT_BIRIM),
    ("ilk_fatura",    False, None),
    ("son_fatura",    False, None),
    ("tedarikci",     False, None),
]

_DETAY_SUTUNLAR = [
    ("Kart Türü", 12), ("Kart Kodu", 16), ("Kart Adı", 36), ("İşlem Türü", 20),
    ("Belge No", 16), ("Tarih", 14), ("Miktar", 12),
    ("Birim Fiyat ₺", 20), ("Tutar ₺", 18), ("Tedarikçi", 34),
]

_DETAY_ALAN = [
    ("kart_tipi",   False, None),
    ("stok_kodu",   False, None),
    ("stok_adi",    False, None),
    ("islem_turu",  False, None),
    ("belge_no",    False, None),
    ("tarih",       False, None),
    ("miktar",       True, _FMT_MIKTAR),
    ("birim_fiyat",  True, _FMT_BIRIM),
    ("tutar",        True, _FMT_PARA),
    ("tedarikci",   False, None),
]

_YONTEM_AD = {"FIFO": "FIFO (İlk Alış)", "LIFO": "LIFO (Son Alış)",
               "WA": "Ağırlıklı Ortalama"}


def kesisim_excel_kaydet(dosya: str, stoklar: list[dict], detaylar: list[dict],
                          tarih_aralik: str = "", yontem: str = "WA") -> None:
    yontem_ad = _YONTEM_AD.get(yontem, yontem)
    wb = openpyxl.Workbook()

    # ── Sayfa 1: Özet ────────────────────────────────────────────────────────
    ws = wb.active
    ws.title = "Kesişim Kümesi"

    n = len(_KESISIM_SUTUNLAR)
    ws.merge_cells(f"A1:{get_column_letter(n)}1")
    h = ws.cell(
        row=1, column=1,
        value=f"CEO ERP — Kesişim Kümesi  |  {tarih_aralik}  |  "
              f"{len(stoklar)} stok  |  Yöntem: {yontem_ad}  |  "
              f"Oluşturma: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    h.fill = _FILL["bilgi"]; h.font = _FONT["bilgi"]
    h.alignment = _SOL; h.border = _KENAR
    ws.row_dimensions[1].height = 24

    ws.row_dimensions[2].height = 28
    for col, (baslik, gen) in enumerate(_KESISIM_SUTUNLAR, 1):
        _hucre(ws, 2, col, baslik, "baslik", "baslik")
        ws.column_dimensions[get_column_letter(col)].width = gen

    for satir, s in enumerate(stoklar, 3):
        ws.row_dimensions[satir].height = 18
        for col, (key, sayisal, fmt) in enumerate(_KESISIM_ALAN, 1):
            ham = s.get(key)
            if sayisal:
                val = _miktar(ham) if fmt in (_FMT_MIKTAR, _FMT_BIRIM) else _adet(ham)
                aln = _SAG
            else:
                val = ("Masraf" if ham == "masraf" else "Stok") if key == "kart_tipi" else (str(ham).strip() if ham is not None else "")
                aln = _SOL
            h = ws.cell(row=satir, column=col, value=val)
            h.fill = _FILL["bileseni"]; h.font = _FONT["veri"]
            h.alignment = aln; h.border = _KENAR
            if fmt and val is not None:
                h.number_format = fmt

    ws.auto_filter.ref = f"A2:{get_column_letter(n)}2"
    ws.freeze_panes = "A3"

    # ── Sayfa 2: Detay (fatura satırı bazında) ───────────────────────────────
    wd = wb.create_sheet("Fatura Detayları")
    nd = len(_DETAY_SUTUNLAR)
    wd.merge_cells(f"A1:{get_column_letter(nd)}1")
    hd = wd.cell(
        row=1, column=1,
        value=f"CEO ERP — Fatura Detayları  |  {tarih_aralik}  |  "
              f"{len(detaylar)} satır  |  "
              f"Oluşturma: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    hd.fill = _FILL["bilgi"]; hd.font = _FONT["bilgi"]
    hd.alignment = _SOL; hd.border = _KENAR
    wd.row_dimensions[1].height = 24

    wd.row_dimensions[2].height = 28
    for col, (baslik, gen) in enumerate(_DETAY_SUTUNLAR, 1):
        _hucre(wd, 2, col, baslik, "baslik", "baslik")
        wd.column_dimensions[get_column_letter(col)].width = gen

    for satir, d in enumerate(detaylar, 3):
        wd.row_dimensions[satir].height = 18
        for col, (key, sayisal, fmt) in enumerate(_DETAY_ALAN, 1):
            ham = d.get(key)
            if sayisal:
                val = _miktar(ham)
                aln = _SAG
            else:
                val = ("Masraf" if ham == "masraf" else "Stok") if key == "kart_tipi" else (str(ham).strip() if ham is not None else "")
                aln = _SOL
            hc = wd.cell(row=satir, column=col, value=val)
            hc.fill = _FILL["bileseni"]; hc.font = _FONT["veri"]
            hc.alignment = aln; hc.border = _KENAR
            if fmt and val is not None:
                hc.number_format = fmt

    wd.auto_filter.ref = f"A2:{get_column_letter(nd)}2"
    wd.freeze_panes = "A3"

    wb.save(dosya)


# ── Bağlama Raporu ────────────────────────────────────────────────────────────

_ESLESTIRME_SUTUNLAR = [
    ("Seçili", "secili", 9, None),
    ("Kart Türü", "kart_tipi", 12, None),
    ("Kart Kodu", "stok_kodu", 19, None),
    ("Kart Adı", "stok_adi", 36, None),
    ("Birim", "birim", 11, None),
    ("Güncel Stok", "guncel_miktar", 17, _FMT_MIKTAR),
    ("Fatura Sayısı", "fatura_sayisi", 15, _FMT_ADET),
    ("Birim Fiyat", "birim_fiyat", 18, _FMT_BIRIM),
    ("Reçete Miktarı", "recete_miktari", 18, _FMT_MIKTAR),
    ("Durum", "islem", 13, None),
    ("İlk Fatura", "ilk_fatura", 15, None),
    ("Son Fatura", "son_fatura", 15, None),
    ("Tedarikçi", "tedarikci", 32, None),
    ("Mamül Kodu", "mamul_kodu", 19, None),
    ("Mamül Adı", "mamul_adi", 36, None),
    ("Reçete Grubu", "hat_kodu", 20, None),
    ("Grup ID", "hat_plani_id", 13, _FMT_ADET),
]


def eslestirme_listesi_excel_kaydet(
    dosya: str, gorunen: list[dict], tumu: list[dict],
) -> None:
    """Eşleştirme tablosunun görünür sırasını ve tüm taramayı iki sayfaya yazar."""
    wb = openpyxl.Workbook()
    for sira, (ad, satirlar) in enumerate((
        ("Görünen Liste", gorunen), ("Tüm Tarama", tumu),
    )):
        ws = wb.active if sira == 0 else wb.create_sheet()
        ws.title = ad
        ws.row_dimensions[1].height = 28
        for sutun, (baslik, _, genislik, _) in enumerate(_ESLESTIRME_SUTUNLAR, 1):
            _hucre(ws, 1, sutun, baslik, "baslik", "baslik")
            ws.column_dimensions[get_column_letter(sutun)].width = genislik

        for satir_no, kayit in enumerate(satirlar, 2):
            ws.row_dimensions[satir_no].height = 20
            renk = "baglandi" if kayit.get("islem") == "Bağlandı" else "atlandi"
            for sutun, (_, alan, _, fmt) in enumerate(_ESLESTIRME_SUTUNLAR, 1):
                ham = kayit.get(alan)
                if alan == "secili":
                    deger = "Evet" if ham else ""
                elif alan == "kart_tipi":
                    deger = "Masraf" if ham == "masraf" else "Stok"
                elif alan == "guncel_miktar" and kayit.get("kart_tipi") == "masraf":
                    deger = None
                elif fmt is not None:
                    try:
                        deger = float(str(ham).strip().replace(",", "."))
                        if not isfinite(deger):
                            raise ValueError("Geçersiz sayı")
                        if fmt == _FMT_ADET:
                            deger = int(deger)
                    except (ValueError, TypeError):
                        deger = None if ham in (None, "", "—") else str(ham)
                        if isinstance(deger, str) and deger.startswith("="):
                            deger = "'" + deger
                else:
                    deger = str(ham).strip() if ham is not None else ""
                    if deger.startswith("="):
                        deger = "'" + deger
                hizalama = _SAG if fmt and isinstance(deger, (int, float)) else _SOL
                _hucre(
                    ws, satir_no, sutun, deger, renk, "veri", hizalama,
                    fmt if fmt and isinstance(deger, (int, float)) else None,
                )
        son_sutun = get_column_letter(len(_ESLESTIRME_SUTUNLAR))
        ws.auto_filter.ref = f"A1:{son_sutun}{max(len(satirlar) + 1, 1)}"
        ws.freeze_panes = "A2"
    wb.save(dosya)


def baglama_excel_kaydet(dosya: str, sonuclar: list[dict]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Mamül Ağacı Raporu"

    ws.row_dimensions[1].height = 30
    for col, ((_, __, ___), gen) in enumerate(
        zip(_BAGLAMA_ALAN, _BAGLAMA_GENISLIK), 1
    ):
        _hucre(ws, 1, col, _BAGLAMA_ALAN[col - 1][0].replace("_", " ").title(),
               "baslik", "baslik")
        ws.column_dimensions[get_column_letter(col)].width = gen

    # Başlık etiketlerini tekrar doğru adlarla yaz
    basliklar = [
        "Kart Türü", "Kart Kodu", "Kart Adı", "Birim", "Güncel Miktar",
        "Fatura Sayısı", "Birim Fiyat", "İlk Fatura", "Son Fatura",
        "Tedarikçi", "Mamül Kodu", "Mamül Adı", "İşlem",
        "Reçete Grubu", "Grup ID", "Reçete Miktarı",
    ]
    for col, (baslik, gen) in enumerate(zip(basliklar, _BAGLAMA_GENISLIK), 1):
        _hucre(ws, 1, col, baslik, "baslik", "baslik")
        ws.column_dimensions[get_column_letter(col)].width = gen

    for satir, s in enumerate(sonuclar, 2):
        fill_key = "baglandi" if s.get("islem") == "Bağlandı" else "atlandi"
        ws.row_dimensions[satir].height = 18

        for col, (key, sayisal, fmt) in enumerate(_BAGLAMA_ALAN, 1):
            ham = s.get(key)

            if sayisal:
                if fmt == _FMT_ADET:
                    val = _adet(ham)
                elif fmt == _FMT_PARA:
                    val = _para(ham)
                else:  # _FMT_MIKTAR, _FMT_BIRIM
                    val = _miktar(ham)
                aln = _SAG
            else:
                val = ("Masraf" if ham == "masraf" else "Stok") if key == "kart_tipi" else (str(ham).strip() if ham is not None else "")
                aln = _SOL

            h = ws.cell(row=satir, column=col, value=val)
            h.fill      = _FILL[fill_key]
            h.font      = _FONT["veri"]
            h.alignment = aln
            h.border    = _KENAR
            if fmt and val is not None:
                h.number_format = fmt

    ws.auto_filter.ref = f"A1:{get_column_letter(len(_BAGLAMA_ALAN))}1"
    ws.freeze_panes = "A2"
    wb.save(dosya)
