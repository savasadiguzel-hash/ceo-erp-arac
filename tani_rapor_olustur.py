#!/usr/bin/env python3
"""
muhasebe_eksik_raporu.xlsx'i programatik olarak olusturur.
mutabakat.py'nin beklettigi formatta (9 sutun, satir 0 baslik).
"""
import sys, os, json, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import pyodbc, openpyxl
from db import sorgular

def baglan():
    cfg = json.load(open(os.path.join(os.path.dirname(__file__), 'config.json')))
    pwd = base64.b64decode(cfg['sifre_enc']).decode()
    cs = (f"DRIVER={{SQL Server}};SERVER={cfg['sunucu']};DATABASE={cfg['veritabani']};"
          f"UID={cfg['kullanici']};PWD={pwd};TrustServerCertificate=yes")
    return pyodbc.connect(cs, timeout=30)

print("DB baglaniliyor...")
conn = baglan()
print("Rapor olusturuluyor (bu birkaç dakika surebilir)...")
satirlar = sorgular.muhasebe_eksik_raporu_olustur(conn)
conn.close()

print(f"Toplam {len(satirlar)} eksik satir bulundu.")

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Muhasebe Eksik Raporu"

# Baslik satiri (mutabakat.py row 0 olarak atliyor)
ws.append([
    "Is Emri Tarihi", "Is Emri No", "Aciklama",
    "Stok Kodu", "Stok Adi",
    "Ihtiyac", "ERP Bakiye", "Onceki Rezervasyon", "Net Eksik"
])

# Veri satirlari
for s in satirlar:
    ws.append([
        s['emir_tarihi'],          # col 0 — mutabakat tarih icin okur
        s['emir_kodu'],            # col 1
        s['emir_aciklama'],        # col 2
        s['stok_kodu'],            # col 3 — mutabakat stok icin okur
        s['stok_adi'],             # col 4
        s['ihtiyac'],              # col 5
        s['erp_bakiye'],           # col 6 — mutabakat bakiye icin okur
        s['onceki_rezervasyon'],   # col 7
        s['net_eksik'],            # col 8
    ])

out = os.path.join(os.path.dirname(__file__), 'muhasebe_eksik_raporu.xlsx')
wb.save(out)
print(f"Kaydedildi: {out}")
