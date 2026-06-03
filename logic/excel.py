"""Excel raporu üretme iş mantığı. UI'dan bağımsızdır."""
from datetime import datetime
import openpyxl
from openpyxl.styles import PatternFill, Font as XFont, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from logic.maliyet import mamul_maliyet_hesapla
from db.sorgular import bom_listesi

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
}
_FONT = {
    "baslik":   XFont(bold=True, color="FFFFFF", name="Segoe UI", size=11),
    "mamul":    XFont(bold=True, color="FFFFFF", name="Segoe UI", size=11),
    "bileseni": XFont(name="Segoe UI", size=10),
    "iscilik":  XFont(italic=True, name="Segoe UI", size=10, color="E65100"),
    "toplam":   XFont(bold=True, name="Segoe UI", size=11, color="1B5E20"),
    "bilgi":    XFont(name="Segoe UI", size=10, color="555555"),
    "veri":     XFont(name="Segoe UI", size=10),
}

_MALIYET_SUTUNLAR = [
    ("Tip", 10), ("Mamül Kodu", 14), ("Mamül Adı", 28),
    ("Bileşen Kodu", 14), ("Bileşen Adı", 30), ("BOM Miktarı", 13),
    ("Birim", 10), ("Birim Maliyet ₺", 18), ("Satır Maliyeti ₺", 18),
    ("Hammadde Toplamı ₺", 20), ("İşçilik ₺", 16), ("Genel Toplam ₺", 20),
]

_BAGLAMA_SUTUNLAR = [
    ("Stok Kodu", 14), ("Stok Adı", 32), ("Fatura Türleri", 20),
    ("Fatura Sayısı", 14), ("Toplam Tutar", 18), ("İlk Fatura", 14),
    ("Son Fatura", 14), ("Tedarikçi", 30), ("Mamül Kodu", 14),
    ("Mamül Adı", 30), ("İşlem", 13),
]


def _hucre(ws, row, col, val, fill_key, font_key, alignment=_ORTA, sayi_fmt=None):
    h = ws.cell(row=row, column=col, value=val)
    h.fill      = _FILL[fill_key]
    h.font      = _FONT[font_key]
    h.alignment = alignment
    h.border    = _KENAR
    if sayi_fmt:
        h.number_format = sayi_fmt
    return h


def maliyet_excel_kaydet(
    dosya: str, conn,
    secili: list[tuple],   # [(mamul_kodu, cb_widget, spin_widget), ...]
    metod: str, bas: str, bit: str, bas_g: str, bit_g: str,
) -> None:
    metod_ad = {"WA": "Ağırlıklı Ortalama", "FIFO": "FIFO", "LIFO": "LIFO"}[metod]
    bom = bom_listesi(conn)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Maliyet Raporu"

    # Bilgi satırı
    ws.merge_cells(f"A1:{get_column_letter(len(_MALIYET_SUTUNLAR))}1")
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

    # Tüm mamüller için paylaşılan önbellek: aynı alt bileşen tekrar SQL'e gitmez
    cache: dict = {}

    satir = 3
    for mamul_kodu, _cb, spin in secili:
        mamul = bom.get(mamul_kodu)
        if not mamul:
            continue
        iscilik = spin.value()
        bilesenleri, hammadde_top = mamul_maliyet_hesapla(
            conn, mamul_kodu, metod, bas, bit, _cache=cache
        )
        genel_top = hammadde_top + iscilik

        # Mamül başlık satırı
        ws.row_dimensions[satir].height = 22
        for col, val in enumerate(
            ["MAMÜL", mamul_kodu, mamul["ad"], "", "", "", "", "", "",
             hammadde_top, iscilik, genel_top], 1
        ):
            aln = _SAG if isinstance(val, float) else (_ORTA if col <= 2 else _SOL)
            fmt = "#,##0.00 ₺" if isinstance(val, float) else None
            _hucre(ws, satir, col, round(val, 2) if isinstance(val, float) else val,
                   "mamul", "mamul", aln, fmt)
        satir += 1

        # Bileşen satırları
        for b in bilesenleri:
            ws.row_dimensions[satir].height = 18
            vals = ["BİLEŞEN", mamul_kodu, mamul["ad"],
                    b["bil_kod"], b["bil_ad"],
                    b["bom_miktar"], b["birim"],
                    b["birim_mal"], b["satir_top"], "", "", ""]
            for col, val in enumerate(vals, 1):
                aln = _SAG if isinstance(val, float) else (_ORTA if col in (1,2,6,7) else _SOL)
                fmt = "#,##0.00" if isinstance(val, float) else None
                _hucre(ws, satir, col, round(val, 4) if isinstance(val, float) else val,
                       "bileseni", "bileseni", aln, fmt)
            satir += 1

        # İşçilik satırı
        if iscilik > 0:
            ws.row_dimensions[satir].height = 18
            vals = ["İŞÇİLİK", mamul_kodu, mamul["ad"],
                    "—", "Manuel İşçilik Tutarı", "", "", "", iscilik, "", "", ""]
            for col, val in enumerate(vals, 1):
                aln = _SAG if isinstance(val, float) else (_ORTA if col in (1,2) else _SOL)
                fmt = "#,##0.00 ₺" if isinstance(val, float) else None
                _hucre(ws, satir, col, round(val, 2) if isinstance(val, float) else val,
                       "iscilik", "iscilik", aln, fmt)
            satir += 1

        # Toplam satırı
        ws.row_dimensions[satir].height = 20
        for col, val in enumerate(
            ["TOPLAM", mamul_kodu, mamul["ad"], "", "", "", "", "", "",
             hammadde_top, iscilik, genel_top], 1
        ):
            aln = _SAG if isinstance(val, float) else (_ORTA if col <= 2 else _SOL)
            fmt = "#,##0.00 ₺" if isinstance(val, float) else None
            _hucre(ws, satir, col, round(val, 2) if isinstance(val, float) else val,
                   "toplam", "toplam", aln, fmt)
        satir += 1

        ws.row_dimensions[satir].height = 6
        satir += 1

    ws.auto_filter.ref = f"A2:{get_column_letter(len(_MALIYET_SUTUNLAR))}2"
    ws.freeze_panes = "A3"
    wb.save(dosya)


def baglama_excel_kaydet(dosya: str, sonuclar: list[dict]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Mamül Ağacı Raporu"

    ws.row_dimensions[1].height = 30
    for col, (ad, gen) in enumerate(_BAGLAMA_SUTUNLAR, 1):
        _hucre(ws, 1, col, ad, "baslik", "baslik")
        ws.column_dimensions[get_column_letter(col)].width = gen

    alan = ["stok_kodu", "stok_adi", "fatura_turleri", "fatura_sayisi", "toplam_tutar",
            "ilk_fatura", "son_fatura", "tedarikci", "mamul_kodu", "mamul_adi", "islem"]

    for satir, s in enumerate(sonuclar, 2):
        fill_key = "baglandi" if s["islem"] == "Bağlandı" else "atlandi"
        ws.row_dimensions[satir].height = 18
        for col, key in enumerate(alan, 1):
            h = ws.cell(row=satir, column=col, value=str(s.get(key, "")))
            h.fill = _FILL[fill_key]; h.font = _FONT["veri"]
            h.alignment = _SOL; h.border = _KENAR

    ws.auto_filter.ref = f"A1:{get_column_letter(len(_BAGLAMA_SUTUNLAR))}1"
    ws.freeze_panes = "A2"
    wb.save(dosya)
