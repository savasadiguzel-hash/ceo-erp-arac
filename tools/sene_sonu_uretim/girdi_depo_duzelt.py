"""Bir emrin girdilerinde deposu yetersiz olan satırların StokDepoId'sini stoğun bulunduğu depoya çevirir.
Kullanım: python girdi_depo_duzelt.py "ŞİRKET.11112026-5" [--commit]   (--commit yoksa rollback = deneme)
Kural: girdinin mevcut deposu emir tarihinde VE bugün (önceki açık emirlerin tüketimi düşülerek, ATP) yeterliyse dokunulmaz;
değilse her iki tarihte de yeterli olan, en çok stoğu olan depo seçilir. Hiçbir depo yetmiyorsa satır değişmez, uyarı verilir.
Eski değerler girdi_depo_yedek_<tarih>.json'a yazılır."""
import sys, io, json
from collections import defaultdict
from datetime import datetime, date
sys.path.insert(0, r'C:\yeni-erp')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from config import DB_DEFAULTS
from db.baglanti import get_connection

GIRIS = (1, 4, 5, 8, 15, 16, 20, 22, 26, 29)
CIKIS = (2, 3, 6, 7, 17, 18, 19, 21, 24, 28)
EK_EMIRLER = ['ŞİRKET.1092026-3']
args = [a for a in sys.argv[1:] if not a.startswith('--')]
HEDEF = args[0]; COMMIT = '--commit' in sys.argv
c = get_connection(**DB_DEFAULTS); c.autocommit = False; cur = c.cursor()
cur.execute("SELECT Id, Adi FROM StokDepoKarti"); depo_ad = {r[0]: r[1].strip() for r in cur.fetchall()}

cur.execute(f"""SELECT ue.Kodu, ue.UretimEmriTarihi, h.Id, hk.Id, hk.Kodu, h.TalepMiktari, ISNULL(h.StokDepoId,2)
 FROM UretimEmri ue JOIN UretimEmriHatPlani h ON h.UretimEmriId=ue.Id JOIN StokKarti hk ON hk.Id=h.KartId
 WHERE ue.DurumId=3 AND (ue.SurecDipnot LIKE 'Fatura:%' OR ue.Kodu IN ({','.join('?'*len(EK_EMIRLER))}))
   AND NOT EXISTS (SELECT 1 FROM UretimEmriHatPlaniStokHareketleri x WHERE x.UretimEmriHatPlaniId=h.Id)
 ORDER BY ue.UretimEmriTarihi, ue.Kodu, h.HatTipi DESC, h.sira""", *EK_EMIRLER)
hatlar = cur.fetchall()
assert any(h[0] == HEDEF for h in hatlar), f'{HEDEF} açık sene sonu emirleri arasında yok'
girdi = {}
for h in hatlar:
    cur.execute("""SELECT g.Id, sk.Id, sk.Kodu, LEFT(sk.Adi,40), g.TalepMiktar, ISNULL(g.StokDepoId,2) FROM UretimEmriHatPlaniGirdi g
      JOIN StokKarti sk ON sk.Id=g.KartId WHERE g.UretimEmriHatPlaniId=? AND g.Tipi<>2 AND (g.Yazilmasin IS NULL OR g.Yazilmasin=0)""", h[2])
    girdi[h[2]] = cur.fetchall()
kartlar = list({g[1] for gs in girdi.values() for g in gs} | {h[3] for h in hatlar})
hareket = defaultdict(list)
for i in range(0, len(kartlar), 500):
    p = kartlar[i:i+500]
    cur.execute(f"""SELECT shd.IslemKartId, sh.IslemKodu, COALESCE(shd.DepoKartId, sh.DepoKartId), COALESCE(shd.KarsiDepoKartId, sh.KarsiDepoKartId),
         sh.BelgeTarihi, shd.Miktar - ISNULL(f.Miktar,0)
      FROM StokHareketDetay shd JOIN StokHareket sh ON sh.Id=shd.HareketId LEFT JOIN StokHareketDetay f ON f.Id=shd.FaturaDetayId
      WHERE shd.IslemKartId IN ({','.join('?'*len(p))}) AND shd.Turu=1 AND shd.Aktif=1 AND sh.Aktif=1 AND sh.FaturaId IS NULL
        AND sh.IslemKodu NOT IN (9,10,11,12,13,14,25,27)""", *p)
    for kid, ik, d, kd, t, m in cur.fetchall():
        m = float(m or 0); t = t.date()
        if ik == 23:
            hareket[(kid, d)].append((t, -m))
            if kd: hareket[(kid, kd)].append((t, m))
        elif ik in GIRIS: hareket[(kid, d)].append((t, m))
        elif ik in CIKIS: hareket[(kid, d)].append((t, -m))
bak = lambda k, d, t: sum(m for x, m in hareket.get((k, d), []) if x <= t)
depolar = lambda k: {d for (kk, d) in hareket if kk == k}

oncesi = defaultdict(float); degisim = []; uyari = []
bugun = date.today()
for ek, et, hid, hkid, hkod, htalep, hdepo in hatlar:
    for gid, kid, kod, ad, talep, gdepo in girdi[hid]:
        talep = float(talep or 0)
        yeter = lambda d: min(bak(kid, d, et.date()), bak(kid, d, bugun)) + oncesi[(kid, d)] - talep >= -1e-6
        d = gdepo
        if ek == HEDEF and not yeter(gdepo):
            aday = sorted([x for x in depolar(kid) if x != gdepo and yeter(x)], key=lambda x: -bak(kid, x, bugun))
            if aday:
                d = aday[0]; degisim.append((gid, hkod, kod, ad, talep, gdepo, d, bak(kid, d, et.date()) + oncesi[(kid, d)]))
            else:
                uyari.append((hkod, kod, ad, talep, {depo_ad.get(x, x): round(min(bak(kid, x, et.date()), bak(kid, x, bugun)) + oncesi[(kid, x)], 3) for x in depolar(kid)}))
        oncesi[(kid, d)] -= talep
    oncesi[(hkid, hdepo)] += float(htalep or 0)

print(f'{HEDEF}: değişecek girdi {len(degisim)}')
for gid, hkod, kod, ad, t, eski, yeni, b in degisim:
    print(f'  girdi {gid} [{hkod}] {kod:18s} {ad:40s} ihtiyaç {t:g}: {depo_ad[eski]} → {depo_ad[yeni]} (emir tarihinde {b:g})')
for hkod, kod, ad, t, dd in uyari:
    print(f'  ⚠ HİÇBİR DEPO YETMİYOR [{hkod}] {kod} {ad} ihtiyaç {t:g} | {dd}')
for gid, *_, eski, yeni, b in degisim:
    cur.execute("UPDATE UretimEmriHatPlaniGirdi SET StokDepoId=? WHERE Id=?", yeni, gid)
if COMMIT and degisim:
    c.commit()
    fn = rf'C:\yeni-erp\girdi_depo_yedek_{datetime.now():%Y%m%d_%H%M%S}.json'
    json.dump({'emir': HEDEF, 'zaman': datetime.now().isoformat(), 'satirlar': [{'girdi_id': x[0], 'kod': x[2], 'eski_depo': x[5], 'yeni_depo': x[6]} for x in degisim]},
              open(fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('COMMIT edildi. Yedek:', fn)
else:
    c.rollback(); print('ROLLBACK (deneme)')
