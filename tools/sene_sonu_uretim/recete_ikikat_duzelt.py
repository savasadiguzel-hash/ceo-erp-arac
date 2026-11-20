"""İki kat girdili reçete + o reçeteyle kapanmış emirlerin düzeltilmesi (varsayılan: GMP-101-230016, ŞİRKET.962026-3 ve -9).
Kullanım: python recete_ikikat_duzelt.py [--commit]   (--commit yoksa rollback = deneme)
Kural: her (Tipi, KartId, Miktar) grubunda satır sayısı n çift olmalı; n/2 satır (en yüksek Id'ler) silinir. Tek sayı varsa işlem durur.
Emirlerde: 17 (üretime çıkış) fişindeki aynı gruptan n/2 detay satırı TEK TEK silinir (tetikleyiciler StokKumulatif'i ve
KullanilanMiktar'ı günceller), bağlı UretimEmriGirdiStokHareketi kayıtları önce silinir, sonra mükerrer girdi satırları silinir,
kalan girdilerin KullanilanMiktar'ı fişteki miktara eşitlenir. 16 fişinin maliyetine dokunulmaz (CEO Toplu Maliyetlendirme yapar).
Silinen tüm satırlar recete_ikikat_yedek_<tarih>.json'a yazılır."""
import sys, io, json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import stok_guncel_bakiyeleri

RECETE = 'GMP-101-230016'
EMIRLER = ['ŞİRKET.962026-3', 'ŞİRKET.962026-9']
COMMIT = '--commit' in sys.argv
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()
yedek = {'zaman': datetime.now().isoformat(), 'recete_girdi': [], 'emir_girdi': [], 'detay': [], 'link': []}
def satir(tbl, i):
    cur.execute(f"SELECT * FROM [{tbl}] WHERE Id=?", i); cols = [d[0] for d in cur.description]; r = cur.fetchone()
    return {k: (v if isinstance(v, (int, float, str, bool, type(None))) else str(v)) for k, v in zip(cols, r)}
def yariya(rows, key):
    g = defaultdict(list)
    for r in rows: g[key(r)].append(r)
    sil = []
    for k, rs in g.items():
        if len(rs) % 2: raise SystemExit(f'TEK SAYI grup {k}: {len(rs)} satır — işlem durduruldu')
        sil += sorted(rs, key=lambda r: r[0])[len(rs) // 2:]
    return sil

# 1) Reçete
cur.execute("""SELECT g.Id, g.Tipi, g.KartId, g.Miktar FROM UretimRecete r JOIN UretimReceteHatPlani h ON h.UretimReceteId=r.Id
  JOIN UretimReceteHatPlaniGirdi g ON g.UretimReceteHatPlaniId=h.Id WHERE r.Kodu=? AND (r.KullanimDisi IS NULL OR r.KullanimDisi=0)""", RECETE)
rg = cur.fetchall(); rsil = yariya(rg, lambda r: (r[1], r[2], r[3]))
print(f'reçete {RECETE}: {len(rg)} satır → {len(rg) - len(rsil)}')
for r in rsil: yedek['recete_girdi'].append(satir('UretimReceteHatPlaniGirdi', r[0])); cur.execute("DELETE FROM UretimReceteHatPlaniGirdi WHERE Id=?", r[0])

# 2) Emirler
geri = defaultdict(float)
for ek in EMIRLER:
    cur.execute("""SELECT h.Id FROM UretimEmriHatPlani h JOIN UretimEmri ue ON ue.Id=h.UretimEmriId JOIN StokKarti hk ON hk.Id=h.KartId
      WHERE ue.Kodu=? AND hk.Kodu=? AND h.HatTipi=1""", ek, RECETE); hid = cur.fetchone()[0]
    cur.execute("SELECT Id, Tipi, KartId, Miktar, TalepMiktar FROM UretimEmriHatPlaniGirdi WHERE UretimEmriHatPlaniId=?", hid)
    eg = cur.fetchall(); esil = yariya(eg, lambda r: (r[1], r[2], r[3]))
    cur.execute("""SELECT d.Id, d.IslemKartId, d.Miktar, d.Turu FROM UretimEmriHatPlaniStokHareketleri x JOIN StokHareket sh ON sh.Id=x.StokHareketId AND sh.IslemKodu=17
      JOIN StokHareketDetay d ON d.HareketId=sh.Id WHERE x.UretimEmriHatPlaniId=?""", hid)
    det = cur.fetchall(); dsil = yariya(det, lambda r: (r[3], r[1], r[2]))
    print(f'{ek}: girdi {len(eg)} → {len(eg) - len(esil)} | çıkış detayı {len(det)} → {len(det) - len(dsil)}')
    sil_g = {r[0] for r in esil}; sil_d = {r[0] for r in dsil}
    # linkler
    if sil_g or sil_d:
        cur.execute(f"""SELECT Id FROM UretimEmriGirdiStokHareketi WHERE StokHareketDetayId IN ({','.join(map(str, sil_d)) or 0})
                        OR UretimEmriGirdiId IN ({','.join(map(str, sil_g)) or 0})""")
        for (lid,) in cur.fetchall():
            yedek['link'].append(satir('UretimEmriGirdiStokHareketi', lid)); cur.execute("DELETE FROM UretimEmriGirdiStokHareketi WHERE Id=?", lid)
    for d in dsil:
        yedek['detay'].append(satir('StokHareketDetay', d[0]))
        cur.execute("SELECT Kodu FROM StokKarti WHERE Id=?", d[1]); geri[cur.fetchone()[0]] += float(d[2])
        cur.execute("DELETE FROM StokHareketDetay WHERE Id=?", d[0])        # tek tek: tetikleyiciler
    for g in esil:
        yedek['emir_girdi'].append(satir('UretimEmriHatPlaniGirdi', g[0])); cur.execute("DELETE FROM UretimEmriHatPlaniGirdi WHERE Id=?", g[0])
    # KullanilanMiktar = fişteki miktar
    cur.execute("""UPDATE g SET KullanilanMiktar = ISNULL((SELECT SUM(d.Miktar) FROM UretimEmriHatPlaniStokHareketleri x JOIN StokHareket sh ON sh.Id=x.StokHareketId AND sh.IslemKodu=17
         JOIN StokHareketDetay d ON d.HareketId=sh.Id WHERE x.UretimEmriHatPlaniId=g.UretimEmriHatPlaniId AND d.IslemKartId=g.KartId), 0)
         / (SELECT COUNT(*) FROM UretimEmriHatPlaniGirdi g2 WHERE g2.UretimEmriHatPlaniId=g.UretimEmriHatPlaniId AND g2.KartId=g.KartId AND g2.Tipi=g.Tipi)
       FROM UretimEmriHatPlaniGirdi g WHERE g.UretimEmriHatPlaniId=? AND g.Tipi<>2""", hid)
    cur.execute("""SELECT COUNT(*) FROM UretimEmriHatPlaniGirdi WHERE UretimEmriHatPlaniId=? AND Tipi<>2 AND ABS(ISNULL(KullanilanMiktar,0)-TalepMiktar)>0.000001""", hid)
    print(f'   KullanilanMiktar≠TalepMiktar kalan girdi: {cur.fetchone()[0]}')

# 3) Stoğa geri dönenler + muhasebe girişiyle çakışma
kod = sorted(geri)
cur.execute(f"""SELECT sk.Kodu, SUM(d.Miktar) FROM StokHareketDetay d JOIN StokHareket sh ON sh.Id=d.HareketId JOIN StokKarti sk ON sk.Id=d.IslemKartId
  WHERE sh.Id=744507 AND sk.Kodu IN ({','.join('?'*len(kod))}) GROUP BY sk.Kodu""", *kod)
muh = {k: float(v) for k, v in cur.fetchall()}
bak = stok_guncel_bakiyeleri(c, kod)
print(f"\n{'Kod':22s} {'geri dönen':>10s} {'bakiye sonra':>12s} {'muhasebe SYM':>12s}")
for k in kod: print(f"{k:22s} {geri[k]:>10g} {bak[k]:>12g} {muh.get(k, ''):>12}")
print('muhasebe girişiyle çakışan kalem:', [k for k in kod if k in muh])
if COMMIT:
    c.commit(); fn = rf'C:\yeni-erp\recete_ikikat_yedek_{datetime.now():%Y%m%d_%H%M%S}.json'
    json.dump(yedek, open(fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); print('COMMIT edildi. Yedek:', fn)
else: c.rollback(); print('ROLLBACK (deneme)')
