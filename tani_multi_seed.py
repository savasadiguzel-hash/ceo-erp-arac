#!/usr/bin/env python3
"""4 farklı seed ile 20 kart bakiye doğrulaması (Metot E)"""
import sys, os, json, base64, random
from pathlib import Path
from datetime import date, datetime
sys.stdout.reconfigure(encoding='utf-8')
import openpyxl, pyodbc

BASE    = Path(__file__).resolve().parent
EKSTRE  = BASE / "dist" / "Stok Kartı Ekstresi_12062026190248.xlsx"
BUGUN   = date(2026, 6, 12)
TOLERANS = 0.5

def _parse_date(val):
    if isinstance(val, datetime): return val.date()
    if isinstance(val, date):     return val
    if isinstance(val, str):
        for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
            try: return datetime.strptime(val.strip(), fmt).date()
            except: pass
    return None

def load_ekstre(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    cards = {}; current = None; son_kalan = 0.0
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0: continue
        col0  = row[0]  if len(row)>0  else None
        col1  = row[1]  if len(row)>1  else None
        col5  = row[5]  if len(row)>5  else None
        col7  = row[7]  if len(row)>7  else None
        col11 = row[11] if len(row)>11 else None
        col17 = row[17] if len(row)>17 else None
        col23 = row[23] if len(row)>23 else None
        if col0 is not None and isinstance(col0, str) and col0.strip():
            if current and current in cards: cards[current]['son_bakiye'] = son_kalan
            current = col0.strip()
            devir = float(col23) if col23 is not None else 0.0
            son_kalan = devir
            cards[current] = {'devir': devir, 'txns': [], 'son_bakiye': devir}
            continue
        if current is None: continue
        if col1 is not None and isinstance(col1, str) and isinstance(col5, str): continue
        if col7 is not None and isinstance(col7, str) and 'Devir' in col7:
            dv = float(col11) if col11 is not None else 0.0
            cards[current]['devir'] = dv
            if col17 is not None:
                try: son_kalan = float(col17); cards[current]['son_bakiye'] = son_kalan
                except: pass
            else: son_kalan = dv; cards[current]['son_bakiye'] = son_kalan
            continue
        tx_date = _parse_date(col5)
        if col1 is not None and isinstance(col1, str) and tx_date is not None:
            try: amount = float(col11) if col11 is not None else 0.0
            except: amount = 0.0
            cards[current]['txns'].append((tx_date, amount))
            if col17 is not None:
                try: son_kalan = float(col17); cards[current]['son_bakiye'] = son_kalan
                except: pass
    if current and current in cards: cards[current]['son_bakiye'] = son_kalan
    wb.close()
    return cards

cfg = json.load(open(BASE / "config.json"))
pwd = base64.b64decode(cfg['sifre_enc']).decode()
cs  = (f"DRIVER={{SQL Server}};SERVER={cfg['sunucu']};DATABASE={cfg['veritabani']};"
       f"UID={cfg['kullanici']};PWD={pwd};TrustServerCertificate=yes")
conn = pyodbc.connect(cs, timeout=30)
cur  = conn.cursor()

print("Excel yükleniyor...")
cards = load_ekstre(EKSTRE)
hareketi_olan = [k for k, c in cards.items() if c['txns']]
print(f"Kart sayısı: {len(cards)}, Hareketi olan: {len(hareketi_olan)}")
print()

for seed in [42, 99, 777, 1234, 5678]:
    random.seed(seed)
    secilen = sorted(random.sample(hareketi_olan, 20))

    yer = ','.join(['?'] * len(secilen))
    cur.execute(f"SELECT Id, Kodu FROM StokKarti WHERE Kodu IN ({yer}) AND Aktif=1", *secilen)
    kid_map  = {r[1]: int(r[0]) for r in cur.fetchall()}
    kid_list = list(kid_map.values())
    if not kid_list:
        print(f"seed={seed}: DB'de kart yok")
        continue

    yer_ids = ','.join(['?'] * len(kid_list))
    cur.execute(f"""
        SELECT shd.IslemKartId,
               SUM(CASE
                   WHEN sh.IslemKodu IN (1,4,5,8,15,16,20,22,26,29)
                       THEN (shd.Miktar - ISNULL(shd_f.Miktar, 0))
                   WHEN sh.IslemKodu IN (2,3,6,7,17,18,19,21,23,24,28)
                       THEN -(shd.Miktar - ISNULL(shd_f.Miktar, 0))
                   ELSE 0
               END) AS Bakiye
        FROM StokHareketDetay shd
        JOIN StokHareket sh ON sh.Id = shd.HareketId
        LEFT JOIN StokHareketDetay shd_f ON shd_f.Id = shd.FaturaDetayId
        WHERE shd.IslemKartId IN ({yer_ids})
          AND sh.Aktif = 1
          AND CAST(sh.BelgeTarihi AS DATE) <= '2026-06-12'
        GROUP BY shd.IslemKartId
    """, *kid_list)
    db_bak = {int(r[0]): float(r[1]) if r[1] is not None else 0.0
              for r in cur.fetchall()}

    ok = 0; fail = []
    for kod in secilen:
        kid = kid_map.get(kod)
        if kid is None: continue
        ceo = cards[kod]['son_bakiye']
        db  = db_bak.get(kid, 0.0)
        if abs(db - ceo) <= TOLERANS:
            ok += 1
        else:
            fail.append(f"{kod}(fark={db-ceo:+.1f})")

    pct = ok / 20 * 100
    status = "✅" if ok >= 19 else ("⚠️" if ok >= 17 else "❌")
    print(f"seed={seed:5d}: {status} {ok:2d}/20 (%{pct:.0f})"
          + (f"  UYUMSUZ: {fail}" if fail else ""))

conn.close()
