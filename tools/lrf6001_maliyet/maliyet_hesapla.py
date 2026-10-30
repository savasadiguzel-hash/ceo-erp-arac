"""LRF 6001 maliyet hesabı — son alış fiyatı + kur farkı yeniden değerleme (SADECE OKUMA).

Kullanım (proje kökünden):
    python -I tools/lrf6001_maliyet/bom_oku.py "LRF 6001 ÜRÜN BOM.xlsx" bom.json
    python tools/lrf6001_maliyet/maliyet_hesapla.py bom.json LRF6001_maliyet.xlsx
    python tools/lrf6001_maliyet/bom_fiyat_isle.py "LRF 6001 ÜRÜN BOM.xlsx" LRF6001_maliyet.xlsx.json "LRF 6001 ÜRÜN BOM - MALİYETLİ.xlsx"

Ayrıntılar: ERP-OKUMA.md → "LRF 6001 Maliyet Çalışması".
"""
import os, sys, json, re, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import DB_DEFAULTS
from db.baglanti import get_connection
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

PARSE_JSON, CIKTI = sys.argv[1], sys.argv[2]
d = json.load(open(PARSE_JSON, encoding="utf-8"))
conn = get_connection(**DB_DEFAULTS)
cur = conn.cursor()

BUGUN = dt.datetime.combine(dt.date.today(), dt.time())   # güncel kur bu tarihten (veya öncesindeki son kayıttan) alınır
DOVIZ_ID = {"USD": "93F5D195-1632-4957-AB52-464DC431A79A", "EUR": "6F454FBD-D5F5-4D8B-A27C-C4FC40FF4A33"}

_kur_cache = {}
def kur(doviz, tarih):
    """GunlukKur.Kur1 (döviz alış) — o tarih veya öncesindeki son geçerli kur."""
    k = (doviz, tarih.date())
    if k not in _kur_cache:
        cur.execute("""SELECT TOP 1 Kur1 FROM GunlukKur WHERE DovizBirimId=? AND Tarih<=? AND Kur1>0
                       ORDER BY Tarih DESC""", DOVIZ_ID[doviz], tarih)
        r = cur.fetchone()
        _kur_cache[k] = float(r[0]) if r else None
    return _kur_cache[k]

USD_BUGUN, EUR_BUGUN = kur("USD", BUGUN), kur("EUR", BUGUN)

_SQL = """
SELECT TOP 1 sh.BelgeTarihi, shd.BirimFiyat, shd.DovizBirimFiyati, db.DovizBirimKod, '{tur}'
FROM StokHareketDetay shd
JOIN StokHareket sh ON sh.Id = shd.HareketId
JOIN {tablo} k ON k.Id = shd.IslemKartId
LEFT JOIN DovizBirim db ON db.DovizBirimId = shd.DovizBirimId
WHERE k.Kodu = ? {turu}
  AND (sh.IslemKodu = 1 OR (sh.IslemKodu = 5 AND sh.FaturaId IS NULL))
  AND shd.BirimFiyat > 0 AND shd.Miktar > 0
ORDER BY sh.BelgeTarihi DESC, sh.Id DESC
"""
def son_alis(kod):
    """Stok (Turu=1) ve masraf tarafındaki en son alış satırı (tarih sınırı yok)."""
    satirlar = []
    for tablo, tur, turu in (("StokKarti", "Stok", "AND shd.Turu = 1"), ("StokMasrafKarti", "Masraf", "")):
        cur.execute(_SQL.format(tablo=tablo, tur=tur, turu=turu), kod)
        r = cur.fetchone()
        if r: satirlar.append(r)
    if not satirlar:
        return None
    t, tl, dvz_f, dvz, tur = max(satirlar, key=lambda r: r[0])
    return dict(tarih=t, tl=float(tl), dvz_f=float(dvz_f or 0), dvz=dvz or "TL", tur=tur)

def degerle(a):
    """Alış satırını bugünkü kura taşır. Döner: (güncel_birim_tl, yöntem, alış_kuru)."""
    if a["dvz"] in ("USD", "EUR") and a["dvz_f"] > 0:
        bugun = USD_BUGUN if a["dvz"] == "USD" else EUR_BUGUN
        return a["dvz_f"] * bugun, f'{a["dvz"]} fiyat × bugünkü {a["dvz"]} kuru', a["tl"] / a["dvz_f"]
    k = kur("USD", a["tarih"])
    return a["tl"] / k * USD_BUGUN, "TL ÷ alış günü USD × bugünkü USD", k

def kart_var(kod):
    cur.execute("SELECT Adi FROM StokKarti WHERE Kodu=? UNION ALL SELECT Adi FROM StokMasrafKarti WHERE Kodu=?", kod, kod)
    r = cur.fetchone()
    return (r[0] or "").strip() if r else None

def ops(kod):
    cur.execute("SELECT Kodu, Adi FROM StokKarti WHERE Kodu LIKE ? UNION SELECT Kodu, Adi FROM StokMasrafKarti WHERE Kodu LIKE ?",
                kod + ":%", kod + ":%")
    return sorted(((r[0], (r[1] or "").strip()) for r in cur.fetchall()), key=lambda x: int(x[0].split(":")[1]) if x[0].split(":")[1].isdigit() else 0)

# Excel kodu → ERP kodu (incelemede doğrulanan eşleşmeler)
ESLESME = {
    "POWER EXRTA RCR123A": "900600503273", "BASEN BO-2": "BSC203", "SERTEC STC-C1": "STC-C1",
    "SERTEC STC-024": "STC-024", "NOPTEL LRF 221": "OEM-LRF-NP", "HMCOMPRS0010": "HMCOMPRS010",
    "CC2541F256TRHARQ": "CC2541F256TRHARQ1", "532617008": "0532617008",
    "SM08B-SRSS-TB(LF)(SN)": "SM08B-SRSS-TB", "CGA2B3X7R1H104K0": "CGA2B3X7R1H104K050BB",
    "C1005X5R0J475K05": "C1005X5R0J475K050BC", "GRM155R60J475ME4": "GRM155R60J475ME47D",
    "503772-1010": "5037721010", "MICROOLED MDP05A": "MDP05APRMRO", "ABS07-32.768KHz-T": "ABS07-32.768KHZ-T",
}
# Elektronik kart (Excel) → ERP'deki LRF 6001 kart reçetesi ve çıplak PCB
KART_PCB = {"GMP-300-230007": ("GMP-300-230015", "GMP-301-230020"), "GMP-300-230011": ("GMP-300-230019", "GMP-301-230024"),
            "GMP-300-230008": ("GMP-300-230016", "GMP-301-230021"), "GMP-300-230010": ("GMP-300-230018", "GMP-301-230023"),
            "GMP-300-230009": ("GMP-300-230017", "GMP-301-230022"), "GMP-300-230012": (None, None)}

def norm(s): return re.sub(r"\s*\(revizyon olacak\)", "", str(s)).strip() if s is not None else None

satirlar = []   # her biri bir maliyet satırı
def ekle(grup, ust, excel_kod, erp_kod, ad, adet, not_="", tip="Parça", kaynak=None):
    s = dict(kaynak=kaynak, grup=grup, ust=ust, excel_kod=excel_kod, erp_kod=erp_kod, ad=ad, adet=adet, tip=tip, not_=not_,
             tarih=None, dvz="", dvz_f=None, alis_kur=None, tl=0.0, guncel=0.0, yontem="")
    if erp_kod:
        a = son_alis(erp_kod)
        if a:
            g, y, k = degerle(a)
            s.update(tarih=a["tarih"], dvz=a["dvz"], dvz_f=a["dvz_f"] if a["dvz"] != "TL" else None,
                     alis_kur=k, tl=a["tl"], guncel=g, yontem=y)
        elif not s["not_"]:
            s["not_"] = "ERP'de alış faturası yok → 0"
    satirlar.append(s)

for x in d["ana"]:
    bolum, adet = x["bolum"], x["adet"]
    konf, eski = norm(x["konf"]), norm(x["eski"])
    if bolum == "ELEKTRONİK":
        kart_kod = konf
        erp_rec, pcb = KART_PCB[kart_kod]
        ust = f'{kart_kod} {x["tanim"]}'
        for r in d["kart"][kart_kod]:
            mpn = r["mpn"]; erp = ESLESME.get(mpn, mpn)
            nt = "" if kart_var(erp) else "ERP'de stok kartı yok → 0"
            if mpn == "MTi-3-0I-T": nt = "ERP'de yalnızca geliştirme kiti (MTI-3-01-DK) var, modülün kendisi yok → 0"
            if erp != mpn and not nt: nt = f"Excel kodu {mpn} → ERP {erp}"
            ekle("Elektronik Kartlar", ust, mpn, erp if kart_var(erp) else None, (r["desc"] or "")[:90], (r["adet"] or 0) * adet, nt, kaynak=(kart_kod, r["satir"]))
        if pcb:
            ekle("Elektronik Kartlar", ust, "", pcb, kart_var(pcb) or "PCB", adet,
                 f"Excel'de yok — ERP reçetesi {erp_rec} içindeki çıplak PCB eklendi", "PCB", kaynak=(kart_kod, "PCB"))
        else:
            satirlar[-1]["not_"] += "" ; ekle("Elektronik Kartlar", ust, "", None, "PCB (çıplak kart)", adet,
                                              "ERP'de bu kartın reçetesi/PCB'si yok → 0", "PCB", kaynak=(kart_kod, "PCB"))
        continue
    if bolum.startswith("ELEKTRONİK AKSESUAR"):
        kod = eski or konf; erp = ESLESME.get(kod, kod)
        ekle("Aksesuar & OEM Modül", "", kod, erp, x["tanim"], adet, f"Excel kodu {kod} → ERP {erp}" if erp != kod else "", kaynak=("Urun BOM", x["satir"]))
        continue
    if bolum == "KABLAJ":
        kod = norm(eski) if eski else konf
        ekle("Kablaj", "", kod, kod, x["tanim"][:90], adet, "Excel'de '(revizyon olacak)' notu var" if "revizyon" in str(x["konf"]) else "", kaynak=("Urun BOM", x["satir"]))
        continue
    if bolum == "MEKANİK":
        ad = kart_var(konf)
        if ad is None:
            ekle("Mekanik", "", konf, None, x["tanim"], adet, "ERP'de stok kartı yok → 0", kaynak=("Urun BOM", x["satir"]))
            continue
        a = son_alis(konf)
        if a:  # kartın kendisinin alışı varsa (hazır alınan parça)
            ekle("Mekanik", konf, konf, konf, x["tanim"], adet, "Parçanın kendi alış faturası", kaynak=("Urun BOM", x["satir"]))
        op_list = ops(konf)
        for ok, oad in op_list:
            ekle("Mekanik", konf, konf, ok, f'{x["tanim"]} — {oad}', adet, "", "Operasyon", kaynak=("Urun BOM", x["satir"]))
        if not a and not op_list:
            ekle("Mekanik", konf, konf, konf, x["tanim"], adet, "Kart var, alış/operasyon kaydı yok → 0", kaynak=("Urun BOM", x["satir"]))
        continue
    if bolum == "OPTİK":
        kod = ESLESME.get(eski, eski)
        ekle("Optik", "", eski, kod, x["tanim"][:90], adet or 1,
             ("Excel'de adet boş → 1 varsayıldı" + (f"; Excel kodu {eski} → ERP {kod}" if kod != eski else "")), kaynak=("Urun BOM", x["satir"]))

# Çevre birimleri — kullanıcı bilgisi (30.10.2026): BC300 çanta kullanılacak
ekle("Çevre Birimleri", "", "BC300", "GMP-110-230004", "BC300 plastik taşıma çantası ve organize sünger", 1,
     "Kullanıcı bilgisi: BC300 çanta kullanılacak (Excel'de ÇANTA satırı kodsuzdu)", kaynak=("Urun BOM", 82))

for s in satirlar:
    s["tl_top"] = s["adet"] * s["tl"]
    s["guncel_top"] = s["adet"] * s["guncel"]
    s["fark"] = s["guncel_top"] - s["tl_top"]

# ---------------------------------------------------------------- Excel
wb = Workbook()
B = Font(bold=True); BW = Font(bold=True, color="FFFFFF")
HDR = PatternFill("solid", fgColor="1F4E78"); GRP = PatternFill("solid", fgColor="D9E1F2")
SARI = PatternFill("solid", fgColor="FFF2CC"); KIRMIZI = PatternFill("solid", fgColor="F8CBAD")
ince = Side(style="thin", color="BFBFBF"); KN = Border(left=ince, right=ince, top=ince, bottom=ince)
TL = '#,##0.00 "₺"'; TL4 = '#,##0.0000'

def baslik(ws, row, cols):
    for i, c in enumerate(cols, 1):
        h = ws.cell(row=row, column=i, value=c); h.font = BW; h.fill = HDR
        h.alignment = Alignment(wrap_text=True, vertical="center"); h.border = KN

gruplar = ["Elektronik Kartlar", "Aksesuar & OEM Modül", "Kablaj", "Mekanik", "Optik", "Çevre Birimleri"]
ws = wb.active; ws.title = "Özet"
ws["A1"] = "LRF 6001 (LAZER MESAFE ÖLÇER) — MALİYET ÇALIŞMASI"; ws["A1"].font = Font(bold=True, size=14)
ws["A2"] = f"Kaynak: LRF 6001 ÜRÜN BOM.xlsx · CEO ERP son alış fiyatları · Hesap tarihi {BUGUN:%d.%m.%Y}"
ws["A3"] = f"Bugünkü kur (GunlukKur, döviz alış): USD {USD_BUGUN:.4f} ₺ · EUR {EUR_BUGUN:.4f} ₺"
baslik(ws, 5, ["Grup", "Kalem", "Fiyatlı", "Fiyatsız (0)", "Alış Günü Maliyeti (₺)", "Güncel Kur Maliyeti (₺)", "Kur Farkı (₺)", "Fark %", "Güncel ($)"])
r = 6
for g in gruplar:
    gs = [s for s in satirlar if s["grup"] == g]
    a, b = sum(s["tl_top"] for s in gs), sum(s["guncel_top"] for s in gs)
    vals = [g, len(gs), sum(1 for s in gs if s["tl"] > 0), sum(1 for s in gs if s["tl"] == 0), a, b, b - a, (b - a) / a if a else 0, b / USD_BUGUN]
    for i, v in enumerate(vals, 1):
        c = ws.cell(row=r, column=i, value=v); c.border = KN
    r += 1
A = sum(s["tl_top"] for s in satirlar); G = sum(s["guncel_top"] for s in satirlar)
for i, v in enumerate(["TOPLAM (malzeme)", len(satirlar), sum(1 for s in satirlar if s["tl"] > 0),
                       sum(1 for s in satirlar if s["tl"] == 0), A, G, G - A, (G - A) / A, G / USD_BUGUN], 1):
    c = ws.cell(row=r, column=i, value=v); c.font = B; c.fill = GRP; c.border = KN
for rr in range(6, r + 1):
    for cc in (5, 6, 7): ws.cell(row=rr, column=cc).number_format = TL
    ws.cell(row=rr, column=8).number_format = "0.0%"; ws.cell(row=rr, column=9).number_format = '#,##0.00 "$"'
r += 2
ws.cell(row=r, column=1, value="HESAP YÖNTEMİ").font = B; r += 1
for t in [
    "• Her kalem için CEO ERP'deki EN SON alış faturası/faturalaşmamış irsaliye fiyatı alındı (tarih sınırı yok, stok + masraf kartı).",
    "• Kur farkı: USD faturalı kalemde döviz birim fiyatı × bugünkü USD; EUR faturalı kalemde döviz birim fiyatı × bugünkü EUR kuru.",
    "• TL faturalı kalemde (ör. yerli talaşlı imalat operasyonları): TL fiyat ÷ alış günündeki USD kuru × bugünkü USD kuru.",
    "• Mekanik parçalarda maliyet, parçanın :XX operasyon kodlarının (talaşlı imalat, kaplama vb.) son alış fiyatlarından oluşur.",
    "• Elektronik kartlar Excel'deki kart sayfalarından hesaplandı; ERP reçetesindeki çıplak PCB ayrıca eklendi.",
    "• DAHİL DEĞİL: işçilik, SMT dizgi/montaj, test, ambalaj, genel giderler; tripod/omuz çantası/boyun askısı (Excel'de kodsuz). BC300 çanta DAHİL.",
]:
    ws.cell(row=r, column=1, value=t); r += 1
r += 1
ws.cell(row=r, column=1, value="EN YÜKSEK 10 KALEM (güncel kur)").font = B; r += 1
baslik(ws, r, ["Grup", "ERP Kodu", "Tanım", "Adet", "Son Alış", "Döviz", "Güncel Tutar (₺)", "Pay %"]); r += 1
for s in sorted(satirlar, key=lambda s: -s["guncel_top"])[:10]:
    for i, v in enumerate([s["grup"], s["erp_kod"], s["ad"][:60], s["adet"], s["tarih"].strftime("%d.%m.%Y") if s["tarih"] else "",
                           s["dvz"], s["guncel_top"], s["guncel_top"] / G], 1):
        c = ws.cell(row=r, column=i, value=v); c.border = KN
    ws.cell(row=r, column=7).number_format = TL; ws.cell(row=r, column=8).number_format = "0.0%"; r += 1
for i, w in enumerate([24, 18, 50, 10, 20, 20, 18, 9, 14], 1): ws.column_dimensions[get_column_letter(i)].width = w

ws2 = wb.create_sheet("Detay")
cols = ["Grup", "Üst Kalem", "Tip", "Excel Kodu", "ERP Kodu", "Tanım", "Adet", "Son Alış Tarihi", "Döviz", "Döviz Birim Fiyatı",
        "Alış Kuru", "Alış Birim (₺)", "Güncel Birim (₺)", "Alış Tutarı (₺)", "Güncel Tutar (₺)", "Kur Farkı (₺)", "Değerleme", "Not"]
baslik(ws2, 1, cols)
r = 2
for g in gruplar:
    for s in [s for s in satirlar if s["grup"] == g]:
        vals = [s["grup"], s["ust"], s["tip"], s["excel_kod"], s["erp_kod"], s["ad"], s["adet"],
                s["tarih"].strftime("%d.%m.%Y") if s["tarih"] else None, s["dvz"], s["dvz_f"], s["alis_kur"],
                s["tl"], s["guncel"], s["tl_top"], s["guncel_top"], s["fark"], s["yontem"], s["not_"]]
        for i, v in enumerate(vals, 1):
            c = ws2.cell(row=r, column=i, value=v); c.border = KN
            if s["tl"] == 0: c.fill = KIRMIZI
            elif s["not_"]: c.fill = SARI
        for cc in (12, 13, 14, 15, 16): ws2.cell(row=r, column=cc).number_format = TL
        ws2.cell(row=r, column=10).number_format = TL4; ws2.cell(row=r, column=11).number_format = TL4
        r += 1
for i, v in enumerate(["TOPLAM"] + [None] * 12 + [A, G, G - A], 1):
    c = ws2.cell(row=r, column=i, value=v); c.font = B; c.fill = GRP
for cc in (14, 15, 16): ws2.cell(row=r, column=cc).number_format = TL
ws2.freeze_panes = "A2"; ws2.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{r-1}"
for i, w in enumerate([20, 30, 10, 22, 22, 50, 7, 12, 7, 12, 10, 14, 14, 15, 15, 14, 30, 50], 1):
    ws2.column_dimensions[get_column_letter(i)].width = w

ws3 = wb.create_sheet("Kontrol Edilecekler")
baslik(ws3, 1, ["Konu", "Açıklama"])
kontrol = [
    ("OEM modül (OEM-LRF-NP)", "Son alış 24.10.2025: 263,92 EUR/adet (6 adet). 2021 alışı 2.311,32 EUR/adet (410 adet), 2019: 4.378,80 USD. "
                                "Son fiyat öncekilerin ~%11'i — fatura satırı (birim/indirim/kısmi fatura) kontrol edilmeli. "
                                f"2021 fiyatı ile güncel maliyet ≈ {2311.3158 * EUR_BUGUN:,.0f} ₺ olurdu."),
    ("OLED ekran", "Excel 'MICROOLED MDP05A' → ERP MDP05APRMRO (regular luminance, 2021) kullanıldı. "
                   "Alternatif MDP05BPRMHO (high luminance, 03.2026: 415,91 EUR) kullanılıyorsa maliyet yükselir."),
    ("Optik adetleri", "Excel'de Adet sütunu boş — hepsi 1 varsayıldı."),
    ("Penta prizma", "Excel'deki HMCOMPRS010 (2022) kullanıldı; ERP'de daha yeni GMP-401-230014 (03.2023, 5.550,74 ₺) kartı da var."),
    ("Pil kartı (GMP-300-230012)", "ERP'de karşılığı/PCB'si yok; yalnızca Excel'deki bileşen dahil edildi."),
    ("MTi-3-0I-T (IMU)", "ERP'de modülün kartı/alışı yok (yalnız geliştirme kiti) → 0."),
    ("Kartı olmayan mekanik parçalar", "12 mekanik parçanın ERP'de stok kartı yok → 0 (çoğu oring/yay/conta)."),
    ("Eski fiyatlar", "Birçok elektronik/optik fiyatı 2021–2023 tarihli; kur farkı yansıtıldı ancak döviz bazlı fiyat artışları yansımaz."),
    ("Dahil olmayanlar", "İşçilik, SMT dizgi, montaj, test, ambalaj, tripod/omuz çantası/boyun askısı. (BC300 çanta dahil edildi.)"),
    ("OEM modül QS numarası", "Teknik resimde QS42753BE; ERP kartı OEM-LRF-NP adında QS42526AE yazıyor. QS42753BE ERP'de hiç geçmiyor. "
                              "24.10.2025 NPT12167 faturası (LRF 6002 projesi) muhtemelen bu modül — faturadan doğrulanmalı."),
]
for i, (k, a) in enumerate(kontrol, 2):
    ws3.cell(row=i, column=1, value=k).font = B; ws3.cell(row=i, column=2, value=a).alignment = Alignment(wrap_text=True)
ws3.column_dimensions["A"].width = 32; ws3.column_dimensions["B"].width = 120

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fiyatsiz import fiyatsiz_sayfasi
fiyatsiz_sayfasi(wb, satirlar, 1)
wb.save(CIKTI)
json.dump(dict(satirlar=satirlar, usd=USD_BUGUN, eur=EUR_BUGUN), open(CIKTI + ".json", "w", encoding="utf-8"), ensure_ascii=False, default=str)
print(f"USD bugün {USD_BUGUN} EUR bugün {EUR_BUGUN}")
for g in gruplar:
    gs = [s for s in satirlar if s["grup"] == g]
    print(f'{g:22} kalem {len(gs):3}  fiyatsız {sum(1 for s in gs if s["tl"]==0):2}  alış {sum(s["tl_top"] for s in gs):12,.2f}  güncel {sum(s["guncel_top"] for s in gs):12,.2f}')
print(f"TOPLAM alış {A:,.2f}  güncel {G:,.2f}  fark {G-A:,.2f} ({(G-A)/A:.1%})  = {G/USD_BUGUN:,.2f} $")
print("Fiyatsız:", [(s["grup"][:4], s["excel_kod"] or s["erp_kod"]) for s in satirlar if s["tl"] == 0])
print("TOP10:"); [print(f'  {s["erp_kod"]:22} {s["adet"]:>4} {s["dvz"]:4} {s["tarih"]:%d.%m.%Y} {s["guncel_top"]:12,.2f}') for s in sorted(satirlar, key=lambda s: -s["guncel_top"])[:10]]
