"""Bir emrin tüm hat + girdi listesi ve bağlı stok hareketleri. Kullanım: python emir_detay.py ŞİRKET.622026-1  (salt okuma)"""
import sys, io
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection
c = get_connection(**DB_DEFAULTS); cur = c.cursor()
for kodu in sys.argv[1:]:
    cur.execute("SELECT Id, Aciklama, CONVERT(varchar(10),UretimEmriTarihi,104), DurumId, CONVERT(varchar(16),CreationTime,120) FROM UretimEmri WHERE Kodu=?", kodu)
    e = cur.fetchone(); print(f'\n### {kodu} {e}')
    cur.execute("""SELECT h.Id, h.HatTipi, sk.Kodu, LEFT(sk.Adi,30), h.TalepMiktari, h.sira FROM UretimEmriHatPlani h JOIN StokKarti sk ON sk.Id=h.KartId
      WHERE h.UretimEmriId=? ORDER BY h.sira, h.Id""", e[0])
    for h in cur.fetchall():
        cur.execute("""SELECT g.Tipi, COALESCE(sk.Kodu, smk.Kodu), g.Miktar FROM UretimEmriHatPlaniGirdi g
          LEFT JOIN StokKarti sk ON sk.Id=g.KartId AND g.Tipi<>2 LEFT JOIN StokMasrafKarti smk ON smk.Id=g.KartId AND g.Tipi=2
          WHERE g.UretimEmriHatPlaniId=? ORDER BY g.Id""", h[0])
        gs = cur.fetchall()
        cur.execute("""SELECT sh.IslemKodu, CONVERT(varchar(10),sh.BelgeTarihi,104) FROM UretimEmriHatPlaniStokHareketleri x JOIN StokHareket sh ON sh.Id=x.StokHareketId
          WHERE x.UretimEmriHatPlaniId=?""", h[0])
        hr = cur.fetchall()
        print(f'  sira {h[5]} HatTipi={h[1]} {h[2]} {h[3]!r} talep={float(h[4] or 0):g} girdi={len(gs)} hareket={hr}')
        stok = [f'{g[1]}×{float(g[2]):g}' for g in gs if g[0] != 2 and ':' not in g[1]]
        ops = [g[1] for g in gs if g[0] == 2 or ':' in g[1]]
        print('     stok:', ', '.join(stok))
        print(f'     masraf/op ({len(ops)}):', ', '.join(ops[:12]), '...' if len(ops) > 12 else '')
