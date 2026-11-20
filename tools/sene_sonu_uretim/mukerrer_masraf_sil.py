"""Açık sene sonu emirlerinde, kapanmamış hatlarda, aynı kodu hatta stok girdisi (Tipi<>2) olarak da bulunan masraf (Tipi=2) satırlarını siler.
Kullanım: python mukerrer_masraf_sil.py [--commit]   (--commit yoksa rollback = deneme)
Silinen satırların tüm kolonları mukerrer_masraf_yedek_<tarih>.json'a yazılır. Bağlı kayıt (depo çıkışı, girdi stok hareketi, transfer) varsa satır silinmez."""
import sys, io, json
from datetime import datetime
from decimal import Decimal
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection

COMMIT = '--commit' in sys.argv
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()
cur.execute("""SELECT g.Id, ue.Kodu, hk.Kodu, m.Kodu, g.TalepMiktar, ISNULL(g.Tutar,0)
 FROM UretimEmriHatPlaniGirdi g JOIN StokMasrafKarti m ON m.Id=g.KartId
 JOIN UretimEmriHatPlani h ON h.Id=g.UretimEmriHatPlaniId JOIN UretimEmri ue ON ue.Id=h.UretimEmriId JOIN StokKarti hk ON hk.Id=h.KartId
 WHERE g.Tipi=2 AND ue.DurumId=3 AND (ue.SurecDipnot LIKE 'Fatura:%' OR ue.Kodu='ŞİRKET.1092026-3')
   AND NOT EXISTS (SELECT 1 FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)
   AND EXISTS (SELECT 1 FROM UretimEmriHatPlaniGirdi g2 JOIN StokKarti s2 ON s2.Id=g2.KartId
               WHERE g2.UretimEmriHatPlaniId=g.UretimEmriHatPlaniId AND g2.Tipi<>2 AND s2.Kodu=m.Kodu)
 ORDER BY ue.Kodu, hk.Kodu, m.Kodu""")
rows = cur.fetchall()
REF = [('UretimEmriHatPlaniDepoCikis', 'UretimEmriHatPlaniGirdiId'), ('UretimEmriGirdiStokHareketi', 'UretimEmriGirdiId'),
       ('StokHareketDetay', 'DepolarArasiTransferUretimGirdiId'), ('DepoTransferTalepDetay', 'UretimEmriGirdiId'),
       ('UretimEmriHatPlaniGirdiTeslimDetayi', None)]
cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='UretimEmriHatPlaniGirdiTeslimDetayi' AND COLUMN_NAME LIKE '%Girdi%Id'")
tc = cur.fetchone(); REF[-1] = ('UretimEmriHatPlaniGirdiTeslimDetayi', tc[0]) if tc else None
REF = [r for r in REF if r]
sil, engel = [], []
for gid, ek, hk, mk, t, tutar in rows:
    bag = []
    for tbl, col in REF:
        cur.execute(f"SELECT COUNT(*) FROM [{tbl}] WHERE [{col}]=?", gid)
        if cur.fetchone()[0]: bag.append(tbl)
    (engel if bag else sil).append((gid, ek, hk, mk, float(t or 0), float(tutar), bag))
from collections import Counter
print('emir bazında silinecek:', dict(Counter(r[1] for r in sil)))
print('tutarı dolu olan (mükerrer maliyet taşıyan):', [(r[1], r[3], r[5]) for r in sil if r[5]])
if engel: print('BAĞLI KAYIT VAR, silinmeyecek:', engel)
yedek = []
for gid, *_ in sil:
    cur.execute("SELECT * FROM UretimEmriHatPlaniGirdi WHERE Id=?", gid); cols = [d[0] for d in cur.description]; r = cur.fetchone()
    yedek.append({k: (str(v) if isinstance(v, (Decimal, datetime)) or (v is not None and not isinstance(v, (int, float, str, bool))) else v) for k, v in zip(cols, r)})
    cur.execute("DELETE FROM UretimEmriHatPlaniGirdi WHERE Id=?", gid)
print(f'silinen: {len(sil)} satır')
if COMMIT:
    c.commit()
    fn = rf'C:\yeni-erp\mukerrer_masraf_yedek_{datetime.now():%Y%m%d_%H%M%S}.json'
    json.dump(yedek, open(fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('COMMIT edildi. Yedek:', fn)
else: c.rollback(); print('ROLLBACK (deneme)')
