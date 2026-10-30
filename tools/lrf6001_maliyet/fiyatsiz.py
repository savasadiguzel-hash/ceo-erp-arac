"""Fiyatı bulunamayan (0 ₺) kalemler sayfası — iki çıktı dosyası da kullanır."""
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def _neden_oneri(s):
    n = s["not_"] or ""
    if s["excel_kod"] == "MTi-3-0I-T":
        return ("ERP'de modülün stok kartı ve alışı yok; yalnızca geliştirme kiti (MTI-3-01-DK) kayıtlı.",
                "Tedarikçi (Movella/Xsens) teklifi ile fiyat girilmeli; modül için stok kartı açılmalı.")
    if s["tip"] == "PCB":
        return ("Pil kartının ERP'de reçetesi ve çıplak PCB kartı yok.",
                "PCB üretici teklifi alınmalı veya pil kartı PCB'si diğer kart panelinin içindeyse 0 kalabilir.")
    if s["tip"] == "Operasyon":
        return ("Operasyon kartı var ama hiç alış faturası/irsaliyesi işlenmemiş.",
                "Fason firmadan fiyat alınmalı; diğer operasyonları fiyatlı olduğu için parça maliyeti eksik kalıyor.")
    if "stok kartı yok" in n:
        return ("ERP'de stok kartı yok (Excel'deki GMP kodu hiç açılmamış).",
                "Stok kartı açılıp alış/fason fiyatı işlenmeli; ya da tedarikçi teklif fiyatı verilmeli.")
    return ("Stok kartı var ama hiç alış faturası/irsaliyesi ya da :XX operasyon kaydı yok.",
            "Parça satın alınıyorsa fiyat, imal ediliyorsa operasyon (:10 talaşlı imalat vb.) maliyetleri girilmeli.")

def fiyatsiz_sayfasi(wb, satirlar, index=1):
    ws = wb.create_sheet("Fiyatı Olmayanlar", index)
    B = Font(bold=True); BW = Font(bold=True, color="FFFFFF")
    HDR = PatternFill("solid", fgColor="C00000"); KIR = PatternFill("solid", fgColor="F8CBAD")
    ince = Side(style="thin", color="BFBFBF"); KN = Border(left=ince, right=ince, top=ince, bottom=ince)
    eksik = [s for s in satirlar if not s["tl"]]
    ws["A1"] = "FİYATI OLMAYAN KALEMLER — maliyete 0 ₺ olarak girdi"; ws["A1"].font = Font(bold=True, size=13, color="C00000")
    ws["A2"] = (f"{len(eksik)} kalem. Bu kalemler fiyatlandırılmadıkça toplam maliyet olduğundan DÜŞÜK görünür. "
                "Çoğu oring / yay / conta / pim gibi düşük tutarlı parçalardır; MTi-3 IMU modülü tek başına önemli bir tutar olabilir.")
    cols = ["#", "Grup", "Excel Kodu", "ERP Kodu", "Tanım", "Adet", "Neden fiyat yok", "Yapılması gereken"]
    for i, c in enumerate(cols, 1):
        h = ws.cell(row=4, column=i, value=c); h.font = BW; h.fill = HDR; h.border = KN
        h.alignment = Alignment(wrap_text=True, vertical="center")
    for k, s in enumerate(eksik, 1):
        neden, oneri = _neden_oneri(s)
        kod = s["erp_kod"] or "(ERP'de yok)"
        vals = [k, s["grup"], s["excel_kod"] or "", kod, s["ad"], s["adet"], neden, oneri]
        for i, v in enumerate(vals, 1):
            c = ws.cell(row=4 + k, column=i, value=v); c.border = KN; c.fill = KIR
            c.alignment = Alignment(wrap_text=True, vertical="top")
    r = 6 + len(eksik)
    ws.cell(row=r, column=1, value="Özet:").font = B
    from collections import Counter
    for j, (g, n) in enumerate(Counter(s["grup"] for s in eksik).items(), 1):
        ws.cell(row=r + j, column=2, value=g); ws.cell(row=r + j, column=3, value=f"{n} kalem")
    for col, w in zip("ABCDEFGH", [4, 18, 20, 22, 48, 6, 50, 60]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A5"
    return eksik
