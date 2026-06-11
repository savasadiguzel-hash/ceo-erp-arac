"""tools/sapan_analiz.py — ER25-16MM ve HMGMSGR0008 detayli analiz"""
import sys, base64, pyodbc, glob, openpyxl
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from datetime import date, datetime
from pathlib import Path
from collections import defaultdict

sifre = base64.b64decode("Y2VvLjEyMzQ=").decode()
conn = pyodbc.connect(
    r"DRIVER={SQL Server};SERVER=WIN-3FATBI9RQAA\CEO1;DATABASE=504;UID=sa;" + f"PWD={sifre};",
    timeout=30
)
cur = conn.cursor()

cur.execute("""
    SELECT DISTINCT sh23.Id FROM StokHareket sh23
    JOIN StokHareketDetay shd23 ON shd23.HareketId=sh23.Id
    WHERE sh23.IslemKodu=23 AND sh23.Aktif=1
      AND EXISTS (
          SELECT 1 FROM StokHareket sh5
          JOIN StokHareketDetay shd5 ON shd5.HareketId=sh5.Id
          WHERE sh5.IslemKodu=5 AND sh5.Aktif=1
            AND sh5.BelgeSiraNo=sh23.BelgeSiraNo
            AND shd5.IslemKartId=shd23.IslemKartId
      )
""")
k23_str = ','.join(str(int(r[0])) for r in cur.fetchall()) or '-1'

# Ekstre
ekstre_file = Path(sorted(glob.glob("Stok K*Ekstresi*.xlsx"),
                          key=lambda p: Path(p).stat().st_mtime, reverse=True)[0])
wb = openpyxl.load_workbook(ekstre_file, read_only=True, data_only=True)
ws = wb.active
ekstre = {}
current = None
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0: continue
    c0  = row[0]  if len(row) > 0  else None
    c4  = row[4]  if len(row) > 4  else None
    c11 = row[11] if len(row) > 11 else None
    c23 = row[23] if len(row) > 23 else None
    if c0 and isinstance(c0, str) and c0.strip():
        current = c0.strip()
        ekstre[current] = {'devir': float(c23) if c23 else 0.0, 'txns': []}
        continue
    if not current or c11 is None: continue
    if isinstance(c4, datetime):  tx = c4.date()
    elif isinstance(c4, date):    tx = c4
    else:                         continue
    try:
        ekstre[current]['txns'].append((tx, float(c11)))
    except Exception:
        pass
wb.close()

def ekstre_bak(kodu, hedef):
    item = ekstre.get(kodu)
    if item is None: return None
    return item['devir'] + sum(a for d, a in item['txns'] if d <= hedef)

LABEL = {1:"Alis Fat.", 2:"Satis Fat.", 3:"Alis Iade", 5:"Alis Irs.",
         6:"Satis Irs.", 16:"Urt.Giris", 17:"Urt.Cikis", 18:"Dep.A.Cikis",
         19:"Say.Eksik", 20:"Say.Fazla", 21:"Fire", 22:"Devir", 23:"Dep.A.Giris"}

def pd(v):
    if isinstance(v, datetime): return v.date()
    if isinstance(v, date):     return v
    if isinstance(v, str):
        for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
            try: return datetime.strptime(v.strip()[:10], fmt).date()
            except: pass
    return None

# Rapor sapan satırları
wb2 = openpyxl.load_workbook("muhasebe_eksik_raporu.xlsx", read_only=True, data_only=True)
ws2 = wb2.active
sapan = defaultdict(list)
for i, row in enumerate(ws2.iter_rows(values_only=True)):
    if i == 0: continue
    stok = str(row[3] or '').strip()
    if stok not in ('ER25-16MM', 'HMGMSGR0008'): continue
    tx = pd(row[0])
    if tx is None: continue
    try:    sapan[stok].append((tx, float(row[6])))
    except: pass
wb2.close()

for kodu in ['ER25-16MM', 'HMGMSGR0008']:
    print(f"\n{'='*70}")
    print(f"KART: {kodu}")
    print(f"{'='*70}")

    cur.execute("SELECT Id FROM StokKarti WHERE Kodu=?", kodu)
    r = cur.fetchone()
    if not r:
        print("  DB'de bulunamadi"); continue
    kid = int(r[0])

    # IslemKodu ozeti
    cur.execute("""
        SELECT sh.IslemKodu, SUM(shd.Miktar), COUNT(*)
        FROM StokHareketDetay shd
        JOIN StokHareket sh ON sh.Id=shd.HareketId
        WHERE shd.IslemKartId=? AND sh.Aktif=1
        GROUP BY sh.IslemKodu ORDER BY sh.IslemKodu
    """, kid)
    print("\n  IslemKodu ozeti (Aktif=1, tum zaman):")
    print(f"  {'KD':>4}  {'Tur':<18}  {'Toplam':>12}  {'Adet':>6}")
    print("  " + "-" * 46)
    for r in cur.fetchall():
        print(f"  {r[0]:>4}  {LABEL.get(r[0], str(r[0])):<18}  {float(r[1]):>12.2f}  {r[2]:>6}")

    # Formul (tum zaman)
    cur.execute(f"""
        SELECT SUM(CASE
            WHEN sh.IslemKodu IN (1,16,20,22)              THEN  shd.Miktar
            WHEN sh.IslemKodu=23 AND sh.Id IN ({k23_str})  THEN  shd.Miktar
            WHEN sh.IslemKodu IN (2,3,6,17,18,19,21)       THEN -shd.Miktar
            ELSE 0 END)
        FROM StokHareketDetay shd
        JOIN StokHareket sh ON sh.Id=shd.HareketId
        WHERE shd.IslemKartId=? AND sh.Aktif=1
    """, kid)
    formul_tum = float(cur.fetchone()[0] or 0)

    eks = ekstre.get(kodu, {'devir': 0.0, 'txns': []})
    eks_devir  = eks['devir']
    eks_txn_sum = sum(a for _, a in eks['txns'])
    eks_son    = eks_devir + eks_txn_sum

    print(f"\n  DB formul (tum zaman)    : {formul_tum:.4f}")
    print(f"  Ekstre devir (col23)     : {eks_devir:.4f}")
    print(f"  Ekstre hareket toplam    : {eks_txn_sum:.4f}  ({len(eks['txns'])} satir)")
    print(f"  Ekstre son bakiye        : {eks_son:.4f}")
    print(f"  FARK (DB - Ekstre son)   : {formul_tum - eks_son:+.4f}")

    # Sapan tarihler detay
    if sapan[kodu]:
        print(f"\n  Rapordaki sapan satirlar:")
        print(f"  {'Tarih':<12}  {'Rapor':>10}  {'DB@tarih':>10}  {'Eks@tarih':>10}  {'Fark':>8}")
        print("  " + "-" * 58)
        for tarih, rapor_bak in sorted(sapan[kodu]):
            ts = str(tarih)
            cur.execute(f"""
                SELECT SUM(CASE
                    WHEN sh.IslemKodu IN (1,16,20,22)              THEN  shd.Miktar
                    WHEN sh.IslemKodu=23 AND sh.Id IN ({k23_str})  THEN  shd.Miktar
                    WHEN sh.IslemKodu IN (2,3,6,17,18,19,21)       THEN -shd.Miktar
                    ELSE 0 END)
                FROM StokHareketDetay shd
                JOIN StokHareket sh ON sh.Id=shd.HareketId
                WHERE shd.IslemKartId=? AND sh.Aktif=1
                  AND CAST(sh.BelgeTarihi AS DATE) <= CAST(? AS DATE)
            """, kid, ts)
            db_t  = float(cur.fetchone()[0] or 0)
            eks_t = ekstre_bak(kodu, tarih) or 0.0
            print(f"  {tarih}  {rapor_bak:>10.4f}  {db_t:>10.4f}  {eks_t:>10.4f}  {db_t-eks_t:>+8.4f}")

    # Ekstre hareketleri
    if eks['txns']:
        print(f"\n  Ekstre hareketleri ({len(eks['txns'])} adet, devir={eks_devir}):")
        print(f"  {'Tarih':<12}  {'Miktar':>10}  {'Kumulatif':>12}")
        print("  " + "-" * 38)
        kum = eks_devir
        for d, a in sorted(eks['txns'], key=lambda x: x[0]):
            kum += a
            print(f"  {d}  {a:>10.4f}  {kum:>12.4f}")
    else:
        print(f"\n  Ekstre'de hareket yok (devir={eks_devir})")

    # DB hareketleri (sadece 2024+)
    cur.execute("""
        SELECT sh.IslemKodu, CAST(sh.BelgeTarihi AS DATE),
               shd.Miktar, sh.Aktif
        FROM StokHareketDetay shd
        JOIN StokHareket sh ON sh.Id=shd.HareketId
        WHERE shd.IslemKartId=?
          AND sh.BelgeTarihi >= '2024-01-01'
        ORDER BY sh.BelgeTarihi, sh.IslemKodu
    """, kid)
    db_rows = cur.fetchall()
    if db_rows:
        print(f"\n  DB hareketleri 2024+ ({len(db_rows)} adet):")
        print(f"  {'KD':>4}  {'Tur':<16}  {'Tarih':<12}  {'Miktar':>10}  {'Aktif':>6}")
        print("  " + "-" * 56)
        for r in db_rows:
            t = r[1]
            if isinstance(t, datetime): t = t.date()
            elif not isinstance(t, date): t = date.fromisoformat(str(t)[:10])
            print(f"  {r[0]:>4}  {LABEL.get(r[0],str(r[0])):<16}  {t}  {float(r[2]):>10.4f}  {r[3]:>6}")

    # 2024 oncesi hareket sayisi (devir farki icin ipucu)
    cur.execute("""
        SELECT sh.IslemKodu, SUM(shd.Miktar)
        FROM StokHareketDetay shd
        JOIN StokHareket sh ON sh.Id=shd.HareketId
        WHERE shd.IslemKartId=? AND sh.Aktif=1
          AND sh.BelgeTarihi < '2024-01-01'
        GROUP BY sh.IslemKodu ORDER BY sh.IslemKodu
    """, kid)
    pre_rows = cur.fetchall()
    if pre_rows:
        print(f"\n  DB hareketleri 2024 oncesi (formul katkisi):")
        for r in pre_rows:
            kodu_pre = r[0]
            if kodu_pre in (1,16,20,22): etkisi = f"+{float(r[1]):.2f}"
            elif kodu_pre in (2,3,6,17,18,19,21): etkisi = f"-{float(r[1]):.2f}"
            else: etkisi = "SAYILMIYOR"
            print(f"    Kod={kodu_pre} ({LABEL.get(kodu_pre,'?')}): {float(r[1]):.2f}  formule etkisi: {etkisi}")

conn.close()
