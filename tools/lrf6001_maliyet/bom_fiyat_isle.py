"""Hesaplanan maliyetleri orijinal BOM'un KOPYASINA, ilgili kodların karşısına işler."""
import os, sys, json, shutil
from copy import copy
from collections import defaultdict
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L

KAYNAK, HESAP_JSON, CIKTI = sys.argv[1], sys.argv[2], sys.argv[3]
h = json.load(open(HESAP_JSON, encoding="utf-8"))
satirlar, USD, EUR = h["satirlar"], h["usd"], h["eur"]

shutil.copyfile(KAYNAK, CIKTI)
wb = openpyxl.load_workbook(CIKTI)

TL = '#,##0.00 "₺"'
ince = Side(style="thin", color="808080"); KN = Border(left=ince, right=ince, top=ince, bottom=ince)
HDR = PatternFill("solid", fgColor="1F4E78"); BW = Font(bold=True, color="FFFFFF")
SARI = PatternFill("solid", fgColor="FFF2CC"); KIRMIZI = PatternFill("solid", fgColor="F8CBAD")
TOP = PatternFill("solid", fgColor="D9E1F2"); B = Font(bold=True)

def baslik(ws, row, col0, basliklar, genislik):
    for i, (t, w) in enumerate(zip(basliklar, genislik)):
        c = ws.cell(row=row, column=col0 + i, value=t)
        c.font = BW; c.fill = HDR; c.border = KN
        c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
        ws.column_dimensions[L(col0 + i)].width = w

def hucre(ws, r, c, v, fmt=None, fill=None, font=None):
    x = ws.cell(row=r, column=c, value=v); x.border = KN
    if fmt: x.number_format = fmt
    if fill: x.fill = fill
    if font: x.font = font
    return x

def tarih(s): return s["tarih"][:10] if s["tarih"] else ""
def gun(t): return f"{t[8:10]}.{t[5:7]}.{t[0:4]}" if t else ""

# ------------------------------------------------------------ kart sayfaları
kart_toplam_hucre = {}   # kart_kod -> (alış toplam hücresi, güncel toplam hücresi)
kart_sat = defaultdict(list)
for s in satirlar:
    if s["kaynak"] and s["kaynak"][0].startswith("GMP-300"):
        kart_sat[s["kaynak"][0]].append(s)

for kart, ss in kart_sat.items():
    ws = wb[kart]
    C0 = 5  # E
    cols = ["ERP Kodu", "Son Alış Tarihi", "Döviz", "Döviz Birim Fiyatı", "Alış Birim (₺)", "Güncel Birim (₺)",
            "Alış Toplam (₺)", "Güncel Toplam (₺)", "Kur Farkı (₺)", "Not"]
    baslik(ws, 6, C0, cols, [22, 12, 7, 12, 14, 14, 15, 15, 14, 45])
    son = 6
    for s in ss:
        if s["kaynak"][1] == "PCB":
            continue
        r = s["kaynak"][1]; son = max(son, r)
        f = KIRMIZI if s["tl"] == 0 else (SARI if s["not_"] and "Excel kodu" in s["not_"] else None)
        hucre(ws, r, C0, s["erp_kod"], fill=f)
        hucre(ws, r, C0 + 1, gun(tarih(s)), fill=f)
        hucre(ws, r, C0 + 2, s["dvz"], fill=f)
        hucre(ws, r, C0 + 3, s["dvz_f"], "#,##0.0000", fill=f)
        hucre(ws, r, C0 + 4, s["tl"], TL, fill=f)
        hucre(ws, r, C0 + 5, s["guncel"], TL, fill=f)
        hucre(ws, r, C0 + 6, f"=D{r}*{L(C0+4)}{r}", TL, fill=f)
        hucre(ws, r, C0 + 7, f"=D{r}*{L(C0+5)}{r}", TL, fill=f)
        hucre(ws, r, C0 + 8, f"={L(C0+7)}{r}-{L(C0+6)}{r}", TL, fill=f)
        hucre(ws, r, C0 + 9, s["not_"], fill=f)
    ilk = 7
    # PCB satırı
    pcb = next(s for s in ss if s["kaynak"][1] == "PCB")
    r = son + 1
    f = KIRMIZI if pcb["tl"] == 0 else SARI
    hucre(ws, r, 1, pcb["erp_kod"] or "PCB", fill=f); hucre(ws, r, 2, pcb["ad"], fill=f)
    hucre(ws, r, 3, "PCB (ERP reçetesinden eklendi)", fill=f); hucre(ws, r, 4, pcb["adet"], fill=f)
    hucre(ws, r, C0, pcb["erp_kod"], fill=f); hucre(ws, r, C0 + 1, gun(tarih(pcb)), fill=f)
    hucre(ws, r, C0 + 2, pcb["dvz"], fill=f); hucre(ws, r, C0 + 3, pcb["dvz_f"], "#,##0.0000", fill=f)
    hucre(ws, r, C0 + 4, pcb["tl"], TL, fill=f); hucre(ws, r, C0 + 5, pcb["guncel"], TL, fill=f)
    hucre(ws, r, C0 + 6, f"=D{r}*{L(C0+4)}{r}", TL, fill=f); hucre(ws, r, C0 + 7, f"=D{r}*{L(C0+5)}{r}", TL, fill=f)
    hucre(ws, r, C0 + 8, f"={L(C0+7)}{r}-{L(C0+6)}{r}", TL, fill=f); hucre(ws, r, C0 + 9, pcb["not_"], fill=f)
    # toplam satırı
    t = r + 1
    hucre(ws, t, 1, "KART TOPLAMI (1 adet)", font=B, fill=TOP)
    for c in range(2, C0 + 6): hucre(ws, t, c, None, fill=TOP)
    for c in (C0 + 6, C0 + 7, C0 + 8):
        hucre(ws, t, c, f"=SUM({L(c)}{ilk}:{L(c)}{r})", TL, fill=TOP, font=B)
    hucre(ws, t, C0 + 9, "İşçilik / SMT dizgi dahil değil", fill=TOP)
    kart_toplam_hucre[kart] = (f"'{kart}'!{L(C0+6)}{t}", f"'{kart}'!{L(C0+7)}{t}")

# ------------------------------------------------------------ ana sayfa
ws = wb["Urun BOM"]
C0 = 10  # J
cols = ["ERP Kodu", "Hesap Adedi", "Son Alış Tarihi", "Döviz", "Alış Birim Maliyeti (₺)", "Güncel Birim Maliyeti (₺)",
        "Alış Toplam (₺)", "Güncel Toplam (₺)", "Kur Farkı (₺)", "Not"]
baslik(ws, 6, C0, cols, [22, 9, 12, 9, 15, 15, 15, 15, 14, 60])

ana = defaultdict(list)
for s in satirlar:
    if s["kaynak"] and s["kaynak"][0] == "Urun BOM":
        ana[s["kaynak"][1]].append(s)

# elektronik kart satırları: Excel ana listesinde kart kodu D sütununda
for r in range(7, ws.max_row + 1):
    kod = ws.cell(row=r, column=4).value
    if kod in kart_toplam_hucre:
        alis_ref, guncel_ref = kart_toplam_hucre[kod]
        rec = {"GMP-300-230007": "GMP-300-230015", "GMP-300-230011": "GMP-300-230019", "GMP-300-230008": "GMP-300-230016",
               "GMP-300-230010": "GMP-300-230018", "GMP-300-230009": "GMP-300-230017"}.get(kod)
        hucre(ws, r, C0, rec or "(ERP'de yok)", fill=SARI)
        hucre(ws, r, C0 + 1, f"=B{r}", fill=SARI)
        hucre(ws, r, C0 + 2, "çok kalem", fill=SARI); hucre(ws, r, C0 + 3, "USD/EUR", fill=SARI)
        hucre(ws, r, C0 + 4, f"={alis_ref}", TL, fill=SARI); hucre(ws, r, C0 + 5, f"={guncel_ref}", TL, fill=SARI)
        hucre(ws, r, C0 + 6, f"={L(C0+1)}{r}*{L(C0+4)}{r}", TL, fill=SARI)
        hucre(ws, r, C0 + 7, f"={L(C0+1)}{r}*{L(C0+5)}{r}", TL, fill=SARI)
        hucre(ws, r, C0 + 8, f"={L(C0+7)}{r}-{L(C0+6)}{r}", TL, fill=SARI)
        hucre(ws, r, C0 + 9, f"Bileşen detayı '{kod}' sayfasında" + (f" — ERP reçetesi {rec}" if rec else " — ERP reçetesi/PCB yok"), fill=SARI)

for r, ss in ana.items():
    adet = ss[0]["adet"]
    birim_alis = sum(s["tl"] for s in ss)        # aynı satırdaki parça + operasyonlar (1 adet için)
    birim_guncel = sum(s["guncel"] for s in ss)
    tarihler = [tarih(s) for s in ss if s["tarih"]]
    dvz = "/".join(sorted({s["dvz"] for s in ss if s["dvz"]}))
    notlar = []
    ops = [s for s in ss if s["tip"] == "Operasyon"]
    if ops:
        notlar.append("Operasyonlar: " + ", ".join(
            f'{s["erp_kod"].split(":")[1]}={s["guncel"]:,.0f}₺' if s["tl"] else f'{s["erp_kod"].split(":")[1]}=fiyat yok'
            for s in ops))
    for s in ss:
        if s["not_"] and s["not_"] not in notlar and s["tip"] != "Operasyon":
            notlar.append(s["not_"])
    erp = ss[0]["erp_kod"].split(":")[0] if ss[0]["erp_kod"] else None
    f = KIRMIZI if birim_alis == 0 else (SARI if any("varsayıldı" in n or "→ ERP" in n or "kontrol" in n for n in notlar) else None)
    hucre(ws, r, C0, erp or "(ERP'de yok)", fill=f)
    hucre(ws, r, C0 + 1, adet, fill=f)
    hucre(ws, r, C0 + 2, gun(max(tarihler)) if tarihler else "", fill=f)
    hucre(ws, r, C0 + 3, dvz, fill=f)
    hucre(ws, r, C0 + 4, birim_alis, TL, fill=f)
    hucre(ws, r, C0 + 5, birim_guncel, TL, fill=f)
    hucre(ws, r, C0 + 6, f"={L(C0+1)}{r}*{L(C0+4)}{r}", TL, fill=f)
    hucre(ws, r, C0 + 7, f"={L(C0+1)}{r}*{L(C0+5)}{r}", TL, fill=f)
    hucre(ws, r, C0 + 8, f"={L(C0+7)}{r}-{L(C0+6)}{r}", TL, fill=f)
    hucre(ws, r, C0 + 9, " | ".join(notlar), fill=f)
    ws.cell(row=r, column=C0 + 9).alignment = Alignment(wrap_text=False)

# OEM modül notu
for r, ss in ana.items():
    if ss[0]["erp_kod"] == "OEM-LRF-NP":
        ws.cell(row=r, column=C0 + 9).value = ("KONTROL: son alış 263,92 EUR (24.10.2025) — 2021'de 2.311 EUR idi; "
                                               "fatura satırı doğrulanmalı | Excel kodu NOPTEL LRF 221 → ERP OEM-LRF-NP")
        for c in range(C0, C0 + 10): ws.cell(row=r, column=c).fill = SARI

# genel toplam bloğu
son = ws.max_row + 2
G, A_, K = L(C0 + 7), L(C0 + 6), L(C0 + 8)
bloklar = [
    ("MALZEME TOPLAMI — ALIŞ GÜNÜ FİYATLARI", f"=SUM({A_}7:{A_}{son-2})"),
    ("MALZEME TOPLAMI — GÜNCEL KUR", f"=SUM({G}7:{G}{son-2})"),
    ("KUR FARKI", f"=SUM({K}7:{K}{son-2})"),
    ("GÜNCEL TOPLAM (USD)", f"=SUM({G}7:{G}{son-2})/{USD}"),
]
for i, (et, form) in enumerate(bloklar):
    r = son + i
    ws.merge_cells(start_row=r, start_column=C0, end_row=r, end_column=C0 + 6)
    hucre(ws, r, C0, et, font=B, fill=TOP)
    hucre(ws, r, C0 + 7, form, '#,##0.00 "$"' if "USD" in et else TL, font=B, fill=TOP)
notlar = [
    f"Hesap tarihi 30.10.2026 · Kur: USD {USD:.4f} ₺, EUR {EUR:.4f} ₺ (CEO ERP GunlukKur, döviz alış).",
    "Yöntem: CEO ERP'deki en son alış fiyatı. USD/EUR faturada döviz fiyatı × bugünkü kur; TL faturada TL ÷ alış günü USD × bugünkü USD.",
    "Mekanik parçalarda birim maliyet = parçanın :XX operasyon kodlarının (ve varsa kendi alışının) toplamı.",
    "Kırmızı: ERP'de fiyat bulunamadı (0). Sarı: kod eşleştirme / varsayım / kontrol gerekli — Not sütununa bakınız.",
    "Dahil değil: işçilik, SMT dizgi, montaj, test, ambalaj, tripod/omuz çantası/boyun askısı. BC300 çanta dahil.",
]
for i, n in enumerate(notlar):
    ws.cell(row=son + 5 + i, column=C0, value=n).font = Font(italic=True, size=9)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fiyatsiz import fiyatsiz_sayfasi
fiyatsiz_sayfasi(wb, satirlar, 1)
wb.calculation.fullCalcOnLoad = True
wb.save(CIKTI)
print("kaydedildi:", CIKTI, "ana satır:", len(ana), "kart:", list(kart_toplam_hucre))
