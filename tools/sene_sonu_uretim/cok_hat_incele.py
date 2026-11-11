"""Çok hatlı reçeteler: reçete hat yapısı vs yerel (CEO'da elle açılmış) emir hat yapısı. Salt okuma."""
import sys, io
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection
c = get_connection(**DB_DEFAULTS); cur = c.cursor()
KODLAR = sys.argv[1:] or ['GMP-101-230022', 'GMP-101-230027', 'GMP-200-230286', 'GMP-200-230287', 'GMP-200-230288', 'GMP-200-230291']

for kod in KODLAR:
    print('\n' + '=' * 100 + f'\n# REÇETE {kod}')
    cur.execute("""SELECT h.Id, h.RootId, h.Tipi, hk.Kodu, LEFT(hk.Adi,35), h.Miktar,
        (SELECT COUNT(*) FROM UretimReceteHatPlaniGirdi g WHERE g.UretimReceteHatPlaniId=h.Id),
        (SELECT COUNT(*) FROM UretimRecete r2 WHERE r2.Kodu=hk.Kodu AND (r2.KullanimDisi IS NULL OR r2.KullanimDisi=0))
      FROM UretimRecete ur JOIN UretimReceteHatPlani h ON h.UretimReceteId=ur.Id LEFT JOIN StokKarti hk ON hk.Id=h.KartId
      WHERE ur.Kodu=? AND (ur.KullanimDisi IS NULL OR ur.KullanimDisi=0) ORDER BY h.Id""", kod)
    hats = cur.fetchall()
    hat_kodlari = {h[3] for h in hats}
    for h in hats:
        print(f'  hat {h[0]} root={h[1]} Tipi={h[2]} {h[3]} {h[4]!r} mik={float(h[5]):g} girdi={h[6]} kendi_recetesi={h[7]}')
        cur.execute("""SELECT g.Tipi, COALESCE(sk.Kodu, smk.Kodu), g.Miktar FROM UretimReceteHatPlaniGirdi g
          LEFT JOIN StokKarti sk ON sk.Id=g.KartId AND g.Tipi<>2 LEFT JOIN StokMasrafKarti smk ON smk.Id=g.KartId AND g.Tipi=2
          WHERE g.UretimReceteHatPlaniId=? ORDER BY g.Id""", h[0])
        gs = cur.fetchall()
        hat_ref = [(g[1], float(g[2])) for g in gs if g[1] in hat_kodlari]
        if hat_ref: print('      girdide başka hat kartı:', hat_ref)
    # yerel emirler
    cur.execute("""SELECT DISTINCT ue.Id, ue.Kodu, CONVERT(varchar(10),ue.UretimEmriTarihi,104), ue.DurumId, ue.Aciklama
      FROM UretimEmri ue JOIN UretimEmriHatPlani h ON h.UretimEmriId=ue.Id JOIN StokKarti sk ON sk.Id=h.KartId
      WHERE sk.Kodu=? OR sk.Kodu IN (SELECT hk.Kodu FROM UretimRecete ur JOIN UretimReceteHatPlani hh ON hh.UretimReceteId=ur.Id
            JOIN StokKarti hk ON hk.Id=hh.KartId WHERE ur.Kodu=? AND hh.Tipi=1)
      ORDER BY ue.Id DESC""", kod, kod)
    emirler = cur.fetchall()[:3]
    for e in emirler:
        print(f'  ## YEREL EMİR {e[1]} ({e[2]}, durum {e[3]}) {e[4]!r}')
        cur.execute("""SELECT h.Id, h.HatTipi, sk.Kodu, LEFT(sk.Adi,30), h.Miktar, h.TalepMiktari, h.sira,
            (SELECT COUNT(*) FROM UretimEmriHatPlaniGirdi g WHERE g.UretimEmriHatPlaniId=h.Id)
          FROM UretimEmriHatPlani h JOIN StokKarti sk ON sk.Id=h.KartId WHERE h.UretimEmriId=? ORDER BY h.sira, h.Id""", e[0])
        for h in cur.fetchall():
            print(f'     sira {h[6]} HatTipi={h[1]} {h[2]} {h[3]!r} mik={float(h[4]):g} talep={float(h[5] or 0):g} girdi={h[7]}')
            cur.execute("""SELECT TOP 4 COALESCE(sk.Kodu, smk.Kodu), g.Miktar, g.TalepMiktar FROM UretimEmriHatPlaniGirdi g
              LEFT JOIN StokKarti sk ON sk.Id=g.KartId AND g.Tipi<>2 LEFT JOIN StokMasrafKarti smk ON smk.Id=g.KartId AND g.Tipi=2
              WHERE g.UretimEmriHatPlaniId=? ORDER BY g.Id""", h[0])
            print('        ilk girdiler:', [(r[0], float(r[1]), float(r[2])) for r in cur.fetchall()])
